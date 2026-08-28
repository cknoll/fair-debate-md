"""
Tests for `fdmd build-debate-repo` / `fair_debate_md.debate_builder`.

The sources here are miniature and written for the test: the fixture debates are
user-facing texts and get rewritten, so asserting on their content would tie these tests
to editorial decisions (see `testdata/process_content_dir__plain/README.md`).
"""

import os
import subprocess

import pytest

from fair_debate_md.debate_builder import build_debate_repo, read_source

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


def write_source(tmp_path, text=SOURCE) -> str:
    fpath = tmp_path / "source.md"
    fpath.write_text(text)
    return str(fpath)


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
