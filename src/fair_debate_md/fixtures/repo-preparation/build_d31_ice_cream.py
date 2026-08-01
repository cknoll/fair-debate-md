"""
Build the fixture content repo `d31-ice-cream` from the plain md sources in
`d31-ice-cream__plain/`.

Usage (from anywhere, with fair_debate_md importable)::

    python build_d31_ice_cream.py

The debate is deliberately a toy topic (which ice cream flavour is best) so that
its content never distracts from what it is actually for: judging frontend design
decisions about nesting. Unlike the synthetic `d30-many-parties` stress fixture it
has realistic text lengths and a realistic answer structure -- 10 parties, 26
contributions, only 5 of the root segments answered, roughly half of the answers
one or two paragraphs long, and one spine reaching level 8.

Why a script instead of `fdmd process-content-dir`:

* the answer structure has to be expressed somewhere. A contribution key encodes
  which *segment* it answers (`a4b` = party b answers segment `a4`), and segment
  numbering cannot be predicted by hand -- the splitter also splits at ":". So
  `STRUCTURE` names the anchor as (parent contribution, segment index) and the
  real key is resolved from the generated text.
* the fixture should look like a debate the app itself produced: one commit per
  contribution, authored by that contribution's party (cf. `core.commit_ctb_list`).

To change the content, edit the files under `d31-ice-cream__plain/<party>/<label>.md`
and re-run this script; to change the structure, edit `STRUCTURE`.
"""

import os
import re
import shutil
import subprocess
import tempfile

from fair_debate_md.core import MDProcessor

pjoin = os.path.join

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.dirname(HERE)
DEBATE_KEY = "d31-ice-cream"
PLAIN_DIR = pjoin(HERE, f"{DEBATE_KEY}__plain")
PATCH_TARGET_DIR = pjoin(FIXTURES, "repos", DEBATE_KEY, "patches_01")

README = f"""\
# Debate "{DEBATE_KEY}"

This repository contains statements which are part of a formalized debate.

Visit <debate_url> to view this debate and <background_url> for background information.
"""

# (label, party, parent_label, segment_index_within_the_parent_contribution)
# `label` also names the plain source file: <party>/<label>.md
# order matters: every parent must occur before its children
STRUCTURE = [
    ("root", "a", None, None),

    # answers to the thesis sentence (root segment index 3)
    ("b-thesis", "b", "root", 3),
    ("c-thesis", "c", "root", 3),
    ("d-thesis", "d", "root", 3),
    ("e-scoreboard", "e", "b-thesis", 1),
    ("f-scoreboard", "f", "b-thesis", 1),
    ("g-broadly", "g", "d-thesis", 0),

    # answers to the seasonality sentence (root segment index 8)
    ("f-season", "f", "root", 8),
    ("g-season", "g", "root", 8),
    ("h-season", "h", "root", 8),
    ("i-season", "i", "root", 8),
    ("i-asparagus", "i", "h-season", 1),
    ("j-asparagus", "j", "h-season", 1),

    # answers to the pistachio sentence (root segment index 10)
    ("e-pistachio", "e", "root", 10),
    ("b-market", "b", "e-pistachio", 2),
    ("h-market", "h", "e-pistachio", 2),

    # answers to the combination sentence (root segment index 13); carries the
    # deep spine down to level 8
    ("c-combi", "c", "root", 13),
    ("d-combi", "d", "root", 13),
    ("spine-L2-d", "d", "c-combi", 0),
    ("spine-L3-c", "c", "spine-L2-d", 0),
    ("spine-L4-e", "e", "spine-L3-c", 0),
    ("spine-L5-d", "d", "spine-L4-e", 0),
    ("spine-L6-c", "c", "spine-L5-d", 0),
    ("spine-L7-e", "e", "spine-L6-c", 0),
    ("spine-L8-d", "d", "spine-L7-e", 0),

    # answer to the melting sentence (root segment index 15)
    ("j-melting", "j", "root", 15),
]

SEGMENT_KEY_RE = re.compile(r"::([a-zA-Z0-9]+)")


def add_keys(plain_md: str, key_prefix: str) -> str:
    mdp = MDProcessor(plain_md=plain_md, key_prefix=key_prefix)
    mdp.convert_plain_md_to_md_with_proto_keys()
    mdp.convert_md_with_proto_keys_to_md_with_real_keys()
    return mdp.md_with_real_keys


def commit_date(i: int) -> str:
    """one contribution roughly every seven hours, starting 2026-03-02"""
    day = 2 + (i * 7) // 24
    hour = 9 + ((i * 7) % 24) // 2
    return f"2026-03-{day:02d}T{hour:02d}:{(i * 13) % 60:02d}:00+01:00"


def build():
    ctb_key_by_label = {}      # label -> contribution key
    segments_by_ctb = {}       # contribution key -> its segment keys, in document order

    tmp_repo = tempfile.mkdtemp(prefix="d31-repo-")

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
           "2026-03-01T18:00:00+01:00")

    for i, (label, party, parent_label, seg_idx) in enumerate(STRUCTURE):
        with open(pjoin(PLAIN_DIR, party, f"{label}.md")) as fp:
            body = fp.read()

        if parent_label is None:
            ctb_key = party
        else:
            parent_key = ctb_key_by_label[parent_label]
            ctb_key = segments_by_ctb[parent_key][seg_idx] + party

        keyed = add_keys(body, key_prefix=ctb_key)
        segments_by_ctb[ctb_key] = SEGMENT_KEY_RE.findall(keyed)
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

    shutil.rmtree(PATCH_TARGET_DIR, ignore_errors=True)
    os.makedirs(PATCH_TARGET_DIR, exist_ok=True)
    git("format-patch", "--root", "-o", PATCH_TARGET_DIR)
    shutil.rmtree(tmp_repo, ignore_errors=True)

    def level(key):
        return len(re.findall(r"[a-z]+[0-9]*", key)) - 1

    print(f"patches written to: {PATCH_TARGET_DIR}")
    print(f"contributions: {len(segments_by_ctb)}, "
          f"parties: {len({party for _, party, *_ in STRUCTURE})}, "
          f"max level: {max(level(k) for k in segments_by_ctb)}")
    for label, key in ctb_key_by_label.items():
        print(f"  L{level(key)}  {key:<24} ({label})")


if __name__ == "__main__":
    build()
