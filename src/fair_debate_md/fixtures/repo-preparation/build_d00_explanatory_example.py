"""
Build the fixture content repo `d00-explanatory-example-debate` from the plain md
sources in `d00-explanatory-example-debate__plain/<lang>/<party>/<label>.md`.

Usage (from anywhere, with fair_debate_md importable)::

    python build_d00_explanatory_example.py            # every language
    python build_d00_explanatory_example.py en         # one language

This is the debate a first-time visitor is pointed to, so it explains the platform by
being an instance of it: the three parties introduce themselves by answering the very
list entries that define them, and the objection against the integrity claim is raised
by a party rather than buried in a footnote.

Why a script instead of `fdmd process-content-dir`:

* `process-content-dir` encodes the anchor of a contribution in its FILE NAME (`b/a14b.md`
  answers segment 14 of `a`), so adding or removing a single sentence in a parent moves
  the anchors of all its children and forces a rename cascade. This debate gets rewritten
  whenever the platform changes, which makes that cost recurring rather than one-off;
* it alternates between two authors by nesting level, so a third party is impossible.

Anchors here are QUOTES, not indices: an entry of `STRUCTURE_<LANG>` names a piece of text
from the parent contribution and the build resolves it to the segment containing it. A
quote matching no segment, or several, aborts the build with the list of candidates.
Rewording a parent is therefore safe as long as the quoted words survive it -- and if they
do not, the build says so instead of silently anchoring the answer somewhere else.

Placeholders in the plain sources, substituted before the segment keys are generated:

* ``{{key}}``    -- the contribution's own key, e.g. `a20b`
* ``{{anchor}}`` -- the key of the segment it answers, e.g. `a20`

Traps when editing the plain sources (the splitter splits at ":" and at every "."):

* one paragraph must be one line -- a hard line break inside a paragraph puts the segment
  key on a line of its own;
* a colon always starts a new segment, so use it only where a split is wanted;
* abbreviations with dots ("e.g.", "i.e.") are torn apart -- write "for instance" instead.

A new language needs a directory `<plain>/<lang>/` and a `STRUCTURE_<LANG>` with quotes
from the texts of that language; the parties, and hence the accounts behind them, stay
the same across languages.
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

SEGMENT_KEY_RE = re.compile(r"::([a-zA-Z0-9]+)")
SEGMENT_RE = re.compile(r"::([a-zA-Z0-9]+)\s*(.*?)(?=::[a-zA-Z0-9]+|\Z)", re.DOTALL)

# The three parties hold accounts on the instance (see fair-debate-web
# `tests/testdata/fixtures01.json`); the names here are the usernames of those accounts,
# so that the git authors of the fixture and its participant rows tell the same story.
PARTY_NAMES = {
    "a": "Explainer",
    "b": "Elaborator",
    "c": "Questioner",
}

# (label, party, parent_label, anchor_quote)
# `label` also names the plain source file: <lang>/<party>/<label>.md
# `anchor_quote` is a literal piece of the parent's text -- it must occur in exactly one
# of the parent's segments. Order matters twice: a parent must precede its children, and
# the order is the order of the commits, i.e. the chronology the debate claims to have.
STRUCTURE_EN = [
    ("root", "a", None, None),

    # the two answering parties introduce themselves on the list entries defining them
    ("b-intro", "b", "root", "`b` is the first party to answer"),
    ("c-intro", "c", "root", "`c` is the second party to answer"),

    # feature 1, and the two footnotes party a adds to it
    ("b-answers", "b", "root", "Persistent in-context answers"),
    ("a-example", "a", "b-answers", "Any number of parties can take part"),
    ("a-markdown", "a", "b-answers", "Contributions may be written in Markdown"),

    # feature 2, the objection against it, and the answer to the objection
    ("b-integrity", "b", "root", "Provable integrity of the content data"),
    ("c-critical", "c", "b-integrity", "nobody has to be appointed to keep watch"),
    ("a-evolution", "a", "c-critical", "So what is actually proven here today?"),

    # written last on purpose: it reports what the opening text could not know
    ("a-selfreply", "a", "root", "A party may also answer a statement of its own"),
]

LANGUAGES = {
    "en": {"debate_key": "d00-explanatory-example-debate", "structure": STRUCTURE_EN},
}

README = """\
# Debate "{debate_key}"

