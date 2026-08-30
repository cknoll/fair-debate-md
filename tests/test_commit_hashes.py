"""
Commit hashes: returned by the commit functions and derived from an existing repo.

Background: the web app needs a per-contribution commit hash to display and to export
(`konzept_manipulationssicherheit.md` in the web repo, E1). Until now `commit_ctb_list`
discarded the commit object it created, and nothing could map a contribution key back to
a commit at all.
"""

import os
import re
import subprocess

import pytest

import fair_debate_md as fdmd
from fair_debate_md.core import (
    DBContribution,
    contribution_commit_hashes,
    debate_bundle,
    debate_commit_log,
    prepare_repo_for_serving,
)


pjoin = os.path.join

SHA_REGEX = re.compile(r"^[0-9a-f]{40}$")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make_debate_repo(host_dir, debate_key="d-hashes"):
    """
    A repo in the shape the web app creates: one initial commit with repo-level
    files, then contributions added through `commit_ctb*`.

    Returns the repo directory. Note that `repo_handling.create_repo` chdirs into
    the new repo; the caller is expected to run inside a tmp dir anyway.
    """
    fdmd.repo_handling.create_repo(host_dir, debate_key, initial_files={"README.md": "# test\n"})
    repo_dir = pjoin(host_dir, debate_key)
    _git(repo_dir, "config", "user.email", "t@t")
    _git(repo_dir, "config", "user.name", "t")
    _git(repo_dir, "config", "commit.gpgsign", "false")
    return repo_dir


def _log_hashes(repo_dir):
    res = subprocess.run(
        ["git", "log", "--format=%H"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    return res.stdout.split()


def _head(repo_dir):
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    return res.stdout.strip()


def test_commit_ctb_returns_the_commit_hash(tmp_path):
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)

    ctb = DBContribution("a", "::a1 First. ::a2 Second.")
    sha = fdmd.commit_ctb(host_dir, "d-hashes", ctb)

    assert SHA_REGEX.match(sha), sha
    assert sha == _head(repo_dir)


def test_commit_ctb_list_returns_one_hash_shared_by_all_contributions(tmp_path):
    """
    Several contributions published in one action land in ONE commit, so they share
    one hash. Intended -- but it means a hash does not identify a contribution.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)

    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First. ::a2 Second."))
    sha = fdmd.commit_ctb_list(
        host_dir,
        "d-hashes",
        [DBContribution("a1b", "::a1b1 Reply one."), DBContribution("a2b", "::a2b1 Reply two.")],
    )

    assert SHA_REGEX.match(sha), sha
    assert sha == _head(repo_dir)

    hashes = contribution_commit_hashes(host_dir, "d-hashes")
    assert hashes["a1b"] == sha
    assert hashes["a2b"] == sha


def test_contribution_commit_hashes_maps_every_contribution(tmp_path):
    host_dir = str(tmp_path)
    _make_debate_repo(host_dir)

    sha_a = fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First. ::a2 Second."))
    sha_b = fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a1b", "::a1b1 Reply b."))

    hashes = contribution_commit_hashes(host_dir, "d-hashes")

    # exactly the contributions, no repo-level files (README.md carries no key)
    assert set(hashes) == {"a", "a1b"}
    assert hashes["a"] == sha_a
    assert hashes["a1b"] == sha_b


def test_contribution_commit_hashes_follows_the_last_change(tmp_path):
    """
    The point of the whole feature: a changed contribution must get a changed hash.
    The commit that *introduced* the file would keep displaying the old one.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)

    sha_intro = fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))
    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a1b", "::a1b1 Reply b."))

    before = contribution_commit_hashes(host_dir, "d-hashes")
    assert before["a"] == sha_intro

    # tamper with the published root contribution
    fpath = pjoin(repo_dir, "a", "a.md")
    with open(fpath, "r") as fp:
        content = fp.read()
    with open(fpath, "w") as fp:
        fp.write(content.replace("First.", "Something else entirely."))
    _git(repo_dir, "add", "a/a.md")
    _git(repo_dir, "commit", "-q", "-m", "tampered")

    after = contribution_commit_hashes(host_dir, "d-hashes")
    assert after["a"] == _head(repo_dir)
    assert after["a"] != before["a"]
    # the untouched contribution keeps its hash
    assert after["a1b"] == before["a1b"]


def test_contribution_commit_hashes_ignores_deleted_files(tmp_path):
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)

    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))
    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a1b", "::a1b1 Reply b."))

    _git(repo_dir, "rm", "-q", "b/a1b.md")
    _git(repo_dir, "commit", "-q", "-m", "remove a1b")

    hashes = contribution_commit_hashes(host_dir, "d-hashes")
    assert set(hashes) == {"a"}


