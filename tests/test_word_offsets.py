"""
Tests for `get_rendered_word_offsets` (raw-word <-> rendered-text alignment),
see src/fair_debate_md/references.py.

The rendered `segment_text` for each case below is written out by hand,
mirroring what `MDProcessor`/`SpanAdder` actually produce for the
corresponding raw markdown with `prettify=False` (verified interactively
against `core.SpanAdder.add_spans_for_keys`, not re-derived here to keep the
tests independent of the rendering pipeline). The raw `words` are the exact
result of `get_segment_words` on the corresponding markdown source.
"""

import os

from bs4 import BeautifulSoup

import fair_debate_md as fdmd
from fair_debate_md.core import DebateDirLoader
from fair_debate_md.references import get_rendered_word_offsets, get_segment_words


def _pairs(offsets):
    return list(zip(offsets[0::2], offsets[1::2]))


def _slices(text, offsets):
    return [text[s:e] for s, e in _pairs(offsets)]


class TestGetRenderedWordOffsets:
    def test_bold_spanning_two_words(self):
        words = get_segment_words("::a1 **very important**", "a1")
        assert words == ["**very", "important**"]
        text = " very important"
        offsets = get_rendered_word_offsets(text, words)
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["very", "important"]

    def test_bold_crossing_tag_boundary_mid_word(self):
        words = get_segment_words("::a1 **wichtig**e", "a1")
        assert words == ["**wichtig**e"]
        text = " wichtige"
        offsets = get_rendered_word_offsets(text, words)
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["wichtige"]

    def test_link(self):
        words = get_segment_words("::a1 [link text](url)", "a1")
        assert words == ["[link", "text](url)"]
        text = " link text"
        offsets = get_rendered_word_offsets(text, words)
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["link", "text"]

    def test_inline_code(self):
        words = get_segment_words("::a1 `a b`", "a1")
        assert words == ["`a", "b`"]
        text = " a b"
        offsets = get_rendered_word_offsets(text, words)
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["a", "b"]

    def test_image_renders_to_no_text(self):
        words = get_segment_words("::a1 ![alt](url) done", "a1")
        assert words == ["![alt](url)", "done"]
        # the renderer emits an <img> tag (no text content); textContent of
        # the surrounding paragraph keeps both whitespace runs around it
        text = "  done"
        offsets = get_rendered_word_offsets(text, words)
        assert len(offsets) == 2 * len(words)
        pairs = _pairs(offsets)
        # the image word gets a null interval
        assert pairs[0][0] == pairs[0][1]
        assert _slices(text, offsets) == ["", "done"]

    def test_list_segment(self):
        md = "- ::a1 First item words\n- ::a2 Second item"
        words = get_segment_words(md, "a1")
        assert words == ["First", "item", "words"]
        text = " First item words"
        offsets = get_rendered_word_offsets(text, words)
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["First", "item", "words"]

    def test_heading_segment(self):
        md = "## ::a1 A heading here"
        words = get_segment_words(md, "a1")
        assert words == ["A", "heading", "here"]
        text = " A heading here"
        offsets = get_rendered_word_offsets(text, words)
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["A", "heading", "here"]

    def test_empty_words_list(self):
        assert get_rendered_word_offsets("some text", []) == []


class TestInvariants:
    CASES = [
        (" very important", ["**very", "important**"]),
        (" wichtige", ["**wichtig**e"]),
        (" link text", ["[link", "text](url)"]),
        (" a b", ["`a", "b`"]),
        ("  done", ["![alt](url)", "done"]),
        (" First item words", ["First", "item", "words"]),
        (" A heading here", ["A", "heading", "here"]),
        ("", []),
        ("no markup at all here", ["no", "markup", "at", "all", "here"]),
    ]

    def test_pair_count_matches_word_count(self):
        for text, words in self.CASES:
            offsets = get_rendered_word_offsets(text, words)
            assert len(offsets) == 2 * len(words), (text, words)

    def test_monotonic_non_overlapping_and_in_bounds(self):
        for text, words in self.CASES:
            offsets = get_rendered_word_offsets(text, words)
            assert offsets == sorted(offsets), (text, words)
            for start, end in _pairs(offsets):
                assert 0 <= start <= end <= len(text), (text, words, start, end)
            for (_, end0), (start1, _) in zip(_pairs(offsets), _pairs(offsets)[1:]):
                assert end0 <= start1, (text, words)

    def test_deterministic(self):
        for text, words in self.CASES:
            assert get_rendered_word_offsets(text, words) == get_rendered_word_offsets(text, words)


