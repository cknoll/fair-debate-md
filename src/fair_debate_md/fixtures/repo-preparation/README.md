This directory contains plain md files (without segment keys) and the scripts that turn
them into valid fair-debate content repos. Rationale: the content of a fixture debate
stays editable as ordinary prose, and the debate -- keys, commits, patches -- is a build
artifact of it.

Every build script writes its patches to `../repos/<debate-key>/patches_01/`, which is
where `fdmd unpack-repos` picks them up. Rebuilding a fixture therefore means: run its
script, commit the changed patches, and re-run `fdmd unpack-repos ./content_repos` in the
web app.

`d00-explanatory-example-debate__plain` -- the debate a first-time visitor is pointed to.
Built by `build_d00_explanatory_example.py`; sources live under `<lang>/<party>/<label>.md`,
currently `en` only. Anchors are declared in the script as **quotes** of the answered text
rather than as segment indices, so rewording a contribution does not move the anchors of
its answers, and a quote that no longer matches aborts the build. Until 2026-08 this
fixture was built with `fdmd process-content-dir`, whose file-name anchors (`b/a14b.md`)
forced a rename cascade after every edit and allowed two parties at most; the deployment
had to special-case it, and its patches here had silently fallen behind the plain sources.

`d31-ice-cream__plain` is built by `build_d31_ice_cream.py`, because that fixture needs a
nesting structure and per-party commits which `process-content-dir` does not provide. See
the module docstring there.

`d33-wachstum-klimaschutz__plain` follows the same pattern (`build_d33_wachstum_klimaschutz.py`).
It is the only German-language fixture and the only one with real argumentative content: a
reconstruction of a radio debate on economic growth vs. climate protection. Its anchors are
still segment indices, so its build script prints, for every contribution, the sentence it
answers -- editing a plain source can shift the indices its children are anchored to.

`fdmd process-content-dir <plain-dir> <target-dir> [--patches]` still exists for a quick
throwaway repo from a directory of plain files. Note that without `--patches` it only
writes the keyed .md files: the git repo is created by the patch step, not by the
conversion.
