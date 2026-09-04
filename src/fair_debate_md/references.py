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

Canonical form: a word reference that covers *every* word of its segment says
exactly what the plain segment reference says, so it is not a form of its own --
"a1_1-7b" on a seven-word segment a1 is written "a1b". `canonical_reference_key`
folds the equivalent spelling away and `validate_reference(..., require_canonical=True)`
refuses it, so that a party cannot answer one segment twice by spelling the same
reference two ways. Partial overlap stays allowed on purpose: a party that
answered "a5-8" may still answer "a5", and "a7_1-3" and "a7_4-8" are two
statements about two different pieces of text.

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

import difflib
import re
from dataclasses import dataclass


# lenient unit pattern: used to decompose keys into units. Strict semantic
# checks (start < end, no range+word combination) happen in `parse_key_unit`.
KEY_UNIT_PATTERN = r"[a-z]+\d+(?:-\d+)?(?:_\d+(?:-\d+)?)?"
key_regex = re.compile(KEY_UNIT_PATTERN)

# A complete contribution key: the units naming what is answered, then the bare
# role-token of the answering party -- "a" (an opening), "a5b", "a3-6b", "a7_7-12f",
# "a3-6b1-2h".
#
# This is the ONE place the shape of a key is written down. Anything that has to
# recognize a key composes it from here instead of spelling out a character class of
# its own: `core._ctb_rel_path_regex` used to say `[a-z0-9]+`, which silently excluded
# every range-referencing key, and nothing noticed because such a key then looks like a
# file that is none of the reader's business. Keys are lowercase by construction, so the
# class is `a-z` and not `a-zA-Z`.
CONTRIBUTION_KEY_PATTERN = r"(?:" + KEY_UNIT_PATTERN + r")*[a-z]+"

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


def _resolve_code_placeholders(parent_md_with_real_keys: str, code_contents: dict = None) -> str:
    """
    The parent's markdown with its code placeholders put back, i.e. the text word
    positions are counted against (relevant for not-yet-committed contributions,
    whose source still carries the placeholders).
    """
    md_src = parent_md_with_real_keys
    if code_contents:
        for placeholder, content in code_contents.items():
            md_src = md_src.replace(placeholder, content)
    return md_src


def _last_reference_unit(ctb_key: str) -> tuple[KeyUnit, str] | None:
    """
    The unit of `ctb_key` that names what is answered, together with the key
    prefix its segment numbers are counted in ("a5-7b2c1_3-5d" -> the unit
    "c1_3-5" and the prefix "a5-7b2c"). None if there is nothing to resolve:
    an opening contribution, or a plain reference, which needs no parent text.
    """
    parts = decompose_key(ctb_key)
    if len(parts) < 2:
        return None
    ref_unit = parse_key_unit(parts[-2])
    if not (ref_unit.is_segment_range or ref_unit.has_word_ref):
        return None
    return ref_unit, "".join(parts[:-2]) + ref_unit.token


def _is_full_span_word_ref(ref_unit: KeyUnit, n_words: int) -> bool:
    """
    Whether `ref_unit`'s word reference covers every word of its segment, i.e.
    states what the plain segment reference already states. True for "a1_1-7" on
    a seven-word segment, and for "a1_1" on a one-word segment.
    """
    if not ref_unit.has_word_ref or ref_unit.word_start != 1:
        return False
    last_word = ref_unit.word_end if ref_unit.word_end is not None else ref_unit.word_start
    return last_word == n_words


def canonical_reference_key(
    ctb_key: str, parent_md_with_real_keys: str, code_contents: dict = None
) -> str:
    """
    Return `ctb_key` with a full-span word reference folded into the plain
    segment reference it is equivalent to ("a1_1-7a" -> "a1a" when segment a1 has
    seven words). Every other key is returned unchanged.

    Motivation: the rule "one answer per (segment, party)" is enforced by the key
    -- one key, one file, one answer. A word reference spanning the whole segment
    is a *different key* for the *same statement*, so without this fold a party
    could answer the same segment twice by selecting all of its words instead of
    clicking the segment (exactly what happened in d31-ice-cream: "a1_1-7a" next
    to "a1a"). Reference-scoped overlap is deliberately kept: partial word
    references and segment ranges name different pieces of text and stay distinct.

    Only the last unit is folded. The inner units are the identity of
    contributions that already exist and must never be rewritten.

    An unresolvable key (segment missing from the parent) is returned unchanged;
    `validate_reference` is the place that reports it, with a better message.
    """
    resolved = _last_reference_unit(ctb_key)
    if resolved is None:
        return ctb_key
    ref_unit, prefix = resolved
    if not ref_unit.has_word_ref:
        return ctb_key

    md_src = _resolve_code_placeholders(parent_md_with_real_keys, code_contents)
    segment_key = f"{prefix}{ref_unit.seg_start}"
    try:
        n_words = len(get_segment_words(md_src, segment_key))
    except ValueError:
        return ctb_key
    if not _is_full_span_word_ref(ref_unit, n_words):
        return ctb_key

    parts = decompose_key(ctb_key)
    parts[-2] = f"{ref_unit.token}{ref_unit.seg_start}"
    return "".join(parts)