@pytest.mark.parametrize("debate_key", ["does-not-exist", "plain-dir"])
def test_contribution_commit_hashes_without_repo_returns_empty(tmp_path, debate_key):
    """
    Same safe direction as `debate_stats.repo_head_fingerprint` in the web app: a
    missing or unreadable repo yields nothing to display, never an exception on a
    page that would otherwise render fine.
    """
    host_dir = str(tmp_path)
    os.makedirs(pjoin(host_dir, "plain-dir"))

    assert contribution_commit_hashes(host_dir, debate_key) == {}


def test_debate_commit_log_is_newest_first_with_timestamps(tmp_path):
    host_dir = str(tmp_path)
    _make_debate_repo(host_dir)

    sha_a = fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))
    sha_b = fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a1b", "::a1b1 Reply b."))

    log = debate_commit_log(host_dir, "d-hashes")

    # newest first: reply, root, then the repo's initial commit
    chain = [entry["hash"] for entry in log]
    assert chain[:2] == [sha_b, sha_a]
    assert len(log) == 3

    assert log[0]["contribution_keys"] == ["a1b"]
    assert log[1]["contribution_keys"] == ["a"]
    # the initial commit carries only README.md -- kept, but with no contribution
    assert log[2]["contribution_keys"] == []

    for entry in log:
        assert entry["timestamp"].startswith("20"), entry["timestamp"]


def test_debate_commit_log_groups_a_multi_contribution_commit(tmp_path):
    host_dir = str(tmp_path)
    _make_debate_repo(host_dir)

    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First. ::a2 Second."))
    sha = fdmd.commit_ctb_list(
        host_dir,
        "d-hashes",
        [DBContribution("a1b", "::a1b1 Reply one."), DBContribution("a2b", "::a2b1 Reply two.")],
    )

    newest = debate_commit_log(host_dir, "d-hashes")[0]
    assert newest["hash"] == sha
    assert sorted(newest["contribution_keys"]) == ["a1b", "a2b"]


def test_debate_commit_log_keeps_deleted_contributions(tmp_path):
    """
    Unlike the hash map: a chain shown as evidence must not quietly omit a removal.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)

    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))
    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a1b", "::a1b1 Reply b."))
    _git(repo_dir, "rm", "-q", "b/a1b.md")
    _git(repo_dir, "commit", "-q", "-m", "remove a1b")

    log = debate_commit_log(host_dir, "d-hashes")
    assert log[0]["contribution_keys"] == ["a1b"], "the removal commit still names the file"
    assert "a1b" not in contribution_commit_hashes(host_dir, "d-hashes")


@pytest.mark.parametrize("debate_key", ["does-not-exist", "plain-dir"])
def test_debate_commit_log_without_repo_returns_empty(tmp_path, debate_key):
    host_dir = str(tmp_path)
    os.makedirs(pjoin(host_dir, "plain-dir"))

    assert debate_commit_log(host_dir, debate_key) == []


def test_debate_bundle_clones_back_into_the_same_history(tmp_path):
    """
    The bundle is handed to readers so they can run `git log` on the chain themselves
    (integrity page, "how to check"). It therefore has to be a real repo again after a
    `git clone`, carrying the very hashes the page displays -- an archive of the working
    tree would look similar and prove nothing.
    """
    host_dir = str(tmp_path)
    _make_debate_repo(host_dir)

    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))
    sha_b = fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a1b", "::a1b1 Reply b."))

    blob = debate_bundle(host_dir, "d-hashes")
    assert blob.startswith(b"# v2 git bundle"), blob[:40]

    bundle_path = pjoin(host_dir, "out.bundle")
    with open(bundle_path, "wb") as fp:
        fp.write(blob)

    clone_dir = pjoin(host_dir, "clone")
    subprocess.run(["git", "clone", "-q", bundle_path, clone_dir], check=True, capture_output=True)

    assert _head(clone_dir) == sha_b
    # the whole chain travels along, not just the tip
    assert [e["hash"] for e in debate_commit_log(host_dir, "d-hashes")] == _log_hashes(clone_dir)
    # ... and so does the content
    assert os.path.isfile(pjoin(clone_dir, "b", "a1b.md"))


@pytest.mark.parametrize("debate_key", ["does-not-exist", "plain-dir"])
def test_debate_bundle_without_repo_returns_empty(tmp_path, debate_key):
    """
    Same safe direction as its neighbours: the caller gets nothing to hand out, not an
    exception on a page that would otherwise render fine.
    """
    host_dir = str(tmp_path)
    os.makedirs(pjoin(host_dir, "plain-dir"))

    assert debate_bundle(host_dir, debate_key) == b""


def test_committing_keeps_the_http_server_info_current(tmp_path):
    """
    The reason this runs after every commit rather than on a schedule: a dumb HTTP client
    reads `info/refs` as written, so a stale one makes a clone deliver an OLDER state
    without failing. On the integrity page that is the worst failure mode available -- a
    reader would not find the fingerprint they noted and conclude manipulation.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)

    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))
    info_refs = pjoin(repo_dir, ".git", "info", "refs")
    assert os.path.isfile(info_refs), "a clone cannot find any ref without this file"
    assert _head(repo_dir) in open(info_refs).read()

    # ... and it follows along, instead of freezing at the first commit
    sha_b = fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a1b", "::a1b1 Reply b."))
    assert sha_b in open(info_refs).read()


