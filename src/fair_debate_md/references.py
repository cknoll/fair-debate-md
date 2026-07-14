"""
Key grammar and reference handling for *flexible references*: segment ranges
and word-level references. See docs/flexible_references_concept.md for the
full design rationale.

Grammar
-------

A key is a sequence of *units*. Each unit is one of::

    <role-token><seg>              plain segment reference, e.g. "a5"
    <role-token><s>-<e>            segment range with s < e, e.g. "a5-7"
    <role-token><seg>_<w>          single-word reference, e.g. "a7_4"
    <role-token><seg>_<v>-<w>      word range with v < w, e.g. "a7_4-8"
    <role-token>                   bare token (only allowed as final unit
                                   of a contribution key), e.g. "b" in "a5-7b"

Semantics:

- "a5-7b":   party b answers segments 5 to 7 (inclusive) of contribution "a".
- "a7_4-8b": party b answers words 4 to 8 (inclusive, 1-based) of segment a7.
- Combining a segment range with a word reference in one unit ("a5-7_4") is
  invalid: a word reference always targets exactly one segment.
- Range and word references may occur in *inner* units of deeper keys
  (they are inherited by all descendant keys), e.g. "a5-7b2c1_3-5d".

Anchor rule: a contribution whose reference unit is a range or word reference
is *anchored* at the (single) last referenced segment -- "a5-7b" is anchored
at segment "a7", "a7_4-8b" at "a7". The anchor determines where the
contribution is attached in the rendered tree.

Word tokenizer (FROZEN SPECIFICATION)
-------------------------------------

Word references are counted against the *raw markdown source* of the target
segment (the ``md_with_real_keys`` representation stored in the debate repo),
so that references can be verified independently of the platform by reading
the plain ``.md`` files. The rules are deliberately dumb and MUST NOT be
"improved" later: contributions are immutable, and any change to the
tokenizer would silently shift all existing word references.

1. The *segment source* is the substring of ``md_with_real_keys`` between the
   end of the segment's key marker (e.g. ``::a7``) and the start of the next
   key marker of the same contribution, or the end of the text.
2. If the segment source contains a newline and the part after the *last*
   newline consists only of whitespace and markdown line prefixes
   (``-``, ``*``, ``+``, ``N.``, ``#``..``######``, ``>``), that trailing
   part (including the newline) is discarded -- it is the structural prefix
   of the *next* block, not content of this segment.
3. *Words* are the maximal runs of non-whitespace characters of the segment
   source (``str.split()``), counted 1-based.

Consequences (intentional): markup characters stay attached to their word
("**bold**" is one word), inline markdown like "[link](url)" contributes the
words of its raw form, and code-block segments have their code tokens counted
as words.
"""

import re
from dataclasses import dataclass


# lenient unit pattern: used to decompose keys into units. Strict semantic
# checks (start < end, no range+word combination) happen in `parse_key_unit`.
key_regex = re.compile(r"[a-z]+\d+(?:-\d+)?(?:_\d+(?:-\d+)?)?")

_STRICT_UNIT_RE = re.compile(r"([a-z]+)(\d+)(?:-(\d+))?(?:_(\d+)(?:-(\d+))?)?$")
_BARE_TOKEN_RE = re.compile(r"[a-z]+$")

# splits a segment key like "a5-7b12" into contribution prefix ("a5-7b") and
# segment number ("12")
_SEGMENT_KEY_SPLIT_RE = re.compile(r"(.*[a-z])(\d+)$")

# trailing structural prefix of the *next* block (see tokenizer rule 2)
_STRUCTURAL_TAIL_RE = re.compile(r"\n[ \t]*(?:(?:[-*+]|\d+\.|#{1,6}|>)[ \t]*)*$")


@dataclass
class KeyUnit:
    """Parsed form of one key unit, see module docstring for the grammar."""

    token: str
    seg_start: int | None = None
    seg_end: int | None = None
    word_start: int | None = None
    word_end: int | None = None

    @property
    def is_bare(self) -> bool:
        return self.seg_start is None

    @property
    def is_segment_range(self) -> bool:
        return self.seg_end is not None

    @property
    def has_word_ref(self) -> bool:
        return self.word_start is not None

    @property
    def anchor_segment_number(self) -> int:
        """Number of the segment this unit is anchored at (see anchor rule)."""
        return self.seg_end if self.seg_end is not None else self.seg_start


def parse_key_unit(unit: str) -> KeyUnit:
    """
    Strictly parse one key unit. Raises ValueError for syntactically or
    semantically invalid units (range+word combination, degenerate or
    reversed ranges, zero-based positions in ranges/word references).
    """
    if _BARE_TOKEN_RE.fullmatch(unit):
        return KeyUnit(token=unit)

    m = _STRICT_UNIT_RE.fullmatch(unit)
    if m is None:
        raise ValueError(f"invalid key unit: '{unit}'")

    token, seg_start, seg_end, word_start, word_end = m.groups()
    res = KeyUnit(
        token=token,
        seg_start=int(seg_start),
        seg_end=int(seg_end) if seg_end is not None else None,
        word_start=int(word_start) if word_start is not None else None,
        word_end=int(word_end) if word_end is not None else None,
    )

    if res.is_segment_range and res.has_word_ref:
        msg = f"invalid key unit '{unit}': segment range and word reference must not be combined"
        raise ValueError(msg)
    if res.is_segment_range:
        if res.seg_start < 1:
            raise ValueError(f"invalid key unit '{unit}': segment range must be 1-based")
        if res.seg_end <= res.seg_start:
            msg = f"invalid key unit '{unit}': range end must be greater than range start"
            raise ValueError(msg)
    if res.has_word_ref:
        if res.word_start < 1:
            raise ValueError(f"invalid key unit '{unit}': word positions are 1-based")
        if res.word_end is not None and res.word_end <= res.word_start:
            msg = f"invalid key unit '{unit}': word range end must be greater than range start"
            raise ValueError(msg)

    return res


