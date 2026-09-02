"""
Tests for `fdmd build-debate-repo` / `fair_debate_md.debate_builder`.

The sources here are miniature and written for the test: the fixture debates are
user-facing texts and get rewritten, so asserting on their content would tie these tests
to editorial decisions (see `testdata/builder_demo_source_README.md`).
"""

import glob
import hashlib
import os
import subprocess

import pytest
import yaml

from fair_debate_md import fixtures, repo_handling
from fair_debate_md.core import split_front_matter
from fair_debate_md.debate_builder import build_debate_repo, read_source
from fair_debate_md.key_management import (
    DEFAULT_SPLITTER_SYNTAX_VERSION,
    SPLITTER_SYNTAX_VERSION,
)
from fair_debate_md.release import __version__ as fdmd_version

pjoin = os.path.join

SOURCE = """\
---
debate_key: d97-builder-demo
parties:
  a: Opener
  b: Answerer
first_commit: 2026-03-01T08:00:00+01:00
hours_between_contributions: 2
---

<!-- !!== label=root party=a ==== -->

# Demo

This is the first sentence. This one will be answered.

<!-- !!== label=answer party=b answers="This one will be answered" ==== -->

An answer to `{{anchor}}`, in a contribution keyed `{{key}}`.
"""


# segments of the opening contribution: a1 "# Ranges", a2 "First sentence.",
# a3 "Second sentence.", a4 "Third sentence.", a5 "Fourth sentence with several words in it."
RANGE_SOURCE = """\
---
debate_key: d96-range-demo
parties:
  a: Opener
  b: Answerer
  c: Third
---

<!-- !!== label=root party=a ==== -->

# Ranges

First sentence. Second sentence. Third sentence. Fourth sentence with several words in it.

<!-- !!== label=block party=b
     answers_from="Second sentence"
     answers_to="Third sentence" ==== -->

An answer to the block.

<!-- !!== label=words party=c answers="Fourth sentence" answers_words="several words in" ==== -->

An answer to those words.
"""


def write_source(tmp_path, text=SOURCE) -> str:
    fpath = tmp_path / "source.md"
    fpath.write_text(text)
    return str(fpath)


def build_ranges(tmp_path, text=RANGE_SOURCE, name="r") -> dict:
    return build_debate_repo(
        write_source(tmp_path, text),
        patches_into=str(tmp_path / f"p-{name}"),
        repo_into=str(tmp_path / f"repo-{name}"),
    )


class TestSourceFormat:
    def test_front_matter_and_markers_are_read(self, tmp_path):
        meta, contributions = read_source(write_source(tmp_path))
        assert meta["debate_key"] == "d97-builder-demo"
        assert meta["parties"] == {"a": "Opener", "b": "Answerer"}
        assert [(c[0], c[1]) for c in contributions] == [("root", "a"), ("answer", "b")]
        assert contributions[0][2] is None                      # the opening answers nothing
        assert contributions[1][2] == "This one will be answered"

    def test_undeclared_party_is_rejected(self, tmp_path):
        src = SOURCE.replace("label=answer party=b", "label=answer party=z")
        with pytest.raises(SystemExit, match="not declared in the front matter"):
            read_source(write_source(tmp_path, src))

    def test_missing_debate_key_is_rejected(self, tmp_path):
        src = SOURCE.replace("debate_key: d97-builder-demo\n", "")
        with pytest.raises(SystemExit, match="front matter lacks the field `debate_key`"):
            read_source(write_source(tmp_path, src))

    def test_a_second_opening_contribution_is_rejected(self, tmp_path):
        src = SOURCE.replace('answers="This one will be answered"', "")
        with pytest.raises(SystemExit, match="exactly one contribution"):
            read_source(write_source(tmp_path, src))


