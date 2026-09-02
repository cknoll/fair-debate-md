import unittest
import os
from textwrap import dedent as twdd

from bs4 import BeautifulSoup
import pytest

from ipydex import activate_ips_on_exception

import fair_debate_md as fdmd
from fair_debate_md.key_management import split_text_into_segments

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

        N2 = 163
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


    # -------------------------------------------------------------------------
    # fine-grained tests on intermediate pipeline results
    # -------------------------------------------------------------------------

    def test_100__preprocess_code_blocks(self):
        """Triple-backtick code blocks are replaced by placeholder code tags."""
        md_src = "some text\n```foo bar```\nmore text"
        mdp = fdmd.MDProcessor(md_src)
        res = mdp._preprocess_code_blocks(md_src)

        # a placeholder code tag was inserted
        self.assertIn('<code class="triple_backticks">', res)
        self.assertIn("</code>", res)
        # the original content is no longer in the output
        self.assertNotIn("foo bar", res)
        # but stored in the internal dict
        self.assertEqual(list(mdp._code_element_contents.values()), ["foo bar"])

    def test_110__md_to_html_simple_list(self):
        """Simple markdown list is converted to <ul>/<li> html."""
        md_src = "- item a\n- item b\n"
        mdp = fdmd.MDProcessor(md_src)
        html = mdp._md_to_html(md_src)
        self.assertIn("<ul>", html)
        self.assertIn("<li>item a</li>", html)
        self.assertIn("<li>item b</li>", html)

    def test_120__add_proto_keys_to_html_simple_sentence(self):
        """A single sentence in a <p> tag gets exactly one proto-key prepended."""
        html_src = "<p>Hello world.</p>"
        mdp = fdmd.MDProcessor("")
        res = mdp._add_proto_keys_to_html(html_src, prefix="k")
        # proto-key appears at the start of the paragraph content
        self.assertIn("::k", res)
        # exactly one proto-key (single sentence, no trailing key after final period)
        self.assertEqual(res.count("::k"), 1)

    def test_130__proto_key_roundtrip_single_sentence(self):
        """Round-trip md -> md-with-proto-keys works for a one-liner."""
        md_src = "Hello world.\n"
        mdp = fdmd.MDProcessor(md_src)
        res = mdp.add_proto_keys_to_md(md_src, prefix="k")
        self.assertIn("::k", res)
        self.assertIn("Hello world.", res)
        # only one proto-key for a single sentence
        self.assertEqual(res.count("::k"), 1)

    def test_140__abbreviations_are_not_split(self):
        """Abbreviations like `i.e.`, `e.g.`, `w.r.t.`, `bspw.` must not trigger segment splits."""
        cases = [
            ("See i.e. this example.", 1),
            ("See e.g. this example.", 1),
            ("See w.r.t. this example.", 1),
            ("Siehe bspw. dieses Beispiel.", 1),
        ]
        for md_src, expected_count in cases:
            with self.subTest(md_src=md_src):
                mdp = fdmd.MDProcessor(md_src)
                res = mdp.add_proto_keys_to_md(md_src, prefix="k")
                self.assertEqual(
                    res.count("::k"), expected_count,
                    f"unexpected proto-key count for: {md_src!r}\nresult: {res!r}",
                )

    def test_160__li_with_sentence_and_nested_list(self):
        """An <li> whose text ends with '.' directly followed by a nested <ul>
        should get exactly one leading proto-key (no trailing one).

        This reproduces the behavioral change introduced by the
        `mdx_truly_sane_lists` extension: there the <li> contains the text
        directly (not wrapped in <p>), followed by a nested <ul>.
        """
        html_src = '<li>sit aliquam eius quiquia.<ul><li>nested item.</li></ul></li>'
        mdp = fdmd.MDProcessor("")
        res = mdp._add_proto_keys_to_html(html_src, prefix="k")
        # should be: one key before "sit", one key before "nested item"
        self.assertEqual(
            res.count("::k"), 2,
            f"unexpected proto-key count\nresult: {res!r}",
        )

    # -------------------------------------------------------------------------
    # tests for the new pure segmentation function
    # -------------------------------------------------------------------------

    def test_200__split_text_empty(self):
        self.assertEqual(split_text_into_segments(""), [])

    def test_201__split_text_single_sentence(self):
        self.assertEqual(split_text_into_segments("Hello world."), ["Hello world."])

    def test_202__split_text_two_sentences(self):
        res = split_text_into_segments("First part. Second part.")
        self.assertEqual(res, ["First part.", " Second part."])

    def test_203__split_text_all_splitters(self):
        for splitter in [".", "!", "?", ":"]:
            with self.subTest(splitter=splitter):
                res = split_text_into_segments(f"a{splitter} b.")
                self.assertEqual(res, [f"a{splitter}", " b."])

    def test_204__split_text_abbreviations(self):
        cases = [
            "See i.e. this example.",
            "See e.g. this example.",
            "See w.r.t. this example.",
            "Siehe bspw. dieses Beispiel.",
        ]
        for text in cases:
            with self.subTest(text=text):
                res = split_text_into_segments(text)
                self.assertEqual(res, [text])

    def test_205__split_text_version_numbers(self):
        res = split_text_into_segments("Uses v12.3 here.")
        self.assertEqual(res, ["Uses v12.3 here."])

    def test_206__split_text_dots_between_digits(self):
        # A dot between digits groups them; splitting it tore "100.000" into
        # "100." and "000 ...", which silently cut a segment in half and made
        # every german thousands separator unusable in a debate source.
        keep_together = [
            "Der Krieg forderte 100.000 Tote.",
            "Das sind 1.234.567 Menschen.",
            "Pi ist etwa 3.14 gross.",
            "Am 24.12.2026 war es soweit.",
        ]
        for text in keep_together:
            with self.subTest(text=text):
                self.assertEqual(split_text_into_segments(text), [text])

        # A sentence really ending in a digit is where the two rulesets differ. Under
        # version 1 the whitespace after the dot was the only thing telling it apart from
        # "100.000", so it split. Version 2 does not split after a digit at all --
        # ordinals ("15. August") are far more common -- and asks for the marker instead.
        text = "Es waren 2022. 500 Leute kamen."
        self.assertEqual(
            split_text_into_segments(text, splitter_version=1),
            ["Es waren 2022.", " 500 Leute kamen."],
        )
        self.assertEqual(split_text_into_segments(text, splitter_version=2), [text])
        marked = "Es waren 2022\\@. 500 Leute kamen."
        self.assertEqual(
            split_text_into_segments(marked, splitter_version=2),
            ["Es waren 2022\\@.", " 500 Leute kamen."],
        )

    def test_207__split_text_abbreviations_extended(self):
        # strong abbreviations (never split), including spaced variants
        cases = [
            "See e. g. this example.",
            "Siehe z.B. dieses Beispiel.",
            "Siehe z. B. dieses Beispiel.",
            "Das gilt, d.h. es stimmt.",
            "Das gilt, d. h. es stimmt.",
            "Es kamen u.a. viele Leute.",
            "Es waren ca. 50 Leute.",
            "Das gilt i.d.R. immer.",
            "Das gilt i. d. R. immer.",
            "Siehe Nr. 5 der Liste.",
            "Rund 3 Mio. Menschen kamen.",
            "A vs. B is the question.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(split_text_into_segments(text), [text])

    def test_208__split_text_weak_abbreviations(self):
        # weak abbreviations: no split if the sentence continues (lowercase),
        # but a split if a new sentence starts (uppercase)
        continuing = [
            "Wir haben Äpfel usw. im Angebot.",
            "We have apples etc. in stock.",
            "Es gab Musik u.v.m. an dem Abend.",
        ]
        for text in continuing:
            with self.subTest(text=text):
                self.assertEqual(split_text_into_segments(text), [text])

        splitting = [
            ("Wir haben Äpfel usw. Der Rest folgt.", ["Wir haben Äpfel usw.", " Der Rest folgt."]),
            ("We have apples etc. Next sentence.", ["We have apples etc.", " Next sentence."]),
        ]
        for text, expected in splitting:
            with self.subTest(text=text):
                self.assertEqual(split_text_into_segments(text), expected)

    def test_209__split_text_abbreviation_word_boundary(self):
        # words that merely *end* like an abbreviation must still split
        # ("africa." vs "ca.", "Absatz." vs "z.")
        cases = [
            ("We visited africa. Next sentence.", ["We visited africa.", " Next sentence."]),
            ("Das steht im Absatz. Bald mehr dazu.", ["Das steht im Absatz.", " Bald mehr dazu."]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(split_text_into_segments(text), expected)

    def test_210__split_text_abbreviation_sentence_case(self):
        # sentence-case variants at the beginning of a sentence
        cases = [
            "Vgl. hierzu Abschnitt 3.",
            "Bspw. dieses Beispiel zeigt es.",
            "Ca. 50 Leute kamen.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(split_text_into_segments(text), [text])

    def test_206__split_text_concatenation_is_identity(self):
        texts = [
            "Hello world.",
            "First. Second. Third.",
            "Question? Answer! Done.",
            "See i.e. this, e.g. that.",
            "",
            "no terminator",
        ]
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual("".join(split_text_into_segments(text)), text)

    def test_150__sentence_splitters(self):
        """Each of the sentence splitters `.`, `!`, `?`, `:` creates a segment boundary."""
        # two sentences separated by each splitter -> two proto-keys
        for splitter in [".", "!", "?", ":"]:
            md_src = f"First part{splitter} second part is long enough.\n"
            with self.subTest(splitter=splitter):
                mdp = fdmd.MDProcessor(md_src)
                res = mdp.add_proto_keys_to_md(md_src, prefix="k")
                self.assertEqual(
                    res.count("::k"), 2,
                    f"unexpected proto-key count for splitter {splitter!r}\nresult: {res!r}",
                )

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

    def test_300__md_to_html_txt1(self):
        """Converting `txt1.md` via the md->html pipeline must yield the
        expected HTML stored in `tests/testdata/txt1_raw_html.html`."""
        expected_fpath = pjoin(TESTDATA_DIR, "txt1_raw_html.html")
        with open(expected_fpath, "r") as fp:
            expected = fp.read()

        mdp = fdmd.MDProcessor(self.txt1)
        actual = mdp._md_to_html(self.txt1)

        self.assertEqual(actual, expected)

    def test_310__flat_list_html_structure(self):
        """A flat markdown list produces correct <ul>/<li> HTML."""
        md_src = "- Item A\n- Item B\n- Item C\n"
        mdp = fdmd.MDProcessor(md_src)
        html = mdp._md_to_html(md_src)
        self.assertIn("<ul>", html)
        self.assertIn("<li>Item A</li>", html)
        self.assertIn("<li>Item B</li>", html)
        self.assertIn("<li>Item C</li>", html)

    def test_320__nested_list_html_structure(self):
        """A nested list produces the correct HTML tree structure."""
        md_src = "- Item A\n- Item B\n    - Nested B1\n    - Nested B2\n- Item C\n"
        mdp = fdmd.MDProcessor(md_src)
        html = mdp._md_to_html(md_src)
        self.assertIn("<ul>", html)
        soup = BeautifulSoup(html, "html.parser")
        item_b_li = None
        for li in soup.find_all("li"):
            if li.get_text().startswith("Item B"):
                item_b_li = li
                break
        self.assertIsNotNone(item_b_li, "Could not find <li> for 'Item B'")
        self.assertIsNotNone(item_b_li.find("ul"), "<li> for 'Item B' should contain a nested <ul>")

    def test_330__nested_list_roundtrip_idempotency(self):
        """md -> html -> md -> html roundtrip must be stable for nested lists (regression for i53)."""
        md_src = "- Item A\n- Item B\n    - Nested B1\n    - Nested B2\n- Item C\n"
        mdp = fdmd.MDProcessor(md_src)
        html1 = mdp._md_to_html(md_src)
        md2 = mdp.markdownify_and_postprocess(html1)
        html2 = fdmd.MDProcessor(md2)._md_to_html(md2)

        soup1 = BeautifulSoup(html1, "html.parser")
        soup2 = BeautifulSoup(html2, "html.parser")

        outer_ul1 = soup1.find("ul")
        outer_ul2 = soup2.find("ul")

        self.assertIsNotNone(outer_ul1, "html1 must contain a <ul>")
        self.assertIsNotNone(outer_ul2, f"html2 must contain a <ul>; md2={md2!r}")

        top_li1 = [li for li in outer_ul1.children if getattr(li, "name", None) == "li"]
        top_li2 = [li for li in outer_ul2.children if getattr(li, "name", None) == "li"]

        if len(top_li1) != 3 or len(top_li2) != 3:
            self.fail(
                f"Expected 3 top-level <li> items in both html1 and html2, "
                f"got {len(top_li1)} and {len(top_li2)}.\nmd2={md2!r}"
            )

        item_b_li1 = next((li for li in top_li1 if li.get_text().startswith("Item B")), None)
        item_b_li2 = next((li for li in top_li2 if li.get_text().startswith("Item B")), None)

        self.assertIsNotNone(item_b_li1, "html1: expected <li> for 'Item B' with nested <ul>")
        nested_ul1 = item_b_li1.find("ul") if item_b_li1 else None
        self.assertIsNotNone(nested_ul1, "html1: <li> for 'Item B' should contain a nested <ul>")
        self.assertEqual(len(nested_ul1.find_all("li")), 2, "html1: nested <ul> should have 2 items")

        self.assertIsNotNone(item_b_li2, f"html2: expected <li> for 'Item B' with nested <ul>; md2={md2!r}")
        nested_ul2 = item_b_li2.find("ul") if item_b_li2 else None
        self.assertIsNotNone(nested_ul2, f"html2: <li> for 'Item B' should contain a nested <ul>; md2={md2!r}")
        self.assertEqual(len(nested_ul2.find_all("li")), 2, f"html2: nested <ul> should have 2 items; md2={md2!r}")

    def test_340__keys_assigned_for_list_contribution(self):
        """Proto-keys and real keys are correctly assigned for a contribution containing a list."""
        md_src = "Intro sentence.\n\n- Item A\n- Item B\n    - Nested B1\n- Item C\n"
        md_with_keys = fdmd.MDProcessor(md_src).add_proto_keys_to_md(md_src, prefix="k")
        self.assertIn("::k", md_with_keys)
        self.assertIn("Item A", md_with_keys)
        self.assertIn("Item B", md_with_keys)
        self.assertIn("Item C", md_with_keys)
        self.assertIn("Intro sentence.", md_with_keys)
        self.assertGreaterEqual(md_with_keys.count("::k"), 2)


if __name__ == "__main__":
    unittest.main()
