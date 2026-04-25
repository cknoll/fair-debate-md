"""
Roundtrip test: markdown -> HTML -> markdown -> HTML.

Goal
----
Check whether the MD/HTML conversion chain used in `fair-debate-md`
(python-markdown with `mdx_truly_sane_lists` for MD->HTML, and a
customized `markdownify.MarkdownConverter` for HTML->MD) is
roundtrip-stable for a realistic markdown sample that contains:

  * inline emphasis (nested `_..._` and `**...**`)
  * a multi-level nested unordered list
  * inline code spans inside list items
  * list items that mix direct text with a nested sublist

If the behavior is correct, the HTML produced from the original markdown
and the HTML produced from the round-tripped markdown should be
structurally identical.

Run:

    /media/data2/venvs/venv_pfi_313/bin/python markdownify_roundtrip.py
"""

import os
import types

import markdown
import markdownify as mdf

from fair_debate_md.utils import detect_list_indent


FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "src", "fair_debate_md", "fixtures", "txt1.md"
)

OUTPUT_HTML_PATH = os.path.join(
    os.path.dirname(__file__), "tests", "testdata", "txt1_raw_html.html"
)

with open(FIXTURE_PATH, encoding="utf-8") as fp:
    ORIGINAL_MD = fp.read()


def md_to_html(md_src: str) -> str:
    """MD -> HTML, same configuration as used in the project.

    The nested-list indentation width is detected from the source and
    passed to `mdx_truly_sane_lists` as `nested_indent`, otherwise
    4-space nested lists are not recognized (library default is 2).
    """
    indent_width = detect_list_indent(md_src)
    return markdown.markdown(
        md_src,
        extensions=["mdx_truly_sane_lists"],
        extension_configs={"mdx_truly_sane_lists": {"nested_indent": indent_width}},
    )


def html_to_md(html_src: str) -> str:
    """HTML -> MD, same customized converter as in
    `fair_debate_md.md_handling.MDHandler.markdownify_and_postprocess`
    (minus the project-specific triple-backtick handling)."""
    mdc = mdf.MarkdownConverter(heading_style="ATX", bullets="-")
    mdc.convert_b = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "**"), mdc)
    mdc.convert_em = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "_"), mdc)
    return mdc.convert(html_src)


def _hr(title: str) -> None:
    print("=" * 72)
    print(title)
    print("=" * 72)


def main():
    _hr("Step 0: original markdown")
    print(ORIGINAL_MD)

    html1 = md_to_html(ORIGINAL_MD)
    _hr("Step 1: HTML produced from original markdown (md -> html)")
    print(html1)
    print()

    with open(OUTPUT_HTML_PATH, "w", encoding="utf-8") as fp:
        fp.write(html1)
    print(f"(written to {OUTPUT_HTML_PATH})")
    print()

    md2 = html_to_md(html1)
    _hr("Step 2: markdown produced from that HTML (html -> md)")
    print(md2)

    html2 = md_to_html(md2)
    _hr("Step 3: HTML produced from the round-tripped markdown (md -> html)")
    print(html2)
    print()

    _hr("Result: structural comparison of Step 1 HTML vs. Step 3 HTML")
    if html1 == html2:
        print("OK: roundtrip is structurally stable (identical HTML).")
    else:
        print("MISMATCH: the two HTML outputs differ.")
        print()
        print("--- HTML from original MD ---")
        print(html1)
        print()
        print("--- HTML from round-tripped MD ---")
        print(html2)


if __name__ == "__main__":
    main()
