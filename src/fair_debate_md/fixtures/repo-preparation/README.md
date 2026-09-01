This directory contains the sources of the fixture debates (plain md, without segment
keys) and the tools that turn them into valid fair-debate content repos. Rationale: the
content stays editable as ordinary prose, and the debate -- keys, commits, patches -- is a
build artifact of it.

Every build writes its patches to `../repos/<debate-key>/patches_01/`, which is where
`fdmd unpack-repos` picks them up. Updating a fixture therefore means: run the build,
commit the changed patches, and re-run `fdmd unpack-repos ./content_repos` in the web app.


## `fdmd build-debate-repo` -- one file in, one debate repo out

The general tool: it takes a debate written as a **single markdown file** and builds the
repo (and the patches) from it.

```bash
fdmd build-debate-repo <source.md>                  # patches -> ./<debate_key>/patches_01
fdmd build-debate-repo <source.md> --into-fixtures  # patches -> the fixture dir here
fdmd build-debate-repo <source.md> --repo-into <dir> --patches-into <dir>
```

Updating one of the fixture debates below is the `--into-fixtures` case: it writes into
the fixture directory of the *installed* fair_debate_md, which with an editable install is
this checkout. Implementation: `fair_debate_md/debate_builder.py`, tests in
`tests/test_debate_builder.py`.

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
- `d01-erklaerende-beispieldebatte__plain/source.md` -- its german counterpart. Same
  structure and the same anchor points, so the two produce almost the same contribution
  keys; only the integrity contribution has more segments in german, which moves `a27b38c`
  to `a27b41c`. Its wording follows the terminology of the german UI in `base/i18n/de.toml`
  rather than the english source -- a *debate* is a "Diskussion" there, and the interface
  addresses the reader informally ("du"), so a translation that said "Debatte" and "Sie"
  would contradict the page it sits on.

Until 2026-08 that fixture was built by `fdmd process-content-dir` from one file per
contribution, with the anchor encoded in the file name (`b/a14b.md` = segment 14 of `a`):
every inserted sentence forced a rename cascade, only two parties were possible, the
deployment had to special-case the debate, and the patches here had silently fallen behind
the sources.


## Debate-specific build scripts

`d31-ice-cream__plain` is built by `build_d31_ice_cream.py`, because that fixture needs a
nesting structure and per-party commits which the old `process-content-dir` did not
provide. See the module docstring there.

`d33-wachstum-klimaschutz__plain` follows the same pattern (`build_d33_wachstum_klimaschutz.py`).
It is the only German-language fixture and the only one with real argumentative content: a
reconstruction of a radio debate on economic growth vs. climate protection. Its anchors are
still segment indices, so its build script prints, for every contribution, the sentence it
answers -- editing a plain source can shift the indices its children are anchored to.

`d31` and `d33` could move to `fdmd build-debate-repo` if their sources were
converted to the single-file format, which would remove their scripts entirely.
`d32-overlapping-refs` could not: it exists to exercise segment ranges (`a3-6b`) and word
ranges (`a7_7-12f`), and an `answers=` quote resolves to exactly one segment. The source
format would have to grow a way of spelling a range first.


## Removed: `fdmd process-content-dir`

Gone since 2026-08-31. It built a repo from a directory of plain files whose *names* were
the anchors (`b/a14b.md` answers segment 14 of `a`), which forced a rename cascade on every
inserted sentence and could only alternate between two parties -- it derived the author
from the nesting level. Its last user, `d00`, moved to `build-debate-repo` in 2026-08, and
after that the only thing it still built was its own test.

`build-debate-repo` covers what it did, minus the file-name anchors. A one-off throwaway
repo is a source file with a front matter header and one marker comment.
