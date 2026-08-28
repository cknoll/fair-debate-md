"""
Build the fixture content repo `d00-explanatory-example-debate` from one plain md file
per language: `d00-explanatory-example-debate__plain/<lang>.md`.

Usage (from anywhere, with fair_debate_md importable)::

    python build_d00_explanatory_example.py            # every language
    python build_d00_explanatory_example.py en         # one language

This is the debate a first-time visitor is pointed to, so it explains the platform by
being an instance of it: the three parties introduce themselves by answering the very
list entries that define them, and the objection against the integrity claim is raised
by a party rather than buried in a footnote.

Source format
-------------

One file per language, holding the whole debate as ordinary markdown, split into
contributions by marker comments::

    <!-- !!== label=root party=a ==== -->

    # Explanatory Example Debate
    ...

    <!-- !!== label=b-intro party=b answers="`b` is the first party to answer" ==== -->

    That is me. ...

The markers are html comments, so the file stays valid markdown and can be read and
previewed as one document -- which is how it is written and reviewed. Fields:

* ``label``   -- a name for this contribution; only used in messages and in the build
  output, so keep it descriptive rather than short;
* ``party``   -- the role-token (`a`, `b`, `c`, ...); also the directory the file lands in;
* ``answers`` -- the text this contribution answers, quoted literally from an EARLIER
  contribution. Must be the last field. Optional exactly once, for the opening
  contribution, which answers nothing.

**The order of the contributions in the file is the chronology of the debate**: it becomes
the order of the commits, and a contribution can only answer what precedes it.

Why quotes instead of segment indices
-------------------------------------

The anchor is resolved by searching the quote in the segments of all contributions built
so far; it must match exactly one of them, otherwise the build aborts and lists the
candidates. Rewording a contribution therefore does not move the anchors of its answers,
and a quote that no longer matches says so instead of silently anchoring the answer
somewhere else. The predecessor of this script, `fdmd process-content-dir`, encoded the
anchor in the file name (`b/a14b.md` answers segment 14 of `a`), so every edit that added
or removed a sentence forced a rename cascade -- for a text that is rewritten whenever the
platform changes, that cost was recurring. It also alternated between two authors by
nesting level, which made a third party impossible.

Placeholders in the sources, substituted before the segment keys are generated:

* ``{{key}}``    -- the contribution's own key, e.g. `a19b`
* ``{{anchor}}`` -- the key of the segment it answers, e.g. `a19`

Traps when editing (the splitter splits at ":" and at every "."):

* one paragraph must be one line -- a hard line break inside a paragraph puts the segment
  key on a line of its own;
* a colon always starts a new segment, so use it only where a split is wanted;
* abbreviations with dots ("e.g.", "i.e.") are torn apart -- write "for instance" instead.

A new language needs a file `<plain>/<lang>.md` with the quotes taken from the texts of
that language, plus an entry in LANGUAGES. The parties, and hence the accounts behind
them, stay the same across languages.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

from fair_debate_md.core import MDProcessor

pjoin = os.path.join

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.dirname(HERE)
PLAIN_ROOT = pjoin(HERE, "d00-explanatory-example-debate__plain")

LANGUAGES = {
    "en": {"debate_key": "d00-explanatory-example-debate"},
}

SEGMENT_KEY_RE = re.compile(r"::([a-zA-Z0-9]+)")
SEGMENT_RE = re.compile(r"::([a-zA-Z0-9]+)\s*(.*?)(?=::[a-zA-Z0-9]+|\Z)", re.DOTALL)

MARKER_RE = re.compile(r"^<!--\s*!!==\s*(?P<head>.*?)\s*=+\s*-->\s*$")
FIELDS_RE = re.compile(
    r"^label=(?P<label>\S+)\s+party=(?P<party>[a-z]+)(?:\s+answers=(?P<answers>.+))?$"
)

# The three parties hold accounts on the instance (see fair-debate-web
# `tests/testdata/fixtures01.json`); the names here are the usernames of those accounts,
# so that the git authors of the fixture and its participant rows tell the same story.
PARTY_NAMES = {
    "a": "Explainer",
    "b": "Elaborator",
    "c": "Questioner",
}

README = """\
# Debate "{debate_key}"

This repository contains statements which are part of a formalized debate.

