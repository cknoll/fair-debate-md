# i53 Fix Report: Nested Markdown List Roundtrip

## Problem

Issue i53 reported that markdown lists (`- item`, also nested) were not being rendered as
`<ul>/<li>` elements in contributions. A secondary concern was that the `md -> html -> md`
roundtrip (the foundation of the key-assignment system) might be destabilized by activating
the `mdx_truly_sane_lists` extension.

The known root cause hypothesis was: `mdx_truly_sane_lists` omits the `<p>` wrapper inside
mixed-content `<li>` elements (text + nested `<ul>`), causing `markdownify` to mis-indent
sibling `<li>` elements during html->md conversion.

## Investigation

### markdownify_problem.py

The script at repo root (`markdownify_problem.py`) demonstrates the hypothetical bug with a
manually constructed HTML snippet. However, when run with markdownify 1.2.2 (the currently
pinned version), Test 1 (no `<p>` wrapper) produces correct indentation. The static "BUG"
comment in the script reflects behavior from an older markdownify version.

### Intermediate HTML inspection

For both flat lists and nested lists (with a sibling `<li>` after the nested `<ul>`):
- `_md_to_html` produces correct `<ul>/<li>` markup with the `mdx_truly_sane_lists` extension.
- The roundtrip `md -> html -> md -> html` yields identical HTML (HTML1 == HTML2).
- The extension is active and contributes to correct parsing of various indentation styles.

### J4-G5 symptom

Not reproducible with current setup. Running `_md_to_html` on a realistic nested list:

```
- Punkt A
- Punkt B
    - Unterebene
- Punkt C
```

produces well-formed `<ul>/<li>` markup with `<ul>` nested inside `<li>Punkt B</li>` and
`<li>Punkt C</li>` correctly at the top level. Both `HAS UL: True` and `HAS LI: True`.

## Resolution

No changes to the rendering pipeline were required. The roundtrip is stable. The
`mdx_truly_sane_lists` extension remains active (`use_extensions = True` in `_md_to_html`).

Four regression tests were added to `tests/test_md_handling.py` as specification guards:
- `test_310__flat_list_html_structure`: flat list produces `<ul>/<li>`
- `test_320__nested_list_html_structure`: nested list produces correct HTML tree
- `test_330__nested_list_roundtrip_idempotency`: roundtrip is stable for nested lists
- `test_340__keys_assigned_for_list_contribution`: proto-keys assigned correctly in list contributions

## Changed Files

- `tests/test_md_handling.py`: 4 regression tests added (commit 5e61e5d)
- `src/fair_debate_md/md_handling.py`: TODO-AIDER block updated in `_md_to_html`
- `i53_fix_report.md`: this file

## Suite Status

61 tests passed, 0 failed.
