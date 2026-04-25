# Developer Documentation

## Behavioral change: `mdx_truly_sane_lists` extension (2026-04)

### Context

The `python-markdown` library is used to convert markdown to html as an
intermediate step in the proto-key pipeline (see `md_handling.py`,
`MDHandler._md_to_html`). Previously no extensions were enabled. In order to
get reliable handling of nested lists with configurable indent width (which
upcoming `markdownify` versions will require), the
[`mdx_truly_sane_lists`](https://pypi.org/project/mdx-truly-sane-lists/)
extension was activated.

### Effects on downstream HTML shape

Activating the extension changes the html output for list items in two
noteworthy ways. These changes propagate through the whole pipeline and thus
affect the final segmented html that downstream consumers (CSS/JS of the web
app) see.

#### 1. No `<p>` wrapper inside `<li>` with mixed content

Old behavior (without extension):

```html
<li>
  <p>sit aliquam eius quiquia.</p>
  <ul>
    <li>nested item</li>
  </ul>
</li>
```

New behavior (with extension):

```html
<li>sit aliquam eius quiquia.<ul>
  <li>nested item</li>
</ul>
</li>
```

As a consequence, the later pipeline step `SpanAdder._replace_p_with_div`
(which rewrites `<p>` → `<div class="p_level{n}">`) no longer produces a
wrapper around the direct text of such `<li>`s. The segment `<span>` is now a
direct child of `<li>` instead of being wrapped in `<div class="p_level0">`.

**Example** (final segmented html, relevant excerpt):

Old:
```html
<li>
  <div class="p_level0">
    <span class="segment" id="a9">sit aliquam eius quiquia.</span>
  </div>
  <ul>…</ul>
</li>
```

New:
```html
<li>
  <span class="segment" id="a9">sit aliquam eius quiquia.</span>
  <ul>…</ul>
</li>
```

Note: the `<div class="p_level0">` wrapper *still* appears for `<li>`s whose
content was originally produced as a `<p>` (e.g. when preceded by a blank
line in the markdown source). The wrapper shape is therefore no longer
guaranteed for every `<li>`-direct text.

#### 2. Stricter interpretation of list nesting

A markdown fragment like

```markdown
- level 0
    - level 1
        - level 2

    - level 1 (continuation after blank line)
```

was previously (without the extension) interpreted as *one* outer list; the
"continuation after blank line" item was attached to the inner (deepest) list
in the html structure. With the extension, the blank line + re-indentation is
treated more strictly: the trailing item starts a *new* `<ul>` at the outer
level.

This is considered the more correct interpretation (it matches what the
indentation visually suggests), but downstream consumers that relied on the
old (deeper-nested) structure need to be aware of the change.

### Test data

The expected html fixture `tests/testdata/txt1_segmented_html.html` was
regenerated to reflect the new extension-enabled output. If a downstream
consumer expected the old shape (e.g. a guaranteed `<div class="p_level0">`
around every `<li>`-direct text), the consumer logic needs to be adapted, or
an additional html-rewriting step must be re-introduced in `SpanAdder`.

See also:
- `src/fair_debate_md/md_handling.py` (extension activation)
- `src/fair_debate_md/core.py::SpanAdder._replace_p_with_div` (p → div rewrite)
- `tests/test_md_handling.py::TestMDHandling::test_030__get_html_with_segments`
