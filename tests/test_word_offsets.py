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

import json
import os
import re

import pytest
from bs4 import BeautifulSoup

import fair_debate_md as fdmd
from fair_debate_md.core import DebateDirLoader
from fair_debate_md.references import (
    decompose_key,
    get_rendered_word_offsets,
    get_segment_source,
    get_segment_words,
    parse_key_unit,
)


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


@pytest.fixture(scope="module")
def all_fixture_debates(tmp_path_factory):
    """
    Load every fixture debate (as returned by `fdmd.unpack_repos`) exactly
    once for this module's cross-fixture test classes below, keyed by
    debate directory name. Fixture debates added later are picked up
    automatically -- nothing here names a specific debate.
    """
    target_dir = tmp_path_factory.mktemp("word-offsets-all-fixtures")
    fdmd.unpack_repos(str(target_dir))
    debate_keys = sorted(os.listdir(str(target_dir)))
    return {
        debate_key: fdmd.load_dir(os.path.join(str(target_dir), debate_key), debate_key=debate_key)
        for debate_key in debate_keys
    }


def _segment_texts(ddl):
    """Map every segment key of `ddl` to its delivered `textContent`."""
    soup = BeautifulSoup(ddl.final_html, "html.parser")
    return {span.attrs["id"]: span.get_text() for span in soup.find_all("span", class_="segment")}


def _owner_mdp_by_segment_key(ddl):
    """
    Mirrors the owner lookup in `DebateDirLoader._compute_word_offsets`
    (core.py): the contribution that actually declared a given segment key,
    needed to resolve raw words / raw source against the right markdown.
    """
    owner_by_segment_key = {}
    for mdp in ddl.tree.values():
        for raw_key in mdp.get_keys():
            owner_by_segment_key[raw_key.lstrip(":")] = mdp
    return owner_by_segment_key


def _segment_words_by_key(ddl):
    owner_by_segment_key = _owner_mdp_by_segment_key(ddl)
    return {
        segment_key: get_segment_words(owner_by_segment_key[segment_key].md_with_real_keys, segment_key)
        for segment_key in ddl.word_offsets
    }


class TestWordOffsetsInvariantsAcrossFixtures:
    """
    Group 1 (T3): the coordinate-system invariants of
    `DebateDirLoader.word_offsets` must hold for every segment of every
    fixture debate, not just the hand-picked markup cases above. This is
    the test that catches a coordinate-system shift.
    """

    def test_invariants_hold_for_every_segment(self, all_fixture_debates, subtests):
        total_segments = 0
        for debate_key in sorted(all_fixture_debates):
            ddl = all_fixture_debates[debate_key]
            segment_texts = _segment_texts(ddl)
            segment_words = _segment_words_by_key(ddl)

            with subtests.test(debate=debate_key, check="segment_key_coverage"):
                # the key set of word_offsets must cover every delivered segment,
                # neither more nor less
                assert set(ddl.word_offsets) == set(segment_texts)

            for segment_key in sorted(ddl.word_offsets):
                total_segments += 1
                with subtests.test(debate=debate_key, segment=segment_key):
                    offsets = ddl.word_offsets[segment_key]
                    text = segment_texts[segment_key]
                    words = segment_words[segment_key]
                    pairs = _pairs(offsets)

                    assert len(pairs) == len(words)
                    assert offsets == sorted(offsets)
                    for start, end in pairs:
                        assert 0 <= start <= end <= len(text)
                    for (_, end0), (start1, _) in zip(pairs, pairs[1:]):
                        assert end0 <= start1

        # sanity: fail loudly instead of silently passing on an empty/degenerate
        # fixture set
        assert len(all_fixture_debates) >= 5
        assert total_segments >= 50


_MARKUP_CHARS = set("*_`[]()!#>")
_THEMATIC_BREAK_LINE_RE = re.compile(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)


