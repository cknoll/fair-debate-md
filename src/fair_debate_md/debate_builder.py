"""
Turn a debate written as ONE markdown file into a content repo (and the patch collection
that ships it).

Usage::

    fdmd build-debate-repo <source.md>
    fdmd build-debate-repo <source.md> --patches-into <dir>
    fdmd build-debate-repo <source.md> --repo-into <dir>      # keep the repo itself
    fdmd build-debate-repo <source.md> --into-fixtures        # update a fixture debate

Without `--repo-into` the repo is built in a temporary directory and only its patch
collection is kept; by default it goes to `./<debate_key>/patches_01`. `--into-fixtures`
writes it into the fixture directory of the *installed* fair_debate_md instead, which is
what maintaining one of the fixture debates needs -- with an editable install that is the
checkout, and `fdmd unpack-repos` picks the result up from there.

Source format
-------------

A yaml front matter header, followed by the contributions, separated by marker comments::

    ---
    debate_key: d00-explanatory-example-debate
    language: en
    parties:
      a: Explainer
      b: Elaborator
    first_commit: 2026-08-24T08:00:00+02:00
    hours_between_contributions: [4, 8]
    active_hours: [8, 22]
    ---

    <!-- !!== label=root party=a ==== -->

    # Explanatory Example Debate
    ...

    <!-- !!== label=b-intro party=b answers="`b` is the first party to answer" ==== -->

    That is me. ...

`parties` maps every role-token to the name the commits are authored with -- usually the
username of the account holding that party on the instance. `language` is documentation
only. `first_commit` dates the repo-creating commit.

`hours_between_contributions` is the gap to the previous commit: a single number is a
fixed step, a `[min, max]` pair is scaled by the length of the contribution, so that a
long text plausibly took its author longer than a one-liner. `active_hours` (optional)
confines the commits to a daily window -- a gap that would land outside it is pushed to
the next morning instead, which keeps a fixture from claiming that somebody published at
four in the morning.

Marker fields, in any order; a value containing spaces goes in double quotes:

* ``label``   -- a name for the contribution, used in messages and in the build output;
* ``party``   -- the role-token, which is also the directory the file lands in;
* ``answers`` -- the text this contribution answers, quoted literally from an EARLIER
  contribution; it must match exactly one segment.

Exactly one contribution carries no reference at all: the opening one, which answers
nothing.

A contribution can also answer a RANGE. Ranges are spelled with quotes as well, for the
same reason the plain anchor is (see below)::

    <!-- !!== label=b-block party=b
         answers_from="The machine costs us around forty euros"
         answers_to="the coffee it produces is" ==== -->

* ``answers_from`` / ``answers_to`` -- a SEGMENT RANGE, used instead of ``answers``. Both
  quotes must resolve to segments of the SAME contribution, `answers_to` to a later one
  than `answers_from`. The key then reads `a3-6b`.
* ``answers_words`` -- a WORD RANGE within one segment, used together with ``answers``:
  the words actually meant, quoted as a run of whole words of that segment. The key then
  reads `a7_7-12b`, or `a7_7b` for a single word.

The two forms cannot be combined -- a word reference always targets exactly one segment.
The grammar is `docs/flexible_references_concept.md`, which also fixes how words are
counted: on the markdown as it is stored in the repo, 1-based, `str.split()`, markup
staying attached to its word. That rule is FROZEN; the quotes here are resolved through
`references.get_segment_words()` rather than counting words a second time.

A marker may span several lines -- everything up to the closing `==== -->` belongs to it,
which is what keeps a marker with two long quotes readable.

The markers are html comments, so the source stays valid markdown and can be written,
read and previewed as one document -- which is how a debate is actually written.

**The order of the contributions in the file is the chronology of the debate**: it becomes
the order of the commits, and a contribution can only answer what precedes it.

Why quotes instead of segment indices
-------------------------------------

An anchor is resolved by searching its quote in the segments of all contributions built so
far; it must match exactly one, otherwise the build aborts and lists the candidates.
Rewording a contribution therefore does not move the anchors of its answers, and a quote
that no longer matches says so instead of silently anchoring the answer somewhere else.

The same holds for range ends and for word ranges, which is why they are quotes too:
segment indices shift when a sentence is inserted, and word positions shift when a single
word is added -- an index-spelled range would move silently, and a word range would end up
covering a different phrase than the one it was written for.

The predecessor of this tool, `fdmd process-content-dir` (removed 2026-08-31), kept
every contribution in a
file of its own and encoded the anchor in its name (`b/a14b.md` answers segment 14 of
`a`), so every inserted sentence forced a rename cascade; it also alternated between two
authors by nesting level, which made a third party impossible.

Placeholders in the text, substituted before the segment keys are generated:

* ``{{key}}``    -- the contribution's own key, e.g. `a19b`
* ``{{anchor}}`` -- the key of the segment it answers, e.g. `a19`

Traps when writing (the splitter splits at ":" and at every "."):

* one paragraph must be one line -- a hard line break inside a paragraph puts the segment
  key on a line of its own;
* a colon always starts a new segment, so use it only where a split is wanted;
* three dots as an ellipsis fall apart into four segments ("(such as ...)" becomes
  "(such as ." / "." / "." / ")") -- write the "…" character instead;
* abbreviations with dots ("e.g.", "i.e.") are NOT a problem, contrary to what this
  docstring claimed until 2026-08-31: `_is_abbreviation_dot()` in `key_management.py`
  already keeps them in one segment. Do not reword a text around them.
"""

