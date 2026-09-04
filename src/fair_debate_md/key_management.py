import re
from bs4 import BeautifulSoup, element


# The version of the segmentation ruleset below -- everything in this module that decides
# where one segment ends and the next begins (`SENTENCE_SPLITTERS`, the abbreviation
# tables, `_is_abbreviation_dot`, `split_text_into_segments`).
#
# It is recorded per contribution, in the yaml front matter of the stored `.md`, because
# segment keys are the prefix of every answer key: `a14c5b` answers segment `a14c5`.
# Re-segmenting an existing text under changed rules therefore does not renumber it, it
# breaks every reference into it. A contribution that says which ruleset produced its
# `::aN` markers can be rendered under exactly that ruleset later, so old debates stay as
# they are while new ones use the current default.
#
# Raise this whenever the segmentation behaviour changes, and keep the previous behaviour
# reachable (`split_text_into_segments` dispatches on the number). See `dev_notes.md`,
# section "splitter syntax", for the changes each version was introduced for.
#
# Version history:
#   1 -- every splitter character splits, regardless of what follows it.
#   2 -- a splitter only splits when whitespace follows (or it ends the text); a dot
#        directly after a digit does not split at all; `\@` immediately before a splitter
#        forces a split that the rules would otherwise suppress, and `\~` suppresses one
#        that the rules would otherwise make.
#
# `\~` was added to version 2 (2026-09-04) instead of opening a version 3. It is a pure
# extension: no text that already claims version 2 contains the sequence, so the number
# still promises what it promised, and nothing has been handed out that would say
# otherwise. That reasoning is allowed while the project is undeployed and it is the
# user's call to make -- see `CLAUDE.md`, section "Splitter syntax version".
SPLITTER_SYNTAX_VERSION = 2

# What a contribution without any recorded version was created under: everything written
# before the field existed came from these rules.
DEFAULT_SPLITTER_SYNTAX_VERSION = 1

# characters which end a sentence / segment
SENTENCE_SPLITTERS = (".", "!", "?", ":")

# Split markers (syntax version 2+). Both are written directly in front of a splitter and
# decide that one splitter against the rules:
#
#   * `\@` FORCES a split the rules suppress. The only way to end a segment on a number
#     ("... bis Ende 2026\@. Jede Verwaesserung ..."), and it breaks a strong abbreviation
#     too ("... z.B\@. Der naechste Satz.").
#   * `\~` SUPPRESSES a split the rules make. For the abbreviation the tables below do not
#     know ("Prof\~. Mueller", "Abb\~. 3", "gem\~. Paragraph 3"). Those tables cannot be
#     complete in any language, and every entry added to them is one more reason for a
#     real sentence end not to split -- so an escape hatch per occurrence is the better
#     answer than an ever longer list.
#
# Why this spelling: LaTeX solves the same problem with `\@.`, with the same meaning, so
# the notation reads correctly to anyone who has met it there. Two alternatives were
# tried against the real pipeline and are not merely worse but unusable: `18\.` loses its
# backslash in python-markdown, so at segmentation time it is indistinguishable from a
# plain dot, and `18.\ ` moves the backslash into the *following* segment. That second
# finding is also why `\~` stands in front of the splitter although LaTeX's counterparts
# (`Dr.~Smith`, `etc.\ `) stand behind it: a marker behind the splitter would land in the
# next segment. What survives of the analogy is the `~`, which is the tie in both.
#
# Since both markers have to touch the splitter, at most one of them can apply to it --
# so there is no precedence between them to define.
#
# The markers stay in the stored `.md`: they are what lets the recorded segmentation be
# re-checked against the text (see `tests/test_splitter_versions.py`), and a reader of the
# raw repo can see why a segment ends where it does. They are removed when the text is
# rendered (`MDProcessor.get_html_with_segments`), so they never show up in the debate.
# They carry no whitespace and therefore do not shift any word position -- the frozen word
# tokenizer counts `2026\@.` as the single word it already counted as `2026.`.
FORCE_SPLIT_MARKER = "\\@"
SUPPRESS_SPLIT_MARKER = "\\~"
SPLIT_MARKERS = (FORCE_SPLIT_MARKER, SUPPRESS_SPLIT_MARKER)

# `_split_v2` reads exactly this many characters back to see which marker (if any) touches
# the splitter, so the two must be equally wide.
MARKER_LEN = len(FORCE_SPLIT_MARKER)
assert all(len(marker) == MARKER_LEN for marker in SPLIT_MARKERS)

