
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
  Both got the `\@` marker and were rebuilt: the segment keys come out byte-identical, and
  the two sentences keep the boundary they should have. d33 waited for the single-file
  sources to land first, so that the marker went into the source that survives. Every
  other fixture stays as it is and keeps saying `splitter_version: 1`, which is true and
  which keeps the dispatch honest -- the fixture set now contains both rulesets.
  Worth knowing before putting the marker anywhere else in a single-file source: an
  `answers=` anchor is matched as a substring of the *keyed segment text*, so a quote
  ending on the marked sentence has to carry the marker too. In d33 the same sentence
  appears twice for that reason. Getting it wrong stops the build with "matches no
  segment" rather than moving the answer somewhere else, which is why this is a note and
  not a trap.


## repo provenance (added 2026-09-02)

Every repo now carries `REPO_INFO.yaml` in its first commit, saying what made it
(`repo_handling.build_repo_info()`): `kind: opened` for a debate the platform opened and
that grew by appending, `kind: built` for a fixture generated from a `source.md`, with the
source name, its sha256 and the build date. The point is the built case: a rebuild
discards the whole commit chain, and without this the integrity page presents the new one
as the history of the debate while a fingerprint somebody noted resolves to nothing.

- [x] **the three script-built fixtures have no `REPO_INFO.yaml`.** Done 2026-09-02:
  `d31-ice-cream`, `d32-overlapping-refs` and `d33-wachstum-klimaschutz` now come from a
  single `source.md` like every other fixture, and their build scripts are gone. What
  stood in the way was the source format rather than the fixtures -- it could anchor an
  answer at exactly one segment, and d32 exists to exercise ranges -- so ranges were added
  to it first, spelled as quotes as well (`answers_from`/`answers_to`, `answers_words`).
  Every contribution key stayed as it was; the commit hashes did not, which is the normal
  price of a rebuild and is what `REPO_INFO.yaml` now records. The older patch collections
  (`d02`..`d06`, `d1-lorem_ipsum`) still cannot get one -- they have no source to name --
  so the reading side has to tolerate absence anyway.

Guarded by `test_every_built_fixture_matches_its_source`: the hash recorded in a fixture's
patch collection must equal the hash of its `source.md`. That is what keeps the record
honest -- editing a source without rebuilding the repo now fails the suite instead of
leaving the repo claiming a source it no longer came from.


## whitespace around inline elements (backlog, added 2026-08-28)

Surfaced while rewriting the `d00-explanatory-example-debate` fixture, whose text
mentions a lot of contribution keys and therefore hits the case in almost every
sentence. Concerned `SpanAdder.convert_soup_to_final_html()` in `core.py`, which
`MDProcessor.get_html_with_segments()` called with `prettify=True` until fdmd 0.10.0.

