"""
The segmentation ruleset and its version.

Segment keys are materialized into the stored `.md`, so a rule change cannot renumber a
published debate -- but it *can* make a fixture rebuilt from its source disagree with the
repo that was handed out earlier. `splitter_version` in the front matter is what makes
that impossible: every contribution says which ruleset produced its `::aN` markers and is
re-rendered under exactly that one.

`TestStoredSegmentationIsReproducible` is what turns the recorded number into a checkable
statement rather than a decoration.
"""

import glob
import os
import re

import pytest

from fair_debate_md import core, references
from fair_debate_md.core import MDProcessor, get_base_name, split_front_matter
from fair_debate_md.key_management import (
    DEFAULT_SPLITTER_SYNTAX_VERSION,
    FORCE_SPLIT_MARKER,
    SPLITTER_SYNTAX_VERSION,
    split_text_into_segments,
    strip_force_split_markers,
)


class TestVersion2Rules:
    """
    The two rules version 2 adds. Both were found in ordinary German prose while writing
    the d33 fixture; see `dev_notes.md`, section "splitter syntax".
    """

    @pytest.mark.parametrize(
        "text",
        [
            "Das betrifft alle User:innen im Land.",  # gender-inclusive colon
            "Wir treffen uns um 14:30 am Bahnhof.",  # clock time
            "Der Wert ist 3:4 gewesen.",  # ratio
        ],
    )
    def test_a_colon_without_following_whitespace_does_not_split(self, text):
        assert split_text_into_segments(text, 2) == [text]
        # ... and this is exactly what changed: version 1 tore them apart
        assert len(split_text_into_segments(text, 1)) > 1

    def test_a_colon_with_following_whitespace_still_splits(self):
        """The useful case has to survive -- it is why `:` is a splitter at all: the
        thesis after it stays separately referenceable."""
        text = "Die Streitfrage lautet: Sind X und Y vereinbar?"
        assert split_text_into_segments(text, 2) == [
            "Die Streitfrage lautet:",
            " Sind X und Y vereinbar?",
        ]

    @pytest.mark.parametrize(
        "text",
        [
            "Am 15. August war es soweit.",
            "Er wurde 3. Platz bei dem Rennen.",
            "Das steht in Kapitel 4. Danach folgt der Anhang.",
        ],
    )
    def test_a_dot_after_a_digit_does_not_split(self, text):
        """Ordinals are far more frequent than a sentence ending in a number. The weak
        abbreviation rule cannot help here: it only suppresses a split before a lowercase
        continuation, and "August" is uppercase."""
        assert split_text_into_segments(text, 2) == [text]

    def test_a_dot_glued_to_the_next_character_does_not_split(self):
        assert split_text_into_segments("Siehe kapitel.abschnitt hier.", 2) == [
            "Siehe kapitel.abschnitt hier."
        ]

    def test_a_splitter_at_the_end_of_the_text_still_splits(self):
        """A text node ends at a tag boundary, and what the tag renders as -- space or no
        space -- is not visible from here. Treating the end as "whitespace follows" keeps
        the boundary behaviour of version 1, so the rule change stays confined to the
        glued cases it was written for."""
        assert split_text_into_segments("Erster Satz. Zweiter Satz.", 2) == [
            "Erster Satz.",
            " Zweiter Satz.",
        ]
        assert split_text_into_segments("Die Frage lautet:", 2) == ["Die Frage lautet:"]

    def test_the_shared_rules_are_untouched(self):
        """Abbreviations, thousands separators and version numbers behave in both."""
        for text in [
            "Der Krieg forderte 100.000 Tote.",
            "Siehe z.B. dieses Beispiel.",
            "Uses v12.3 here.",
        ]:
            assert split_text_into_segments(text, 1) == [text]
            assert split_text_into_segments(text, 2) == [text]


