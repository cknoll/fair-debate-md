This directory contains the sources of the fixture debates (plain md, without segment
keys) and the tools that turn them into valid fair-debate content repos. Rationale: the
content stays editable as ordinary prose, and the debate -- keys, commits, patches -- is a
build artifact of it.

Every build writes its patches to `../repos/<debate-key>/patches_01/`, which is where
`fdmd unpack-repos` picks them up. Updating a fixture therefore means: run the build,
commit the changed patches, and re-run `fdmd unpack-repos ./content_repos` in the web app.


## `build_debate_repo.py` -- one file in, one debate repo out

The general tool: it takes a debate written as a **single markdown file** and builds the
repo (and the patches) from it.

```bash
python build_debate_repo.py <source.md>
python build_debate_repo.py <source.md> --patches-into <dir> --repo-into <dir>
```

The source carries its own metadata in a yaml front matter header (`debate_key`, the
`parties` map from role-token to author name, the commit dates), and separates the
contributions by marker comments:

```
<!-- !!== label=b-intro party=b answers="`b` is the first party to answer" ==== -->
```

The markers are html comments, so the source stays valid markdown and can be written, read
and previewed as one document. `answers` quotes the answered text literally; the build
resolves the quote against the segments of everything built so far and aborts, listing the
candidates, if it matches none or several. Rewording a contribution therefore does not move
the anchors of its answers. The order of the contributions in the file is the chronology of
the debate. See the module docstring for the full format.

Debates built this way, one directory per debate -- a translation is a debate of its own,
with its own `dNN` key, not a variant of another one:

- `d00-explanatory-example-debate__plain/source.md` -- the debate a first-time visitor is
  pointed to (english).

Until 2026-08 that fixture was built by `fdmd process-content-dir` from one file per
contribution, with the anchor encoded in the file name (`b/a14b.md` = segment 14 of `a`):
every inserted sentence forced a rename cascade, only two parties were possible, the
deployment had to special-case the debate, and the patches here had silently fallen behind
the sources.


## Debate-specific build scripts

`d31-ice-cream__plain` is built by `build_d31_ice_cream.py`, because that fixture needs a
nesting structure and per-party commits which `process-content-dir` did not provide. See
the module docstring there.

`d33-wachstum-klimaschutz__plain` follows the same pattern (`build_d33_wachstum_klimaschutz.py`).
It is the only German-language fixture and the only one with real argumentative content: a
reconstruction of a radio debate on economic growth vs. climate protection. Its anchors are
still segment indices, so its build script prints, for every contribution, the sentence it
answers -- editing a plain source can shift the indices its children are anchored to. Both
could move to `build_debate_repo.py` if their sources were converted to the single-file
format.


## `fdmd process-content-dir`

`fdmd process-content-dir <plain-dir> <target-dir> [--patches]` still exists for a quick
throwaway repo from a directory of plain files whose names are keys. Note that without
`--patches` it only writes the keyed .md files: the git repo is created by the patch step,
not by the conversion.
