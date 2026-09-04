# fair-debate-md

## Version discipline

`src/fair_debate_md/release.py` holds `__version__`, and **it has to be maintained
deliberately from now on** -- it is no longer a cosmetic number.

Reason: the version is written into the content repos this library produces
(`REPO_INFO.yaml`, see `repo_handling.py`), and those repos are handed out to readers as
git clones and bundles. A repo therefore states which software segmented its text and
built its history. That statement is only worth something if the number actually moves
when the behaviour does.

Grades:

- **patch** -- fixes that cannot change how existing text is segmented or how a repo is
  laid out;
- **minor** -- new capability, new field in the repo metadata, anything a reader of an
  old repo would notice as "this was made by something newer";
- **major** -- a change to the splitter syntax or to the repo layout, i.e. something that
  makes an old repo's content and a new build of the same source disagree.

**Bump in the merge commit into `develop`, never in a feature branch.** The number
depends on the order branches arrive, which a branch cannot know -- and two branches
picking the same number merge *without* a conflict, so nothing catches it. A branch
states what it earns as a commit trailer instead:

    Version-Bump: minor

The merge takes the highest trailer of what it brings in, raises the number from the one
`develop` currently has, edits `release.py` in the merge commit itself, and says so:
`Merge branch '...' into develop (bump version to 0.15.0)`.

While the library is at 0.x, read the last rule as **minor** instead: the statement a
reader needs about segmentation is `splitter_version`, which is per contribution and
exact, and reserving 1.0.0 for the release that declares this library's interface stable
says more than spending it on a punctuation rule. Version 0.9.0 (splitter syntax 2) is
the first bump made under this reading. Once 1.0.0 is out, the rule above applies
literally again.

The same applies to `base/release.py` in the **fair-debate-web** repo: the platform
version is recorded in the repos the platform itself opens for live debates. See that
repo's `CLAUDE.md`.

Note the asymmetry, it is deliberate: a *built* repo (a fixture debate rebuilt from its
`source.md`) records only build-time data, never the version of the instance serving it.
Otherwise a deploy of a new web version would rewrite the root commit of every fixture
repo and with it every fingerprint in its chain.

## Splitter syntax version

Contributions carry `splitter_version` in their yaml front matter. It records which
segmentation ruleset produced the `::aN` markers in that file. Do not change
`SENTENCE_SPLITTERS` or the abbreviation heuristics in `key_management.py` without
raising `SPLITTER_SYNTAX_VERSION` and keeping the old behaviour reachable -- segment keys
are the prefix of every answer key, so re-segmenting an existing text does not renumber
it, it breaks every reference into it. `split_text_into_segments()` dispatches on the
number; every version stays a function of its own in `_SPLITTERS_BY_VERSION`.

"Keeping it reachable" is not a matter of good intentions:
`tests/test_splitter_versions.py::TestStoredSegmentationIsReproducible` strips the
markers off every built fixture, segments the text again under the version that
contribution claims, and requires the markers to come back in the same places. A rule
change that would renumber an existing repo fails there, naming the repo it would damage.
Fixtures whose text was written by hand rather than by the splitter are listed and
excused in that file.

A purely additive rule may stay inside the current version instead of opening a new one --
`\~` (2026-09-04) was added to version 2 this way, because no text that already claimed
version 2 contained the sequence, and nothing has been deployed that would state the old
meaning elsewhere. Before the first release a climbing version number costs more
credibility than it buys precision. Whether a change is additive enough for this is **the
user's decision, not the implementer's** -- propose it, do not assume it.

Background: `dev_notes.md`, section "splitter syntax".
