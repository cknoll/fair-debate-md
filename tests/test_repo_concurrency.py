"""
Opening repos from several threads at once.

The platform calls `create_repo()` + `commit_ctb()` from a request handler, and a web
server may serve two requests at the same time. Until 0.11.1 that path steered git
through *process-global* state -- `os.chdir(repo_dir)`, then a bare `os.system("git
init")` and `open(fname, "w")` relative to it -- which a second thread silently
redirects. Two threads were enough to break one of the two repos, eight broke all eight:
`git init` ran in a foreign directory, two of them collided in the same one, files were
written next to the wrong repo. The errors that reached the caller pointed nowhere near
the cause ("unable to create temporary file", "Reference at 'HEAD' does not exist").

The test therefore does not check an error message. It checks the property that was lost:
every thread that publishes gets a working repo with its own contribution committed.
"""

import os
import threading

import pytest

import fair_debate_md as fdmd
from fair_debate_md import repo_handling


pjoin = os.path.join

BODY = "Erster Satz. Zweiter Satz.\n\nDritter Absatz mit etwas Text.\n"


def _publish(host_dir: str, debate_key: str):
    repo_handling.create_repo(host_dir, debate_key)
    fdmd.commit_ctb(host_dir, debate_key, fdmd.DBContribution("a", BODY))


@pytest.mark.parametrize("n_threads", [2, 8])
def test_concurrent_repo_creation(tmp_path, n_threads):
    host_dir = str(tmp_path)
    keys = [f"d{i:02d}-concurrent" for i in range(n_threads)]
    failures = {}

    # a barrier rather than plain starts: the threads have to be inside `create_repo` at
    # the same time, which is not reliable if they are merely started in a loop
    start = threading.Barrier(n_threads)

    def run(debate_key):
        try:
            start.wait()
            _publish(host_dir, debate_key)
        except Exception as ex:
            failures[debate_key] = repr(ex)

    threads = [threading.Thread(target=run, args=(key,)) for key in keys]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == {}

    for key in keys:
        repo_dir = pjoin(host_dir, key)
        assert os.path.isdir(pjoin(repo_dir, ".git")), f"{key}: no git dir"
        # the contribution of *this* debate, not of a thread that wrote to the wrong place
        assert os.path.isfile(pjoin(repo_dir, "a", "a.md")), f"{key}: contribution missing"
        hashes = fdmd.core.contribution_commit_hashes(host_dir, key)
        assert "a" in hashes, f"{key}: contribution not committed"


def test_create_repo_leaves_the_working_directory_alone(tmp_path):
    """
    `create_repo` used to chdir and rely on a decorator to undo it. Nothing should move
    now -- neither during the call (which no test can observe from outside) nor after it.
    """

    before = os.getcwd()
    repo_handling.create_repo(str(tmp_path), "d-cwd")
    assert os.getcwd() == before