class TestAnchorResolution:
    """The point of quote anchors: a broken one stops the build instead of moving an answer."""

    def test_quote_that_matches_nothing_aborts(self, tmp_path):
        src = SOURCE.replace('answers="This one will be answered"', 'answers="not in the text"')
        with pytest.raises(SystemExit, match="matches no segment"):
            build_debate_repo(write_source(tmp_path, src), patches_into=str(tmp_path / "p"))

    def test_ambiguous_quote_aborts(self, tmp_path):
        # "sentence" occurs in the heading paragraph twice once the text is duplicated
        src = SOURCE.replace(
            "This is the first sentence. This one will be answered.",
            "This is the first sentence. This is another sentence. This one will be answered.",
        ).replace('answers="This one will be answered"', 'answers="sentence"')
        with pytest.raises(SystemExit, match="matches 2 segments"):
            build_debate_repo(write_source(tmp_path, src), patches_into=str(tmp_path / "p"))

    def test_anchor_survives_a_reworded_parent(self, tmp_path):
        """Inserting a sentence before the anchor must not move the answer."""
        keys_before = build_debate_repo(
            write_source(tmp_path), patches_into=str(tmp_path / "p1"), repo_into=str(tmp_path / "r1")
        )
        src = SOURCE.replace(
            "This is the first sentence.",
            "This is the first sentence. An inserted one, which shifts the indices.",
        )
        keys_after = build_debate_repo(
            write_source(tmp_path, src),
            patches_into=str(tmp_path / "p2"),
            repo_into=str(tmp_path / "r2"),
        )
        # the anchor moved from a3 to a4, and the answer moved with it -- without any edit
        # to the marker, which is what index-based anchors could not do
        assert keys_before["answer"] == "a3b"
        assert keys_after["answer"] == "a4b"


class TestMarkerFields:
    """The fields are read in any order and may be spread over several lines."""

    def test_field_order_is_free(self, tmp_path):
        src = SOURCE.replace(
            'label=answer party=b answers="This one will be answered"',
            'answers="This one will be answered" party=b label=answer',
        )
        _, contributions = read_source(write_source(tmp_path, src))
        assert contributions[1].label == "answer"
        assert contributions[1].answers == "This one will be answered"

    def test_a_marker_may_span_several_lines(self, tmp_path):
        src = SOURCE.replace(
            '<!-- !!== label=answer party=b answers="This one will be answered" ==== -->',
            '<!-- !!== label=answer party=b\n'
            '     answers="This one will be answered" ==== -->',
        )
        _, contributions = read_source(write_source(tmp_path, src))
        assert contributions[1].answers == "This one will be answered"
        assert contributions[1].body.startswith("An answer to")

    def test_an_unclosed_marker_is_reported(self, tmp_path):
        src = SOURCE.replace(' answers="This one will be answered" ==== -->', "")
        with pytest.raises(SystemExit, match="never closed"):
            read_source(write_source(tmp_path, src))

    def test_an_unknown_field_is_rejected(self, tmp_path):
        src = SOURCE.replace("label=answer party=b", "label=answer party=b answres=x")
        with pytest.raises(SystemExit, match="unknown marker field 'answres'"):
            read_source(write_source(tmp_path, src))

    def test_answers_and_answers_from_exclude_each_other(self, tmp_path):
        src = SOURCE.replace(
            'answers="This one will be answered"',
            'answers="This one" answers_from="will be" answers_to="answered"',
        )
        with pytest.raises(SystemExit, match="exclude each other"):
            read_source(write_source(tmp_path, src))

    def test_a_half_range_is_rejected(self, tmp_path):
        src = SOURCE.replace('answers=', 'answers_from=')
        with pytest.raises(SystemExit, match="needs both 'answers_from' and 'answers_to'"):
            read_source(write_source(tmp_path, src))

    def test_word_range_without_a_segment_is_rejected(self, tmp_path):
        src = SOURCE.replace('answers=', 'answers_words=')
        with pytest.raises(SystemExit, match="'answers_words' needs 'answers'"):
            read_source(write_source(tmp_path, src))


