# fair-debate-md

## Version discipline

`src/fair_debate_md/release.py` holds `__version__`, and **it has to be maintained
deliberately from now on** -- it is no longer a cosmetic number.

Reason: the version is written into the content repos this library produces
(`REPO_INFO.yaml`, see `repo_handling.py`), and those repos are handed out to readers as
git clones and bundles. A repo therefore states which software segmented its text and
built its history. That statement is only worth something if the number actually moves
when the behaviour does.

Bump it in the same commit as the change that earns it:

- **patch** -- fixes that cannot change how existing text is segmented or how a repo is
  laid out;
- **minor** -- new capability, new field in the repo metadata, anything a reader of an
  old repo would notice as "this was made by something newer";
- **major** -- a change to the splitter syntax or to the repo layout, i.e. something that
  makes an old repo's content and a new build of the same source disagree.

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
it, it breaks every reference into it. Background and the open items: `dev_notes.md`,
section "splitter syntax".
