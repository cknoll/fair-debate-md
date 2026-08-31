`builder_demo_source.md` is frozen input for the rendering test in `test_core.py`.

Deliberately tiny and never edited: that test compares rendered markup literally, and it
used to run on the explanatory example debate -- so every edit to that debate's text broke
it. Content meant to be read by users does not belong in a literal assertion.

It replaces `process_content_dir__plain/`, which fed the removed `fdmd
process-content-dir`. The contributions and their keys (`a`, `a3b`, `a3b2a`) are the same;
only the way they are written down changed, from one file per contribution with the anchor
in its name to one file for the whole debate with quoted anchors.