class TestRangeReferences:
    """
    Ranges are quoted, not numbered, for the same reason plain anchors are -- see the
    module docstring of `debate_builder`.
    """

    def test_a_segment_range_is_anchored_at_its_end(self, tmp_path):
        keys = build_ranges(tmp_path)
        assert keys["block"] == "a3-4b"
        assert (tmp_path / "repo-r" / "b" / "a3-4b.md").exists()

    def test_a_word_range_names_the_words_it_quotes(self, tmp_path):
        keys = build_ranges(tmp_path)
        # "Fourth(1) sentence(2) with(3) several(4) words(5) in(6) it.(7)"
        assert keys["words"] == "a5_4-6c"

    def test_a_single_word_gets_a_single_position(self, tmp_path):
        """`a5_4-4` would be a degenerate range, which the key grammar rejects."""
        src = RANGE_SOURCE.replace('answers_words="several words in"', 'answers_words="several"')
        assert build_ranges(tmp_path, src)["words"] == "a5_4c"

    def test_ranges_survive_a_reworded_parent(self, tmp_path):
        """
        The whole point of quoting instead of numbering: inserting a sentence and a word
        shifts every index the two references would have been spelled with, and neither
        reference moves.
        """
        src = RANGE_SOURCE.replace(
            "First sentence.", "An inserted sentence. First sentence."
        ).replace("Fourth sentence with several", "Fourth sentence with a few and several")
        keys = build_ranges(tmp_path, src, name="shifted")
        assert keys["block"] == "a4-5b"        # was a3-4b
        assert keys["words"] == "a6_7-9c"      # was a5_4-6c

    def test_a_range_across_two_contributions_aborts(self, tmp_path):
        src = RANGE_SOURCE.replace(
            'answers="Fourth sentence" answers_words="several words in"',
            'answers_from="Fourth sentence" answers_to="An answer to the block"',
        )
        with pytest.raises(SystemExit, match="spans two contributions"):
            build_ranges(tmp_path, src)

    def test_a_reversed_range_aborts(self, tmp_path):
        src = RANGE_SOURCE.replace('answers_from="Second sentence"',
                                   'answers_from="Third sentence"').replace(
                                   'answers_to="Third sentence"', 'answers_to="Second sentence"')
        with pytest.raises(SystemExit, match="must quote a LATER segment"):
            build_ranges(tmp_path, src)

    def test_a_word_quote_that_matches_nothing_lists_the_words(self, tmp_path):
        """Whole words as the frozen tokenizer sees them -- 'words in it' misses 'it.'."""
        src = RANGE_SOURCE.replace('answers_words="several words in"',
                                   'answers_words="several words in it"')
        with pytest.raises(SystemExit, match="matches no run of words") as excinfo:
            build_ranges(tmp_path, src)
        assert "7:it." in str(excinfo.value)

    def test_an_ambiguous_word_quote_aborts(self, tmp_path):
        src = RANGE_SOURCE.replace(
            "Fourth sentence with several words in it.",
            "Fourth sentence with words and more words in it.",
        ).replace('answers_words="several words in"', 'answers_words="words"')
        with pytest.raises(SystemExit, match="matches 2 runs of words"):
            build_ranges(tmp_path, src)

    def test_a_range_reference_one_level_down(self, tmp_path):
        """
        The segments of a range-referencing contribution are `a3-4b1`, `a3-4b2`, … --
        anchoring inside them is what the segment-key pattern here has to allow for.
        """
        src = RANGE_SOURCE + (
            '\n<!-- !!== label=deep party=c\n'
            '     answers_from="An answer to the block"\n'
            '     answers_to="An answer to those words" ==== -->\n'
            "\nNo, that is two contributions.\n"
        )
        with pytest.raises(SystemExit, match="spans two contributions"):
            build_ranges(tmp_path, src)

        src = RANGE_SOURCE.replace(
            "An answer to the block.",
            "An answer to the block. A second sentence of it. A third one.",
        ) + (
            '\n<!-- !!== label=deep party=c\n'
            '     answers_from="An answer to the block"\n'
            '     answers_to="A second sentence of it" ==== -->\n'
            "\nA reply reaching into the block answer.\n"
        )
        assert build_ranges(tmp_path, src, name="deep")["deep"] == "a3-4b1-2c"


