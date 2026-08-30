Frozen input for the `process-content-dir` tests in `test_core.py`.

Deliberately tiny and never edited: those tests compare a directory tree and rendered
markup literally, and they used to run on the explanatory example debate -- so every edit
to that debate's text broke them (see the TODO they carried). Content that is meant to be
read by users does not belong in a literal assertion.