class TestForceSplitMarker:
    """
    The opt-in for the rare sentence that really does end on a number. See
    `FORCE_SPLIT_MARKER` for why it is spelled `\\@` and not something more obvious.
    """

    def test_it_forces_a_split_the_rules_would_suppress(self):
        text = "Die Umsetzung läuft bis Ende 2026\\@. Jede Verwässerung wäre ein Signal."
        assert split_text_into_segments(text, 2) == [
            "Die Umsetzung läuft bis Ende 2026\\@.",
            " Jede Verwässerung wäre ein Signal.",
        ]

    def test_it_also_breaks_a_strong_abbreviation(self):
        """Not just the digit rule -- the abbreviation tables can be overridden too, which
        is the only way to end a sentence on "z.B." at all."""
        text = "Nimm etwas Konkretes, z.B\\@. Der Rest folgt."
        assert split_text_into_segments(text, 2) == [
            "Nimm etwas Konkretes, z.B\\@.",
            " Der Rest folgt.",
        ]

    def test_it_is_inert_where_no_splitter_follows(self):
        text = "Eine Adresse wie foo\\@bar bleibt unberührt."
        assert split_text_into_segments(text, 2) == [text]
        assert strip_force_split_markers(text) == text

    def test_the_segments_still_concatenate_to_the_input(self):
        """The invariant the whole segmentation rests on: nothing is dropped while
        splitting. The marker is removed when the text is rendered, not here."""
        text = "Bis Ende 2026\\@. Jede Verwässerung wäre ein Signal."
        assert "".join(split_text_into_segments(text, 2)) == text

    def test_it_survives_into_the_stored_markdown_but_not_into_the_html(self):
        """The two halves of its contract. It has to stay in the repo -- that is what
        `TestStoredSegmentationIsReproducible` reads and what tells a human reader why the
        segment ends there -- and it must never reach the debate."""
        mdp = MDProcessor("Die Umsetzung läuft bis Ende 2026\\@. Jede Verwässerung folgt.")
        mdp.convert()

        assert FORCE_SPLIT_MARKER in mdp.md_with_real_keys
        assert mdp.get_keys() == ["::a1", "::a2"]

        assert FORCE_SPLIT_MARKER not in mdp.segmented_html
        assert "2026." in mdp.segmented_html

    def test_it_does_not_shift_any_word_position(self):
        """The word tokenizer is frozen (`docs/flexible_references_concept.md`). The
        marker carries no whitespace, so `2026\\@.` is the one word `2026.` already was --
        every existing word reference into the segment keeps pointing at what it pointed
        at."""
        marked = MDProcessor("Wir schaffen das bis Ende 2026\\@. Ja.")
        marked.convert()
        plain = MDProcessor("Wir schaffen das bis Ende 2026x. Ja.")
        plain.convert()

        words_marked = references.get_segment_words(marked.md_with_real_keys, "a1")
        words_plain = references.get_segment_words(plain.md_with_real_keys, "a1")
        assert len(words_marked) == len(words_plain)
        assert words_marked[-1] == "2026\\@."


class TestVersionDispatch:
    def test_the_default_is_the_current_version(self):
        text = "Am 15. August war es soweit."
        assert split_text_into_segments(text) == split_text_into_segments(text, SPLITTER_SYNTAX_VERSION)

    def test_an_unknown_version_is_refused_rather_than_guessed(self):
        """A repo naming a ruleset we do not have is a repo we cannot render correctly.
        Falling back to the current rules would silently renumber it."""
        with pytest.raises(ValueError, match="unknown splitter syntax version"):
            split_text_into_segments("Hallo. Welt.", 99)

    def test_a_processor_segments_under_the_version_it_was_given(self):
        text = "Es waren 2022. 500 Leute kamen."
        v1 = MDProcessor(text, splitter_version=1)
        v1.convert()
        v2 = MDProcessor(text, splitter_version=2)
        v2.convert()
        assert v1.get_keys() == ["::a1", "::a2"]
        assert v2.get_keys() == ["::a1"]


# the collections that predate the builder: their `.md` files were written by hand (or by
# an early script), with the `::aN` markers placed manually, and were never the output of
# `split_text_into_segments`. It shows in ways that have nothing to do with segmentation --
# emphasis written as `*porro*` where markdownify writes `_porro_`, different blank-line
# layout. They have no source to be rebuilt from either (see dev_notes.md, "repo
# provenance"), so there is nothing here that could go stale. Everything else is opted in
# by default, so a fixture added later is covered without anyone remembering to add it.
_HAND_AUTHORED_COLLECTIONS = frozenset(
    [
        "d02-test_debate",
        "d03-test_debate",
        "d04-test_debate",
        "d05-hidden_test_debate",
        "d06-private_test_debate",
        "d1-lorem_ipsum",
        "d30-many-parties",
    ]
)


class TestStoredSegmentationIsReproducible:
    """
    The first real consumer of the recorded version, and the reason the dispatch is not
    dead code: strip the `::aN` markers from a stored contribution, segment the text again
    under the version that contribution *claims*, and the markers must come back exactly
    where they were.

    This is the strongest regression test available for any future rule change. A change
    that would renumber an existing repo fails here, in the repo it would damage, instead
    of being noticed after the fingerprints have been handed out.
    """

    @staticmethod
    def _strip_keys(md_with_real_keys: str, prefix: str) -> str:
        """The stored text minus its segment markers -- i.e. what was fed to the splitter."""
        return re.sub(rf"::{re.escape(prefix)}\d+ ", "", md_with_real_keys)

    def test_every_built_fixture_reproduces_its_own_markers(self, tmp_path):
        core.unpack_repos(str(tmp_path))

        checked = 0
        for repo_name in sorted(os.listdir(tmp_path)):
            if repo_name in _HAND_AUTHORED_COLLECTIONS:
                continue
            for fpath in sorted(glob.glob(os.path.join(tmp_path, repo_name, "*", "*.md"))):
                prefix = get_base_name(fpath)
                front_matter, stored = split_front_matter(open(fpath).read())
                version = front_matter.get("splitter_version", DEFAULT_SPLITTER_SYNTAX_VERSION)

                mdp = MDProcessor(
                    plain_md=self._strip_keys(stored, prefix),
                    key_prefix=prefix,
                    splitter_version=version,
                )
                assert mdp.convert_plain_md_to_md_with_real_keys() == stored, (
                    f"{repo_name}/{os.path.basename(fpath)} says splitter_version {version}, "
                    f"but re-segmenting its text under that ruleset does not reproduce the "
                    f"`::{prefix}N` markers it carries"
                )
                checked += 1

        assert checked > 100, f"only {checked} contributions checked -- did the rollout change?"