Visit <debate_url> to view this debate and <background_url> for background information.
"""


def normalize(text: str) -> str:
    return " ".join(text.split())


def parse_source(fpath: str) -> list:
    """
    Split a language file into [(label, party, anchor_quote_or_None, body), ...].
    """
    with open(fpath) as fp:
        lines = fp.read().splitlines()

    contributions = []
    current = None

    for lineno, line in enumerate(lines, start=1):
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
                '    expected: label=<name> party=<token> [answers=<quoted text>]'
            )
        anchor = fields.group("answers")
        if anchor is not None:
            anchor = anchor.strip().strip('"')
        current = {
            "label": fields.group("label"),
            "party": fields.group("party"),
            "anchor": anchor,
            "lineno": lineno,
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

    return [(c["label"], c["party"], c["anchor"], "\n".join(c["lines"]).strip() + "\n")
            for c in contributions]


def add_keys(plain_md: str, key_prefix: str) -> str:
    mdp = MDProcessor(plain_md=plain_md, key_prefix=key_prefix)
    mdp.convert_plain_md_to_md_with_proto_keys()
    mdp.convert_md_with_proto_keys_to_md_with_real_keys()
    return mdp.md_with_real_keys


def commit_date(i: int) -> str:
    """one contribution every five hours, starting 2026-08-24T09:00"""
    total_hour = 9 + 5 * i
    return f"2026-08-{24 + total_hour // 24:02d}T{total_hour % 24:02d}:{(i * 17) % 60:02d}:00+02:00"


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


def build(lang: str):
    debate_key = LANGUAGES[lang]["debate_key"]
    source_path = pjoin(PLAIN_ROOT, f"{lang}.md")
    patch_target_dir = pjoin(FIXTURES, "repos", debate_key, "patches_01")

    segments = {}   # contribution key -> (segment keys, segment texts), in document order
    keys = {}       # label -> contribution key
    anchor_of = {}  # label -> the text this contribution answers
    parties = set()

    tmp_repo = tempfile.mkdtemp(prefix=f"{debate_key}-repo-")

    def git(*argv, env_extra=None):
        env = dict(os.environ)
        env.update(env_extra or {})
        subprocess.run(["git", *argv], cwd=tmp_repo, check=True, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def commit(message, name, email, date):
        git("commit", "-m", message, env_extra={
            "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": date,
        })

    git("init", "-b", "main")
    with open(pjoin(tmp_repo, "README.md"), "w") as fp:
        fp.write(README.format(debate_key=debate_key))
    git("add", "README.md")
    commit("first commit", "fair debate system", "fair_debate_system@fair-debate-users.org",
           "2026-08-24T08:00:00+02:00")

    for i, (label, party, anchor_quote, body) in enumerate(parse_source(source_path)):
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
        parties.add(party)

        rel_path = pjoin(party, f"{ctb_key}.md")
        repo_path = pjoin(tmp_repo, rel_path)
        os.makedirs(os.path.dirname(repo_path), exist_ok=True)
        with open(repo_path, "w") as fp:
            fp.write(keyed)

        git("add", rel_path)
        commit(f"add contribution {rel_path}",
               PARTY_NAMES[party],
               f"{debate_key}_{party}@fair-debate-users.org",
               commit_date(i))

    shutil.rmtree(patch_target_dir, ignore_errors=True)
    os.makedirs(patch_target_dir, exist_ok=True)
    git("format-patch", "--root", "-o", patch_target_dir)
    shutil.rmtree(tmp_repo, ignore_errors=True)

    def level(key):
        return len(re.findall(r"[a-z]+[0-9]*", key)) - 1

    print(f"[{lang}] patches written to: {patch_target_dir}")
    print(f"[{lang}] contributions: {len(keys)}, "
          f"parties: {len(parties)}, "
          f"max level: {max(level(k) for k in keys.values())}")
    for label, key in keys.items():
        print(f"  L{level(key)}  {key:<24} ({label})")
        if label in anchor_of:
            print(f"        answers: {anchor_of[label][:88]}")


if __name__ == "__main__":
    langs = sys.argv[1:] or list(LANGUAGES)
    for lang in langs:
        if lang not in LANGUAGES:
            raise SystemExit(f"unknown language {lang!r}, known: {', '.join(LANGUAGES)}")
        build(lang)
