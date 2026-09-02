# Flexible References: Segment Ranges and Word-Level References

Status: backend implemented in `fair-debate-md` (module `references.py`), frontend support
in `fair-debate-web` not yet implemented. This document is the specification and handover
for the frontend work.

## Motivation

Originally a reply always referenced exactly **one** segment. This concept generalizes the
reference in two directions:

1. **Segment ranges** — a reply can reference several sequential segments of one contribution.
2. **Word-level references** — a reply can reference a contiguous word range *within* one segment.

Design decision: the reference information is encoded **in the key itself** (not in metadata).
Rationale: keys stay self-contained and self-describing — from any descendant key one can still
see what the original reply referred to; debates remain verifiable from the raw `.md` files in
the public git repo without running the platform. The price (accepted deliberately): reference
info is frozen into all descendant keys forever; this is unproblematic because committed
contributions are **immutable by design** (a hard project commitment as of this concept).

## Key grammar

A key is a sequence of *units*. Each unit is one of:

| form | meaning | example |
|------|---------|---------|
| `<token><seg>` | plain segment reference | `a5` |
| `<token><s>-<e>` | segment range, `s < e`, inclusive | `a5-7` |
| `<token><seg>_<w>` | single word `w` of the segment | `a7_4` |
| `<token><seg>_<v>-<w>` | word range, `v < w`, inclusive, 1-based | `a7_4-8` |
| `<token>` | bare role-token, only as final unit | the `b` in `a5-7b` |

Lenient decomposition regex (one unit): `[a-z]+\d+(?:-\d+)?(?:_\d+(?:-\d+)?)?`

Additional strict rules (checked by `references.parse_key_unit`):

- Segment range and word reference must **not** be combined in one unit (`a5-7_4` is invalid);
  a word reference always targets exactly one segment. Cross-segment partial references
  ("from mid-a5 to mid-a7") are intentionally **not supported** (round up to full segments).
- Degenerate and reversed ranges are **rejected**, not canonicalized (`a5-5`, `a7-5`, `a7_4-4`),
  so that no two spellings of the same reference can circulate.
- Positions in ranges and word references are 1-based (`a0-3`, `a7_0` are invalid).
- `-` is the uniform range separator (segments and words); `_` introduces the word level.
  Both characters are unproblematic in HTML ids, URLs, filenames, and CSS selectors
  (which is why `..` and `[]` were rejected as syntax).

Examples: `a5-7b` = party b replies to segments 5–7 of contribution `a`.
`a7_4-8b` = party b replies to words 4–8 of segment `a7`. Inner units may carry references
too (inherited by descendants): `a5-7b2c1_3-5d` is valid.

## Semantics

- **Anchor rule:** a contribution is *anchored* at the **last** referenced segment
  (`a5-7b` → anchor `a7`; `a7_4-8b` → anchor `a7`). The anchor determines where the
  contribution is attached/rendered in the tree (below the anchor segment, matching reading
  flow). Helper: `references.get_anchor_segment_key`.
- **Segment ids inherit references:** the segments of contribution `a5-7b` have ids
  `a5-7b1`, `a5-7b2`, … — so the anchor of `a5-7b2c` is `a5-7b2`.
- **Collision semantics (deliberate decision):** keys are unique, but the same party may now
  file several replies with *overlapping* references (`a7b`, `a5-7b` and `a7_2-3b` may coexist).
  This is allowed; moderating redundant replies is a matter of debate culture, not of the
  key system.

## Word tokenizer (FROZEN specification)

Word references are counted against the **raw markdown source** (`md_with_real_keys`, i.e.
the text stored in the debate repo), *not* against rendered text. Rationale: transparency —
references must be verifiable by reading the plain `.md` files in the public git repo,
without running a renderer. This also matches hand-authored contributions (fixtures,
direct git commits).

The rules are deliberately dumb and **MUST NOT be "improved" later**: contributions are
immutable and word positions are *recomputed* on every render (unlike segment keys, which are
materialized into the `.md` files). Any tokenizer change would silently shift all existing
word references. This is the opposite of the sentence-segmentation heuristics
(`SENTENCE_SPLITTERS`, abbreviation lists), which may evolve freely exactly *because*
segment keys are materialized.

1. The **segment source** is the substring of `md_with_real_keys` between the end of the
   segment's key marker (e.g. `::a7`) and the start of the next key marker of the same
   contribution, or the end of the text.
2. If the segment source contains a newline and the part after the **last** newline consists
   only of whitespace and markdown line prefixes (`-`, `*`, `+`, `N.`, `#`…`######`, `>`),
   that trailing part (including the newline) is discarded — it is the structural prefix of
   the *next* block, not content of this segment.
