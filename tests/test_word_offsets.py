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