import datetime
import os
import re
import shutil
import subprocess
import tempfile
import typing

from git import Actor, Repo

from . import references, repo_handling
from .core import MDProcessor, build_front_matter, split_front_matter
from .key_management import SPLITTER_SYNTAX_VERSION

pjoin = os.path.join

# Segment keys may carry references themselves (`a3-6b1`), so "-" and "_" belong to the
# character class -- without them the segments of a range-referencing contribution are
# invisible here and nothing can be anchored inside it.
#
# Keys are lowercase by construction, so `A-Z` has no business here (it was only ever
# generosity). The class stays deliberately looser than `references.CONTRIBUTION_KEY_PATTERN`
# though, and that is not the same oversight as the one fixed in `core`: that regex
# recognizes file names this library wrote itself, where exactness is free, while these
# two read markers out of text. A marker the grammar rejects would not be reported here,
# it would silently merge into the preceding segment's body -- so a malformed key is
# better matched and then found wrong than not matched at all.
_SEGMENT_KEY_CHARS = r"[a-z0-9_-]+"
SEGMENT_KEY_RE = re.compile(r"::(" + _SEGMENT_KEY_CHARS + r")")
SEGMENT_RE = re.compile(
    r"::(" + _SEGMENT_KEY_CHARS + r")\s*(.*?)(?=::" + _SEGMENT_KEY_CHARS + r"|\Z)", re.DOTALL
)

MARKER_START_RE = re.compile(r"^<!--\s*!!==")
MARKER_RE = re.compile(r"^<!--\s*!!==\s*(?P<head>.*?)\s*=+\s*-->\s*$", re.DOTALL)
# one `name=value` pair of a marker head; unquoted values must not contain spaces
FIELD_RE = re.compile(r"(?P<name>[a-z_]+)=(?:\"(?P<quoted>[^\"]*)\"|(?P<bare>\S+))")

MARKER_FIELDS = ("label", "party", "answers", "answers_from", "answers_to", "answers_words")


class Contribution(typing.NamedTuple):
    """One contribution as the source spells it -- what it answers, not yet where."""

    label: str
    party: str
    answers: str | None = None
    answers_from: str | None = None
    answers_to: str | None = None
    answers_words: str | None = None
    body: str = ""

    @property
    def is_opening(self) -> bool:
        return self.answers is None and self.answers_from is None


class Built(typing.NamedTuple):
    """A contribution that is already in the repo, as later ones can refer to it."""

    segment_keys: list
    segment_texts: list   # whitespace-normalized, for matching the anchor quotes
    md: str               # the keyed markdown, which is what word positions are counted on

# a contribution of this many characters gets the longest gap; longer ones are capped
FULL_LENGTH = 1500


def scaled_gap(text_len: int, gap_min: float, gap_max: float) -> datetime.timedelta:
    """Time an author needed for a contribution: longer text, longer gap."""
    share = min(1.0, text_len / FULL_LENGTH)
    minutes = round((gap_min + (gap_max - gap_min) * share) * 60 / 5) * 5
    return datetime.timedelta(minutes=minutes)