_SPLIT_MARKER_RE = re.compile(
    "(?:"
    + "|".join(re.escape(marker) for marker in SPLIT_MARKERS)
    + r")(?=["
    + re.escape("".join(SENTENCE_SPLITTERS))
    + r"])"
)


def strip_split_markers(text: str) -> str:
    """Remove every split marker that is in effect, i.e. that precedes a splitter."""
    return _SPLIT_MARKER_RE.sub("", text)


# Abbreviations whose trailing dot practically never ends a sentence.
# A dot terminating (or lying inside) such an abbreviation never splits.
# Matching details (see `_is_abbreviation_dot`):
#   * a word boundary is required before the abbreviation
#     ("africa." does not match "ca.")
#   * internal dots may be followed by whitespace ("z. B." == "z.B.")
#   * a sentence-case variant is matched as well ("Vgl." for "vgl.")
_STRONG_ABBREVIATIONS = (
    # English
    "i.e.",
    "e.g.",
    "w.r.t.",
    "cf.",
    "vs.",
    "approx.",
    "resp.",
    # German
    "bspw.",
    "bzgl.",
    "bzw.",
    "ca.",
    "d.h.",
    "evtl.",
    "ggf.",
    "i.d.R.",
    "inkl.",
    "sog.",
    "u.a.",
    "u.U.",
    "vgl.",
    "z.B.",
    "z.T.",
    "Nr.",
    "Mio.",
    "Mrd.",
)

# Abbreviations which often *do* end a sentence ("... Äpfel, Birnen usw. Der
# nächste Satz."). Their final dot only suppresses a split if the text
# continues in lowercase; their internal dots never split.
_WEAK_ABBREVIATIONS = (
    "etc.",
    "usw.",
    "usf.",
    "o.ä.",
    "o.Ä.",
    "u.v.m.",
)

# version-number pattern: something like "v1." followed by a digit
# means the dot is part of a version number, not a sentence splitter.
_VERSION_RE = re.compile(r"v\d+\.$")

# char before the abbreviation must not be a word char or a dot
_BOUNDARY = r"(?<![\w.])"


def _abbr_regex_fragment(abbr: str) -> str:
    """
    Regex fragment matching `abbr`, allowing optional whitespace after
    internal dots (so that "z. B." matches like "z.B.").
    """
    assert abbr.endswith(".")
    parts = abbr[:-1].split(".")
    return r"\.\s?".join(re.escape(p) for p in parts) + r"\."


def _case_variants(abbr: str) -> tuple:
    """Return `abbr` plus (if different) its sentence-case variant."""
    sentence_case = abbr[0].upper() + abbr[1:]
    if sentence_case == abbr:
        return (abbr,)
    return (abbr, sentence_case)


def _compile_abbr_res(abbreviations: tuple) -> tuple:
    """
    Compile matching regexes for `abbreviations`.

    :return: 2-tuple ``(end_re, partial_res)`` where
        - ``end_re`` matches when the text ends with a complete abbreviation
        - ``partial_res`` is a list of ``(prefix_re, rest_re)`` pairs for dots
          *inside* an abbreviation: ``prefix_re`` must match the end of the
          text so far and ``rest_re`` the (whitespace-stripped) continuation
    """
    end_fragments = []
    partial_res = []
    for base in abbreviations:
        for abbr in _case_variants(base):
            end_fragments.append(_abbr_regex_fragment(abbr))
            fragments = abbr[:-1].split(".")
            for k in range(1, len(fragments)):
                prefix = ".".join(fragments[:k]) + "."
                rest = ".".join(fragments[k:]) + "."
                prefix_re = re.compile(_BOUNDARY + _abbr_regex_fragment(prefix) + r"$")
                rest_re = re.compile(_abbr_regex_fragment(rest))
                partial_res.append((prefix_re, rest_re))
    end_re = re.compile(_BOUNDARY + "(?:" + "|".join(end_fragments) + r")$")
    return end_re, partial_res


_STRONG_END_RE, _STRONG_PARTIAL_RES = _compile_abbr_res(_STRONG_ABBREVIATIONS)
_WEAK_END_RE, _WEAK_PARTIAL_RES = _compile_abbr_res(_WEAK_ABBREVIATIONS)
_ALL_PARTIAL_RES = _STRONG_PARTIAL_RES + _WEAK_PARTIAL_RES


