This directory contains the sources of the fixture debates (plain md, without segment
keys) and the tools that turn them into valid fair-debate content repos. Rationale: the
content stays editable as ordinary prose, and the debate -- keys, commits, patches -- is a
build artifact of it.

Every build writes its patches to `../repos/<debate-key>/patches_01/`, which is where
`fdmd unpack-repos` picks them up. Updating a fixture therefore means: run the build,
commit the changed patches, and re-run `fdmd unpack-repos ./content_repos` in the web app.

One step further if the edit **added or removed a contribution**: the web app states the
contribution count of every fixture debate by hand, in `tests/testdata/fixtures01.json`,
and nothing over here can see that it went stale. Run
`manage.py initializefixtures --refresh-fixture-counts` there, or the count silently
disagrees with the repo until somebody else's test run says so. It has happened three
times; see that repo's backlog item `i-n-committed-stale-guard`.


## `fdmd build-debate-repo` -- one file in, one debate repo out

The general tool: it takes a debate written as a **single markdown file** and builds the
repo (and the patches) from it.

```bash
fdmd build-debate-repo <source.md>                  # patches -> ./<debate_key>/patches_01
fdmd build-debate-repo <source.md> --into-fixtures  # patches -> the fixture dir here
fdmd build-debate-repo <source.md> --repo-into <dir> --patches-into <dir>
```

Updating one of the fixture debates below is the `--into-fixtures` case: it writes into
the fixture directory of the *installed* fair_debate_md, which with an editable install is
this checkout. Implementation: `fair_debate_md/debate_builder.py`, tests in
`tests/test_debate_builder.py`.

The source carries its own metadata in a yaml front matter header (`debate_key`, the
`parties` map from role-token to author name, the commit dates), and separates the
contributions by marker comments:

```
<!-- !!== label=b-intro party=b answers="`b` is the first party to answer" ==== -->
```

The markers are html comments, so the source stays valid markdown and can be written, read
and previewed as one document. `answers` quotes the answered text literally; the build
resolves the quote against the segments of everything built so far and aborts, listing the
candidates, if it matches none or several. Rewording a contribution therefore does not move
the anchors of its answers. The order of the contributions in the file is the chronology of
the debate. See the module docstring for the full format.

A contribution can also answer a *range*, and a range is quoted as well -- an index would
move when a sentence is inserted, which is exactly what this format exists to avoid. A
marker may span several lines, which is what keeps two long quotes readable:

```
<!-- !!== label=b-block party=b
     answers_from="The machine costs us around forty euros"
     answers_to="the coffee it produces is" ==== -->            ->  a3-6b

<!-- !!== label=f-words party=f
     answers="A kettle and a press"
     answers_words="cost us maybe sixty euros once," ==== -->   ->  a7_7-12f
```

`answers_words` quotes whole words as the *markdown source* spells them -- punctuation and
markup stay attached to the word, so "once," is one word and "once" does not match it. The
counting rule behind that is frozen (`docs/flexible_references_concept.md`); a quote that
matches no run of words aborts the build and prints the segment's words with their numbers.

Debates built this way, one directory per debate -- a translation is a debate of its own,
with its own `dNN` key, not a variant of another one:

- `d00-explanatory-example-debate__plain/source.md` -- the debate a first-time visitor is
  pointed to (english).
- `d01-erklaerende-beispieldebatte__plain/source.md` -- its german counterpart. Same
  structure and the same anchor points, so the two produce almost the same contribution
  keys; only the integrity contribution has more segments in german, which moves `a27b38c`
  to `a27b41c`. It addresses the reader informally ("du"), like the german interface does.
  A *debate* is a "Debatte" here, and so is it in the interface: the german texts were
  changed over from "Diskussion" on 2026-09-01, by the user's decision. Keep new german
  sources on "Debatte"; a compound that does not name the platform object (the standing
  example is "Diskussionskultur") is the only reason to depart from it.
- `d34-pazifismus-ukraine__plain/source.md` -- german, argumentative: a role play between
  two fictional persons on pacifism and the war in Ukraine, both referring to one podcast
  episode. Eleven contributions along three threads, deliberately unresolved.
