"""
Build the fixture content repo `d32-overlapping-refs` from the plain md sources in
`d32-overlapping-refs__plain/`.

Usage (from anywhere, with fair_debate_md importable)::

    python build_d32_overlapping_refs.py

Purpose: make the *display* problem of flexible references (see
`docs/flexible_references_concept.md`) assessable in the frontend. The backend
grammar allows replies to reference a segment range (`a3-6b`) or a word range
within a segment (`a7_7-12f`), and explicitly permits overlapping references --
including several by the same party. What that does to the rendered debate
cannot be judged from the specification, only from a debate that actually
contains the awkward cases.

The topic is deliberately a toy dispute (whether the office coffee machine
should go) with realistic sentence lengths; every reference constellation below
is plausible as something a real participant would write.

The constellations covered (all anchored per the anchor rule, i.e. rendered
below the LAST referenced segment):

  a3-6b        party b answers the four arguments as a block
  a4c          party c answers only the third of them   -> narrow reply renders
                                                            BEFORE the range that
                                                            encloses it
  a5-8d        party d answers a5..a8                   -> partially overlaps b's
                                                            range; neither contains
                                                            the other
  a5b          party b again, narrowly, inside its own earlier range (allowed
               by design: "one reply per (reference, party)")
  a7e          full-segment reply ...
  a7_7-12f     ... and a word-range reply to the same segment
  a7_10-16g    ... and a second word range overlapping f's
  a3-6b1-2h    a range reference one level down, over b's own segments

Structure entries name the reference as indices into the parent contribution's
segment list, because segment numbering cannot be predicted by hand:

    (label, party, parent_label, ref)   with ref being
        i               -> plain reference to the parent's i-th segment
        (i, j)          -> segment range, i-th .. j-th segment
        (i, (v, w))     -> word range v..w (1-based, inclusive) in the i-th segment
"""

import os
import re
import shutil
import subprocess
import tempfile

from fair_debate_md.core import MDProcessor
from fair_debate_md import references

pjoin = os.path.join

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.dirname(HERE)
DEBATE_KEY = "d32-overlapping-refs"
PLAIN_DIR = pjoin(HERE, f"{DEBATE_KEY}__plain")
PATCH_TARGET_DIR = pjoin(FIXTURES, "repos", DEBATE_KEY, "patches_01")

README = f"""\
# Debate "{DEBATE_KEY}"

This repository contains statements which are part of a formalized debate.

Visit <debate_url> to view this debate and <background_url> for background information.
"""

STRUCTURE = [
    ("root", "a", None, None),

    # the four arguments (a3..a6) answered as a block ...
    ("b-block", "b", "root", (2, 5)),
    # ... while c answers only one of them, and b itself follows up on another
    ("c-repairs", "c", "root", 3),
    ("b-narrow", "b", "root", 4),
    # d's range starts inside b's and ends outside it
    ("d-straddle", "d", "root", (4, 7)),

    # same segment, three granularities
    ("e-costing", "e", "root", 6),
    ("f-words", "f", "root", (6, (7, 12))),
    ("g-words", "g", "root", (6, (10, 16))),

    # a range one level down, over b's own segments
    ("h-nested-range", "h", "b-block", (0, 1)),
]

SEGMENT_KEY_RE = re.compile(r"::([a-zA-Z0-9_-]+)")
SEGMENT_TAIL_RE = re.compile(r"^(.*?)(\d+)$")


def add_keys(plain_md: str, key_prefix: str) -> str:
    mdp = MDProcessor(plain_md=plain_md, key_prefix=key_prefix)
    mdp.convert_plain_md_to_md_with_proto_keys()
    mdp.convert_md_with_proto_keys_to_md_with_real_keys()
    return mdp.md_with_real_keys


def split_segment_key(segment_key: str) -> tuple[str, int]:
    """"a5-7b2" -> ("a5-7b", 2); the base is everything before the segment number"""
    m = SEGMENT_TAIL_RE.fullmatch(segment_key)
    if m is None:
        raise ValueError(f"not a segment key: '{segment_key}'")
    return m.group(1), int(m.group(2))


