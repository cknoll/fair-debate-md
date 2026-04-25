"""
Demonstration of a bug / unexpected behavior in `markdownify` (HTML -> Markdown).

Problem
-------
When an <li> element contains direct text followed by a nested <ul>
(without wrapping the text in a <p> tag), `markdownify` fails to correctly
restore the list-nesting level for subsequent sibling <li>s.

Specifically, a sibling <li> that follows the nested <ul> inside the same
parent <ul> is rendered at the *wrong* indent level (too deeply indented),
producing markdown that, when re-parsed, yields a *different* tree than the
original HTML.

Context in `fair-debate-md`
---------------------------
After activating the `mdx_truly_sane_lists` extension of `python-markdown`,
nested lists are emitted without the implicit `<p>` wrapper inside `<li>`s
that have mixed (text + block) content. This triggers the described bug
when the HTML is converted back to markdown via `markdownify`.

The two test cases below contrast:
  * Test 1: HTML without <p>-wrapper  -> WRONG markdown (indent is 4 spaces
                                         instead of 0 for the trailing sibling)
  * Test 2: HTML with    <p>-wrapper  -> correct markdown

Run this file directly:

    /media/data2/venvs/venv_pfi_313/bin/python markdownify_problem.py
"""

import types

import markdownify as mdf


def convert(html: str) -> str:
    """Convert HTML to markdown using the same customized converter as
    used in `fair_debate_md.md_handling.MDHandler.markdownify_and_postprocess`
    (minus the project-specific triple-backtick handling)."""
    mdc = mdf.MarkdownConverter(heading_style="ATX", bullets="-")
    mdc.convert_b = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "**"), mdc)
    mdc.convert_em = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "_"), mdc)
    return mdc.convert(html)


# ---------------------------------------------------------------------------
# Test 1: <li> with direct text + nested <ul>, NO <p> wrapper
# ---------------------------------------------------------------------------
HTML_NO_P_WRAPPER = (
    "<ul>"
    "<li>Item A</li>"
    "<li>Item B<ul>"
    "<li>Nested B1</li>"
    "<li>Nested B2</li>"
    "</ul>"
    "</li>"
    "<li>Item C</li>"
    "</ul>"
)

# Expected (structurally correct) markdown:
#
#     - Item A
#     - Item B
#         - Nested B1
#         - Nested B2
#     - Item C
#
# Observed (wrong) markdown: `Item C` gets indented as if it belonged to the
# nested list, although in the HTML it is a sibling of `Item B` in the outer <ul>.


# ---------------------------------------------------------------------------
# Test 2: same structure, but with <p> wrapper around the direct text
# ---------------------------------------------------------------------------
HTML_WITH_P_WRAPPER = (
    "<ul>"
    "<li>Item A</li>"
    "<li><p>Item B</p><ul>"
    "<li>Nested B1</li>"
    "<li>Nested B2</li>"
    "</ul>"
    "</li>"
    "<li>Item C</li>"
    "</ul>"
)

# Expected and observed markdown match:
#
#     - Item A
#     - Item B
#
#         - Nested B1
#         - Nested B2
#     - Item C


def main():
    print("=" * 72)
    print("Test 1: <li> with direct text + nested <ul>  (NO <p>-wrapper)")
    print("=" * 72)
    print("HTML input:")
    print(HTML_NO_P_WRAPPER)
    print()
    print("markdownify output:")
    print(convert(HTML_NO_P_WRAPPER))
    print()
    print("-> BUG: 'Item C' is indented at the nested level (4 spaces),")
    print("        although in the HTML it is a sibling of 'Item B' in the outer <ul>.")
    print()

    print("=" * 72)
    print("Test 2: same structure but WITH <p>-wrapper around direct text")
    print("=" * 72)
    print("HTML input:")
    print(HTML_WITH_P_WRAPPER)
    print()
    print("markdownify output:")
    print(convert(HTML_WITH_P_WRAPPER))
    print()
    print("-> OK: 'Item C' is at the correct outer-list level.")


if __name__ == "__main__":
    main()