def test_prepare_repo_packs_once_loose_objects_pile_up(tmp_path):
    """
    Every loose object costs the cloning client its own HTTP request; packing them turns
    a few hundred requests into a handful. The threshold is ours because `git gc --auto`
    samples one object bucket and reports zero at these repo sizes.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)
    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 One. ::a2 Two. ::a3 Three."))
    for ctb_key in ["a1b", "a2c", "a3d", "a1e"]:
        fdmd.commit_ctb(host_dir, "d-hashes", DBContribution(ctb_key, f"::{ctb_key}1 Reply."))

    def loose_count():
        res = subprocess.run(
            ["git", "count-objects", "-v"], cwd=repo_dir, capture_output=True, text=True
        )
        return int(res.stdout.split("count: ")[1].split()[0])

    assert loose_count() > 0, "the commits above should leave loose objects behind"

    # below the limit nothing is packed -- gc on every commit would be wasted work
    prepare_repo_for_serving(repo_dir, loose_object_limit=10_000)
    assert loose_count() > 0

    prepare_repo_for_serving(repo_dir, loose_object_limit=0)
    assert loose_count() == 0, "above the limit the objects move into a pack"
    assert os.path.isfile(pjoin(repo_dir, ".git", "objects", "info", "packs"))
    # packing must not lose anything the page displays
    assert len(debate_commit_log(host_dir, "d-hashes")) == 6


@pytest.mark.parametrize("debate_key", ["does-not-exist", "plain-dir"])
def test_prepare_repo_without_repo_is_silent(tmp_path, debate_key):
    """A repo that cannot be prepared must not bring down the publishing that succeeded."""
    host_dir = str(tmp_path)
    os.makedirs(pjoin(host_dir, "plain-dir"))

    prepare_repo_for_serving(pjoin(host_dir, debate_key))


def _make_signing_key(tmp_dir):
    """A throwaway key, so the signing path is exercised without touching a real one."""
    key_path = pjoin(tmp_dir, "test_signing_key")
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", key_path],
        check=True,
        capture_output=True,
    )
    return key_path


def _signature_states(repo_dir, allowed_signers=None):
    """`%G?` per commit, newest first: G = good, U = unknown key, N = unsigned."""
    args = ["git"]
    if allowed_signers is not None:
        args += ["-c", f"gpg.ssh.allowedSignersFile={allowed_signers}"]
    res = subprocess.run(
        args + ["log", "--format=%G?"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    return res.stdout.split()


def test_commits_carry_the_platform_identity(tmp_path):
    """
    Without an explicit committer git falls back to the identity of the unix user running
    the process -- which put a private address into every commit of every debate repo, and
    those repos are downloadable. It is also the principal `allowed_signers` names.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)

    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))

    res = subprocess.run(
        ["git", "log", "--format=%cn|%ce|%an", "-1"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    committer_name, committer_email, author_name = res.stdout.strip().split("|")
    settings = fdmd.repo_handling.platform_settings
    assert committer_name == settings.committer_name
    assert committer_email == settings.committer_email
    # the author still names the contributing party -- that distinction is the point
    assert author_name != committer_name


def test_commits_are_signed_when_a_key_is_configured(tmp_path):
    """
    E4: a signature turns "a manipulation can be noticed" into "it can be proven". The
    check runs through git itself with an allowed_signers file, because a signature that
    is present but does not verify would be worthless and looks identical from Python.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)
    key_path = _make_signing_key(host_dir)

    settings = fdmd.repo_handling.platform_settings
    previous = settings.signing_key_path
    settings.signing_key_path = key_path
    try:
        fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))
        fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a1b", "::a1b1 Reply."))
    finally:
        settings.signing_key_path = previous

    allowed = pjoin(host_dir, "allowed_signers")
    with open(f"{key_path}.pub") as fp:
        key_type, key_data = fp.read().split()[:2]
    with open(allowed, "w") as fp:
        fp.write(f"{settings.committer_email} {key_type} {key_data}\n")

    states = _signature_states(repo_dir, allowed)
    assert states[:2] == ["G", "G"], states
    # the repo's initial commit predates the key and stays unsigned -- signing starts
    # where it starts, it does not rewrite what came before
    assert states[-1] == "N", states


def test_commits_stay_unsigned_without_a_key(tmp_path):
    """Running this library must not require a secret."""
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)
    assert fdmd.repo_handling.platform_settings.signing_key_path is None

    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))

    assert _signature_states(repo_dir) == ["N", "N"]