def into_active_hours(when, window):
    """
    Move a timestamp into the daily window `(day_start, day_end)`, keeping its minutes.

    Nobody publishes at four in the morning, and a fixture whose commit times say
    otherwise looks made up -- which it is, but needlessly so. Too late in the evening
    means the next morning; too early means later the same morning. Without a window
    (`window is None`) the timestamp is left alone.
    """
    if window is None:
        return when
    day_start, day_end = window
    if when.time() > datetime.time(day_end):
        return (when + datetime.timedelta(days=1)).replace(hour=day_start)
    if when.time() < datetime.time(day_start):
        return when.replace(hour=day_start)
    return when


def normalize(text: str) -> str:
    return " ".join(text.split())


def parse_marker_fields(head: str, where: str) -> dict:
    """
    Read the `name=value` pairs of a marker head into a dict, in any order.

    The fields used to be matched by one regex with a fixed order, which could not grow a
    second reference field without turning into a case distinction over orderings.
    """
    fields = {}
    pos = 0
    for match in FIELD_RE.finditer(head):
        if head[pos:match.start()].strip():
            raise SystemExit(
                f"{where}: cannot read the marker fields, stray text before "
                f"'{match.group('name')}=':\n    {head[pos:match.start()].strip()}"
            )
        name = match.group("name")
        if name not in MARKER_FIELDS:
            raise SystemExit(
                f"{where}: unknown marker field '{name}'\n"
                f"    known fields: {', '.join(MARKER_FIELDS)}"
            )
        if name in fields:
            raise SystemExit(f"{where}: marker field '{name}' is given twice")
        quoted, bare = match.group("quoted"), match.group("bare")
        fields[name] = quoted if quoted is not None else bare
        pos = match.end()

    if head[pos:].strip():
        raise SystemExit(
            f"{where}: cannot read the marker fields, trailing text:\n    {head[pos:].strip()}"
        )
    for name in ("label", "party"):
        if name not in fields:
            raise SystemExit(f"{where}: the marker lacks the field '{name}'")

    if "answers" in fields and "answers_from" in fields:
        raise SystemExit(
            f"{where}: 'answers' and 'answers_from' exclude each other -- a contribution "
            "answers either one segment or a range of them"
        )
    if ("answers_from" in fields) != ("answers_to" in fields):
        raise SystemExit(
            f"{where}: a segment range needs both 'answers_from' and 'answers_to'"
        )
    if "answers_words" in fields and "answers" not in fields:
        raise SystemExit(
            f"{where}: 'answers_words' needs 'answers' -- a word range names the words "
            "inside the ONE segment that 'answers' quotes, and cannot span a segment range"
        )
    return fields


def read_source(fpath: str) -> tuple:
    """
    Return (metadata, [Contribution, ...]) -- the source as written, without resolving
    any of its quotes.
    """
    with open(fpath) as fp:
        raw = fp.read()

    meta, body_src = split_front_matter(raw)
    for field in ("debate_key", "parties"):
        if field not in meta:
            raise SystemExit(f"{fpath}: front matter lacks the field `{field}`")

    # the front matter is stripped, so line numbers in messages must be shifted back
    offset = len(raw.splitlines()) - len(body_src.splitlines())

    lines = body_src.splitlines()
    contributions = []
    current = None
    i = 0

    while i < len(lines):
        line = lines[i]
        lineno = i + 1 + offset
        if not MARKER_START_RE.match(line):
            if current is None and line.strip():
                raise SystemExit(
                    f"{fpath}:{lineno}: text before the first contribution marker:\n    {line}"
                )
            if current is not None:
                current["lines"].append(line)
            i += 1
            continue

        # a marker may be spread over several lines; it ends at the closing `==== -->`
        chunk = [line]
        while MARKER_RE.match("\n".join(chunk)) is None:
            i += 1
            if i >= len(lines):
                raise SystemExit(
                    f"{fpath}:{lineno}: this marker is never closed with `==== -->`:\n"
                    f"    {line}"
                )
            chunk.append(lines[i])
        head = MARKER_RE.match("\n".join(chunk)).group("head")

        fields = parse_marker_fields(head, f"{fpath}:{lineno}")
        party = fields["party"]
        if party not in meta["parties"]:
            raise SystemExit(
                f"{fpath}:{lineno}: party '{party}' is not declared in the front matter "
                f"(declared: {', '.join(sorted(meta['parties']))})"
            )
        current = {"fields": fields, "lines": []}
        contributions.append(current)
        i += 1

    if not contributions:
        raise SystemExit(f"{fpath}: no contribution marker found")

    parsed = [
        Contribution(
            body="\n".join(c["lines"]).strip() + "\n",
            **{name: c["fields"].get(name) for name in MARKER_FIELDS},
        )
        for c in contributions
    ]

    opening = [c for c in parsed if c.is_opening]
    if len(opening) != 1 or opening[0] is not parsed[0]:
        raise SystemExit(
            f"{fpath}: exactly one contribution must have no `answers=` field, and it must "
            f"be the first one (found: {[c.label for c in opening]})"
        )
    return meta, parsed


