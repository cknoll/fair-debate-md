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
)
from fair_debate_md.repo_handling import prepare_repo_for_serving


pjoin = os.path.join

SHA_REGEX = re.compile(r"^[0-9a-f]{40}$")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make_debate_repo(host_dir, debate_key="d-hashes"):
    """
    A repo in the shape the web app creates: one initial commit with repo-level
    files, then contributions added through `commit_ctb*`.

    Returns the repo directory.
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


def test_commit_ctb_list_refuses_an_empty_list(tmp_path):
    """
    Nothing to commit is the caller's decision to make, not ours. Before 2026-09-09 the
    empty list crashed with an `UnboundLocalError` deep inside the function -- the web
    platform hit that whenever a participant published "all" with nothing pending.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)
    head_before = _head(repo_dir)

    with pytest.raises(ValueError, match="no contributions to commit"):
        fdmd.commit_ctb_list(host_dir, "d-hashes", [])

    # refused before anything was written: no commit, no staged leftovers
    assert _head(repo_dir) == head_before
    res = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    assert res.stdout == ""


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


def test_contribution_commit_hashes_covers_range_referencing_keys(tmp_path):
    """
    The regression test for the bug that made this whole area worth revisiting: the path
    regex described a key as `[a-z0-9]+`, so every key carrying a range (`a3-6b`) or a
    word range (`a7_7-12f`) fell into the branch meant for README.md and vanished from
    the hash map -- on `d32-overlapping-refs` that was 4 of 9 contributions.

    It stayed unnoticed because nothing counted contributions on a debate that has such
    keys: the integrity page simply showed fewer rows, and a `?ctb=a3-6b` link resolved
    to nothing, which the view treats as "no focus" and thus looks merely outdated.

    The keys below are the ones that repo actually contains, nested case included.
    """
    host_dir = str(tmp_path)
    _make_debate_repo(host_dir)

    fdmd.commit_ctb(
        host_dir, "d-hashes", DBContribution("a", " ".join(f"::a{i} S{i}." for i in range(1, 13)))
    )
    range_keys = ["a3-6b", "a5-8d", "a7_7-12f", "a7_10-16g", "a3-6b1-2h"]
    expected = {"a"}
    for ctb_key in range_keys:
        fdmd.commit_ctb(host_dir, "d-hashes", DBContribution(ctb_key, f"::{ctb_key}1 Reply."))
        expected.add(ctb_key)

    hashes = contribution_commit_hashes(host_dir, "d-hashes")
    assert set(hashes) == expected

    # the commit log has to agree about what a contribution is -- the two functions
    # share the path regex, and a divergence here means one of them lies
    logged_keys = {
        key
        for entry in debate_commit_log(host_dir, "d-hashes")
        for key in entry["contribution_keys"]
    }
    assert logged_keys == expected


def test_repo_level_files_are_skipped_without_a_warning(caplog):
    """
    The counterpart to the check below: what a repo legitimately carries at its root
    must not produce noise, otherwise the warning is ignored within a fortnight.
    """
    from fair_debate_md.core import _ctb_key_from_rel_path

    unexpected = set()
    with caplog.at_level("WARNING"):
        for rel_path in ["README.md", "REPO_INFO.yaml", "allowed_signers"]:
            assert _ctb_key_from_rel_path(rel_path, unexpected) is None

    assert unexpected == set()
    assert caplog.records == []


def test_an_unrecognized_path_is_reported_once(tmp_path, caplog):
    """
    A path that is neither a contribution nor a known repo-level file used to share the
    silent branch with both. It now says so -- once per call, not once per commit that
    touched the file, since git names a path in every commit that changed it.
    """
    host_dir = str(tmp_path)
    repo_dir = _make_debate_repo(host_dir)
    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))

    stray = pjoin(repo_dir, "a", "NOT_A_KEY.md")
    for round_no in range(2):
        with open(stray, "w") as fp:
            fp.write(f"stray {round_no}\n")
        _git(repo_dir, "add", "a/NOT_A_KEY.md")
        _git(repo_dir, "commit", "-q", "-m", f"stray {round_no}")

    with caplog.at_level("WARNING"):
        hashes = contribution_commit_hashes(host_dir, "d-hashes")

    assert set(hashes) == {"a"}, "the stray file must not become a contribution"
    warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert len(warnings) == 1, "two commits touched it, but the report is per call"
    assert "a/NOT_A_KEY.md" in warnings[0].getMessage()


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


