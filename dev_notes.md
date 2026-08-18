
2026-05-17 20:29:12

(activate obsolete test (yet fails))
claude --resume e59bc5df-b24a-4bae-b0c4-222ebcdddf98



---

- [] load metadata from `metadata.toml`
- [] prevent AssertionError if contribution is empty (only generate warning or ignore contribution)
- [x] add separate css class to DBContribution divs
- [x] store debate_key in final-html


## splitter syntax (backlog, added 2026-08-18)

Surfaced while writing the `d33-wachstum-klimaschutz` fixture, where both rules below
produced unwanted segments in ordinary German prose. All three items concern
`split_text_into_segments()` / `_is_abbreviation_dot()` in `key_management.py`.

- [] **(1) drop the colon as a sentence splitter, and require whitespace after a dot.**
  Currently `SENTENCE_SPLITTERS` contains `:`, so *every* colon starts a new segment --
  "Die Streitfrage lautet: Sind X und Y vereinbar?" becomes two segments. Same for a dot
  that is not followed by whitespace. Note the trade-off: for a colon introducing a
  quoted thesis the current split is arguably useful (it makes the thesis separately
  referenceable), so this is a deliberate change of behaviour, not a pure bugfix.

- [] **(2) a dot directly after a digit should not split by default.**
  Ordinals ("15. August", "3. Platz") are far more frequent than a sentence ending in a
  number, so the default should be "do not split". The existing weak-abbreviation rule
  does not help here: it only suppresses the split when the continuation is lowercase,
  and "August" is uppercase.
  For the rare case where a split after a number *is* wanted, an explicit opt-in marker
  is needed. Idea from the user: an additional character in the source, e.g.
  "Hilde war 18.; August war ein Jahr älter." -- acknowledged as a crutch.
  Open design question: such a marker must not remain visible in the rendered text, so
  an escape-like construct that disappears during rendering (`\.`, or a dot followed by
  an empty html comment) may be preferable to a literal punctuation character.

- [] **(3) persist the splitter-syntax version per contribution.**
  Items (1) and (2) change how existing text is segmented, and segment keys are the
  prefix of every answer key (`a14c5b` answers segment `a14c5`). Re-segmenting an
  existing debate under new rules therefore does not just renumber segments, it breaks
  the references of all answers to it. So (3) is not an independent nicety but a
  precondition for shipping (1) and (2): every contribution must record the syntax
  version it was created under, and be re-rendered with exactly that version, so that
  old debates stay byte-identical while new ones use the current default.
  Open: where to store it. `core.split_front_matter()` already exists, so yaml front
  matter in the contribution `.md` keeps the information inside the content repo and
  travels with it (preferable to a db column, which the repo alone would not carry).
  Also to be decided when (1)/(2) land: whether the existing fixtures are rebuilt under
  the new version or pinned to the old one.