def _write_debate(tmp_path, files: dict):
    for rel_path, content in files.items():
        fpath = tmp_path / rel_path
        fpath.parent.mkdir(exist_ok=True)
        fpath.write_text(content)


class TestWordOffsetsCriticalCondition:
    """
    The critical condition of the `DebateDirLoader.word_offsets` contract
    (see its docstring in core.py): offsets index into the segment's
    *delivered* HTML text content, exactly as a browser would read
    `document.getElementById(segment_key).textContent`. This test loads a
    real fixture debate, parses the actually-delivered `final_html` (not
    `md_with_real_keys`, not the pre-prettify `html_src`), and checks that
    every offset pair slices out precisely the expected raw word,
    character for character. If the coordinate system is ever shifted
    (e.g. offsets computed against a different string than what gets
    parsed here), this test goes red.
    """

    def test_offsets_index_into_delivered_text_content(self, tmp_path):
        fdmd.unpack_repos(str(tmp_path))
        repo_dir = os.path.join(str(tmp_path), fdmd.TEST_DEBATE_KEY)
        ddl = fdmd.load_dir(repo_dir, debate_key=fdmd.TEST_DEBATE_KEY)

        soup = BeautifulSoup(ddl.final_html, "html.parser")
        span = soup.find(id="a4")
        assert span is not None, "fixture debate d1-lorem_ipsum is expected to contain segment 'a4'"
        text_content = span.get_text()

        # segment a4 is plain text, no markup -- chosen so raw words and
        # rendered words coincide exactly, making this a strict check
        expected_words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a4")
        assert expected_words == [
            "Dolor",
            "etincidunt",
            "neque",
            "sed",
            "tempora",
            "porro",
            "quiquia.",
        ]

        offsets = ddl.word_offsets["a4"]
        assert len(offsets) == 2 * len(expected_words)
        for word, (start, end) in zip(expected_words, _pairs(offsets)):
            assert text_content[start:end] == word


