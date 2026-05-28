"""Phase 4 — Sorting via order_hint + git fallback for legacy headerless files."""

import os
import subprocess
import tempfile
import textwrap

import pytest

from fair_debate_md.core import (
    DBContribution,
    DebateDirLoader,
    MDProcessor,
    _sort_key,
)


pjoin = os.path.join


def _setup_three_party_debate(root_dir):
    """
    Create the standard a/b/c/d layout used by these tests.

    Layout:
        <root_dir>/a/a.md   (statement with 3 segments a1, a2, a3)
        <root_dir>/b/a1b.md (reply to a1 by token b)
        <root_dir>/c/a1c.md (reply to a1 by token c)
        <root_dir>/d/a1d.md (reply to a1 by token d)
    """
    a_dir = pjoin(root_dir, "a")
    b_dir = pjoin(root_dir, "b")
    c_dir = pjoin(root_dir, "c")
    d_dir = pjoin(root_dir, "d")
    for p in (a_dir, b_dir, c_dir, d_dir):
        os.makedirs(p)

    with open(pjoin(a_dir, "a.md"), "w") as fp:
        fp.write("::a1 First. ::a2 Second. ::a3 Third.\n")
    with open(pjoin(b_dir, "a1b.md"), "w") as fp:
        fp.write("::a1b1 Reply b.\n")
    with open(pjoin(c_dir, "a1c.md"), "w") as fp:
        fp.write("::a1c1 Reply c.\n")
    with open(pjoin(d_dir, "a1d.md"), "w") as fp:
        fp.write("::a1d1 Reply d.\n")

    return {
        "a": pjoin(a_dir, "a.md"),
        "a1b": pjoin(b_dir, "a1b.md"),
        "a1c": pjoin(c_dir, "a1c.md"),
        "a1d": pjoin(d_dir, "a1d.md"),
    }


def _git(cwd, *args, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env=env,
    )


def _git_init_with_identity(repo_dir):
    _git(repo_dir, "init", "-q", "-b", "main")
    _git(repo_dir, "config", "user.email", "t@t")
    _git(repo_dir, "config", "user.name", "t")
    _git(repo_dir, "config", "commit.gpgsign", "false")


def _git_commit_file(repo_dir, rel_fpath, message, author_date):
    """
    Stage a single file and commit it with a fixed author/committer date,
    so commit-order timestamps are deterministic.
    """
    env = {
        "GIT_AUTHOR_DATE": author_date,
        "GIT_COMMITTER_DATE": author_date,
    }
    _git(repo_dir, "add", rel_fpath, env_extra=env)
    _git(repo_dir, "commit", "-q", "-m", message, env_extra=env)


# ---------------------------------------------------------------------------
# (a) Headerless legacy files, no git repo -> fall back to lex. tiebreaker.
# ---------------------------------------------------------------------------


def test_headerless_no_git_sorts_lexicographically():
    with tempfile.TemporaryDirectory() as tmp:
        _setup_three_party_debate(tmp)

        ddl = DebateDirLoader(dirpath=tmp, debate_key="test-no-git")
        ddl.load_dir()

        # all three siblings under a1 should have order_hint == None
        for k in ("a1b", "a1c", "a1d"):
            assert ddl.tree[k].order_hint is None, (
                f"{k}: expected order_hint=None (no header, no git), got {ddl.tree[k].order_hint!r}"
            )

        ddl.generate_html_with_contributions()
        childs = ddl.root_mdp.contribution_childs["a1"]
        keys = [c.key_prefix for c in childs]
        assert keys == ["a1b", "a1c", "a1d"], keys


# ---------------------------------------------------------------------------
# (b) Headerless files in a git repo -> mdp.created comes from git, order
#     follows commit time, not lex order.
# ---------------------------------------------------------------------------