def _is_abbreviation_dot(text_so_far: str, text_rest: str) -> bool:
    """
    Decide whether a `.` at position `len(text_so_far)` (exclusive, i.e. the
    dot itself is the last char of `text_so_far`) belongs to an abbreviation
    and should therefore NOT be treated as a sentence splitter.

    :param text_so_far:  the text up to *and including* the candidate splitter
    :param text_rest:    the text after the candidate splitter (may start with
                         whitespace and then another abbreviation fragment)
    """
    stripped_rest = text_rest.lstrip()

    # dot terminates a strong abbreviation -> never split
    if _STRONG_END_RE.search(text_so_far):
        return True

    # dot terminates a weak abbreviation -> only suppress the split if the
    # text continues in lowercase (i.e. the sentence goes on)
    if _WEAK_END_RE.search(text_so_far):
        first = stripped_rest[:1]
        if first and not first.isupper():
            return True

    # dot inside an abbreviation, e.g. "e." followed by "g." (also spans the
    # spaced variants like "z. B.")
    for prefix_re, rest_re in _ALL_PARTIAL_RES:
        if prefix_re.search(text_so_far) and rest_re.match(stripped_rest):
            return True

    # a dot between two digits groups them rather than ending a sentence:
    # "100.000", "3.14", "24.12.2026". Checked against the UNstripped rest on
    # purpose -- in "Es waren 2022. 500 kamen." the dot does end the sentence,
    # and only the whitespace tells the two cases apart.
    if text_so_far[-2:-1].isdigit() and text_rest[:1].isdigit():
        return True

    # version number like "...v12." followed by a digit
    if _VERSION_RE.search(text_so_far) and stripped_rest[:1].isdigit():
        return True

    return False


def split_text_into_segments(text: str, splitter_version: int = None) -> list[str]:
    """
    Split `text` at sentence splitters (``.``, ``!``, ``?``, ``:``) into
    segments, under the ruleset `splitter_version` (default: the current
    `SPLITTER_SYNTAX_VERSION`). Splitters stay attached to the preceding
    segment, and the concatenation of the returned segments always equals the
    input text -- including any force-split marker, which is removed only when
    the text is rendered.

    Common to all versions: known abbreviations (see `_STRONG_ABBREVIATIONS` /
    `_WEAK_ABBREVIATIONS`, e.g. ``i.e.``, ``z.B.``, also in spaced form
    ``z. B.``), dots between digits (``100.000``, ``3.14``, ``24.12.2026``) and
    version numbers (``v12.3``) do NOT cause a split.

    Version 1 splits at every other splitter character, whatever follows it.
    Version 2 adds the two rules in `_split_v2` and the `\\@` / `\\~` escapes.
    """
    if not text:
        return []

    if splitter_version is None:
        splitter_version = SPLITTER_SYNTAX_VERSION

    try:
        splitter = _SPLITTERS_BY_VERSION[splitter_version]
    except KeyError:
        raise ValueError(
            f"unknown splitter syntax version: {splitter_version!r} "
            f"(known: {sorted(_SPLITTERS_BY_VERSION)})"
        ) from None

    return splitter(text)


def _assemble_segments(text: str, split_after: list[int]) -> list[str]:
    """Cut `text` after each index in `split_after` (ascending, splitter inclusive)."""
    segments: list[str] = []
    start = 0
    for i in split_after:
        segments.append(text[start : i + 1])
        start = i + 1

    # trailing text (no final splitter)
    if start < len(text):
        segments.append(text[start:])

    return segments


def _split_v1(text: str) -> list[str]:
    """
    Syntax version 1: every splitter character splits, regardless of what
    follows it. Kept reachable because contributions written under it carry
    materialized keys that only these rules reproduce.
    """
    split_after = []
    for i, ch in enumerate(text):
        if ch not in SENTENCE_SPLITTERS:
            continue
        if ch == "." and _is_abbreviation_dot(text[: i + 1], text[i + 1 :]):
            continue
        split_after.append(i)

    return _assemble_segments(text, split_after)