def test_a_new_repo_ships_allowed_signers_in_its_first_commit(tmp_path):
    """
    Without this file a reader who clones the repo cannot verify anything -- git refuses
    with "gpg.ssh.allowedSignersFile needs to be configured". Shipping it inside the repo
    turns the check into two commands and no key hunting.

    It has to be COMMITTED, not merely present: an untracked file travels with neither
    `git clone` nor `debate_bundle()`.
    """
    host_dir = str(tmp_path)
    key_path = _make_signing_key(host_dir)

    settings = fdmd.repo_handling.platform_settings
    previous = settings.signing_key_path
    settings.signing_key_path = key_path
    try:
        repo_dir = _make_debate_repo(host_dir, debate_key="d-signed")
        fdmd.commit_ctb(host_dir, "d-signed", DBContribution("a", "::a1 First."))
    finally:
        settings.signing_key_path = previous

    signers_path = pjoin(repo_dir, "allowed_signers")
    assert os.path.isfile(signers_path)

    tracked = subprocess.run(
        ["git", "ls-files", "allowed_signers"], cwd=repo_dir, capture_output=True, text=True
    )
    assert tracked.stdout.strip() == "allowed_signers", "must be committed, not just present"

    # ... and it actually verifies the repo's own commits, which is the whole point
    assert _signature_states(repo_dir, signers_path)[0] == "G"


def test_without_a_key_no_allowed_signers_is_written(tmp_path):
    """A file naming no key would only mislead."""
    host_dir = str(tmp_path)
    assert fdmd.repo_handling.platform_settings.signing_key_path is None
    repo_dir = _make_debate_repo(host_dir)

    assert not os.path.exists(pjoin(repo_dir, "allowed_signers"))


def test_the_commit_log_can_report_the_signature_status(tmp_path):
    """
    What the integrity page shows per commit. It verifies against the repo's own
    `allowed_signers` -- the same file a reader who clones will use.
    """
    host_dir = str(tmp_path)
    key_path = _make_signing_key(host_dir)

    settings = fdmd.repo_handling.platform_settings
    previous = settings.signing_key_path
    settings.signing_key_path = key_path
    try:
        _make_debate_repo(host_dir, debate_key="d-signed")
        fdmd.commit_ctb(host_dir, "d-signed", DBContribution("a", "::a1 First."))
    finally:
        settings.signing_key_path = previous

    log = debate_commit_log(host_dir, "d-signed", with_signature_status=True)
    assert [entry["signature"] for entry in log] == ["G", "G"]

    # off by default: verifying costs a signature check per commit, and only one page
    # displays it
    plain = debate_commit_log(host_dir, "d-signed")
    assert all(entry["signature"] == "" for entry in plain)


def test_unsigned_commits_are_reported_as_such(tmp_path):
    host_dir = str(tmp_path)
    _make_debate_repo(host_dir)
    fdmd.commit_ctb(host_dir, "d-hashes", DBContribution("a", "::a1 First."))

    log = debate_commit_log(host_dir, "d-hashes", with_signature_status=True)
    assert [entry["signature"] for entry in log] == ["N", "N"]


def test_the_signing_key_fingerprint_is_available(tmp_path):
    """Shown on the integrity page and written into the hash export, so a reader can tell
    later whether the key changed."""
    host_dir = str(tmp_path)
    key_path = _make_signing_key(host_dir)

    settings = fdmd.repo_handling.platform_settings
    previous = settings.signing_key_path
    settings.signing_key_path = key_path
    try:
        fingerprint = fdmd.repo_handling.signing_key_fingerprint()
    finally:
        settings.signing_key_path = previous

    assert fingerprint.startswith("SHA256:")
    expected = subprocess.run(
        ["ssh-keygen", "-lf", key_path], capture_output=True, text=True, check=True
    )
    assert fingerprint in expected.stdout

    settings.signing_key_path = None
    assert fdmd.repo_handling.signing_key_fingerprint() == ""
    settings.signing_key_path = previous