class TestWordOffsetsMarkupIntegration:
    """
    Integration tests over a temporary debate (pattern: `_write_debate` /
    `TestDebateIntegration` in tests/test_references.py), exercising the
    full pipeline (markdown -> segmented+prettified HTML -> `word_offsets`)
    for the markup cases required by the T2 task.
    """

    def _load(self, tmp_path, md_src, debate_key):
        _write_debate(tmp_path, {"a/a.md": md_src})
        return fdmd.load_dir(str(tmp_path), debate_key=debate_key)

    def test_bold_spanning_two_words(self, tmp_path):
        ddl = self._load(tmp_path, "::a1 **very important** words here.\n", "test-wo-bold")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == ["**very", "important**", "words", "here."]
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["very", "important", "words", "here."]

    def test_bold_crossing_tag_boundary_mid_word_is_exact(self, tmp_path):
        """
        Regression test for T2b: under `prettify=True` (the actually
        delivered rendering, kept unchanged by orchestrator decision),
        BeautifulSoup's prettify inserts whitespace at *every* tag boundary,
        including inside inline markup. For "**wichtig**e" this splits the
        rendered "wichtige" into "wichtig" + injected whitespace + "e". The
        frozen contract requires this to be ONE non-empty, contiguous
        interval spanning the whole range (injected whitespace included),
        and the two following words must keep correct, non-null intervals
        (no cascade). This replaces the former
        `test_bold_crossing_tag_boundary_mid_word_is_a_known_limitation`,
        which documented exactly this defect instead of the fix.
        """
        ddl = self._load(tmp_path, "::a1 **wichtig**e stuff follows.\n", "test-wo-wichtig")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == ["**wichtig**e", "stuff", "follows."]
        assert len(offsets) == 2 * len(words)
        assert text == "\n\n    wichtig\n   \n   e stuff follows.\n  "
        assert _slices(text, offsets) == ["wichtig\n   \n   e", "stuff", "follows."]

    def test_link_url_does_not_bleed_into_next_word(self, tmp_path):
        """
        Runaway regression test for T2b: an earlier fix attempt (skipping
        unmatched *rendered* whitespace mid-word in a local scan) let the
        unmatched URL characters of "text](url)" run on and accidentally
        resync with the *next* word's rendered occurrence ("here."),
        matching "h", "e", "r" of "http" against "h", "e", "r" of "here.".
        Global alignment must not reproduce this: the interval of
        "text](url)" ends at "text", strictly before "here." starts, and
        "here." gets its own correct interval.
        """
        ddl = self._load(tmp_path, "::a1 [link text](http://example.org) here.\n", "test-wo-link-runaway")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == ["[link", "text](http://example.org)", "here."]
        pairs = _pairs(offsets)
        text_word_end, here_word_start = pairs[1][1], pairs[2][0]
        assert text_word_end <= here_word_start
        assert _slices(text, offsets) == ["link", "text", "here."]

    def test_no_cascade_from_consecutive_unmatched_words(self, tmp_path):
        """
        Explicit cascade regression test for T2b requirement 3: two
        consecutive raw words that render to no text at all (images) must
        not corrupt the interval assignment of the words that follow them
        in the same segment.
        """
        md_src = (
            "::a1 Start ![img1](http://example.org/1.png) "
            "![img2](http://example.org/2.png) middle two words end.\n"
        )
        ddl = self._load(tmp_path, md_src, "test-wo-no-cascade")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == [
            "Start",
            "![img1](http://example.org/1.png)",
            "![img2](http://example.org/2.png)",
            "middle",
            "two",
            "words",
            "end.",
        ]
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["Start", "", "", "middle", "two", "words", "end."]

    def test_link(self, tmp_path):
        ddl = self._load(tmp_path, "::a1 [link text](http://example.org) here.\n", "test-wo-link")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == ["[link", "text](http://example.org)", "here."]
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["link", "text", "here."]

    def test_inline_code(self, tmp_path):
        ddl = self._load(tmp_path, "::a1 Inline code `a b` shown.\n", "test-wo-code")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == ["Inline", "code", "`a", "b`", "shown."]
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["Inline", "code", "a", "b", "shown."]

    def test_image_null_intervals(self, tmp_path):
        ddl = self._load(tmp_path, "::a1 Image ![alt](http://example.org/x.png) done.\n", "test-wo-image")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == ["Image", "![alt](http://example.org/x.png)", "done."]
        assert len(offsets) == 2 * len(words)
        pairs = _pairs(offsets)
        # the image word renders to no text -> null interval
        assert pairs[1][0] == pairs[1][1]
        assert _slices(text, offsets) == ["Image", "", "done."]

    def test_list_segment(self, tmp_path):
        md_src = "- ::a1 First list item words\n- ::a2 Second list item\n"
        ddl = self._load(tmp_path, md_src, "test-wo-list")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == ["First", "list", "item", "words"]
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["First", "list", "item", "words"]

    def test_heading_segment(self, tmp_path):
        ddl = self._load(tmp_path, "## ::a1 A heading here\n", "test-wo-heading")
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        text = soup.find(id="a1").get_text()
        offsets = ddl.word_offsets["a1"]
        words = get_segment_words(ddl.tree["a"].md_with_real_keys, "a1")
        assert words == ["A", "heading", "here"]
        assert len(offsets) == 2 * len(words)
        assert _slices(text, offsets) == ["A", "heading", "here"]


class TestWordOffsetsLoadDirVsGenerateHtml:
    def test_word_offsets_equal_regardless_of_call_path(self, tmp_path):
        files = {
            "a/a.md": "::a1 First statement. ::a2 Second statement has five words. ::a3 Third.\n",
            "b/a1-2b.md": "::a1-2b1 Reply to the first two statements.\n",
        }

        tmp_path_1 = tmp_path / "via-module-function"
        tmp_path_1.mkdir()
        _write_debate(tmp_path_1, files)
        ddl_via_module_function = fdmd.load_dir(str(tmp_path_1), debate_key="test-wo-load-dir-1")

        tmp_path_2 = tmp_path / "via-explicit-calls"
        tmp_path_2.mkdir()
        _write_debate(tmp_path_2, files)
        ddl_via_explicit_calls = DebateDirLoader(dirpath=str(tmp_path_2), debate_key="test-wo-load-dir-2")
        assert ddl_via_explicit_calls.word_offsets == {}
        ddl_via_explicit_calls.load_dir()
        assert ddl_via_explicit_calls.word_offsets == {}
        ddl_via_explicit_calls.generate_html_with_contributions()

        assert ddl_via_explicit_calls.word_offsets
        assert ddl_via_explicit_calls.word_offsets == ddl_via_module_function.word_offsets