This repository contains statements which are part of a formalized debate.

Visit <debate_url> to view this debate and <background_url> for background information.
"""


def normalize(text: str) -> str:
    return " ".join(text.split())


def add_keys(plain_md: str, key_prefix: str) -> str:
    mdp = MDProcessor(plain_md=plain_md, key_prefix=key_prefix)
    mdp.convert_plain_md_to_md_with_proto_keys()
    mdp.convert_md_with_proto_keys_to_md_with_real_keys()
    return mdp.md_with_real_keys


def commit_date(i: int) -> str:
    """one contribution every five hours, starting 2026-08-24T09:00"""
    total_hour = 9 + 5 * i
    return f"2026-08-{24 + total_hour // 24:02d}T{total_hour % 24:02d}:{(i * 17) % 60:02d}:00+02:00"


def resolve_anchor(quote: str, parent_label: str, seg_keys: list, seg_texts: list) -> tuple:
    """
    Return (segment_key, segment_text) of the single segment of the parent containing
    `quote`. Raising here is the point of the quote-based anchors: a shifted or vanished
    anchor must stop the build instead of moving an answer somewhere else.
    """
    needle = normalize(quote)
    hits = [(k, t) for k, t in zip(seg_keys, seg_texts) if needle in t]
    if len(hits) == 1:
        return hits[0]

    what = "matches no segment" if not hits else f"matches {len(hits)} segments"
    lines = [f"anchor quote {what} of contribution '{parent_label}':", f"    {needle!r}", ""]
    if hits:
        lines.append("candidates:")
        lines += [f"    {k}  {t[:100]}" for k, t in hits]
    else:
        lines.append("segments of the parent:")
        lines += [f"    {k}  {t[:100]}" for k, t in zip(seg_keys, seg_texts)]
    raise SystemExit("\n".join(lines))


def build(lang: str):
    spec = LANGUAGES[lang]
    debate_key = spec["debate_key"]
    plain_dir = pjoin(PLAIN_ROOT, lang)
    patch_target_dir = pjoin(FIXTURES, "repos", debate_key, "patches_01")

    ctb_key_by_label = {}   # label -> contribution key
    seg_keys_by_ctb = {}    # contribution key -> segment keys, in document order
    seg_texts_by_ctb = {}   # contribution key -> segment texts, in document order
    anchor_of = {}          # label -> the text this contribution answers

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

    for i, (label, party, parent_label, anchor_quote) in enumerate(spec["structure"]):
        with open(pjoin(plain_dir, party, f"{label}.md")) as fp:
            body = fp.read()

        if parent_label is None:
            ctb_key, anchor_key = party, ""
        else:
            parent_key = ctb_key_by_label[parent_label]
            anchor_key, anchor_text = resolve_anchor(
                anchor_quote, parent_label,
                seg_keys_by_ctb[parent_key], seg_texts_by_ctb[parent_key],
            )
            ctb_key = anchor_key + party
            anchor_of[label] = anchor_text

        # the texts talk about their own keys, which are only known here
        body = body.replace("{{key}}", ctb_key).replace("{{anchor}}", anchor_key)

        keyed = add_keys(body, key_prefix=ctb_key)
        seg_keys_by_ctb[ctb_key] = SEGMENT_KEY_RE.findall(keyed)
        seg_texts_by_ctb[ctb_key] = [normalize(t) for _, t in SEGMENT_RE.findall(keyed)]
        ctb_key_by_label[label] = ctb_key

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
    print(f"[{lang}] contributions: {len(ctb_key_by_label)}, "
          f"parties: {len({p for _, p, *_ in spec['structure']})}, "
          f"max level: {max(level(k) for k in ctb_key_by_label.values())}")
    for label, key in ctb_key_by_label.items():
        print(f"  L{level(key)}  {key:<24} ({label})")
        if label in anchor_of:
            print(f"        answers: {anchor_of[label][:88]}")


if __name__ == "__main__":
    langs = sys.argv[1:] or list(LANGUAGES)
    for lang in langs:
        if lang not in LANGUAGES:
            raise SystemExit(f"unknown language {lang!r}, known: {', '.join(LANGUAGES)}")
        build(lang)
