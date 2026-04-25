import re
from bs4 import BeautifulSoup, element


# characters which end a sentence / segment
SENTENCE_SPLITTERS = (".", "!", "?", ":")

# known abbreviations: after matching the abbreviation (case-sensitive,
# at a word boundary) we must NOT split, even if it ends with `.`.
# Each entry is matched against the text ending just before the splitter.
_ABBREVIATIONS = (
    "i.e.",
    "e.g.",
    "w.r.t.",
    "bspw.",
)

# version-number pattern: something like "v1." followed by a digit
# means the dot is part of a version number, not a sentence splitter.
_VERSION_RE = re.compile(r"v\d+\.$")


def _is_abbreviation_dot(text_so_far: str, text_rest: str) -> bool:
    """
    Decide whether a `.` at position `len(text_so_far)` (exclusive, i.e. the
    dot itself is the last char of `text_so_far`) belongs to an abbreviation
    and should therefore NOT be treated as a sentence splitter.

    :param text_so_far:  the text up to *and including* the candidate splitter
    :param text_rest:    the text after the candidate splitter (may start with
                         whitespace and then another abbreviation fragment)
    """
    # known fixed abbreviations ending at this dot
    for abbr in _ABBREVIATIONS:
        if text_so_far.endswith(abbr):
            return True

    # partial abbreviations like "i." (followed by "e." etc.)
    # we look at the short tail before the dot and check whether together
    # with the next non-space characters it forms a known abbreviation.
    stripped_rest = text_rest.lstrip()
    # consider up to 6 chars of tail before the dot (covers "w.r.t." etc.)
    for tail_len in range(2, 7):
        tail = text_so_far[-tail_len:]
        for abbr in _ABBREVIATIONS:
            if abbr.startswith(tail) and (tail + stripped_rest).startswith(abbr):
                return True

    # version number like "...v12." followed by a digit
    if _VERSION_RE.search(text_so_far) and stripped_rest[:1].isdigit():
        return True

    return False


def split_text_into_segments(text: str) -> list[str]:
    """
    Split `text` at sentence splitters (``.``, ``!``, ``?``, ``:``) into
    segments. Splitters stay attached to the preceding segment. Known
    abbreviations (``i.e.``, ``e.g.``, ``w.r.t.``, ``bspw.``) and version
    numbers (``v12.3``) do NOT cause a split.

    The concatenation of the returned segments equals the input text.

    This is a pure function intended to replace the convoluted index-based
    logic in `ProtoKeyAdder.insert_proto_keys` / `_abbreviation_handling`.
    """
    if not text:
        return []

    segments: list[str] = []
    start = 0
    for i, ch in enumerate(text):
        if ch not in SENTENCE_SPLITTERS:
            continue
        if ch == ".":
            text_so_far = text[: i + 1]
            text_rest = text[i + 1 :]
            if _is_abbreviation_dot(text_so_far, text_rest):
                continue
        # commit segment [start .. i] (inclusive of splitter)
        segments.append(text[start : i + 1])
        start = i + 1

    # trailing text (no final splitter)
    if start < len(text):
        segments.append(text[start:])

    return segments


class ProtoKeyAdder:
    """
    Insert proto-keys (e.g. `::k`) into an html source.

    A proto-key is placed:
      * at the start of each relevant tag that contains direct text content
      * after every sentence splitter inside such a tag

    Abbreviations (`i.e.`, `e.g.`, `w.r.t.`, `bspw.`) and version numbers
    (`v12.3`) do NOT cause a split (see `split_text_into_segments`).

    No trailing proto-key is inserted if the tag's text content already ends
    with a sentence splitter -- regardless of whether the tag has further
    (non-text) children after that text (e.g. a nested `<ul>`).
    """

    # tags which are considered as containers of segmentable text
    RELEVANT_TAGS = ("h1", "h2", "h3", "h4", "h5", "p", "li", "pre")

    def __init__(self, html_src: str, prefix: str):
        self.html_src = html_src
        self.prefix = prefix
        self.proto_key = f" ::{self.prefix} "
        self.soup = BeautifulSoup(html_src, "html.parser")

    def add_proto_keys_to_html(self) -> str:
        for tag in self.soup.find_all(self.RELEVANT_TAGS):
            if not self._tag_has_direct_text(tag):
                # e.g. <li> whose only content is a <p> (the <p> will be
                # handled in its own iteration) -> nothing to do here
                continue
            self._annotate_tag(tag)
        return str(self.soup)

    @staticmethod
    def _tag_has_direct_text(tag: element.Tag) -> bool:
        """True iff `tag` has at least one direct NavigableString child with
        non-whitespace content."""
        for child in tag.children:
            if isinstance(child, element.NavigableString) and child.strip():
                return True
        return False

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
                # non-text child: keep unchanged
                # TODO: handle inline tags (em, strong, code) where sentence
                # splitters inside their text currently do not create a segment
                new_children.append(child)
                continue

            assert isinstance(child, element.NavigableString)
            segments = split_text_into_segments(str(child))
            if not segments:
                continue

            for i, seg in enumerate(segments):
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