- `d35-rente-generationengerechtigkeit__plain/source.md` -- german, and the worked-out
  case of the demo pair: a deliberately pointed opinion piece on pension reform, answered
  along four threads down to level 4. One of them ends in an actual concession, which is
  the point the fixture is meant to show.
- `d36-handyverbot-schule__plain/source.md` -- german, deliberately shallow: the same kind
  of opinion piece (phone ban at schools, minimum age for social media) with three
  unanswered objections from two other parties. It is the live-demo counterpart of d35 --
  an audience is supposed to add the next contribution, so most claims are left untouched
  on purpose.
- `d31-ice-cream__plain/source.md` -- english, and a toy topic on purpose (which ice cream
  flavour is best), so that its content never distracts from what it is for: judging
  frontend decisions about nesting. Ten parties, 26 contributions, only five root segments
  answered, one spine reaching level 8.
- `d32-overlapping-refs__plain/source.md` -- english, the reference fixture: a toy dispute
  about the office coffee machine whose replies deliberately overlap. It is the only
  fixture using `answers_from`/`answers_to` and `answers_words`, and it exists so that the
  *display* problem of overlapping references can be judged in the frontend rather than
  argued about in the specification -- see `docs/flexible_references_concept.md`.
- `d33-wachstum-klimaschutz__plain/source.md` -- german, and the only fixture with real
  argumentative content: three students argue out whether economic growth and climate
  protection are compatible, after listening to a radio debate on the question. The root
  contribution names that broadcast as their source and says what the setup is, namely a
  role play: the students make the arguments in their own words rather than reporting what
  the two guests said, and the text deliberately holds no verbatim quote from it (checked
  against the transcript kept in `source_transcripts__gitignore__/`). Three parties -- `a`
  poses the questions and never argues, `b` holds the growth position and `c` the degrowth
  one -- 18 contributions, a spine down to level 5, and one contribution that agrees with
  what it answers instead of objecting, which no other fixture does.

Until 2026-08 the first of these was built by `fdmd process-content-dir` from one file per
contribution, with the anchor encoded in the file name (`b/a14b.md` = segment 14 of `a`):
every inserted sentence forced a rename cascade, only two parties were possible, the
deployment had to special-case the debate, and the patches here had silently fallen behind
the sources.


## Removed: the debate-specific build scripts

Gone since 2026-09-02: `build_d31_ice_cream.py`, `build_d32_overlapping_refs.py` and
`build_d33_wachstum_klimaschutz.py`, together with the per-contribution plain files they
read. The three debates are ordinary `source.md` files now.

They existed because the source format could not express what they needed. Each named its
anchors as *indices* into the parent contribution's segment list, which is what the format
avoids -- and d32 needed segment and word ranges, which the format did not offer at all
until it learned `answers_from`/`answers_to` and `answers_words` on the same day.

The cost of keeping them had become visible twice: all three carried their own hardcoded
README with the literal placeholders `<debate_url>`/`<background_url>` (dead duplication,
since `rollout_patches()` replaces the README anyway), and each created its root commit
itself, so none of them picked up `REPO_INFO.yaml` when that arrived -- their integrity
page said "not recorded" while every other fixture named its origin.

The rebuild kept every contribution key exactly as it was; what changed is the yaml front
matter in each file, the added `REPO_INFO.yaml`, the commit dates (which now come from
`first_commit` and `hours_between_contributions`) and, as with any rebuild, all hashes.


## Removed: `fdmd process-content-dir`

Gone since 2026-08-31. It built a repo from a directory of plain files whose *names* were
the anchors (`b/a14b.md` answers segment 14 of `a`), which forced a rename cascade on every
inserted sentence and could only alternate between two parties -- it derived the author
from the nesting level. Its last user, `d00`, moved to `build-debate-repo` in 2026-08, and
after that the only thing it still built was its own test.

`build-debate-repo` covers what it did, minus the file-name anchors. A one-off throwaway
repo is a source file with a front matter header and one marker comment.