3. **Words** are the maximal runs of non-whitespace characters (`str.split()`), counted
   **1-based**.

Intentional consequences:

- Markup stays attached to its word: `**very important**` = 2 words (`**very`, `important**`).
- Inline markdown contributes its raw form: `[link text](url)` = 2 words (`[link`, `text](url)`).
- Code-block segments have their code tokens (including the ` ``` ` fences) counted as words.
- Whitespace-free scripts (CJK) effectively cannot use word references — accepted limitation.
- A force-split marker (`key_management.FORCE_SPLIT_MARKER`, e.g. `2026\@.`) is part of the
  word it sits in, exactly as `**bold**` is. It carries no whitespace, so it changes no word
  *count* and no position — which is why segmentation could be given an opt-in marker at all
  without touching this specification.

Reference implementation and spec tests: `references.get_segment_words`,
`tests/test_references.py::TestSegmentWords`. The frontend must implement the *identical*
tokenization (trivial by design: whitespace split) plus the segment-source extraction, or
obtain word data from the backend.

## Validation

`DebateDirLoader.load_dir` validates every range/word reference at load time
(`validate_references`); `references.validate_reference` is the underlying function:

- referenced segments (range start and anchor) must exist in the parent contribution;
- word positions must not exceed the word count of the target segment;
- for range/word references a missing parent contribution is a hard error.

Plain references keep the legacy behavior (silently ignored orphans). Syntactically invalid
keys (e.g. degenerate ranges) fail `is_valid_key`; files with such names are ignored by the
loader like any other invalid filename.

## Backend API (fair-debate-md)

All in `fair_debate_md.references` (re-exported via `fair_debate_md.core`):

- `parse_key_unit(unit) -> KeyUnit` — strict parse of one unit; raises `ValueError`.
- `decompose_key(key) -> list[str]` — split key into units (lenient).
- `is_valid_key(key) -> bool` — full syntactic + strict per-unit validation.
- `get_anchor_segment_key(ctb_key)` / `get_first_referenced_segment_key(ctb_key)` /
  `get_parent_contribution_key(ctb_key)`.
- `get_segment_source(md, segment_key)` / `get_segment_words(md, segment_key)`.
- `validate_reference(ctb_key, parent_md, code_contents=None)`.

## Rendered HTML (what the frontend gets)

Contribution divs with range/word references carry data attributes (plain references are
unchanged and carry none):

```html
<div class="contribution level1" id="contribution_a1-2b"
     data-ref-anchor="a2" data-ref-seg-start="a1">…</div>

<div class="contribution level1" id="contribution_a2_2-3c"
     data-ref-anchor="a2" data-ref-words="2-3">…</div>
```

- `data-ref-anchor`: id of the anchor segment (the div is inserted right after it).
- `data-ref-seg-start`: id of the first referenced segment (only for segment ranges).
- `data-ref-words`: `"4"` or `"4-8"` (only for word references).

## Frontend work (fair-debate-web, not yet implemented)

What a frontend session needs to cover (scope to be decided there):

1. **Bleach allowlist:** allow the new `data-ref-*` attributes in `settings.py`, otherwise
   they are stripped from the rendered HTML.
2. **Key charset:** anything that parses/matches keys must accept `-` and `_`:
   URL patterns in `urls.py`, model fields/validators in `models.py` (check max lengths:
   keys get longer), and key handling in `static/core.js` (fold/unfold logic, segment-id
   parsing, `querySelector` calls — `-`/`_` are safe in CSS selectors, that was a criterion).
3. **Reference display:** highlight the referenced range (`data-ref-seg-start` … anchor)
   resp. the referenced words when a contribution is unfolded/hovered. Word highlighting
   requires mapping raw-markdown word indices onto the rendered DOM. Recommended approach:
   compute the raw↔rendered word alignment **server-side** (the pipeline has both raw
   source and HTML per segment; ship only divergent offsets), keep JS dumb. Note that a
   word can span inline-tag boundaries (`**wichtig**e` renders as one word in two DOM
   nodes) — highlighting must wrap partial text nodes.
4. **Reply UI:** allow selecting multiple sequential segments (→ range key) and a word
   range within one segment (mouse selection snapped to word boundaries → `_v-w` key).
   The word indices must be computed against the **raw** segment source (see tokenizer
   spec) — the selection UI needs the alignment from point 3 in reverse.
5. **Uniqueness:** the DB-level constraint "one reply per (segment, party)" becomes
   "one reply per (reference, party)" — overlapping references by the same party are
   allowed by design.
6. **Discoverability (optional, later):** a range reply is only rendered at its anchor;
   segments inside the range other than the anchor could get a marker so the reply is
   discoverable from them.

## Test fixtures

`d32-overlapping-refs` is the fixture for this concept: a toy dispute whose replies
deliberately overlap, covering a segment range (`a3-6b`), a narrow reply inside a range
(`a4c`), two partially overlapping ranges (`a5-8d`), full-segment and word-range replies
to the same segment (`a7e`, `a7_7-12f`, `a7_10-16g`) and a range one level down
(`a3-6b1-2h`). The md-side integration tests additionally build temporary debates, see
`tests/test_references.py::TestDebateIntegration`.

Its source is `fixtures/repo-preparation/d32-overlapping-refs__plain/source.md`. Since
2026-09-02 the references are written there as quotes rather than as indices: the source
format spells a segment range as `answers_from=`/`answers_to=` and a word range as
`answers=` plus `answers_words=`, and derives the positions through
`references.get_segment_words()`, i.e. through the tokenizer frozen below. Adding a
fixture changes the fixture set that `fair-debate-web`'s `initializefixtures` and test
counters depend on — coordinate with the web repo.

## Word offset table

Status: backend implemented and wired into the render pipeline (`DebateDirLoader.word_offsets`,
computed in `_compute_word_offsets`); no frontend consumer yet. This section is the handover for
the raw↔rendered word alignment referenced in point 3 of "Frontend work" above; details of *why*
this particular algorithm was chosen and what it does and does not cover are in
`word_offsets_report.md` at the repo root.

**The contract.** `ddl.word_offsets: dict[str, list[int]]`. Keys are segment keys (`a7`, `a3-6b2`,
…) for **all** segments of the debate, not only referenced ones. Each value is a flat list
`[start0, end0, start1, end1, …]` — one `[start, end)` pair per raw word of that segment, in the
same order as `references.get_segment_words(md, segment_key)`.

**Coordinate system and the critical condition.** The offsets are character offsets into the
`textContent` of the *emitted* segment element — exactly the string
`document.getElementById("a7").textContent` returns in the browser. They are explicitly **not**
offsets into the Markdown source and **not** offsets into any intermediate HTML string.
`BeautifulSoup(..., prettify=True)` (used for `final_html`) inserts whitespace at tag boundaries,
and this whitespace is real `textContent` once delivered — so the offsets are deliberately
computed against the *final* delivered string, including that injected whitespace when it falls
inside a word's interval (see "Words across tag boundaries" below).

**Invariants.** For segment key `k` with raw words `words = get_segment_words(md, k)` and text
`text = document.getElementById(k).textContent`:

- pair count is exact: `len(word_offsets[k]) == 2 * len(words)`, no more, no fewer;
- offsets are non-decreasing across the whole list and non-overlapping between consecutive pairs;
- every offset lies in `[0, len(text)]`.

**Null intervals.** A raw word that has no visible rendered counterpart — an image reference
(`![alt](url)`) or a standalone thematic break (`---` on its own line, i.e. `<hr>`) — gets a
zero-length interval `[p, p]` at the plausible position (right after the previous word's end, or
`0` for the first word). The pair count stays correct: the word is still counted, it just maps to
an empty slice. The frontend should not highlight anything for such a word, but must **not** skip
it when advancing through the numbering — it still occupies its 1-based word index.

**Words across tag boundaries.** `**wichtig**e` is **one** raw word but renders across two inline
tags (`<strong>wichtig</strong>e`), with prettify whitespace injected between them. It still maps
to **one** contiguous interval spanning that whitespace, because the alignment works against
`textContent`, which has no notion of tags — `<strong>` and `</strong>` simply do not appear in
the string being indexed. Highlighting such a word in the DOM therefore requires wrapping a
partial range across two (or more) text nodes, not just one.

**Example.** `d32-overlapping-refs`, segment `a7`, reference key `a7_7-12` (words 7–12,
1-based, end-inclusive) targets the raw words `cost us maybe sixty euros once,`. Given
`pairs = word_offsets["a7"]`, group it into per-word pairs first —
`word_pairs = list(zip(pairs[0::2], pairs[1::2]))` — then the 1-based end-inclusive range
`[start, end]` maps to the plain Python slice `word_pairs[start - 1 : end]` (this is the
conversion the frontend needs: `word_pairs[7 - 1 : 12]` selects exactly words 7 through 12).
Measured for this fixture: `word_pairs[6:12] == [(31, 35), (36, 38), (39, 44), (45, 50),
(51, 56), (57, 62)]`, and `text[31:35] == "cost"`, …, `text[57:62] == "once,"`; the combined
highlighted span is `text[31:62] == "cost us maybe sixty euros once,"` — the first selected
pair's start to the last selected pair's end, since pairs in a range are always contiguous and
non-overlapping.
