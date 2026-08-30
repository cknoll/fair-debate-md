import os
import subprocess
from . import utils
import glob
import git

from ipydex import IPS

pjoin = os.path.join


class PlatformSettings:
    """
    How this instance identifies itself in the repos it writes.

    Module-level with defaults so fair_debate_md stays usable and testable on its own;
    the web app overwrites the values once at startup (`base/apps.py`), and single calls
    can override them through arguments. See `konzept_manipulationssicherheit.md`, E4, in
    the web repo.

    `committer_*` matters beyond cosmetics. Without it git falls back to the identity of
    the unix user running the process -- which put a private address into every commit of
    every debate repo, and those repos are downloadable since `/d/<key>/bundle` exists.
    It is also the principal a repo's `.allowed_signers` names, so two instances writing
    into the same repos must agree on it or verification stops.

    The default domain is `.invalid` (reserved for this purpose by RFC 2606): an
    unconfigured instance is then recognisably not a real one.

    `signing_key_path` of None means commits are created unsigned -- no error, because
    nobody should need a secret to run this library.
    """

    committer_name = "Fair debate"
    committer_email = "platform@fair-debate.invalid"
    signing_key_path = None


platform_settings = PlatformSettings()


@utils.preserve_cwd
def rollout_patches(repo_dir: str, patch_dir: str, start=0, limit=None):
    patch_dir = os.path.abspath(patch_dir)
    os.makedirs(repo_dir, exist_ok=True)
    os.chdir(repo_dir)

    patch_files = glob.glob(pjoin(patch_dir, f"*.patch"))
    patch_files.sort()

    patch_files_limited = patch_files[start:limit]

    patch_files_str = " ".join(patch_files_limited)

    if not os.path.isdir(pjoin(repo_dir, ".git")):
        os.system("git init")
    cmd = f"git am {patch_files_str}"
    os.system(cmd)


@utils.preserve_cwd
def create_repo(repo_host_dir: str, debate_key: str, initial_files: dict[str, str]):
    """
    :param repo_host_dir:   str; absolute path
    :param debate_key:      str
    :param initial_files:   dict; {fname: content, ...}

    """

    repo_dir = pjoin(repo_host_dir, debate_key)

    # raise an error if directory already exists
    os.makedirs(repo_dir)
    os.chdir(repo_dir)
    if not os.path.isdir(pjoin(repo_dir, ".git")):
        os.system("git init")

    repo = git.Repo(repo_dir)
    apply_platform_identity(repo_dir)

    for fname, content in initial_files.items():
        with open(fname, "w") as fp:
            fp.write(content)
        repo.index.add(fname)

    msg = "first commit"
    author = get_author(name="fair debate system")
    repo.index.commit(message=msg, author=author)


def apply_platform_identity(repo_dir: str, settings: PlatformSettings = None):
    """
    Write the platform's committer identity into a repo's own git config.

    Idempotent, and called before every commit rather than only at creation time, so
    repos that predate this pick it up on their next write.

    The *signing key path* is deliberately NOT stored here even though git would read it
    from the same place. It is the one setting that depends on the machine rather than on
    the repo: a moved secrets directory (or a differently laid out server) would then have
    to be corrected in every repo separately, and `git commit -S` aborts when the key is
    missing -- so publishing would stop. It is passed per call instead, see
    `core.commit_ctb_list`.
    """

    if settings is None:
        settings = platform_settings

    for key, value in [
        ("user.name", settings.committer_name),
        ("user.email", settings.committer_email),
        # only relevant when a signing key is configured, but harmless otherwise and
        # cheaper to set once than to decide about on every commit
        ("gpg.format", "ssh"),
    ]:
        try:
            subprocess.run(
                ["git", "config", key, value],
                cwd=repo_dir,
                capture_output=True,
                timeout=30,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return


def get_author(debate_key: str = None, author_role: str = None, name: str = None):

    if name is None:
        name = f"fair debate user {debate_key} {author_role}"
        email = f"{debate_key}_{author_role}@fair-debate-users.org"
    else:
        email = f'{name.replace(" ", "_")}@fair-debate-users.org'

    author = git.Actor(name=name, email=email)
    return author