def _is_markup_free_source(source: str) -> bool:
    """
    Conservative, character-based criterion for "raw word and rendered word
    must be character-identical". A segment only qualifies if none of its
    raw words can possibly be transformed by rendering.

    Excludes three things, all found by T3 (see task_004/task_005 reports):
    - inline-markup punctuation (`_MARKUP_CHARS`) -- the original criterion;
    - a literal backslash: a raw word like "in\\-context\\-answers" contains
      none of `_MARKUP_CHARS`, but is a markdown escape sequence, and the
      renderer strips the backslashes, so raw and rendered word differ;
    - a line consisting only of a markdown thematic-break marker (`---`,
      `***`, `___`, three or more of the same character, with optional
      surrounding whitespace): such a line contains none of `_MARKUP_CHARS`
      either, but renders to an `<hr>` with no text content at all.

    This criterion is intentionally conservative: its purpose is to select
    segments where raw word and rendered word are *guaranteed* to coincide,
    not to sweep in as many segments as possible. Any raw source with a
    transformation the tokenizer/renderer might apply belongs on the
    exclusion side, even if that leaves segments out that would, in
    practice, still turn out exact.
    """
    if any(ch in _MARKUP_CHARS for ch in source):
        return False
    if "\\" in source:
        return False
    if _THEMATIC_BREAK_LINE_RE.search(source):
        return False
    return True


def _iter_markup_free_words(all_fixture_debates):
    """
    Yield `(debate_key, segment_key, word_index, word, rendered_slice)` for
    every raw word of every markup-free segment across all fixture debates.
    `word_index` is 1-based, matching the reference grammar's word
    numbering.
    """
    for debate_key in sorted(all_fixture_debates):
        ddl = all_fixture_debates[debate_key]
        segment_texts = _segment_texts(ddl)
        owner_by_segment_key = _owner_mdp_by_segment_key(ddl)
        for segment_key in sorted(ddl.word_offsets):
            owner_mdp = owner_by_segment_key[segment_key]
            source = get_segment_source(owner_mdp.md_with_real_keys, segment_key)
            if not _is_markup_free_source(source):
                continue
            words = get_segment_words(owner_mdp.md_with_real_keys, segment_key)
            text = segment_texts[segment_key]
            pairs = _pairs(ddl.word_offsets[segment_key])
            for word_index, (word, (start, end)) in enumerate(zip(words, pairs), start=1):
                yield debate_key, segment_key, word_index, word, text[start:end]


class TestWordOffsetsExactnessWithoutMarkup:
    """
    Group 2 (T3): for segments whose raw markdown source contains none of
    the characters that introduce inline markup, the rendered text at each
    word's offsets must be character-for-character identical to the raw
    word -- no markup means nothing should have been stripped, escaped, or
    shifted by rendering.
    """

    def test_markup_free_criterion_hits_a_substantial_number_of_segments(self, all_fixture_debates):
        markup_free_segments = {
            (debate_key, segment_key)
            for debate_key, segment_key, *_ in _iter_markup_free_words(all_fixture_debates)
        }
        # measured: 337 of 393 fixture segments (2026-08-06), after excluding
        # backslash-escapes and thematic-break lines in addition to inline
        # markup punctuation; generous margin (~70% of the measured value)
        # below that so this stays robust, but high enough to fail loudly if
        # the criterion stops matching almost everything
        assert len(markup_free_segments) >= 235

    def test_exact_match_for_markup_free_segments(self, all_fixture_debates):
        """
        T3 real finding (see task_004 report): with the original,
        punctuation-only `_is_markup_free_source`, 12 of the then-3994
        markup-free words mismatched exactly -- escaped hyphens (e.g.
        "in\\-context\\-answers") lose their backslash on render, and a
        horizontal-rule line ("---") renders to no text at all, even though
        neither source contains any of the excluded markup punctuation.
        Resolved (task_005) by precising the criterion itself -- excluding
        backslashes and thematic-break lines -- rather than loosening this
        assertion or marking the test xfail; see
        `TestWordOffsetsKnownNonExactCategories` for explicit coverage of
        both excluded categories.
        """
        mismatches = [
            (debate_key, segment_key, word_index, word, actual)
            for debate_key, segment_key, word_index, word, actual in _iter_markup_free_words(
                all_fixture_debates
            )
            if actual != word
        ]
        assert not mismatches, mismatches