class TestBuild:
    def test_repo_contents_and_commits(self, tmp_path):
        keys = build_debate_repo(
            write_source(tmp_path),
            patches_into=str(tmp_path / "patches"),
            repo_into=str(tmp_path / "repo"),
        )
        repo = tmp_path / "repo"

        assert keys == {"root": "a", "answer": "a3b"}
        assert (repo / "a" / "a.md").exists()
        assert (repo / "b" / "a3b.md").exists()

        # the placeholders are replaced with the keys that are only known at build time
        assert "An answer to `a3`, in a contribution keyed `a3b`." in (repo / "b" / "a3b.md").read_text()

        log = subprocess.run(
            ["git", "log", "--format=%an|%ad|%s", "--date=iso-strict"],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        # newest first: the parties author their own commits, spaced by the declared step
        assert log[2].startswith("fair debate system|2026-03-01T08:00:00+01:00|first commit")
        assert log[1].startswith("Opener|2026-03-01T10:00:00+01:00|add contribution a/a.md")
        assert log[0].startswith("Answerer|2026-03-01T12:00:00+01:00|add contribution b/a3b.md")

    def test_patches_land_outside_the_repo(self, tmp_path):
        """`git format-patch` runs with the repo as cwd -- a relative target must not be
        resolved against it (which used to put the patches inside the built repo)."""
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            build_debate_repo(write_source(tmp_path), patches_into="patches", repo_into="repo")
        finally:
            os.chdir(cwd)
        assert (tmp_path / "patches" / "0001-first-commit.patch").exists()
        assert not (tmp_path / "repo" / "patches").exists()

    def test_default_patch_target_is_the_debate_key(self, tmp_path):
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            build_debate_repo(write_source(tmp_path))
        finally:
            os.chdir(cwd)
        assert (tmp_path / "d97-builder-demo" / "patches_01" / "0001-first-commit.patch").exists()


class TestProvenance:
    """
    `REPO_INFO.yaml` and the per-contribution `splitter_version`: what a repo says about
    the software and the source that made it. See `repo_handling.build_repo_info()`.
    """

    def test_built_repo_records_its_source(self, tmp_path):
        source_path = write_source(tmp_path)
        build_debate_repo(
            source_path,
            patches_into=str(tmp_path / "patches"),
            repo_into=str(tmp_path / "repo"),
        )

        info = yaml.safe_load((tmp_path / "repo" / "REPO_INFO.yaml").read_text())
        assert info["kind"] == "built"
        assert info["fdmd_version"] == fdmd_version
        # the directory above the file is what names the debate -- every source is
        # called `source.md`, so a bare basename would say nothing
        assert info["source"]["path"].endswith("source.md")
        assert os.path.dirname(info["source"]["path"])

        expected = hashlib.sha256(open(source_path, "rb").read()).hexdigest()
        assert info["source"]["sha256"] == expected

    def test_built_repo_records_no_instance_state(self, tmp_path):
        """
        A built repo goes into a checked-in patch collection and is rolled out unchanged
        on every deploy. Anything instance-dependent in it would give the debate a fresh
        chain of fingerprints whenever the platform is updated -- which is the damage this
        file exists to document, not to cause.
        """
        settings = repo_handling.PlatformSettings()
        settings.platform_version = "9.9.9"
        content = repo_handling.build_repo_info(
            source_path=write_source(tmp_path), settings=settings
        )
        assert "9.9.9" not in content
        assert "platform_version" not in content

    def test_opened_repo_records_the_platform(self, tmp_path):
        """The other half: a repo the platform opens for a live debate is written once and
        never rebuilt, so naming the platform version there costs nothing and says which
        software created the history."""
        settings = repo_handling.PlatformSettings()
        settings.platform_version = "9.9.9"
        info = yaml.safe_load(repo_handling.build_repo_info(settings=settings))
        assert info["kind"] == "opened"
        assert info["platform_version"] == "9.9.9"
        assert "source" not in info

    def test_contributions_record_the_splitter_version(self, tmp_path):
        build_debate_repo(
            write_source(tmp_path),
            patches_into=str(tmp_path / "patches"),
            repo_into=str(tmp_path / "repo"),
        )
        front_matter, body = split_front_matter((tmp_path / "repo" / "a" / "a.md").read_text())
        assert front_matter["splitter_version"] == SPLITTER_SYNTAX_VERSION
        # the body must be untouched by the header -- the keys are what answers point at
        assert body.startswith("# ::a1 Demo")
        # a fixture's chronology lives in its commit dates; a second copy in the file
        # could only ever disagree with them
        assert "created" not in front_matter

    def test_a_file_without_a_version_counts_as_version_one(self, tmp_path):
        """Everything written before the field existed came from ruleset 1, so the default
        is a statement about history rather than a fallback for a missing value."""
        front_matter, _ = split_front_matter("# ::a1 no header here\n")
        assert front_matter == {}
        assert DEFAULT_SPLITTER_SYNTAX_VERSION == 1

    def test_every_built_fixture_matches_its_source(self):
        """
        The recorded hash is only worth something if it is kept current: editing a
        `source.md` without rebuilding the repo would leave the collection naming a source
        it no longer came from, and nothing in the repo would show it. So the check is
        mechanical rather than a rule in a document.

        Every fixture with a `source.md` is covered, which since 2026-09-02 is every
        fixture that has a source at all -- d31/d32/d33 lost their own build scripts then.
        """
        prep_dir = pjoin(os.path.dirname(fixtures.__file__), "repo-preparation")
        sources = sorted(glob.glob(pjoin(prep_dir, "*__plain", "source.md")))
        assert sources, f"no fixture sources found below {prep_dir}"

        checked = 0
        for source_path in sources:
            meta, _ = read_source(source_path)
            patch = pjoin(fixtures.TEST_REPO_HOST_DIR, meta["debate_key"],
                          "patches_01", "0001-first-commit.patch")
            if not os.path.exists(patch):
                continue

            info_src = _repo_info_from_patch(open(patch).read())
            if info_src is None:
                continue

            info = yaml.safe_load(info_src)
            expected = hashlib.sha256(open(source_path, "rb").read()).hexdigest()
            assert info["source"]["sha256"] == expected, (
                f"{meta['debate_key']}: the patch collection records a different source "
                f"than {os.path.relpath(source_path, prep_dir)} currently is -- rebuild it "
                f"with `fdmd build-debate-repo ... --into-fixtures`"
            )
            checked += 1

        assert checked, "no built fixture carried a REPO_INFO.yaml -- did the build change?"


def _repo_info_from_patch(patch_text: str) -> str | None:
    """The content of REPO_INFO.yaml as the given patch creates it, or None."""
    lines = patch_text.splitlines()
    try:
        start = lines.index(f"+++ b/{repo_handling.REPO_INFO_FILENAME}")
    except ValueError:
        return None

    out = []
    for line in lines[start + 1:]:
        if line.startswith("+"):
            out.append(line[1:])
        elif line.startswith("@@"):
            continue
        elif out:
            break
    return "\n".join(out)


class TestReadRepoInfo:
    def test_absent_file_is_a_normal_answer(self, tmp_path):
        """The collections predating this file cannot be given provenance retroactively,
        so the caller has to be able to say "not recorded" instead of guessing."""
        assert repo_handling.read_repo_info(str(tmp_path), "d99-nothing-here") == {}

    def test_roundtrip(self, tmp_path):
        repo_dir = tmp_path / "d99-demo"
        repo_dir.mkdir()
        (repo_dir / repo_handling.REPO_INFO_FILENAME).write_text(
            repo_handling.build_repo_info()
        )
        info = repo_handling.read_repo_info(str(tmp_path), "d99-demo")
        assert info["kind"] == "opened"
        assert info["fdmd_version"]

    def test_damaged_file_does_not_propagate(self, tmp_path):
        """A repo is handed out and cloned; a broken metadata file in one must not be able
        to take down the page that lists it."""
        repo_dir = tmp_path / "d99-demo"
        repo_dir.mkdir()
        (repo_dir / repo_handling.REPO_INFO_FILENAME).write_text("kind: [unclosed\n")
        assert repo_handling.read_repo_info(str(tmp_path), "d99-demo") == {}