def validate_reference(
    ctb_key: str,
    parent_md_with_real_keys: str,
    code_contents: dict = None,
    require_canonical: bool = False,
):
    """
    Validate the reference encoded in the last reference unit of `ctb_key`
    against the parent contribution's markdown source. Only range and word
    references are checked (plain references keep the legacy behavior).

    :param code_contents:   optional mapping of code placeholders to their
                            original content (relevant for not-yet-committed
                            contributions whose source still contains
                            placeholders)
    :param require_canonical:
                            also refuse a reference that is merely a second
                            spelling of a simpler one (a word reference covering
                            the whole segment, see `canonical_reference_key`).
                            Off by default *on purpose*: this runs on every repo
                            the loader opens, and a rule that was not in force
                            when a contribution was written must not make an
                            existing debate unreadable. Callers that mint a NEW
                            key -- the platform and the fixture builder -- pass
                            True, so the non-canonical form cannot enter a repo
                            in the first place.

    Raises ValueError with a descriptive message on inconsistency.
    """
    resolved = _last_reference_unit(ctb_key)
    if resolved is None:
        return
    ref_unit, prefix = resolved
    md_src = _resolve_code_placeholders(parent_md_with_real_keys, code_contents)

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
        if require_canonical and _is_full_span_word_ref(ref_unit, len(words)):
            canonical = canonical_reference_key(ctb_key, parent_md_with_real_keys, code_contents)
            msg = (
                f"invalid reference '{ctb_key}': the word reference covers all "
                f"{len(words)} words of segment '{segment_key}' and therefore says what "
                f"the plain segment reference says -- write it as '{canonical}'"
            )
            raise ValueError(msg)


