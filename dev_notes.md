
2026-05-17 20:29:12

(activate obsolete test (yet fails))
claude --resume e59bc5df-b24a-4bae-b0c4-222ebcdddf98



---

- [] load metadata from `metadata.toml`
- [] prevent AssertionError if contribution is empty (only generate warning or ignore contribution)
- [x] add separate css class to DBContribution divs
- [x] store debate_key in final-html


## splitter syntax (backlog, added 2026-08-18)

Surfaced while writing the `d33-wachstum-klimaschutz` fixture, where the colon after
"lautet" and the dot in "15. August" produced unwanted segments in ordinary German
prose; the gender-inclusive-colon case below was contributed by the user. Items (1) and
(2) concern `split_text_into_segments()` / `_is_abbreviation_dot()` in
`key_management.py`.

- [x] **(1) a splitter only splits when whitespace follows it.**
  -> done (2026-09-02), syntax version 2, `_split_v2` in `key_management.py`. It fixes
  the gender-inclusive colon ("User:innen"), clock times ("14:30") and any punctuation
  glued to the next character. A colon that *is* followed by whitespace keeps its
  splitter function, so the useful case ("Die Streitfrage lautet: Sind X und Y
  vereinbar?" -> the thesis stays separately referenceable) is unaffected. Only `:` is
  concerned among the gender forms -- `*` and `_` are not splitters.
  Applied to all four splitters, not just `.` and `:` -- there is no case where a glued
  `!` or `?` should behave differently, and a uniform rule is one rule less to remember.
  The end of the text counts as "whitespace follows" on purpose: the text handed to the
  splitter is one html text node, and whether the following tag renders as a space is not
  visible from there. That confines the change to the glued cases it was written for --
  measured over every source and every built contribution, it changes no existing key.

- [x] **(2) a dot directly after a digit does not split by default.**
  -> done (2026-09-02), syntax version 2. Ordinals ("15. August", "3. Platz") are far
  more frequent than a sentence ending in a number. The weak-abbreviation rule could not
  help: it only suppresses the split when the continuation is lowercase, and "August" is
  uppercase.
  The opt-in for the rare real case is `FORCE_SPLIT_MARKER`, spelled **`\@` directly in
  front of the splitter**: "... bis Ende 2026\@. Jede Verwaesserung ...". It is the same
  notation LaTeX uses for the same purpose (`\@.` forces a sentence end), it is glued to
  the dot rather than to the space, and it overrides the abbreviation tables too, which
  is the only way to end a sentence on "z.B." at all.
  The two candidates listed here before were not merely worse, they turned out unusable
  when tried against the real pipeline: `18\.` loses its backslash inside
  python-markdown, so by the time the splitter sees the text it is an ordinary dot; and
  `18.\ ` leaves the backslash at the *start of the following segment*.
  The marker stays in the stored `.md` (it is what
  `TestStoredSegmentationIsReproducible` re-checks, and it tells a reader of the raw repo
  why the segment ends there) and is removed in `MDProcessor.get_html_with_segments()`,
  so it never reaches the debate. It carries no whitespace, so it shifts no word position.
  Not built, and not needed so far: the opposite marker, one that *suppresses* a split
  the rules do make (LaTeX's `\ `). Worth adding only when a text actually wants it.

- [x] **(3) persist the splitter-syntax version per contribution.**
  → done (2026-09-02): `SPLITTER_SYNTAX_VERSION` in `key_management.py`, written as
  `splitter_version` into the yaml front matter of every contribution by both write paths
  (`core.write_ctb_to_file` for a live publication, `debate_builder` for a built fixture)
  and read back into `MDProcessor.splitter_version`. A file without the field counts as
  version 1, which is a statement about history rather than a fallback.
  The dispatch followed with (1)/(2) (2026-09-02): `split_text_into_segments()` picks a
  ruleset out of `_SPLITTERS_BY_VERSION`, and an unknown version is refused rather than
  guessed. Its consumer is `tests/test_splitter_versions.py::TestStoredSegmentationIsReproducible`,
  which strips the markers off every built fixture and requires re-segmentation under the
  recorded version to put them back where they were -- that is what turns the recorded
  number into a checkable statement.
  The original entry, for the reasoning:
  Items (1) and (2) change how existing text is segmented, and segment keys are the
  prefix of every answer key (`a14c5b` answers segment `a14c5`). Re-segmenting an
  existing debate under new rules therefore does not just renumber segments, it breaks
  the references of all answers to it. So (3) is not an independent nicety but a
  precondition for shipping (1) and (2): every contribution must record the syntax
  version it was created under, and be re-rendered with exactly that version, so that
  old debates stay byte-identical while new ones use the current default.
  Decided: store it as yaml front matter in the contribution `.md` (`core.split_front_matter()`
  already exists), so the information stays inside the content repo and travels with it;
  explicitly not a db column, which the repo alone would not carry.
  Decided when (1)/(2) landed (2026-09-02), after measuring instead of guessing: the
  patterns were counted over every source and every built contribution first. Rule (1)
  had **no** effect anywhere. Rule (2) touched exactly two split points, both genuine
  sentence ends: "... Speicherung von CO2. Bei Prozessemissionen ..." in d33
  (`b/b-instrumente.md`) and "... bis Ende 2026. Jede Verwaesserung ..." in d35
  (`source.md`). Everything else matching `digit + dot` is markdown ordered-list syntax,
  which becomes `<li>` and never reaches the splitter, or sits inside `**bold**`, which
  is not segmented either.
  d35 got the `\@` marker and was rebuilt: the segment keys come out byte-identical, and
  the sentence keeps the boundary it should have. Every other fixture stays as it is and
  keeps saying `splitter_version: 1`, which is true and which keeps the dispatch honest --
  the fixture set now contains both rulesets.

- [] **d33 still needs the `\@` marker.** The second of the two measured spots. It was
  left out on purpose: a parallel line of work is converting d31/d32/d33 to single-file
  sources, so editing `b/b-instrumente.md` now would only be overwritten.
  Nothing is broken in the meantime -- d33 records `splitter_version: 1` and is rendered
  under version 1. The damage happens the moment somebody rebuilds it under version 2
  without the marker: `a14c5b8c6b10`, the last segment of that contribution and currently
  unanswered, silently merges into `a14c5b8c6b9` and the sentence loses a boundary it
  should have. So whoever lands the single-file d33 source writes
  "... Speicherung von CO2\@. Bei Prozessemissionen ..." into it.


## repo provenance (added 2026-09-02)

Every repo now carries `REPO_INFO.yaml` in its first commit, saying what made it
(`repo_handling.build_repo_info()`): `kind: opened` for a debate the platform opened and
that grew by appending, `kind: built` for a fixture generated from a `source.md`, with the
source name, its sha256 and the build date. The point is the built case: a rebuild
discards the whole commit chain, and without this the integrity page presents the new one
as the history of the debate while a fingerprint somebody noted resolves to nothing.

- [] **the three script-built fixtures have no `REPO_INFO.yaml`.** `d31-ice-cream`,
  `d32-overlapping-refs` and `d33-wachstum-klimaschutz` are built by their own scripts
  (`build_d3*.py`), which create the root commit themselves instead of going through
  `build_debate_repo()`. They therefore missed the change. The older patch collections
  (`d02`..`d06`, `d1-lorem_ipsum`) cannot get one at all -- they have no source to name --
  so the reading side has to tolerate absence anyway; this is about consistency of the
  demo set, not about correctness.
Guarded by `test_every_built_fixture_matches_its_source`: the hash recorded in a fixture's
patch collection must equal the hash of its `source.md`. That is what keeps the record
honest -- editing a source without rebuilding the repo now fails the suite instead of
leaving the repo claiming a source it no longer came from.


## whitespace around inline elements (backlog, added 2026-08-28)

Surfaced while rewriting the `d00-explanatory-example-debate` fixture, whose text
mentions a lot of contribution keys and therefore hits the case in almost every
sentence. Concerns `SpanAdder.convert_soup_to_final_html()` in `core.py` (called with
`prettify=True` from `MDProcessor.convert()`, ~line 394).

- [] **inline elements get a space before the following punctuation.**
  `soup.prettify()` puts every tag on a line of its own, and the browser renders that
  line break as a space. Source:

      Their statements are keyed `a1`, `a2` and so on.

  delivered html:

      Their statements are keyed
      <code>a1</code>
      ,
      <code>a2</code>
      and so on.

  rendered: `Their statements are keyed a1 , a2 and so on.` -- with a space before the
  comma. The same happens after `<em>`/`<strong>` and before a full stop. Affects every
  debate, not just this fixture.

  Worth knowing before touching it: the rendered segment text is what
  `get_rendered_word_offsets()` (`references.py`) aligns raw words against, and its
  docstring names prettify-injected whitespace explicitly as one of the cases the global
  alignment is built to survive. Removing that whitespace should make its job easier
  rather than harder, but it shifts the offsets of every existing segment, and some
  tests in `test_word_offsets.py` compare offsets literally. Also to be checked: whether
  anything besides readability of the delivered html depends on `prettify` at all -- if
  not, dropping it may be cheaper than post-processing it away.
