# Word offset table — implementation report

Summary of the run that added `references.get_rendered_word_offsets` and wired it into
`DebateDirLoader.word_offsets` (`core.py`). Companion to the "Word offset table" section in
`docs/flexible_references_concept.md`, which states the contract for the frontend; this report
covers the algorithm choice, coverage, measured sizes, and open items.

## Chosen alignment algorithm and why

`get_rendered_word_offsets` aligns `probe = " ".join(words)` (the raw words) against
`segment_text` (the delivered `textContent`) using **global sequence alignment**
(`difflib.SequenceMatcher(None, probe, segment_text, autojunk=False)`), then intersects each
word's range in `probe` with the matcher's `get_matching_blocks()`. This replaced an earlier
**local greedy two-pointer scan** that walked both strings left to right, consuming raw
characters whenever they did not match the rendered text. That local scan had two concrete
defects that forced the switch:

1. **Cascade on `**wichtig**e`.** `prettify=True` injects whitespace between `wichtig` and `e`
   because they end up in separate inline tags. The local scan's forward pointer, once it hit
   this unexpected whitespace mid-word, had no way to resynchronize — it degraded to consuming
   raw characters as "unmatched" for the rest of the word, and every word *after* it in the
   segment followed the same misaligned pointer, collapsing to null intervals. One prettify
   artifact took out the rest of the segment.
2. **Runaway on `[link text](url)`.** The scan's permissive skip-non-matching-raw-characters
   step let `](http://example.org)` — which has no counterpart in the rendered text at all — run
   forward until it coincidentally matched the *next* word's rendered characters, attributing
   part of the URL's tail to the wrong word.

The global matcher solves both by construction: it computes the matching blocks for the *whole*
`probe`/`segment_text` pair in one pass, independent of any per-word left-to-right walk. A gap in
one word's mapping (missing markup characters, injected whitespace, an unrenderable URL) has no
effect on any other word's blocks — there is no shared pointer to desynchronize, and no "consume
until it matches something" step that could latch onto the wrong target. Each word's interval is
`[min(mapped indices), max(mapped indices) + 1)`, or a null interval when no raw character of
that word maps to anything.

**Determinism and pair-count guarantee.** `SequenceMatcher` is deterministic for identical
inputs (no randomness, no iteration-order dependence). Pair count is guaranteed structurally, not
just empirically: the algorithm iterates over `words` directly, emitting exactly one `[start,
end)` pair per word regardless of how many (or how few) characters of that word matched — never
more pairs than raw words, never fewer. A final monotonicity/overlap/in-bounds clamp pass is a
safety net for degenerate input, not load-bearing for the count guarantee.

## Covered markup cases, measured slices

Measured live through the full pipeline (`fdmd.load_dir` → `ddl.word_offsets`), matching
`TestWordOffsetsMarkupIntegration` in `tests/test_word_offsets.py` (full detail incl. `repr()`
of rendered text in `task_003_result.md`):

| case | raw | rendered slices |
|---|---|---|
| bold spanning two words | `**very important**` | `['very', 'important']` |
| bold crossing a tag boundary mid-word | `**wichtig**e` | `['wichtig\n   \n   e']` (one interval) |
| link | `[link text](url)` | `['link', 'text']` |
| inline code | `` `a b` `` | `['a', 'b']` |
| image (null interval) | `![alt](url)` | `['']` (zero-length, correctly placed) |
| list segment | (list item words) | exact, no markup involved |
| heading segment | (heading words) | exact, no markup involved |

## Deliberately not covered, with rationale

From `task_003_result.md`, unchanged by this run (no test asserts exact slices for these; the
algorithm has no per-markup-type special casing, so it is expected — but not verified — to
degrade gracefully rather than to cascade or run away):

- **Nested/overlapping inline markup** (`**bold *and italic* text**`, `**[text](url)**`).
- **Adjacent markdown-syntax collisions with no separating whitespace** (`**a****b**`, two links
  back to back) — a stress case for whether the single-space `probe` separator still
  disambiguates word boundaries when the rendered text also has no separator.
- **Reference-style links** (`[text][ref]` + `[ref]: url`) and **footnotes** — not exercised;
  depends on whether the Markdown renderer in use supports them at all.
