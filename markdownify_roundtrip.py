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

import types

import markdown
import markdownify as mdf


ORIGINAL_MD = """\
Ut _quiquia **eius** dolorem_ voluptatem. **Adipisci sit adipisci non est**.

- Ipsum velit adipisci
- Adipisci est magnam etincidunt sed:
    - `some code ` Sed etincidunt etincidunt
    - sit aliquam eius quiquia.
        - Ut etincidunt magnam ut etincidunt `some code`
        - quiquia quisquam porro.
    - Ut modi dolor est labore velit non.
"""


def md_to_html(md_src: str) -> str:
    """MD -> HTML, same configuration as used in the project."""
    return markdown.markdown(md_src, extensions=["mdx_truly_sane_lists"])


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

    # the result html1 is already obviously wrong. nested list is not recognized. we can stop here for now.
    return

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