def build_reference_unit(parent_segments: list, ref) -> str:
    """
    Build the key unit that encodes `ref` against `parent_segments`
    (the parent contribution's segment keys, in document order).
    """
    if isinstance(ref, int):
        return parent_segments[ref]

    index, second = ref
    if isinstance(second, int):
        # segment range: same base, first..last segment number
        base, start_number = split_segment_key(parent_segments[index])
        _, end_number = split_segment_key(parent_segments[second])
        return f"{base}{start_number}-{end_number}"

    word_start, word_end = second
    return f"{parent_segments[index]}_{word_start}-{word_end}"


def commit_date(i: int) -> str:
    """one contribution roughly every five hours, starting 2026-04-06"""
    day = 6 + (i * 5) // 24
    hour = 9 + ((i * 5) % 24) // 2
    return f"2026-04-{day:02d}T{hour:02d}:{(i * 17) % 60:02d}:00+02:00"


def build():
    ctb_key_by_label = {}      # label -> contribution key
    segments_by_ctb = {}       # contribution key -> its segment keys, in document order
    md_by_ctb = {}             # contribution key -> keyed markdown (for word lookups)

    tmp_repo = tempfile.mkdtemp(prefix="d32-repo-")

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
        fp.write(README)
    git("add", "README.md")
    commit("first commit", "fair debate system", "fair_debate_system@fair-debate-users.org",
           "2026-04-05T18:00:00+02:00")

    report = []
    for i, (label, party, parent_label, ref) in enumerate(STRUCTURE):
        with open(pjoin(PLAIN_DIR, party, f"{label}.md")) as fp:
            body = fp.read()

        if parent_label is None:
            ctb_key = party
        else:
            parent_key = ctb_key_by_label[parent_label]
            ctb_key = build_reference_unit(segments_by_ctb[parent_key], ref) + party
            if not references.is_valid_key(ctb_key):
                raise ValueError(f"generated key is invalid: '{ctb_key}' (label {label})")
            references.validate_reference(ctb_key, md_by_ctb[parent_key])

        keyed = add_keys(body, key_prefix=ctb_key)
        segments_by_ctb[ctb_key] = SEGMENT_KEY_RE.findall(keyed)
        md_by_ctb[ctb_key] = keyed
        ctb_key_by_label[label] = ctb_key

        rel_path = pjoin(party, f"{ctb_key}.md")
        repo_path = pjoin(tmp_repo, rel_path)
        os.makedirs(os.path.dirname(repo_path), exist_ok=True)
        with open(repo_path, "w") as fp:
            fp.write(keyed)

        git("add", rel_path)
        commit(f"add contribution {rel_path}",
               f"fair debate user {DEBATE_KEY} {party}",
               f"{DEBATE_KEY}_{party}@fair-debate-users.org",
               commit_date(i))

        # report what the reference actually resolved to, so that word ranges can
        # be eyeballed against the source they were meant to cover
        detail = ""
        if parent_label is not None:
            parent_key = ctb_key_by_label[parent_label]
            anchor = references.get_anchor_segment_key(ctb_key)
            detail = f"anchor {anchor}"
            if isinstance(ref, tuple) and isinstance(ref[1], tuple):
                words = references.get_segment_words(
                    md_by_ctb[parent_key], segments_by_ctb[parent_key][ref[0]])
                v, w = ref[1]
                detail += "   words: " + " ".join(words[v - 1:w])
        report.append(f"  {ctb_key:<16} ({label})  {detail}")

    shutil.rmtree(PATCH_TARGET_DIR, ignore_errors=True)
    os.makedirs(PATCH_TARGET_DIR, exist_ok=True)
    git("format-patch", "--root", "-o", PATCH_TARGET_DIR)
    shutil.rmtree(tmp_repo, ignore_errors=True)

    print(f"patches written to: {PATCH_TARGET_DIR}")
    print(f"contributions: {len(segments_by_ctb)}, "
          f"parties: {len({party for _, party, *_ in STRUCTURE})}")
    print("\n".join(report))


if __name__ == "__main__":
    build()