def add_keys(plain_md: str, key_prefix: str) -> str:
    mdp = MDProcessor(plain_md=plain_md, key_prefix=key_prefix)
    mdp.convert_plain_md_to_md_with_proto_keys()
    mdp.convert_md_with_proto_keys_to_md_with_real_keys()
    return mdp.md_with_real_keys


def resolve_anchor(quote: str, label: str, segments: dict, field: str = "answers") -> tuple:
    """
    Return (contribution_key, segment_key, segment_text) of the single segment containing
    `quote`, searched across every contribution built so far. Raising here is the point of
    quote anchors: an anchor that shifted or vanished must stop the build, not move an
    answer elsewhere.

    `segments` maps a contribution key to a `Built`.
    """
    needle = normalize(quote)
    hits = [
        (ctb_key, seg_key, text)
        for ctb_key, built in segments.items()
        for seg_key, text in zip(built.segment_keys, built.segment_texts)
        if needle in text
    ]
    if len(hits) == 1:
        return hits[0]

    what = "matches no segment" if not hits else f"matches {len(hits)} segments"
    lines = [f"`{field}` of '{label}' {what} of the preceding contributions:",
             f"    {needle!r}", ""]
    if hits:
        lines.append("candidates -- make the quote longer to pick one:")
        lines += [f"    {k}  {t[:100]}" for _, k, t in hits]
    else:
        lines.append("segments available at this point:")
        lines += [
            f"    {k}  {t[:100]}"
            for built in segments.values()
            for k, t in zip(built.segment_keys, built.segment_texts)
        ]
    raise SystemExit("\n".join(lines))


def resolve_word_range(quote: str, label: str, parent_md: str, segment_key: str) -> tuple:
    """
    Return the 1-based, inclusive word range `(start, end)` that `quote` covers in
    `segment_key`.

    The words are those of the FROZEN tokenizer (`references.get_segment_words`), so the
    quote must be a run of whole words as the markdown source spells them -- markup and
    punctuation included ("once," is one word, "once" does not match it). That strictness
    is deliberate: the positions written into the key are read back against the very same
    tokenizer, and a quote that "almost" matches would silently cover other words.
    """
    words = references.get_segment_words(parent_md, segment_key)
    needle = quote.split()
    if not needle:
        raise SystemExit(f"`answers_words` of '{label}' is empty")

    hits = [i for i in range(len(words) - len(needle) + 1) if words[i:i + len(needle)] == needle]
    if len(hits) == 1:
        return hits[0] + 1, hits[0] + len(needle)

    what = "matches no run of words" if not hits else f"matches {len(hits)} runs of words"
    numbered = " ".join(f"{i}:{w}" for i, w in enumerate(words, start=1))
    raise SystemExit(
        f"`answers_words` of '{label}' {what} in segment {segment_key}:\n"
        f"    {' '.join(needle)!r}\n\n"
        "the words of that segment, as the frozen tokenizer counts them:\n"
        f"    {numbered}"
    )


