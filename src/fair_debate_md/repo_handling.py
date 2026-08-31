import os
import re
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
    It is also the principal a repo's `allowed_signers` names, so two instances writing
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


PATCH_DATE_RE = re.compile(r"^Date:\s*(.+)$", re.MULTILINE)


def first_patch_date(patch_files: list) -> str | None:
    """The `Date:` header of the earliest patch, so a repo can be dated like its content."""

    if not patch_files:
        return None
    with open(patch_files[0]) as fp:
        # the header is the first few lines; no need to read a whole patch for it
        match = PATCH_DATE_RE.search(fp.read(2000))
    return match.group(1).strip() if match else None


@utils.preserve_cwd
def rollout_patches(repo_dir: str, patch_dir: str, start=0, limit=None,
                    settings: PlatformSettings = None):
    """
    Turn a patch collection into a real repo, committed and signed like a live one.

    This is where a fixture debate actually becomes a repository, and therefore the only
    place where its identity and its signatures can be decided. A patch carries neither:
    `git format-patch` writes the *author* into the mail header and drops the committer
    and the signature, and `git am` builds fresh commit objects. Whatever a patch
    collection was built from, the commits a reader ends up cloning are made here.

    Three things follow, all of which used to go wrong silently:

    * without a configured identity `git am` takes the one of the unix user running it,
      which put a private address into every fixture repo -- and those are downloadable
      through `/d/<key>/bundle`;
    * without `-S` nothing is signed, however carefully the patches were prepared;
    * without `--committer-date-is-author-date` the committer date is "now", so every
      rollout produced different commit hashes for identical content.

    `allowed_signers` goes in as the repo's first commit, before the patches: it names the
    key the following commits are signed with, and it must not sit in the checked-in patch
    data, where a key change would invalidate every collection at once. Without a signing
    key the file is not written and the commit does not happen, so a run without secrets
    behaves as before.
    """

    if settings is None:
        settings = platform_settings

    patch_dir = os.path.abspath(patch_dir)
    os.makedirs(repo_dir, exist_ok=True)
    os.chdir(repo_dir)

    patch_files = glob.glob(pjoin(patch_dir, f"*.patch"))
    patch_files.sort()

    patch_files_limited = patch_files[start:limit]

    patch_files_str = " ".join(patch_files_limited)

    if not os.path.isdir(pjoin(repo_dir, ".git")):
        os.system("git init")

    apply_platform_identity(repo_dir, settings)

    sign_args = []
    if settings.signing_key_path:
        sign_args = ["-c", f"user.signingkey={settings.signing_key_path}"]

        if write_allowed_signers(repo_dir, settings):
            repo = git.Repo(repo_dir)
            repo.index.add(ALLOWED_SIGNERS_FILENAME)
            # the platform itself, not `get_author()`, which would derive a user address
            # from the name -- this commit is repo metadata and has no debate author
            author = git.Actor(name=settings.committer_name, email=settings.committer_email)
            # dated like the patch it precedes, not "now": a repo whose first commit is
            # younger than its second reads as a repaired history, which is the one
            # impression an integrity page must not create by accident
            stamp = first_patch_date(patch_files_limited)
            env = {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp} if stamp else {}
            with repo.git.custom_environment(**env):
                commit_index(repo, repo_dir, "name the key these commits are signed with",
                             author, settings)

    # `-S` signs, and the date option keeps the rollout reproducible. Both have to be
    # passed here rather than configured in the repo: the key path depends on the machine
    # (see `apply_platform_identity`), and committing the date behaviour to the config
    # would change it for every later commit in that repo too.
    argv = ["git", *sign_args, "am", "--committer-date-is-author-date"]
    if sign_args:
        argv.append("-S")
    os.system(" ".join(argv) + " " + patch_files_str)


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

    # into the initial commit, next to the README: that commit carries repo metadata and
    # no debate content yet, so this is where a file describing the repo belongs. It also
    # means readers get it from the very first commit onwards instead of finding it added
    # somewhere in the middle of a debate's history.
    if write_allowed_signers(repo_dir):
        repo.index.add(ALLOWED_SIGNERS_FILENAME)

    msg = "first commit"
    author = get_author(name="fair debate system")
    # through `commit_index`, not `repo.index.commit`, so this commit is signed like every
    # other one. It is the commit carrying README and allowed_signers -- the files the
    # whole verification rests on; leaving exactly those unsigned would be backwards.
    commit_index(repo, repo_dir, msg, author)


ALLOWED_SIGNERS_FILENAME = "allowed_signers"


