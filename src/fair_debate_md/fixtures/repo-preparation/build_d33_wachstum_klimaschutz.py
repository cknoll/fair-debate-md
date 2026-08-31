"""
Build the fixture content repo `d33-wachstum-klimaschutz` from the plain md sources in
`d33-wachstum-klimaschutz__plain/`.

Usage (from anywhere, with fair_debate_md importable)::

    python build_d33_wachstum_klimaschutz.py

Unlike the other fixtures this one carries *real* argumentative content: it is a
reconstruction of a German radio debate on whether economic growth and climate
protection are compatible (Deutschlandfunk, "Streitkultur", mid-August 2026, see the
root contribution for the source url). The arguments of the two guests were taken over
in substance, heavily shortened and rearranged into contributions; they are explicitly
not verbatim quotes, and the contributions are therefore attributed by role only, not
by name.

What this fixture adds to the existing ones:

* it is the only German-language fixture (d30/d31/d32 are English), which makes it the
  natural sample for i18n work and for screenshots aimed at a German audience;
* it has few parties but deep mutual nesting -- 3 role-tokens, 18 contributions, a spine
  down to level 5 -- whereas d30/d31 are wide (24 resp. 10 parties) and d32 is about
  reference overlaps;
* not every answer is an objection: `c-zustimmung` explicitly agrees with the segment it
  answers, which no other fixture exercises.

Structure: role-token `a` is the editorial frame (topic, context, the disputed question,
and three further anchor sentences), `b` is the economist, `c` is the journalist.

Why a script instead of the (since removed) `fdmd process-content-dir` -- see the
module docstring of
`build_d31_ice_cream.py`; the reasoning is identical.

To change the content, edit the files under
`d33-wachstum-klimaschutz__plain/<party>/<label>.md` and re-run this script. Note that
the segment indices in `STRUCTURE` refer to the *generated* segments, so editing a text
can shift the anchors of its children -- the script prints the anchor sentence of every
contribution so that such a shift is visible.

Traps when editing the plain sources (the splitter also splits at ":" and at every "."):

* one paragraph must be one line -- a hard line break inside a paragraph puts the
  segment key on a line of its own;
* a colon always starts a new segment, so use it only where a split is wanted;
* dates like "15. August" or "15.08.2026" are torn into two or three segments; write
  them without a period ("Mitte August 2026") or keep them out of the text.
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
DEBATE_KEY = "d33-wachstum-klimaschutz"
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

    # the two opening statements answer the disputed question itself (root segment 13)
    ("b-eingang", "b", "root", 13),
    ("c-eingang", "c", "root", 13),

    # the remaining anchors offered by the editorial frame
    ("c-grundgesetz", "c", "root", 14),   # the constitutional amendment proposal
    ("b-grundgesetz", "b", "root", 15),   # "is that a suitable means?"
    ("c-studien", "c", "root", 16),       # the decoupling studies
    ("c-kreislauf", "c", "root", 18),     # social feasibility of the transition
    ("b-sozialpolitik", "b", "root", 18),

    # objections to the opening statement of b
    ("c-zeit", "c", "b-eingang", 6),      # innovation cycles take longer than 20 years
    ("c-global", "c", "b-eingang", 9),    # "global" is a smaller set of countries

    # the main spine: 10 percent -> grid/storage -> heat pump -> instruments -> costs
    ("b-netz", "b", "c-eingang", 4),
    ("c-waermepumpe", "c", "b-netz", 7),
    ("b-instrumente", "b", "c-waermepumpe", 5),
    ("c-cdr", "c", "b-instrumente", 8),
    ("c-zustimmung", "c", "b-instrumente", 4),   # agreement, not objection

    # the second spine: circular economy -> dystopia -> nature enforces it -> capitalism
    ("b-dystopie", "b", "c-kreislauf", 3),
    ("c-natur", "c", "b-dystopie", 5),
    ("b-kapitalismus", "b", "c-natur", 5),
]

SEGMENT_KEY_RE = re.compile(r"::([a-zA-Z0-9]+)")
SEGMENT_RE = re.compile(r"::([a-zA-Z0-9]+)\s*(.*?)(?=::[a-zA-Z0-9]+|\Z)", re.DOTALL)


def add_keys(plain_md: str, key_prefix: str) -> str:
    mdp = MDProcessor(plain_md=plain_md, key_prefix=key_prefix)
    mdp.convert_plain_md_to_md_with_proto_keys()
    mdp.convert_md_with_proto_keys_to_md_with_real_keys()
    return mdp.md_with_real_keys


def commit_date(i: int) -> str:
    """one contribution every three hours, starting 2026-08-16T09:00"""
    total_hour = 9 + 3 * i
    return f"2026-08-{16 + total_hour // 24:02d}T{total_hour % 24:02d}:{(i * 13) % 60:02d}:00+02:00"


def build():
    ctb_key_by_label = {}      # label -> contribution key
    segments_by_ctb = {}       # contribution key -> its segment keys, in document order
    segment_texts = {}         # contribution key -> its segment texts, in document order

    tmp_repo = tempfile.mkdtemp(prefix="d33-repo-")

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
           "2026-08-16T08:00:00+02:00")

    anchor_of = {}  # label -> the sentence this contribution answers

    for i, (label, party, parent_label, seg_idx) in enumerate(STRUCTURE):
        with open(pjoin(PLAIN_DIR, party, f"{label}.md")) as fp:
            body = fp.read()

        if parent_label is None:
            ctb_key = party
        else:
            parent_key = ctb_key_by_label[parent_label]
            ctb_key = segments_by_ctb[parent_key][seg_idx] + party
            anchor_of[label] = segment_texts[parent_key][seg_idx]

        keyed = add_keys(body, key_prefix=ctb_key)
        segments_by_ctb[ctb_key] = SEGMENT_KEY_RE.findall(keyed)
        segment_texts[ctb_key] = [" ".join(t.split()) for _, t in SEGMENT_RE.findall(keyed)]
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
        print(f"  L{level(key)}  {key:<28} ({label})")
        if label in anchor_of:
            print(f"        answers: {anchor_of[label][:88]}")


if __name__ == "__main__":
    build()