def decompose_key(key):
    """
    :param key:     str like "a4b12a2b" or "a5-7b2c1_3-5d"
    """
    # to match the parts with an easy regex we append a digit and remove it later
    parts = key_regex.findall(f"{key}0")

    if parts:
        # remove the trailing 0 from last part
        assert parts[-1][-1] == "0"
        parts[-1] = parts[-1][:-1]

    return parts


def is_valid_key(key):
    parts = decompose_key(key)
    if not parts or "".join(parts) != key:
        return False
    for part in parts:
        try:
            parse_key_unit(part)
        except ValueError:
            return False
    # bare tokens are only allowed as the final unit
    for part in parts[:-1]:
        if _BARE_TOKEN_RE.fullmatch(part):
            return False
    return True


def get_anchor_segment_key(ctb_key: str) -> str | None:
    """
    Return the key of the segment a contribution is anchored at (the segment
    after which it is rendered), or None for the root contribution or
    unparsable keys.

    Examples: "a5b" -> "a5";  "a5-7b" -> "a7";  "a7_4-8b" -> "a7";
              "a5-7b2c" -> "a5-7b2" (segment ids inherit inner references).
    """
    parts = decompose_key(ctb_key)
    if len(parts) < 2:
        return None
    try:
        ref_unit = parse_key_unit(parts[-2])
    except ValueError:
        return None
    return "".join(parts[:-2]) + f"{ref_unit.token}{ref_unit.anchor_segment_number}"


def get_first_referenced_segment_key(ctb_key: str) -> str | None:
    """
    Return the key of the *first* referenced segment ("a5-7b" -> "a5").
    For plain and word references this equals the anchor segment.
    """
    parts = decompose_key(ctb_key)
    if len(parts) < 2:
        return None
    try:
        ref_unit = parse_key_unit(parts[-2])
    except ValueError:
        return None
    return "".join(parts[:-2]) + f"{ref_unit.token}{ref_unit.seg_start}"


def get_parent_contribution_key(ctb_key: str) -> str | None:
    """
    Return the key of the contribution which contains the referenced
    segment(s). Examples: "a5-7b" -> "a"; "a1c3aa" -> "a1c"; "a" -> None.
    """
    parts = decompose_key(ctb_key)
    if len(parts) < 2:
        return None
    try:
        ref_unit = parse_key_unit(parts[-2])
    except ValueError:
        return None
    return "".join(parts[:-2]) + ref_unit.token


def get_segment_source(md_with_real_keys: str, segment_key: str) -> str:
    """
    Extract the raw markdown source of one segment (tokenizer rules 1 and 2,
    see module docstring).

    :param md_with_real_keys:   markdown source containing ``::<key>`` markers
    :param segment_key:         e.g. "a7" or "a5-7b2"
    """
    m = _SEGMENT_KEY_SPLIT_RE.fullmatch(segment_key)
    if m is None:
        raise ValueError(f"invalid segment key: '{segment_key}'")
    prefix = m.group(1)

    marker_re = re.compile("::" + re.escape(prefix) + r"\d+")
    matches = list(marker_re.finditer(md_with_real_keys))
    for i, match in enumerate(matches):
        if match.group() != f"::{segment_key}":
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_with_real_keys)
        span = md_with_real_keys[start:end]
        # drop the structural prefix of the next block (rule 2)
        return _STRUCTURAL_TAIL_RE.sub("", span)

    msg = f"segment key '{segment_key}' not found in the given markdown source"
    raise ValueError(msg)


def get_segment_words(md_with_real_keys: str, segment_key: str) -> list[str]:
    """
    Return the list of words of one segment (frozen tokenizer, see module
    docstring). Word references are 1-based indices into this list.
    """
    return get_segment_source(md_with_real_keys, segment_key).split()


def validate_reference(ctb_key: str, parent_md_with_real_keys: str, code_contents: dict = None):
    """
    Validate the reference encoded in the last reference unit of `ctb_key`
    against the parent contribution's markdown source. Only range and word
    references are checked (plain references keep the legacy behavior).

    :param code_contents:   optional mapping of code placeholders to their
                            original content (relevant for not-yet-committed
                            contributions whose source still contains
                            placeholders)

    Raises ValueError with a descriptive message on inconsistency.
    """
    parts = decompose_key(ctb_key)
    if len(parts) < 2:
        return
    ref_unit = parse_key_unit(parts[-2])
    if not (ref_unit.is_segment_range or ref_unit.has_word_ref):
        return

    prefix = "".join(parts[:-2]) + ref_unit.token
    md_src = parent_md_with_real_keys
    if code_contents:
        for placeholder, content in code_contents.items():
            md_src = md_src.replace(placeholder, content)

    for seg_num in sorted({ref_unit.seg_start, ref_unit.anchor_segment_number}):
        marker = f"::{prefix}{seg_num}"
        if not re.search(re.escape(marker) + r"(?!\d)", md_src):
            msg = (
                f"invalid reference '{ctb_key}': referenced segment '{prefix}{seg_num}' "
                "does not exist in the parent contribution"
            )
            raise ValueError(msg)

    if ref_unit.has_word_ref:
        segment_key = f"{prefix}{ref_unit.seg_start}"
        words = get_segment_words(md_src, segment_key)
        last_word = ref_unit.word_end if ref_unit.word_end is not None else ref_unit.word_start
        if last_word > len(words):
            msg = (
                f"invalid reference '{ctb_key}': word position {last_word} exceeds "
                f"the word count ({len(words)}) of segment '{segment_key}'"
            )
            raise ValueError(msg)
