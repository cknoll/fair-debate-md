import os
import tempfile

import yaml

from fair_debate_md.core import (
    DBContribution,
    split_front_matter,
    write_ctb_to_file,
)
from fair_debate_md.key_management import SPLITTER_SYNTAX_VERSION


def test_yaml_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        ctb = DBContribution(ctb_key="a1b", body="Hello world\n")
        write_ctb_to_file(tmp, ctb)
        with open(ctb.fpath) as fp:
            content = fp.read()

        assert content.startswith("---\n")
        fm, body = split_front_matter(content)
        assert isinstance(fm, dict)
        assert "created" in fm
        # ISO-8601 year prefix
        assert fm["created"].startswith("20")
        # what split_front_matter returns must match what yaml.safe_load yields
        # on the raw header block
        end_idx = content.find("\n---\n", 4)
        header_src = content[4:end_idx]
        parsed = yaml.safe_load(header_src)
        assert parsed["created"] == fm["created"]
        # body should not contain the header markers
        assert not body.startswith("---")


def test_split_front_matter_missing_header():
    text = "no header here\nstill no header\n"
    fm, body = split_front_matter(text)
    assert fm == {}
    assert body == text


def test_split_front_matter_dict_order_hint_default():
    # ensure order_hint default does not break existing callers
    ctb = DBContribution(ctb_key="a1b", body="x")
    assert ctb.order_hint is None


def test_live_publication_records_the_splitter_version():
    """
    The rules that decided where the `::aN` markers sit have to travel with the file:
    the repo is handed out on its own, and segment keys are the prefix of every answer
    key, so re-segmenting under changed rules breaks every reference into the text.
    """
    with tempfile.TemporaryDirectory() as tmp:
        ctb = DBContribution(ctb_key="a1b", body="Hello world. And a second sentence.\n")
        write_ctb_to_file(tmp, ctb)
        with open(ctb.fpath) as fp:
            fm, body = split_front_matter(fp.read())

    assert fm["splitter_version"] == SPLITTER_SYNTAX_VERSION
    assert body.startswith("::a1b1 Hello world.")


def test_key_with_traversal_is_refused_before_anything_is_written():
    """
    A contribution key decides the path this function writes to, so a key holding `../`
    escapes the repository -- and the escape does not stop at the project directory.

    Reachable from the web platform until 2026-09-07 (security audit S1): the key is
    assembled there from a hidden form field, and the platform's own validation had a gap
    for exactly the keys that leave the tree. The platform closed that gap; this checks
    the second line, which lives here because this is the function that writes and it has
    other callers (the builder, the CLI).

    Both halves matter: nothing is written, and no directory is left behind either -- the
    check runs before `makedirs`, which would otherwise create the escaped path.
    """
    import pytest

    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = os.path.join(tmp, "repo")
        os.makedirs(repo_dir)
        outside = os.path.join(tmp, "OUTSIDE")

        ctb = DBContribution(ctb_key="../../OUTSIDEa", body="whatever\n")
        with pytest.raises(ValueError, match="outside the repository"):
            write_ctb_to_file(repo_dir, ctb)

        assert not os.path.exists(f"{outside}.md")
        assert os.listdir(tmp) == ["repo"], "a directory was created outside the repo"
        assert os.listdir(repo_dir) == [], "something was created inside the repo"
