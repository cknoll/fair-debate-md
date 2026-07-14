"""
Tests for flexible references (segment ranges and word-level references),
see src/fair_debate_md/references.py and docs/flexible_references_concept.md.
"""

import os

import pytest
from bs4 import BeautifulSoup

import fair_debate_md as fdmd
from fair_debate_md import references
from fair_debate_md.references import (
    parse_key_unit,
    decompose_key,
    is_valid_key,
    get_anchor_segment_key,
    get_first_referenced_segment_key,
    get_parent_contribution_key,
    get_segment_source,
    get_segment_words,
    validate_reference,
)


class TestParseKeyUnit:
    def test_plain_unit(self):
        unit = parse_key_unit("a5")
        assert unit.token == "a"
        assert unit.seg_start == 5
        assert not unit.is_segment_range
        assert not unit.has_word_ref
        assert unit.anchor_segment_number == 5

    def test_segment_range(self):
        unit = parse_key_unit("a5-7")
        assert (unit.seg_start, unit.seg_end) == (5, 7)
        assert unit.is_segment_range
        assert unit.anchor_segment_number == 7

    def test_single_word(self):
        unit = parse_key_unit("a7_4")
        assert (unit.seg_start, unit.word_start, unit.word_end) == (7, 4, None)
        assert unit.has_word_ref
        assert unit.anchor_segment_number == 7

    def test_word_range(self):
        unit = parse_key_unit("a7_4-8")
        assert (unit.word_start, unit.word_end) == (4, 8)

    def test_bare_token(self):
        unit = parse_key_unit("ab")
        assert unit.token == "ab"
        assert unit.is_bare

    def test_multi_char_token_with_range(self):
        unit = parse_key_unit("aa12-15")
        assert unit.token == "aa"
        assert (unit.seg_start, unit.seg_end) == (12, 15)

    def test_reject_range_word_combination(self):
        with pytest.raises(ValueError, match="must not be combined"):
            parse_key_unit("a5-7_4")

    def test_reject_degenerate_segment_range(self):
        with pytest.raises(ValueError, match="greater than"):
            parse_key_unit("a5-5")

    def test_reject_reversed_segment_range(self):
        with pytest.raises(ValueError, match="greater than"):
            parse_key_unit("a7-5")

    def test_reject_degenerate_word_range(self):
        with pytest.raises(ValueError, match="greater than"):
            parse_key_unit("a7_4-4")

    def test_reject_zero_based(self):
        with pytest.raises(ValueError, match="1-based"):
            parse_key_unit("a0-3")
        with pytest.raises(ValueError, match="1-based"):
            parse_key_unit("a7_0")

    def test_reject_malformed(self):
        for bad in ("a", "5a", "A5", "a5-", "a5_", "a-5", "a5-7-9", "a5_4_8"):
            if bad == "a":
                continue  # bare token, valid
            with pytest.raises(ValueError):
                parse_key_unit(bad)


class TestDecomposeAndValidity:
    def test_decompose_with_ranges(self):
        assert decompose_key("a5-7b") == ["a5-7", "b"]
        assert decompose_key("a7_4-8b") == ["a7_4-8", "b"]
        assert decompose_key("a7_4b2c") == ["a7_4", "b2", "c"]
        assert decompose_key("a5-7b2c1_3-5d") == ["a5-7", "b2", "c1_3-5", "d"]

    def test_decompose_plain_regression(self):
        assert decompose_key("a5") == ["a5"]
        assert decompose_key("a304b1") == ["a304", "b1"]
        assert decompose_key("a3ab") == ["a3", "ab"]

    def test_valid_keys(self):
        for key in ("a", "a5", "a5b", "a5-7b", "a7_4b", "a7_4-8b", "a5-7b2c1_3-5d", "aa5ab3b"):
            assert is_valid_key(key), key

    def test_invalid_keys(self):
        invalid = (
            "",
            "a5-5b",  # degenerate range
            "a7-5b",  # reversed range
            "a5-7_4b",  # range+word combination
            "a7_4-4b",  # degenerate word range
            "a0-3b",  # zero-based range
            "5a",
            "A5",
            "a5-b",
            "a5_b",
        )
        for key in invalid:
            assert not is_valid_key(key), key

    def test_is_valid_fpath_with_new_syntax(self):
        assert fdmd.core.is_valid_fpath("/some/dir/b/a5-7b.md")
        assert fdmd.core.is_valid_fpath("/some/dir/b/a7_4-8b.md")
        assert not fdmd.core.is_valid_fpath("/some/dir/b/a5-5b.md")