- [x] **inline elements get a space before the following punctuation.**
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

  The defect is one step wider than "a space before punctuation": the whitespace is
  injected at *every* inline tag boundary, so it also cuts a word that markup splits.
  `**wichtig**e` is delivered as `wichtig\n   \n   e` and read aloud as "wichtig e".

  Second reporter, same artefact: `fair-debate-web/todo_notes.md`, section "feature
  2026-08-31: allow images in contributions", trap 2 -- an `<img>` immediately before
  `.` or `,` shows as "symbol .". That is why the glyphs there were placed where a space
  follows anyway and the german sentences were reworded rather than merely punctuated;
  that note defers the actual fix to this item.

  Blast radius, measured rather than assumed: `final_html` is computed per request
  (`base/views.py` takes `ddl.final_html` into the `segmented_html` template variable)
  and is stored neither in a content repo nor in the database. Changing it therefore
  moves no contribution key, no segment key and no commit hash -- this is a rendering
  change, not a content change, and it needs no fixture rebuild.

  *Done 2026-09-04 in fdmd 0.10.0.* `prettify=False` at the single call site in
  `MDProcessor.get_html_with_segments()` -- the whole defect was that one keyword. The
  option considered against it (keep prettify, strip the injected whitespace again
  afterwards) was dropped because it needs a heuristic to tell "this line break means a
  space" from "this one means nothing", which is exactly the information prettify has
  already thrown away, and because every newly allowed inline tag would have to be
  taught to it -- `img` had just become the second reporter that way.

  The readability that prettify was there for turns out to be mostly preserved: the
  newlines between `<div class="p_level0">` blocks come from the markdown converter, so
  the delivered html is one line per block, not one line per document.

  What the change actually moved, measured against the regenerated `txt1` fixture: 34
  segments, every key identical, exactly one segment's rendered text different -- the
  fix itself (`Adipisci sit adipisci non est .` -> `... est.`). No repo, no database and
  no reference key is involved, as expected: a reference such as `a7_7-12f` counts *word
  indices* from the markdown, and only the character offsets derived from them move.
  Those are computed per request and reach the frontend in the same response as the html
  they index into (`data-word_offsets` in `main_show_debate.html`, read by `core.js`), so
  the two cannot disagree.

  Three tests here had to follow, all of them for the same reason -- they asserted the
  prettified string literally: the expectation in `test_030__get_html_with_segments`
  (which round-tripped its expected value through `prettify()` and no longer needs to)
  plus the regenerated `tests/testdata/txt1_segmented_html.html`;
  `test_bold_crossing_tag_boundary_mid_word_is_exact`, whose contract is unchanged while
  the string it measures against got simpler (`"wichtig\n   \n   e"` -> `"wichtige"`);
  and `test_thematic_break_word_maps_to_null_interval`, where the null interval sits at
  64 instead of 67. Nothing in `get_rendered_word_offsets()` was touched to make any of
  them pass, which is worth recording: it aligns against the delivered string instead of
  assuming a coordinate system, and that is what let the switch flip.

  Five more in **fair-debate-web** (`test_backend.py` `test_030`/`test_061`/`test_062`,
  `test_frontend.py` `test_g032`/`test_g120`), same cause, and they are the reason that
  repo's `requirements.txt` now asks for `fair_debate_md>=0.10.0`: its tests describe the
  unprettified rendering and would fail against an older fdmd. Worth noting how they read
  before -- `"This is a level 1\n     <strong>\n      answer\n     </strong>\n     from a
  unittest."` -- an expectation nobody could have written down as *intended* output. That
  a whole suite had normalized the defect into its expectations is the better argument
  for fixing it at the source than any single rendering was.

  Left as it is: `_strip_me_` in `convert_code_placeholders()` /
  `decode_strip_me_tags()`. With prettify gone it has nothing left to repair, but it is
  harmless and it is the safety net if anyone ever turns prettify back on. Removing it
  is a separate, purely cosmetic change.

  Worth knowing, and what the fix had to respect:

  - The rendered segment text is what `get_rendered_word_offsets()` (`references.py`)
    aligns raw words against, and its docstring names prettify-injected whitespace
    explicitly as one of the cases the global alignment is built to survive. Removing
    that whitespace should make its job easier rather than harder, but it shifts the
    offsets of every segment. Most of `test_word_offsets.py` compares *sliced text* and
    would survive; `test_bold_crossing_tag_boundary_mid_word_is_exact` asserts the
    prettified string literally and has to be rewritten.
  - `tests/test_md_handling.py` compares against prettified expectations (~line 377 plus
    the `txt1_segmented_html*.html` files under `tests/testdata/`).
  - There is already a precedent for repairing prettify's damage rather than avoiding
    it: the `_strip_me_` attribute, set in `convert_code_placeholders()` and removed in
    `decode_strip_me_tags()`, exists solely to undo the whitespace prettify injects
    *inside* a `<code>` tag. What is still open is the whitespace *outside* it.
  - The open question "does anything besides readability depend on `prettify`?" was
    answered by measurement rather than by reading: flipping the flag broke 3 of 238
    tests, none of which tested readability. That is what made the cheap route the
    right one.