def build_allowed_signers_content(settings: PlatformSettings = None) -> str:
    """
    The `allowed_signers` line for this instance's signing key, or "" without one.

    Format is OpenSSH's, and it differs from a `.pub` file -- the principal replaces the
    trailing comment:

        .pub:             ssh-ed25519 AAAA...  <comment>
        allowed_signers:  <principal> ssh-ed25519 AAAA...

    The principal is the committer address, because that is what git matches a commit
    signature against.

    The public half is derived from the private key with `ssh-keygen -y` rather than read
    from a neighbouring `.pub`: the configured path points at the private key, and a
    `.pub` beside it may or may not exist (it does not survive every way of moving a key
    around). Deriving it is one subprocess and cannot disagree with the key actually used.
    """

    if settings is None:
        settings = platform_settings
    if not settings.signing_key_path:
        return ""

    try:
        result = subprocess.run(
            ["ssh-keygen", "-y", "-f", settings.signing_key_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""

    parts = result.stdout.split()
    if len(parts) < 2:
        return ""
    key_type, key_data = parts[0], parts[1]

    return f"{settings.committer_email} {key_type} {key_data}\n"


def signing_key_fingerprint(settings: PlatformSettings = None) -> str:
    """
    The `SHA256:...` fingerprint of this instance's signing key, or "" without one.

    Short enough to print on a page and to keep in a saved export, so a reader can tell
    later whether the key changed -- which is the cheap half of what a public key
    publication buys (konzept_manipulationssicherheit.md, E4).
    """

    if settings is None:
        settings = platform_settings
    if not settings.signing_key_path:
        return ""

    try:
        result = subprocess.run(
            ["ssh-keygen", "-lf", settings.signing_key_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""

    for part in result.stdout.split():
        if part.startswith("SHA256:"):
            return part
    return ""


def write_allowed_signers(repo_dir: str, settings: PlatformSettings = None) -> bool:
    """
    Put this instance's `allowed_signers` into a repo, so a reader who clones it can
    verify the signatures without hunting for the key first.

    :return:    True if the file was written

    Does not commit -- the caller decides when that happens. It has to *become* committed
    eventually though: an untracked file travels with neither `git clone` nor the bundle,
    and would then help nobody.

    Deliberately not hidden behind a leading dot: this is the file readers are supposed to
    find, and a dotfile does not show up in a plain `ls`.
    """

    content = build_allowed_signers_content(settings)
    if not content:
        return False

    with open(pjoin(repo_dir, ALLOWED_SIGNERS_FILENAME), "w") as fp:
        fp.write(content)
    return True


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


def commit_index(repo, repo_dir: str, msg: str, author, settings: PlatformSettings = None) -> str:
    """
    Commit what is staged, signed when this instance has a signing key.

    :return:    hex sha of the new commit

    Goes through the git CLI instead of `repo.index.commit()` because GitPython cannot
    produce a signature: `IndexFile.commit()` has no parameter for one, and it builds the
    commit object itself rather than calling git. (It *can* carry one -- `Commit.__init__`
    takes `gpgsig` and `_serialize` writes it -- so the gap is only in creating it; see
    `gitPythonSigningFeatureRequest.md`.)

    The signing key is passed per call rather than stored in the repo's config: it is the
    one setting that depends on the machine, and a wrong path in a repo config would abort
    every commit there. Identity settings do live in the repo config, written by
    `apply_platform_identity()`.

    Without a configured key the commit is simply unsigned -- running this library must
    not require a secret.
    """

    if settings is None:
        settings = platform_settings

    apply_platform_identity(repo_dir, settings)

    config_args = []
    if settings.signing_key_path:
        config_args = [
            "-c",
            f"user.signingkey={settings.signing_key_path}",
            "-c",
            "commit.gpgsign=true",
        ]

    # `repo.git.execute` with the full argv, because the `-c` options belong to git
    # itself and have to precede the subcommand -- `repo.git.commit(...)` could only
    # place them after it. Errors surface as GitCommandError: a commit that fails must
    # not pass silently, the caller is about to report a publication as done.
    repo.git.execute(
        ["git", *config_args, "commit", "-m", msg,
         f"--author={author.name} <{author.email}>", "--no-verify"]
    )
    return repo.head.commit.hexsha


# Above this many loose objects a repo is packed before it is served (see
# `prepare_repo_for_serving`). Deliberately our own threshold instead of `git gc --auto`:
# that one estimates the loose-object count by sampling a single `objects/` bucket, which
# at these repo sizes reports zero often enough that the packing never happens (measured
# 2026-08-30 on d30-many-parties: 171 loose objects, `gc --auto` with gc.auto=50 did
# nothing). `git count-objects` gives the exact number for about 2 ms.
LOOSE_OBJECT_PACK_LIMIT = 50


def prepare_repo_for_serving(repo_dir: str, loose_object_limit: int = LOOSE_OBJECT_PACK_LIMIT):
    """
    Make a debate repo cloneable over plain HTTP, and keep that cheap.

    Called after every commit. Two steps, and the order matters -- packing rewrites what
    the index has to describe:

    1. `git gc` once the loose objects pile up. Serving happens over git's "dumb" HTTP
       protocol, where the client fetches **every object with its own request**: 171 loose
       objects meant 173 requests through Django, packing them cut that to a handful (and
       684 KB to 24 KB, measured on d30-many-parties).
    2. `git update-server-info`, which writes `info/refs` and `objects/info/packs`. A dumb
       client has no git on the other end to compute those, so without them a clone fails
       outright -- and, worse, a *stale* index makes the clone silently deliver an older
       state. On an integrity page that is the ugliest failure mode there is: a reader
       would not find the fingerprint they noted and conclude manipulation where only an
       index was out of date. Hence after every commit, not on a schedule.

    Failures stay silent, like everywhere else in this module: a repo that cannot be
    prepared must not bring down the publishing action that just succeeded.
    """

    if not os.path.isdir(pjoin(repo_dir, ".git")):
        return

    try:
        result = subprocess.run(
            ["git", "count-objects", "-v"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        loose = 0
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("count: "):
                    loose = int(line.split()[1])
                    break

        if loose > loose_object_limit:
            subprocess.run(["git", "gc", "-q"], cwd=repo_dir, capture_output=True, timeout=300)

        subprocess.run(
            ["git", "update-server-info"], cwd=repo_dir, capture_output=True, timeout=30
        )
    except (FileNotFoundError, OSError, ValueError, subprocess.TimeoutExpired):
        return


def get_author(debate_key: str = None, author_role: str = None, name: str = None):

    if name is None:
        name = f"fair debate user {debate_key} {author_role}"
        email = f"{debate_key}_{author_role}@fair-debate-users.org"
    else:
        email = f'{name.replace(" ", "_")}@fair-debate-users.org'

    author = git.Actor(name=name, email=email)
    return author