class TestKeyHelpers:
    def test_anchor_segment_key(self):
        assert get_anchor_segment_key("a5b") == "a5"
        assert get_anchor_segment_key("a5-7b") == "a7"
        assert get_anchor_segment_key("a7_4-8b") == "a7"
        # segment ids inherit inner references
        assert get_anchor_segment_key("a5-7b2c") == "a5-7b2"
        assert get_anchor_segment_key("a1c3aa") == "a1c3"

    def test_anchor_segment_key_root_and_invalid(self):
        assert get_anchor_segment_key("a") is None

    def test_first_referenced_segment_key(self):
        assert get_first_referenced_segment_key("a5-7b") == "a5"
        assert get_first_referenced_segment_key("a5b") == "a5"
        assert get_first_referenced_segment_key("a7_4-8b") == "a7"

    def test_parent_contribution_key(self):
        assert get_parent_contribution_key("a5-7b") == "a"
        assert get_parent_contribution_key("a1c3aa") == "a1c"
        assert get_parent_contribution_key("a5-7b2c") == "a5-7b"
        assert get_parent_contribution_key("a") is None


class TestSegmentWords:
    MD1 = "::a1 First sentence here. ::a2 Second statement has five words. ::a3 Third."

    def test_mid_paragraph_segments(self):
        assert get_segment_words(self.MD1, "a1") == ["First", "sentence", "here."]
        assert get_segment_words(self.MD1, "a2") == ["Second", "statement", "has", "five", "words."]
        # last segment (terminated by end of text)
        assert get_segment_words(self.MD1, "a3") == ["Third."]

    def test_markup_stays_attached(self):
        md = "::a1 This is **very important** and _subtle_."
        assert get_segment_words(md, "a1") == ["This", "is", "**very", "important**", "and", "_subtle_."]

    def test_unordered_list_prefix_excluded(self):
        md = "- ::a1 First item words\n- ::a2 Second item"
        assert get_segment_words(md, "a1") == ["First", "item", "words"]
        assert get_segment_words(md, "a2") == ["Second", "item"]

    def test_ordered_list_prefix_excluded(self):
        md = "1. ::a1 First item\n2. ::a2 Second item"
        assert get_segment_words(md, "a1") == ["First", "item"]

    def test_heading_prefix_excluded(self):
        md = "::a1 Paragraph text.\n\n## ::a2 A heading"
        assert get_segment_words(md, "a1") == ["Paragraph", "text."]
        assert get_segment_words(md, "a2") == ["A", "heading"]

    def test_nested_list_prefix_excluded(self):
        md = "- ::a1 Outer item:\n    - ::a2 nested item"
        assert get_segment_words(md, "a1") == ["Outer", "item:"]

    def test_marker_prefix_no_collision(self):
        # the marker ::a1 must not be confused with ::a14
        md = "::a1 Short. ::a14 Longer segment text here."
        assert get_segment_words(md, "a1") == ["Short."]
        assert get_segment_words(md, "a14") == ["Longer", "segment", "text", "here."]

    def test_segment_key_with_inherited_reference(self):
        md = "::a1-2b1 Reply to the range. ::a1-2b2 More text."
        assert get_segment_words(md, "a1-2b1") == ["Reply", "to", "the", "range."]

    def test_missing_segment_raises(self):
        with pytest.raises(ValueError, match="not found"):
            get_segment_words(self.MD1, "a99")

    def test_source_preserves_inner_newlines(self):
        # a code-block segment keeps its content tokens
        md = "::a1 Intro:\n\n::a2 ```\nsome code tokens\n```\n\n::a3 After."
        assert get_segment_words(md, "a2") == ["```", "some", "code", "tokens", "```"]


class TestValidateReference:
    MD1 = "::a1 First sentence here. ::a2 Second statement has five words. ::a3 Third."

    def test_valid_range(self):
        validate_reference("a1-3b", self.MD1)

    def test_valid_word_range(self):
        validate_reference("a2_2-5b", self.MD1)
        validate_reference("a2_5b", self.MD1)

    def test_plain_reference_not_checked(self):
        # legacy behavior: plain references are not validated here
        validate_reference("a99b", self.MD1)

    def test_range_end_missing(self):
        with pytest.raises(ValueError, match="does not exist"):
            validate_reference("a2-9b", self.MD1)

    def test_word_position_exceeds_count(self):
        with pytest.raises(ValueError, match="exceeds"):
            validate_reference("a2_2-6b", self.MD1)
        with pytest.raises(ValueError, match="exceeds"):
            validate_reference("a3_2b", self.MD1)


def _write_debate(tmp_path, files: dict):
    for rel_path, content in files.items():
        fpath = tmp_path / rel_path
        fpath.parent.mkdir(exist_ok=True)
        fpath.write_text(content)


