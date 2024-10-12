import unittest
import os
from textwrap import dedent as twdd
from ipydex import IPS, activate_ips_on_exception

import fair_debate_md as fdmd

from fair_debate_md.utils import compare_strings

activate_ips_on_exception()
pjoin = os.path.join

TESTDATA_DIR = pjoin(os.path.abspath(os.path.dirname(__file__)), "testdata")
FIXTURE_DIR = fdmd.fixtures.path
TESTDATA1 = pjoin(FIXTURE_DIR, "txt1.md")


class TestCases1(unittest.TestCase):
    def setUp(self):
        self.key_prefix = "::a"
        with open(TESTDATA1) as fp:
            self.txt1 = fp.read()
        return

    def save_debug_result(self, result, suffix=".md"):
        # useful if result changes or for debugging
        debug_fpath = TESTDATA1.replace(".md", f"_debug{suffix}")
        with open(debug_fpath, "w") as fp:
            fp.write(result)

    def test_010__add_keys_to_md(self):
        md2 = fdmd.add_proto_keys_to_md(self.txt1, prefix="k")
        expected_result_fpath = TESTDATA1.replace(".md", "_with_proto_keys.md").replace(
            FIXTURE_DIR, TESTDATA_DIR
        )

        if 0:
            self.save_debug_result(md2)
            return

        with open(expected_result_fpath, "r") as fp:
            md2_expected = fp.read()

        md2 = remove_trailing_spaces(md2)
        self.assertEqual(md2, md2_expected)

    def test_011__process_p_tag(self):
        html_src = "<p>Ut <em>quiquia <strong>eius</strong> dolorem</em> voluptatem. Adipisci sit adipisci non est.</p>"
        pka = fdmd.ProtoKeyAdder(html_src, prefix="k")
        pka.add_proto_keys_to_html()
        res = str(pka.soup)
        expected_res = (
            "<p>::k Ut <em>quiquia <strong>eius</strong> dolorem</em> voluptatem."
            " ::k  Adipisci sit adipisci non est.</p>"
        )
        self.assertEqual(res, expected_res)

    def test_021__add_spans(self):
        tag1 = "<h1>::a1 Ipsum non ut est.</h1>"

        sa = fdmd.SpanAdder(tag1, key_prefix=self.key_prefix)
        res = sa.add_spans_for_keys()
        res_expected = '<h1><span class="segment" id="a1"> Ipsum non ut est.</span></h1>'
        self.assertEqual(res, res_expected)

    def test_022__add_spans(self):
        tag2 = (
            "<p>::a2 Ut <em>quiquia <strong>eius</strong> dolorem</em> voluptatem."
            " ::a3 <strong>Adipisci sit adipisci non est</strong>.</p>"
        )

        sa = fdmd.SpanAdder(tag2, key_prefix=self.key_prefix)
        res = sa.add_spans_for_keys()

        res_expected = (
            '<p><span class="segment" id="a2"> Ut <em>quiquia <strong>eius</strong>'
            " dolorem</em> voluptatem.</span>"
            '<span class="segment" id="a3"> <strong>Adipisci sit adipisci non est</strong>.</span></p>'
        )

        self.assertEqual(res, res_expected)

    def test_023__add_spans(self):
        tag3 = (
            "<p>::a2 Ut <em>quiquia <strong>eius</strong> dolorem</em> voluptatem."
            " ::a3 <strong>Adipisci sit adipisci non est</strong>."
            " ::a4 Dolor etincidunt neque sed tempora porro quiquia."
            " ::a5 Porro velit non consectetur numquam velit.</p>"
        )

        sa = fdmd.SpanAdder(tag3, key_prefix=self.key_prefix)
        res = sa.add_spans_for_keys()
        res_expected = (
            '<p><span class="segment" id="a2"> Ut <em>quiquia <strong>eius</strong>'
            " dolorem</em> voluptatem.</span>"
            '<span class="segment" id="a3"> <strong>Adipisci sit adipisci non est</strong>.</span>'
            '<span class="segment" id="a4"> Dolor etincidunt neque sed tempora porro quiquia.</span>'
            '<span class="segment" id="a5"> Porro velit non consectetur numquam velit.</span></p>'
        )
        self.assertEqual(res, res_expected)

    def test_024__add_spans(self):
        html_src = twdd("""
        <ul>
        <li>::a6 Ipsum velit adipisci</li>
        <li>
        <p>::a7 Adipisci est magnam etincidunt sed:</p>
        <ul>
        <li>::a8 <code>some code</code> Sed etincidunt etincidunt</li>
        <li>
        <p>::a9 sit aliquam eius quiquia.</p>
        <ul>
        <li>::a10 Ut etincidunt magnam ut etincidunt <code>some code</code></li>
        <li>::a11 quiquia quisquam porro.<ul>
        <li>::a12 Ut modi dolor est labore velit non.</li>
        </ul>
        </li>
        </ul>
        </li>
        </ul>
        </li>
        </ul>
        """)

        res_expected = twdd("""
        <ul>
        <li><span class="segment" id="a6"> Ipsum velit adipisci</span></li>
        <li>
        <p><span class="segment" id="a7"> Adipisci est magnam etincidunt sed:</span></p>
        <ul>
        <li><span class="segment" id="a8"> <code>some code</code> Sed etincidunt etincidunt</span></li>
        <li>
        <p><span class="segment" id="a9"> sit aliquam eius quiquia.</span></p>
        <ul>
        <li><span class="segment" id="a10"> Ut etincidunt magnam ut etincidunt <code>some code</code></span></li>
        <li><span class="segment" id="a11"> quiquia quisquam porro.</span><ul>
        <li><span class="segment" id="a12"> Ut modi dolor est labore velit non.</span></li>
        </ul>
        </li>
        </ul>
        </li>
        </ul>
        </li>
        </ul>
        """)

        sa = fdmd.SpanAdder(html_src, key_prefix=self.key_prefix)
        res = sa.add_spans_for_keys()
        self.assertEqual(res, res_expected)

    def test_030__get_html_with_segments(self):

        # test empty string
        res = fdmd.convert_plain_md_to_segmented_html("")
        self.assertEqual(res, "")

        # test simple string
        res = fdmd.convert_plain_md_to_segmented_html("foo bar")
        res_expected = '<p><span class="segment" id="a1"> foo bar</span></p>'
        self.assertEqual(res, res_expected)

        # test full file
        res = fdmd.convert_plain_md_to_segmented_html(self.txt1)

        if 0:
            self.save_debug_result(res, suffix=".html")

        expected_result_fpath = pjoin(TESTDATA_DIR, "txt1_segmented_html.html")
        with open(expected_result_fpath, "r") as fp:
            res_expected = fp.read()

        self.assertEqual(res, res_expected)




def remove_trailing_spaces(txt):
    return "\n".join([line.rstrip(" ") for line in txt.split("\n")])