def resolve_reference(ctb: Contribution, segments: dict) -> tuple:
    """
    Turn the quotes of one contribution into the key unit that encodes its reference.

    Returns (key_unit, anchor_segment_key, anchored_text) -- the unit being `a7`, `a3-6`
    or `a7_7-12`, and the anchor the segment the contribution is rendered below (the LAST
    referenced one, see `docs/flexible_references_concept.md`).
    """
    if ctb.answers_from is not None:
        start_ctb, start_key, _ = resolve_anchor(
            ctb.answers_from, ctb.label, segments, "answers_from")
        end_ctb, end_key, end_text = resolve_anchor(
            ctb.answers_to, ctb.label, segments, "answers_to")
        if start_ctb != end_ctb:
            raise SystemExit(
                f"the range of '{ctb.label}' spans two contributions ({start_key} and "
                f"{end_key}) -- a reference stays within one contribution"
            )
        start_no = int(start_key[len(start_ctb):])
        end_no = int(end_key[len(end_ctb):])
        if end_no <= start_no:
            raise SystemExit(
                f"the range of '{ctb.label}' ends at {end_key}, which is not after its "
                f"start {start_key} -- `answers_to` must quote a LATER segment "
                "(a range over a single segment is spelled with `answers` alone)"
            )
        return f"{start_ctb}{start_no}-{end_no}", end_key, end_text

    parent_ctb, seg_key, seg_text = resolve_anchor(ctb.answers, ctb.label, segments)
    if ctb.answers_words is None:
        return seg_key, seg_key, seg_text

    start, end = resolve_word_range(
        ctb.answers_words, ctb.label, segments[parent_ctb].md, seg_key)
    unit = f"{seg_key}_{start}" if start == end else f"{seg_key}_{start}-{end}"
    return unit, seg_key, " ".join(ctb.answers_words.split())


