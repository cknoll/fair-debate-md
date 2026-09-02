
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

- [] **(1) a splitter only splits when whitespace follows it.**
  Applies to both `.` and `:`. Currently every colon starts a new segment, which breaks
  the gender-inclusive colon that some users write ("User:innen" -> two segments). The
  same rule also fixes clock times ("14:30") and any dot glued to the next character.
  A colon that *is* followed by whitespace keeps its splitter function, so the useful
  case ("Die Streitfrage lautet: Sind X und Y vereinbar?" -> the thesis stays separately
  referenceable) is unaffected. Only `:` is concerned among the gender forms -- `*` and
  `_` are not splitters.

- [] **(2) a dot directly after a digit should not split by default.**
  Ordinals ("15. August", "3. Platz") are far more frequent than a sentence ending in a
  number, so the default should be "do not split". The existing weak-abbreviation rule
  does not help here: it only suppresses the split when the continuation is lowercase,
  and "August" is uppercase.
  For the rare case where a split after a number *is* wanted, an explicit opt-in marker
  is needed. Decided: the marker must NOT remain visible in the rendered text, so it is
  an escape-like construct, not a literal punctuation character.
  The concrete syntax is deliberately left open. Candidates:
    * `18\. August` -- but a backslash conventionally means "take the next character
      literally", while here it would mean "treat the dot as a splitter after all", i.e.
      a different function for a familiar character;
    * `18.\ August` -- backslash before the space instead of before the dot.
  Worth knowing when deciding: LaTeX has exactly this problem and solves it in both
  directions -- `\ ` suppresses a sentence-end after a dot, and `\@.` forces one where
  the heuristic misses it. Our opt-in is the `\@.` direction, so a syntax borrowed from
  `\ ` would read *inverted* to LaTeX-trained users. That argues for a marker glued to
  the dot rather than to the space, or for a third character altogether.

- [x] **(3) persist the splitter-syntax version per contribution.**
  → done (2026-09-02): `SPLITTER_SYNTAX_VERSION` in `key_management.py`, written as
  `splitter_version` into the yaml front matter of every contribution by both write paths
  (`core.write_ctb_to_file` for a live publication, `debate_builder` for a built fixture)
  and read back into `MDProcessor.splitter_version`. A file without the field counts as
  version 1, which is a statement about history rather than a fallback.
  **Still missing, and the actual work of (1)/(2):** nothing yet *dispatches* on the
  recorded version -- `split_text_into_segments()` has one behaviour. Recording had to come
  first so that contributions written from now on can be re-rendered under their own rules;
  the dispatch is written when the first alternative ruleset exists.
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
  Still to be decided when (1)/(2) land: whether the existing fixtures are rebuilt under
  the new version or pinned to the old one.


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