def get_rendered_word_offsets(segment_text: str, words: list[str]) -> list[int]:
    """
    Align raw-markdown words (as returned by `get_segment_words`) with their
    rendered occurrence in `segment_text`, the rendered plain-text content of
    the same segment (i.e. what `element.textContent` gives the frontend).

    Coordinate system: character offsets into `segment_text`, i.e. the same
    string this function receives -- callers must pass the exact rendered
    text they later index into.

    Returns a flat list ``[start0, end0, start1, end1, ...]``, one
    ``(start, end)`` pair per entry in `words`, in the same order. Each pair
    is a half-open interval (``segment_text[start:end]``).

    Invariants (guaranteed for arbitrary input):

    - ``len(result) == 2 * len(words)``, always.
    - offsets are monotonically non-decreasing, pairs never overlap, and all
      values lie in ``[0, len(segment_text)]``.
    - deterministic: depends only on the two arguments, in order.

    Alignment algorithm: a single left-to-right scan that consumes `words`
    and `segment_text` in lockstep. Before each word, leading whitespace in
    `segment_text` is skipped (words are separated by exactly the renderer's
    inter-word whitespace). A word is then matched character by character
    against `segment_text` starting at the current position: matching
    characters advance both pointers, and any non-matching raw-word character
    is skipped without advancing the rendered-text position -- covering both
    markdown markup (``*_`[]()#>!``, invisible in rendered text) and content
    the renderer drops entirely, such as the URL part of ``[text](url)``.
    This makes the function robust to markup that spans word or tag
    boundaries (``**wichtig**e`` -> one interval covering ``wichtige``)
    without needing to parse markdown itself.

    Null-interval behavior: if no character of a word could be matched (e.g.
    ``![alt](url)``, which renders to no text at all), the word gets an empty
    interval ``[p, p]`` at the end of the previous word's interval (0 if it is
    the first word) rather than a guessed span -- callers must expect and
    handle zero-length intervals.

    Alignment algorithm: global sequence alignment via
    ``difflib.SequenceMatcher`` (``autojunk=False``), not a local scan. A
    "probe" string is built by joining `words` with single spaces; the
    matcher aligns `probe` against `segment_text` as a whole and returns
    matching blocks that are monotonic and internally consistent by
    construction. Each word's known character range in `probe` is then
    intersected with those blocks to obtain the set of its characters that
    have a counterpart in `segment_text`; the word's interval is the span
    from the first to the last such counterpart. A final pass clamps offsets
    to be monotonically non-decreasing and non-overlapping, guarding against
    degenerate inputs.

    This is deliberately global rather than local: a purely local,
    character-by-character scan has to guess, for each raw character that
    fails to match, whether it is markup to skip (advance the raw pointer,
    hold the rendered pointer) or content the renderer dropped outright --
    and a wrong guess either fractures one word into several null intervals
    (e.g. "**wichtig**e" rendered with prettify-injected whitespace between
    "wichtig" and "e") or lets the raw pointer run on and accidentally
    resync with a *later* word's rendered text (e.g. the URL of
    "[text](url)" bleeding into the next word). Global alignment avoids both
    failure modes: it considers the whole string at once, so an unmatched
    stretch in the middle of one word does not have to be classified at all
    -- it simply contributes no mapped characters -- and it cannot let one
    word's unmatched tail "consume" a later word's rendered occurrence,
    because the matcher already committed to the overall best alignment
    before any per-word interval is read off.
    """
    n = len(segment_text)
    if not words:
        return []

    # `probe`: raw words joined by single spaces, and each word's character
    # range [p_start, p_end) within `probe` (computed by counting lengths,
    # not by searching).
    word_ranges: list[tuple[int, int]] = []
    pos = 0
    for i, word in enumerate(words):
        if i:
            pos += 1
        word_ranges.append((pos, pos + len(word)))
        pos += len(word)
    probe = " ".join(words)

    matcher = difflib.SequenceMatcher(None, probe, segment_text, autojunk=False)
    blocks = [b for b in matcher.get_matching_blocks() if b.size > 0]

    # For each word, find the min/max segment_text index reached by mapping
    # its probe range through the matching blocks (partial mapping: only
    # characters inside `equal` blocks are mapped at all).
    mapped_min: list[int | None] = [None] * len(words)
    mapped_max: list[int | None] = [None] * len(words)

    block_idx = 0
    for word_idx, (p_start, p_end) in enumerate(word_ranges):
        # blocks are sorted by `a`; once a block ends before the current
        # word starts, it is behind every later (larger) word range too.
        while block_idx < len(blocks) and blocks[block_idx].a + blocks[block_idx].size <= p_start:
            block_idx += 1
        j = block_idx
        while j < len(blocks) and blocks[j].a < p_end:
            a, b, size = blocks[j]
            lo = max(a, p_start)
            hi = min(a + size, p_end)
            if lo < hi:
                seg_lo = b + (lo - a)
                seg_hi = b + (hi - a) - 1
                if mapped_min[word_idx] is None or seg_lo < mapped_min[word_idx]:
                    mapped_min[word_idx] = seg_lo
                if mapped_max[word_idx] is None or seg_hi > mapped_max[word_idx]:
                    mapped_max[word_idx] = seg_hi
            j += 1

    offsets: list[int] = [0] * (2 * len(words))
    last_end = 0
    for word_idx in range(len(words)):
        if mapped_min[word_idx] is None:
            start = end = last_end
        else:
            start = mapped_min[word_idx]
            end = mapped_max[word_idx] + 1
        offsets[2 * word_idx] = start
        offsets[2 * word_idx + 1] = end
        last_end = end

    # Enforce monotonicity and non-overlap explicitly, so the contract holds
    # even if the mapping above ever produced a locally-plausible but
    # globally-inconsistent interval for degenerate input.
    prev_end = 0
    for word_idx in range(len(words)):
        start, end = offsets[2 * word_idx], offsets[2 * word_idx + 1]
        start = max(start, prev_end)
        end = max(end, start)
        offsets[2 * word_idx], offsets[2 * word_idx + 1] = start, end
        prev_end = end
    for i, value in enumerate(offsets):
        offsets[i] = max(0, min(n, value))

    return offsets