def build_debate_repo(
    source_path: str, patches_into: str = None, repo_into: str = None, into_fixtures: bool = False
) -> dict:
    """
    Build the content repo described by `source_path` and write its patch collection.

    Returns {label: contribution_key} of the contributions, in the order of the source.
    """
    meta, contributions = read_source(source_path)
    debate_key = meta["debate_key"]
    party_names = meta["parties"]

    first_commit = meta.get("first_commit", "2026-01-01T08:00:00+00:00")
    if isinstance(first_commit, str):
        first_commit = datetime.datetime.fromisoformat(first_commit)
    gap = meta.get("hours_between_contributions", 5)
    # a scalar is a fixed step, a [min, max] pair is scaled by the length of the text
    gap_min, gap_max = (gap, gap) if isinstance(gap, (int, float)) else (gap[0], gap[1])
    active_hours = meta.get("active_hours")

    if into_fixtures:
        if patches_into is not None:
            raise SystemExit("--into-fixtures and --patches-into exclude each other")
        from . import fixtures

        patches_into = pjoin(fixtures.TEST_REPO_HOST_DIR, debate_key, "patches_01")
    elif patches_into is None:
        patches_into = pjoin(debate_key, "patches_01")

    # git runs with the repo as its cwd, so a relative target would end up INSIDE the repo
    patches_into = os.path.abspath(patches_into)

    if repo_into is None:
        repo_dir = tempfile.mkdtemp(prefix=f"{debate_key}-repo-")
        keep_repo = False
    else:
        repo_dir = os.path.abspath(repo_into)
        shutil.rmtree(repo_dir, ignore_errors=True)
        os.makedirs(repo_dir)
        keep_repo = True

    segments = {}   # contribution key -> Built, in document order
    keys = {}       # label -> contribution key
    anchor_of = {}  # label -> the text this contribution answers

    def run_git(*argv):
        subprocess.run(["git", *argv], cwd=repo_dir, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def commit(message, name, email, date):
        """
        One commit, through the same function a live publication goes through.

        Not a local `git commit`: identity and signing then had to be spelled out twice,
        in two places that must agree but nothing keeps in step -- exactly how
        `create_repo()` once ended up leaving the initial commit of every repo unsigned.
        `commit_index()` decides both, so this only supplies what is specific here.

        Specific here is the date -- a fixture invents its chronology, a live publication
        does not -- and it goes in through the environment, which is git's own way of
        overriding it and needs no parameter on the shared function. The party is the
        AUTHOR, the platform is the COMMITTER, which is the split `commit_index()` makes
        anyway; before this the party was both, so the fixtures were the only repos
        claiming that a debate participant had operated the platform.
        """

        stamp = date.isoformat()
        with repo.git.custom_environment(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp):
            repo_handling.commit_index(repo, repo_dir, message, Actor(name=name, email=email))

    run_git("init", "-b", "main")
    repo = Repo(repo_dir)
    # The README written here is a placeholder that `rollout_patches()` replaces: it names
    # the addresses of whichever instance serves the repo, and this build may run anywhere.
    # `allowed_signers` is left out entirely for the same reason -- it names a key, and
    # freezing one into checked-in patch data would invalidate every collection at once.
    readme_path = pjoin(repo_dir, repo_handling.README_FILENAME)
    with open(readme_path, "w") as fp:
        fp.write(repo_handling.build_readme(debate_key))
    run_git("add", repo_handling.README_FILENAME)

    # `REPO_INFO.yaml`, unlike the README, is NOT replaced at rollout: it describes this
    # build, and the build is what a reader needs to know about. It says `kind: built`,
    # names the source and its content hash, and carries the date -- which is the point,
    # because every rebuild discards the previous commit chain and nothing else in the
    # repo would say that this happened. It goes into the patch collection so it travels;
    # anything instance-dependent must stay out of it, or a deploy would rewrite the root
    # commit of every fixture repo (see `build_repo_info()`).
    repo_info_path = pjoin(repo_dir, repo_handling.REPO_INFO_FILENAME)
    with open(repo_info_path, "w") as fp:
        fp.write(repo_handling.build_repo_info(source_path=source_path))
    run_git("add", repo_handling.REPO_INFO_FILENAME)

    commit("first commit", "fair debate system", "fair_debate_system@fair-debate-users.org",
           first_commit)

    when = first_commit
    for ctb in contributions:
        label, party, body = ctb.label, ctb.party, ctb.body
        if ctb.is_opening:
            ctb_key, anchor_key = party, ""
        else:
            key_unit, anchor_key, anchor_text = resolve_reference(ctb, segments)
            ctb_key = key_unit + party
            anchor_of[label] = anchor_text
            if not references.is_valid_key(ctb_key):
                raise SystemExit(
                    f"the reference of '{label}' produced the invalid key '{ctb_key}'"
                )
            try:
                # the same check the loader runs on every repo it opens, run here so that
                # a broken reference cannot reach a patch collection in the first place
                references.validate_reference(
                    ctb_key,
                    segments[references.get_parent_contribution_key(ctb_key)].md,
                    require_canonical=True,
                )
            except ValueError as err:
                raise SystemExit(f"the reference of '{label}' is inconsistent: {err}")

        # the texts talk about their own keys, which are only known here
        body = body.replace("{{key}}", ctb_key).replace("{{anchor}}", anchor_key)

        keyed = add_keys(body, key_prefix=ctb_key)
        segments[ctb_key] = Built(
            segment_keys=SEGMENT_KEY_RE.findall(keyed),
            segment_texts=[normalize(t) for _, t in SEGMENT_RE.findall(keyed)],
            md=keyed,
        )
        keys[label] = ctb_key

        rel_path = pjoin(party, f"{ctb_key}.md")
        repo_path = pjoin(repo_dir, rel_path)
        os.makedirs(os.path.dirname(repo_path), exist_ok=True)
        with open(repo_path, "w") as fp:
            # the same header a live publication writes, minus `created`: a fixture's
            # chronology is invented and lives in the commit dates, and a second copy of
            # it in the file could only ever disagree with them
            fp.write(build_front_matter(splitter_version=SPLITTER_SYNTAX_VERSION))
            fp.write(keyed)

        when = into_active_hours(when + scaled_gap(len(body), gap_min, gap_max), active_hours)

        run_git("add", rel_path)
        commit(f"add contribution {rel_path}",
               party_names[party],
               f"{debate_key}_{party}@fair-debate-users.org",
               when)

    shutil.rmtree(patches_into, ignore_errors=True)
    os.makedirs(patches_into, exist_ok=True)
    run_git("format-patch", "--root", "-o", patches_into)

    def level(key):
        return len(re.findall(r"[a-z]+[0-9]*", key)) - 1

    print(f"{debate_key}: {len(keys)} contributions, "
          f"{len({c.party for c in contributions})} parties, "
          f"max level {max(level(k) for k in keys.values())}")
    for label, key in keys.items():
        print(f"  L{level(key)}  {key:<24} ({label})")
        if label in anchor_of:
            print(f"        answers: {anchor_of[label][:88]}")
    print(f"patches written to: {patches_into}")
    if keep_repo:
        print(f"repo kept at:       {repo_dir}")
    else:
        shutil.rmtree(repo_dir, ignore_errors=True)

    return keys
