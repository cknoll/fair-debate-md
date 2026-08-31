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

Marker fields:

* ``label``   -- a name for the contribution, used in messages and in the build output;
* ``party``   -- the role-token, which is also the directory the file lands in;
* ``answers`` -- the text this contribution answers, quoted literally from an EARLIER
  contribution. Must be the last field, and is absent exactly once: on the opening
  contribution, which answers nothing.

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

from git import Actor, Repo

from . import repo_handling
from .core import MDProcessor, split_front_matter

pjoin = os.path.join

SEGMENT_KEY_RE = re.compile(r"::([a-zA-Z0-9]+)")
SEGMENT_RE = re.compile(r"::([a-zA-Z0-9]+)\s*(.*?)(?=::[a-zA-Z0-9]+|\Z)", re.DOTALL)

MARKER_RE = re.compile(r"^<!--\s*!!==\s*(?P<head>.*?)\s*=+\s*-->\s*$")
FIELDS_RE = re.compile(
    r"^label=(?P<label>\S+)\s+party=(?P<party>[a-z]+)(?:\s+answers=(?P<answers>.+))?$"
)

# No `allowed_signers` next to it: that file names the signing key, and freezing a key
# into checked-in patch data would invalidate every collection at once when it changes.
# `repo_handling.rollout_patches()` adds it when the repo is actually created.
README = """\
# Debate "{debate_key}"

This repository contains statements which are part of a formalized debate.

Visit <debate_url> to view this debate and <background_url> for background information.
"""


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


def read_source(fpath: str) -> tuple:
    """
    Return (metadata, [(label, party, anchor_quote_or_None, body), ...]).
    """
    with open(fpath) as fp:
        raw = fp.read()

    meta, body_src = split_front_matter(raw)
    for field in ("debate_key", "parties"):
        if field not in meta:
            raise SystemExit(f"{fpath}: front matter lacks the field `{field}`")

    # the front matter is stripped, so line numbers in messages must be shifted back
    offset = len(raw.splitlines()) - len(body_src.splitlines())

    contributions = []
    current = None

    for lineno, line in enumerate(body_src.splitlines(), start=1 + offset):
        match = MARKER_RE.match(line)
        if match is None:
            if current is None and line.strip():
                raise SystemExit(
                    f"{fpath}:{lineno}: text before the first contribution marker:\n    {line}"
                )
            if current is not None:
                current["lines"].append(line)
            continue

        fields = FIELDS_RE.match(match.group("head"))
        if fields is None:
            raise SystemExit(
                f"{fpath}:{lineno}: cannot read the marker fields:\n"
                f"    {match.group('head')}\n"
                "    expected: label=<name> party=<token> [answers=<quoted text>]"
            )
        party = fields.group("party")
        if party not in meta["parties"]:
            raise SystemExit(
                f"{fpath}:{lineno}: party '{party}' is not declared in the front matter "
                f"(declared: {', '.join(sorted(meta['parties']))})"
            )
        anchor = fields.group("answers")
        if anchor is not None:
            anchor = anchor.strip().strip('"')
        current = {
            "label": fields.group("label"),
            "party": party,
            "anchor": anchor,
            "lines": [],
        }
        contributions.append(current)

    if not contributions:
        raise SystemExit(f"{fpath}: no contribution marker found")

    opening = [c for c in contributions if c["anchor"] is None]
    if len(opening) != 1 or opening[0] is not contributions[0]:
        raise SystemExit(
            f"{fpath}: exactly one contribution must have no `answers=` field, and it must "
            f"be the first one (found: {[c['label'] for c in opening]})"
        )

    parsed = [
        (c["label"], c["party"], c["anchor"], "\n".join(c["lines"]).strip() + "\n")
        for c in contributions
    ]
    return meta, parsed


def add_keys(plain_md: str, key_prefix: str) -> str:
    mdp = MDProcessor(plain_md=plain_md, key_prefix=key_prefix)
    mdp.convert_plain_md_to_md_with_proto_keys()
    mdp.convert_md_with_proto_keys_to_md_with_real_keys()
    return mdp.md_with_real_keys


def resolve_anchor(quote: str, label: str, segments: dict) -> tuple:
    """
    Return (segment_key, segment_text) of the single segment containing `quote`, searched
    across every contribution built so far. Raising here is the point of quote anchors: an
    anchor that shifted or vanished must stop the build, not move an answer elsewhere.

    `segments` maps a contribution key to (segment_keys, segment_texts).
    """
    needle = normalize(quote)
    hits = [
        (seg_key, text)
        for seg_keys, texts in segments.values()
        for seg_key, text in zip(seg_keys, texts)
        if needle in text
    ]
    if len(hits) == 1:
        return hits[0]

    what = "matches no segment" if not hits else f"matches {len(hits)} segments"
    lines = [f"the anchor of '{label}' {what} of the preceding contributions:",
             f"    {needle!r}", ""]
    if hits:
        lines.append("candidates -- make the quote longer to pick one:")
        lines += [f"    {k}  {t[:100]}" for k, t in hits]
    else:
        lines.append("segments available at this point:")
        lines += [
            f"    {k}  {t[:100]}"
            for seg_keys, texts in segments.values()
            for k, t in zip(seg_keys, texts)
        ]
    raise SystemExit("\n".join(lines))


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

    segments = {}   # contribution key -> (segment keys, segment texts), in document order
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
    with open(pjoin(repo_dir, "README.md"), "w") as fp:
        fp.write(README.format(debate_key=debate_key))
    run_git("add", "README.md")
    commit("first commit", "fair debate system", "fair_debate_system@fair-debate-users.org",
           first_commit)

    when = first_commit
    for label, party, anchor_quote, body in contributions:
        if anchor_quote is None:
            ctb_key, anchor_key = party, ""
        else:
            anchor_key, anchor_text = resolve_anchor(anchor_quote, label, segments)
            ctb_key = anchor_key + party
            anchor_of[label] = anchor_text

        # the texts talk about their own keys, which are only known here
        body = body.replace("{{key}}", ctb_key).replace("{{anchor}}", anchor_key)

        keyed = add_keys(body, key_prefix=ctb_key)
        segments[ctb_key] = (
            SEGMENT_KEY_RE.findall(keyed),
            [normalize(t) for _, t in SEGMENT_RE.findall(keyed)],
        )
        keys[label] = ctb_key

        rel_path = pjoin(party, f"{ctb_key}.md")
        repo_path = pjoin(repo_dir, rel_path)
        os.makedirs(os.path.dirname(repo_path), exist_ok=True)
        with open(repo_path, "w") as fp:
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
          f"{len({p for _, p, _, _ in contributions})} parties, "
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