def test_headerless_with_git_sorts_by_commit_time():
    with tempfile.TemporaryDirectory() as tmp:
        paths = _setup_three_party_debate(tmp)
        _git_init_with_identity(tmp)

        # root statement is committed first
        _git_commit_file(tmp, "a/a.md", "add root", "2024-01-01T10:00:00+00:00")
        # Now commit children OUT of lex order: c first, then b, then d.
        _git_commit_file(tmp, "c/a1c.md", "add a1c", "2024-02-01T10:00:00+00:00")
        _git_commit_file(tmp, "b/a1b.md", "add a1b", "2024-03-01T10:00:00+00:00")
        _git_commit_file(tmp, "d/a1d.md", "add a1d", "2024-04-01T10:00:00+00:00")

        ddl = DebateDirLoader(dirpath=tmp, debate_key="test-with-git")
        ddl.load_dir()

        # all three siblings should have ISO timestamps from git
        for k in ("a1b", "a1c", "a1d"):
            assert ddl.tree[k].order_hint is not None, (
                f"{k}: expected git-derived order_hint, got None"
            )
            assert ddl.tree[k].order_hint.startswith("2024-"), ddl.tree[k].order_hint

        ddl.generate_html_with_contributions()
        childs = ddl.root_mdp.contribution_childs["a1"]
        keys = [c.key_prefix for c in childs]
        # c committed earliest, then b, then d
        assert keys == ["a1c", "a1b", "a1d"], keys


# ---------------------------------------------------------------------------
# (c) YAML header beats git: a file with explicit `created` far in the past
#     sorts before all git-derived siblings.
# ---------------------------------------------------------------------------


def test_yaml_header_beats_git():
    with tempfile.TemporaryDirectory() as tmp:
        paths = _setup_three_party_debate(tmp)

        # Add a fourth role-token e: header says 1999-01-01 (very old), but
        # the file is committed last so git would say it's the newest.
        e_dir = pjoin(tmp, "e")
        os.makedirs(e_dir)
        with open(pjoin(e_dir, "a1e.md"), "w") as fp:
            fp.write(
                "---\ncreated: '1999-01-01T00:00:00+00:00'\n---\n"
                "::a1e1 Reply e.\n"
            )

        _git_init_with_identity(tmp)
        _git_commit_file(tmp, "a/a.md", "add root", "2024-01-01T10:00:00+00:00")
        _git_commit_file(tmp, "c/a1c.md", "add a1c", "2024-02-01T10:00:00+00:00")
        _git_commit_file(tmp, "b/a1b.md", "add a1b", "2024-03-01T10:00:00+00:00")
        _git_commit_file(tmp, "d/a1d.md", "add a1d", "2024-04-01T10:00:00+00:00")
        _git_commit_file(tmp, "e/a1e.md", "add a1e", "2024-05-01T10:00:00+00:00")

        ddl = DebateDirLoader(dirpath=tmp, debate_key="test-header-wins")
        ddl.load_dir()

        assert ddl.tree["a1e"].order_hint == "1999-01-01T00:00:00+00:00"

        ddl.generate_html_with_contributions()
        childs = ddl.root_mdp.contribution_childs["a1"]
        keys = [c.key_prefix for c in childs]
        # e first (1999), then git order c, b, d
        assert keys == ["a1e", "a1c", "a1b", "a1d"], keys


# ---------------------------------------------------------------------------
# (d) Sort-function unit test mixing order_hint (DB-style) + created (repo-style)
# ---------------------------------------------------------------------------


def test_sort_key_mixed_order_hint_and_none():
    """Unit test for `_sort_key`: order_hint asc, None last, lex. tiebreaker."""
    # Build lightweight MDProcessor instances and set the attributes the
    # sort key reads (order_hint, key_prefix).
    def _mk(key, order_hint):
        m = MDProcessor(key_prefix=key, md_with_real_keys=f"::{key}1 x.")
        m.order_hint = order_hint
        return m

    items = [
        _mk("a1d", "2024-04-01T10:00:00+00:00"),
        _mk("a1b", None),
        _mk("a1c", "2024-02-01T10:00:00+00:00"),
        _mk("a1e", None),
        _mk("a1f", "2024-02-01T10:00:00+00:00"),  # same hint as a1c -> lex
    ]
    items.sort(key=_sort_key)
    keys = [m.key_prefix for m in items]
    # a1c and a1f share hint -> lex (c < f), then a1d, then Nones lex (b < e)
    assert keys == ["a1c", "a1f", "a1d", "a1b", "a1e"], keys


def test_sort_key_db_contribution_with_order_hint_beats_no_hint():
    """A DBContribution-style mdp with order_hint sorts ahead of a None one."""
    m_db = MDProcessor(key_prefix="a1c", plain_md="x")
    m_db.order_hint = "2024-01-01T00:00:00+00:00"

    m_legacy = MDProcessor(key_prefix="a1b", md_with_real_keys="::a1b1 y.")
    m_legacy.order_hint = None  # explicit

    siblings = [m_legacy, m_db]
    siblings.sort(key=_sort_key)
    assert [s.key_prefix for s in siblings] == ["a1c", "a1b"]