- **Very long runs of repeated identical short words** — a potential `difflib.SequenceMatcher`
  worst case (its recursive matching can degrade on highly repetitive input); not present in any
  current fixture, `d31-ice-cream` (largest fixture) does not trigger it, but that is not a
  guarantee for future large, repetitive debates.
- **RTL / combining Unicode characters** and multi-codepoint grapheme clusters — offsets are
  plain Python string (code-point) indices throughout; not script-aware either way.

Two further categories were found in later tasks (`task_004_result.md`, `task_005_result.md`)
while measuring exactness against fixtures. Both are **correct behavior, not bugs** — the
algorithm does the right thing given what actually renders — but the rendered slice is not
character-identical to the raw word, so they are excluded from the "exact match" test criterion:

- **Backslash-escaped punctuation**, e.g. raw word `in\-context\-answers`. The renderer strips
  the backslashes on output (`in-context-answers`); the offset correctly targets the unescaped
  rendered text, which by definition differs from the raw word.
- **Standalone thematic-break lines** (`---` on its own line, rendered as `<hr>`, no text
  content). The offset is a correct null interval `[p, p]`; the pair count still matches the raw
  word count exactly, with no cascade into neighboring words.

## Measured table sizes per fixture debate

`len(json.dumps(ddl.word_offsets))`, unindented, measured 2026-08-06 (`task_004_result.md`):

| debate | segments | JSON bytes |
|---|---|---|
| d00-explanatory-example-debate | 71 | 5380 |
| d02-test_debate | 16 | 1189 |
| d03-test_debate | 16 | 1189 |
| d04-test_debate | 16 | 1189 |
| d05-hidden_test_debate | 16 | 1235 |
| d06-private_test_debate | 16 | 1235 |
| d1-lorem_ipsum | 62 | 3741 |
| d30-many-parties | 65 | 8663 |
| d31-ice-cream | 84 | 13180 |
| d32-overlapping-refs | 31 | 4791 |

`d31-ice-cream` is the largest at 13180 bytes for 84 segments / 2952 offset pairs — above the
original ~9 KB ballpark estimate. This is not treated as a problem: the regression test bound is
set at 40 KB (roughly 3x the measured value), deliberately as an alarm against accidentally
serializing raw text into the table (a size jump of that magnitude would signal a bug), not as a
micro-optimization target. No fixture debate is anywhere near a size that would be a practical
payload concern.

## Open items for the frontend run

- **1-based end-inclusive word numbers → slice.** Reference keys use `_start-end` (1-based,
  end-inclusive). Against the flat `word_offsets[key]` list, group into per-word pairs first
  (`word_pairs = list(zip(pairs[0::2], pairs[1::2]))`), then the range slices as
  `word_pairs[start - 1 : end]`. See the worked example in `docs/flexible_references_concept.md`.
- **Null intervals.** Zero-length `[p, p]` pairs must be counted when advancing through word
  indices but skipped when highlighting (nothing to wrap in the DOM).
- **Prettify whitespace inside an interval.** A word's interval can include injected whitespace
  (including newlines) between inline tags (`**wichtig**e` case above) — a highlight can
  therefore visibly span a line break. This is expected, not a bug to work around.
- **Serialization format is not decided.** Only the Python object (`ddl.word_offsets`, a
  `dict[str, list[int]]`) exists so far; how it reaches the frontend (embedded in the rendered
  page, a separate JSON endpoint, etc.) is out of scope for this run and open for the
  `fair-debate-web` side.

## Reported, not fixed

- **Frozen tokenizer specification** (`get_segment_words`, `get_segment_source`,
  `_STRONG_ABBREVIATIONS`, `SENTENCE_SPLITTERS`): no bug found across this run's three
  investigative tasks. Left untouched, as required.
- **Latent pre-existing bug**, `core.py` `DebateDirLoader.load_dir`, `self.tree[base_name] = mdp`
  (currently at line 552): silently overwrites the tree entry if two contribution files resolve
  to the same base name. Out of scope for this run; not fixed.
- **Pre-existing `black` deviation** in `references.py` (a double blank line right before
  `key_regex = ...`): not introduced by this run, left untouched.
