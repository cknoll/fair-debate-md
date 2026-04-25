import unittest
import os
from textwrap import dedent as twdd

from bs4 import BeautifulSoup
import pytest

from ipydex import activate_ips_on_exception

import fair_debate_md as fdmd

activate_ips_on_exception()
pjoin = os.path.join

TESTDATA_DIR = pjoin(os.path.abspath(os.path.dirname(__file__)), "testdata")
FIXTURE_DIR = fdmd.fixtures.path
TESTDATA1 = pjoin(FIXTURE_DIR, "txt1.md")


def remove_trailing_spaces(txt):
    return "\n".join([line.rstrip(" ") for line in txt.split("\n")])


class TestMDHandling(unittest.TestCase):
    """
    Tests focused on markdown-level handling (proto-keys, real keys, segmented html).

    These tests were refactored out of `test_core.py` to allow working on
    markdown-handling independently from the rest of the code.
    """

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

        # small part for easier debugging:

        N = 148

        txt1 = self.txt1[:N]

        mdp = fdmd.MDProcessor(txt1)
        md2 = mdp.add_proto_keys_to_md(txt1, prefix="k", early_placeholder_replacement=True).rstrip()

        expected_result_fpath = TESTDATA1.replace(".md", "_with_proto_keys.md").replace(
            FIXTURE_DIR, TESTDATA_DIR
        )

        with open(expected_result_fpath, "r") as fp:
            md2_expected = fp.read()

        N2 = 164
        md2_ex = md2_expected[:N2]

        self.assertEqual(md2, md2_ex)


        # now the full content
        mdp = fdmd.MDProcessor(self.txt1)
        md2 = mdp.add_proto_keys_to_md(self.txt1, prefix="k", early_placeholder_replacement=True)
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

    # mark as known to fail
    @pytest.mark.xfail
    def test_031__get_html_with_segments_bug(self):


        md_src1_a = twdd("""
        - level 0
            - level 1
        """)

        md_src1_b = twdd("""
        - level 0
          - level 1
        """)

        r1_a = fdmd.MDProcessor(md_src1_a).add_proto_keys_to_md()
        r1_b = fdmd.MDProcessor(md_src1_b).add_proto_keys_to_md()

        self.assertEqual(r1_a, r1_b)

        md_src1_a = twdd("""
        text

        - level 0
            - level 1
                - level 2
            - level 1
        - level 0
        """)

        md_src1_b = twdd("""
        text

        - level 0
          - level 1
            - level 2
          - level 1
        - level 0
        """)

        r1_a = fdmd.MDProcessor(md_src1_a).add_proto_keys_to_md()
        r1_b = fdmd.MDProcessor(md_src1_b).add_proto_keys_to_md()

        self.assertEqual(r1_a, r1_b)


    def test_030__get_html_with_segments(self):

        # test empty string
        _, res = fdmd.core._convert_plain_md_to_segmented_html("")
        self.assertEqual(res, "")

        # test simple string
        _, res = fdmd.core._convert_plain_md_to_segmented_html("foo bar")
        res_expected = '<div class="p_level0"><span class="segment" id="a1"> foo bar</span></div>'

        # we do conversion twice because the backend currently does so
        # (to handle inline code-tags with _strip_me_ attribute)
        res_expected = str(BeautifulSoup(res_expected, "html.parser").prettify())
        res_expected = str(BeautifulSoup(res_expected, "html.parser"))
        self.assertEqual(res, res_expected)

        # test full file
        md_with_real_keys, res = fdmd.core._convert_plain_md_to_segmented_html(self.txt1)

        if 0:
            self.save_debug_result(res, suffix="_pretty.md")

        expected_result_fpath = pjoin(TESTDATA_DIR, "txt1_segmented_html.html")
        with open(expected_result_fpath, "r") as fp:
            res_expected = fp.read()

        # IPS(-1) # TODO: fixme
        self.assertEqual(res, res_expected)


if __name__ == "__main__":
    unittest.main()
