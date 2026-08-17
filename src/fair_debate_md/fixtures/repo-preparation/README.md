This directory contains plain md files which can be converted into a valid fair-debate-repo e.g. by `fdmd process-content-dir ./d00-explanatory-example-debate__plain ./d00-explanatory-example-debate`.

Rationale: This allows to easily edit the content of the explanatory example debate and then convert it into a debate consisting of comitted contributions.

`d31-ice-cream__plain` works the same way but is built by its own script,
`build_d31_ice_cream.py` (`python build_d31_ice_cream.py`), because that fixture needs
a nesting structure and per-party commits which `process-content-dir` does not provide.
See the module docstring there.

`d33-wachstum-klimaschutz__plain` follows the same pattern (`build_d33_wachstum_klimaschutz.py`).
It is the only German-language fixture and the only one with real argumentative content: a
reconstruction of a radio debate on economic growth vs. climate protection. Its build script
also prints, for every contribution, the sentence it answers -- useful because editing a plain
source can shift the segment indices its children are anchored to.
