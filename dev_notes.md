
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

- [] **(3) persist the splitter-syntax version per contribution.**
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