class TestWordOffsetsKnownNonExactCategories:
    """
    Group 2b (T3): explicit, hand-checked coverage of the two raw-word
    categories that `_is_markup_free_source` excludes precisely because
    they are known to render non-identically (see its docstring). Neither
    case below is a defect of `get_rendered_word_offsets` -- the offsets
    are the correct, contract-compliant answer for what actually gets
    rendered; the mismatch is between the *raw* word and the rendered
    text, which the exclusion criterion already accounts for.
    """

    def test_backslash_escape_word_maps_to_unescaped_slice(self, all_fixture_debates):
        """
        Segment "a3" of "d00-explanatory-example-debate" has raw word 2
        "in\\-context\\-answers" (with literal backslashes escaping the
        hyphens -- markdown syntax for a literal "-"). The renderer strips
        the backslashes on output, so the offsets correctly point at the
        unescaped rendered text; the slice differs from the raw word by
        design, not by bug.
        """
        ddl = all_fixture_debates["d00-explanatory-example-debate"]
        owner_by_segment_key = _owner_mdp_by_segment_key(ddl)
        words = get_segment_words(owner_by_segment_key["a3"].md_with_real_keys, "a3")
        assert words[1] == "in\\-context\\-answers"

        text = _segment_texts(ddl)["a3"]
        pairs = _pairs(ddl.word_offsets["a3"])
        start, end = pairs[1]
        assert (start, end) == (16, 34)
        assert text[start:end] == "in-context-answers"

    def test_thematic_break_word_maps_to_null_interval(self, all_fixture_debates):
        """
        Segment "a8" of "d02-test_debate" has raw word 9 "---" on its own
        line -- markdown syntax for a thematic break (`<hr>`), which has no
        text content at all. The offsets correctly assign it a null
        interval right after the preceding word's end, and the pair count
        still matches the raw word count exactly: the word is neither
        dropped nor does it swallow a neighbor's interval.
        """
        ddl = all_fixture_debates["d02-test_debate"]
        owner_by_segment_key = _owner_mdp_by_segment_key(ddl)
        words = get_segment_words(owner_by_segment_key["a8"].md_with_real_keys, "a8")
        assert words == [
            "Mollit",
            "culpa",
            "pariatur",
            "officia",
            "duis",
            "tempor",
            "adipiscing",
            "consequat.",
            "---",
        ]

        text = _segment_texts(ddl)["a8"]
        pairs = _pairs(ddl.word_offsets["a8"])
        assert len(pairs) == len(words)

        start, end = pairs[8]
        assert (start, end) == (67, 67)
        assert text[start:end] == ""


class TestWordOffsetsD32OverlappingRefsEndToEnd:
    """
    Group 3 (T3): end-to-end proof against a real reference in the
    `d32-overlapping-refs` fixture (see
    `src/fair_debate_md/fixtures/repo-preparation/build_d32_overlapping_refs.py`).
    Contributions "a7_7-12f" and "a7_10-16g" both carry a 1-based,
    end-inclusive word-range reference into segment "a7" (see
    `references.parse_key_unit` / `tests/test_references.py`). Slicing
    `word_offsets["a7"]` at that range must reproduce exactly the phrase
    the fixture's own build script printed as the reference's resolved
    text.
    """

    @pytest.mark.parametrize(
        "ctb_key, expected_phrase",
        [
            ("a7_7-12f", "cost us maybe sixty euros once,"),
            ("a7_10-16g", "sixty euros once, take up less space,"),
        ],
    )
    def test_word_range_reference_resolves_to_expected_phrase(
        self, all_fixture_debates, ctb_key, expected_phrase
    ):
        ddl = all_fixture_debates["d32-overlapping-refs"]
        ref_unit = parse_key_unit(decompose_key(ctb_key)[-2])
        assert ref_unit.has_word_ref, ctb_key

        text = _segment_texts(ddl)["a7"]
        pairs = _pairs(ddl.word_offsets["a7"])
        # word range is 1-based, end-inclusive, see references.KeyUnit
        selected = pairs[ref_unit.word_start - 1 : ref_unit.word_end]

        slices = [text[start:end] for start, end in selected]
        assert " ".join(slices) == expected_phrase


class TestWordOffsetsJsonSizeRegression:
    """
    Group 4 (T3): size alarm for `DebateDirLoader.word_offsets`. The table
    stores only integer offset pairs, never the segment text itself; if
    someone accidentally started storing the raw text too, the JSON size
    would jump by roughly an order of magnitude. This is not a
    micro-optimization target -- the bound is deliberately generous.
    """

    def test_word_offsets_json_size_for_d31_ice_cream(self, all_fixture_debates):
        ddl = all_fixture_debates["d31-ice-cream"]
        size = len(json.dumps(ddl.word_offsets))
        # measured: 13180 bytes (2026-08-06); generous 3x margin as an alarm,
        # not a tuning target
        assert size <= 40_000