def _split_v2(text: str) -> list[str]:
    """
    Syntax version 2. Two rules on top of version 1, plus one escape:

    * a splitter only splits when whitespace follows it, or when it ends the
      text. This keeps the gender-inclusive colon ("User:innen"), clock times
      ("14:30") and any punctuation glued to the next character in one segment,
      while the useful colon ("Die Streitfrage lautet: Sind X und Y
      vereinbar?") keeps its splitter function. "Ends the text" counts as
      whitespace on purpose: `text` is one html text node, and what follows the
      node boundary is a tag, whose rendered spacing we cannot see from here.

    * a dot directly after a digit never splits. Ordinals ("15. August",
      "3. Platz") are far more common than a sentence ending in a number, and
      the weak-abbreviation rule cannot help -- it only suppresses a split
      before a lowercase continuation, and "August" is uppercase.

    * `FORCE_SPLIT_MARKER` directly in front of a splitter overrides all of
      that, including the abbreviation tables. It is the opt-in for the rare
      sentence that really does end on a number.

    * `SUPPRESS_SPLIT_MARKER` directly in front of a splitter is the opposite:
      that splitter does not split, whatever the rules say. It is the opt-out
      for the abbreviation the tables do not know ("Prof\\~. Mueller") -- they
      never will know all of them.
    """
    split_after = []
    for i, ch in enumerate(text):
        if ch not in SENTENCE_SPLITTERS:
            continue

        marker = text[max(0, i - MARKER_LEN) : i]

        if marker == SUPPRESS_SPLIT_MARKER:
            continue

        if marker != FORCE_SPLIT_MARKER:
            text_rest = text[i + 1 :]
            if text_rest and not text_rest[0].isspace():
                continue
            if ch == ".":
                if text[i - 1 : i].isdigit():
                    continue
                if _is_abbreviation_dot(text[: i + 1], text_rest):
                    continue

        split_after.append(i)

    return _assemble_segments(text, split_after)


_SPLITTERS_BY_VERSION = {
    1: _split_v1,
    2: _split_v2,
}