class TestDebateIntegration:
    def test_range_and_word_replies(self, tmp_path):
        _write_debate(
            tmp_path,
            {
                "a/a.md": "::a1 First statement. ::a2 Second statement has five words. ::a3 Third.\n",
                "b/a1-2b.md": "::a1-2b1 Reply to the first two statements.\n",
                "c/a2_2-3c.md": "::a2_2-3c1 Reply to words two and three.\n",
            },
        )
        ddl = fdmd.load_dir(str(tmp_path), debate_key="test-flexible-refs")
        soup = BeautifulSoup(ddl.final_html, "html.parser")

        range_div = soup.find(id="contribution_a1-2b")
        assert range_div is not None
        assert range_div.attrs["data-ref-anchor"] == "a2"
        assert range_div.attrs["data-ref-seg-start"] == "a1"
        assert "data-ref-words" not in range_div.attrs

        word_div = soup.find(id="contribution_a2_2-3c")
        assert word_div is not None
        assert word_div.attrs["data-ref-anchor"] == "a2"
        assert word_div.attrs["data-ref-words"] == "2-3"
        assert "data-ref-seg-start" not in word_div.attrs

        # both contributions are anchored after segment a2 (and before a3)
        all_ids = [tag["id"] for tag in soup.find_all(id=True)]
        idx_a2 = all_ids.index("a2")
        idx_a3 = all_ids.index("a3")
        idx_range = all_ids.index("contribution_a1-2b")
        idx_word = all_ids.index("contribution_a2_2-3c")
        assert idx_a2 < idx_range < idx_a3
        assert idx_a2 < idx_word < idx_a3
        # deterministic sibling order by role-token: b before c
        assert idx_range < idx_word

    def test_plain_reply_has_no_ref_attributes(self, tmp_path):
        _write_debate(
            tmp_path,
            {
                "a/a.md": "::a1 First statement. ::a2 Second statement.\n",
                "b/a1b.md": "::a1b1 Plain reply.\n",
            },
        )
        ddl = fdmd.load_dir(str(tmp_path), debate_key="test-plain-refs")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        div = soup.find(id="contribution_a1b")
        assert div is not None
        assert "data-ref-anchor" not in div.attrs

    def test_deep_reply_below_range_reply(self, tmp_path):
        _write_debate(
            tmp_path,
            {
                "a/a.md": "::a1 First statement. ::a2 Second statement.\n",
                "b/a1-2b.md": "::a1-2b1 Reply to both statements. ::a1-2b2 With two segments.\n",
                "a/a1-2b2a.md": "::a1-2b2a1 Counter-reply of party a.\n",
            },
        )
        ddl = fdmd.load_dir(str(tmp_path), debate_key="test-deep-range")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        assert soup.find(id="contribution_a1-2b2a") is not None

    def test_invalid_word_reference_raises(self, tmp_path):
        _write_debate(
            tmp_path,
            {
                "a/a.md": "::a1 Only three words.\n",
                "b/a1_2-9b.md": "::a1_2-9b1 Reply referencing too many words.\n",
            },
        )
        with pytest.raises(ValueError, match="exceeds"):
            fdmd.load_dir(str(tmp_path), debate_key="test-invalid-word-ref")

    def test_invalid_range_reference_raises(self, tmp_path):
        _write_debate(
            tmp_path,
            {
                "a/a.md": "::a1 First statement. ::a2 Second statement.\n",
                "b/a1-5b.md": "::a1-5b1 Reply referencing missing segments.\n",
            },
        )
        with pytest.raises(ValueError, match="does not exist"):
            fdmd.load_dir(str(tmp_path), debate_key="test-invalid-range-ref")

    def test_invalid_key_file_is_ignored(self, tmp_path):
        # files with syntactically invalid keys (degenerate range) are ignored
        _write_debate(
            tmp_path,
            {
                "a/a.md": "::a1 First statement.\n",
                "b/a1-1b.md": "::a1-1b1 Degenerate range.\n",
            },
        )
        ddl = fdmd.load_dir(str(tmp_path), debate_key="test-degenerate-range")
        assert "a1-1b" not in ddl.tree


class TestWriteCtb:
    def test_write_ctb_with_range_key(self, tmp_path):
        from fair_debate_md.core import DBContribution, write_ctb_to_file

        ctb = DBContribution(ctb_key="a1-2b", body="Reply to a range.")
        write_ctb_to_file(str(tmp_path), ctb)
        assert ctb.author_role == "b"
        assert ctb.fpath == str(tmp_path / "b" / "a1-2b.md")
        assert os.path.exists(ctb.fpath)
        with open(ctb.fpath) as fp:
            content = fp.read()
        assert "::a1-2b1" in content