class ProtoKeyAdder:
    """
    Insert proto-keys (e.g. `::k`) into an html source.

    A proto-key is placed:
      * at the start of each relevant tag that contains direct text content
      * after every sentence splitter inside such a tag

    Abbreviations (`i.e.`, `e.g.`, `z.B.`, `bspw.`, ...) and version numbers
    (`v12.3`) do NOT cause a split (see `split_text_into_segments`).

    No trailing proto-key is inserted if the tag's text content already ends
    with a sentence splitter -- regardless of whether the tag has further
    (non-text) children after that text (e.g. a nested `<ul>`).
    """

    # tags which are considered as containers of segmentable text
    RELEVANT_TAGS = ("h1", "h2", "h3", "h4", "h5", "p", "li", "pre")

    # inline tags which, when they follow a sentence splitter, start a new
    # sentence and therefore need a preceding proto-key. Other (block-level)
    # child tags such as <ul>, <ol>, <p>, ... do NOT trigger a preceding key.
    INLINE_TAGS = ("em", "strong", "code", "i", "b", "a", "span")

    def __init__(self, html_src: str, prefix: str, splitter_version: int = None):
        self.html_src = html_src
        self.prefix = prefix
        self.splitter_version = splitter_version
        self.proto_key = f" ::{self.prefix} "
        self.soup = BeautifulSoup(html_src, "html.parser")

    def add_proto_keys_to_html(self) -> str:
        for tag in self.soup.find_all(self.RELEVANT_TAGS):
            if self._tag_has_direct_text(tag):
                self._annotate_tag(tag)
            elif self._tag_is_code_block_container(tag):
                # special case: a paragraph whose only meaningful child is a
                # triple-backtick code block. Treat it as a single segment
                # and prepend one proto-key.
                self._prepend_single_proto_key(tag)
            # else: e.g. <li> whose only content is a <p> (the <p> will be
            # handled in its own iteration) -> nothing to do here
        return str(self.soup)

    @staticmethod
    def _tag_has_direct_text(tag: element.Tag) -> bool:
        """True iff `tag` has at least one direct NavigableString child with
        non-whitespace content."""
        for child in tag.children:
            if isinstance(child, element.NavigableString) and child.strip():
                return True
        return False

    @staticmethod
    def _tag_is_code_block_container(tag: element.Tag) -> bool:
        """True iff `tag` contains a direct triple-backtick code child and no
        other meaningful text/tag children.

        This handles the case ``<p><code class="triple_backticks">...</code></p>``
        which has no direct text but logically represents one segment.
        """
        has_code_block = False
        for child in tag.children:
            if isinstance(child, element.Tag):
                classes = child.get("class") or []
                if child.name == "code" and "triple_backticks" in classes:
                    has_code_block = True
                    continue
                # any other tag disqualifies this as a pure code-block container
                return False
            # NavigableString: whitespace is OK, non-whitespace is not (would
            # already have been caught by `_tag_has_direct_text`)
            if isinstance(child, element.NavigableString) and child.strip():
                return False
        return has_code_block

    def _prepend_single_proto_key(self, tag: element.Tag) -> None:
        """Insert a single leading proto-key at the start of ``tag``."""
        tag.insert(0, element.NavigableString(self.proto_key.lstrip()))

    def _annotate_tag(self, tag: element.Tag) -> None:
        """
        Rewrite the direct children of `tag` by inserting proto-keys.

        Strategy:
          * iterate over direct children;
          * for each NavigableString: segment it and intersperse proto-keys;
          * non-text children (nested tags) are kept as-is;
          * exactly one leading proto-key is placed at the start of the tag;
          * a trailing proto-key is only kept if the last text segment does
            NOT end with a sentence splitter.
        """
        original_children = list(tag.children)
        tag.clear()

        # new children built up incrementally; we always start with a leading
        # proto-key (stripped of the leading space -- the key is at position 0)
        new_children: list = [self.proto_key.lstrip()]

        # track whether the last text segment we emitted ends with a splitter;
        # used to decide whether a proto-key should precede the next segment
        # and whether to drop a trailing key at the very end
        last_text_ends_with_splitter = False

        # index of the last text segment we actually emitted (in new_children);
        # used to drop a trailing proto-key after the final segment
        last_segment_idx: int | None = None

        for child in original_children:
            if isinstance(child, element.Tag):
                # non-text child (inline tag like <em>, <strong>, <code>, or
                # a nested block like <ul>): keep unchanged.
                # If the preceding text segment ended with a sentence
                # splitter, the inline tag starts a new sentence and we
                # emit a separator proto-key before it. Block-level nested
                # tags (e.g. <ul>) are handled by the trailing-key cleanup
                # below since they are typically the last child.
                # TODO: sentence splitters INSIDE inline tags currently do
                # not create a segment.
                if last_text_ends_with_splitter and child.name in self.INLINE_TAGS:
                    new_children.append(self.proto_key)
                    last_text_ends_with_splitter = False
                new_children.append(child)
                continue

            assert isinstance(child, element.NavigableString)
            segments = split_text_into_segments(str(child), self.splitter_version)
            if not segments:
                continue

            for i, seg in enumerate(segments):
                if seg.strip() == "":
                    # whitespace-only segment (e.g. trailing space after the
                    # last sentence splitter): keep the whitespace to preserve
                    # text identity, but do NOT emit a separator proto-key
                    # for it.
                    new_children.append(element.NavigableString(seg))
                    continue
                if i > 0:
                    # separator between segments: proto-key
                    new_children.append(self.proto_key)
                new_children.append(element.NavigableString(seg))
                last_segment_idx = len(new_children) - 1
                last_text_ends_with_splitter = seg.rstrip().endswith(SENTENCE_SPLITTERS)

        # if the final text segment ends with a sentence splitter we do NOT
        # want a trailing proto-key. That case can only occur if the leading
        # proto-key we prepended is the only key and the tag has no segments
        # after nested tags -- handled implicitly because we never append a
        # trailing key. But we may need to drop a separator key that was
        # followed by only short / no further content.
        #
        # Concretely, drop a trailing proto-key at the very end of the tag
        # (i.e. if the last element is a proto-key string).
        while new_children and new_children[-1] == self.proto_key:
            new_children.pop()

        # Edge case: a tag that consists only of nested tags with no direct
        # text -> we should not have been called (filtered in caller), but
        # be defensive: if we emitted only the leading key and nothing else,
        # drop it.
        if len(new_children) == 1 and new_children[0] == self.proto_key.lstrip():
            new_children = []

        # Drop the leading proto-key if the first real segment already starts
        # with whitespace AND the tag originally started with whitespace --
        # preserves byte-identical output w.r.t. the previous implementation.
        # (no-op otherwise)

        tag.extend(new_children)

        # silence unused-variable warnings in analyzers
        _ = last_segment_idx, last_text_ends_with_splitter
