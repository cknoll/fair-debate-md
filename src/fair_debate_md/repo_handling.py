import datetime
import email.parser
import email.policy
import hashlib
import os
import re
import shlex
import subprocess
from . import utils
import glob
import git
import yaml

from .release import __version__ as fdmd_version

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

    # For the README that every repo carries. Like the committer address these default to
    # `.invalid` (RFC 2606), so a repo built by an unconfigured instance is recognisably
    # not from a real one instead of quietly naming somebody else's site.
    platform_name = "Fair Debate"
    debate_url_template = "https://fair-debate.invalid/d/{debate_key}"
    background_url = "https://fair-debate.invalid/about"

    # The version of the web application, recorded in `REPO_INFO.yaml` of a repo this
    # instance opens itself. None means "not a platform", which is what a repo built by
    # the library alone should say -- see `build_repo_info()`.
    platform_version = None


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


def amend_head(repo_dir: str, sign_args: list, filenames: list = (), author: str = None):
    """
    Rewrite the commit that is currently HEAD: add files to it, correct its author, or both.

    The committer date is pinned to the author date of that commit, the same rule
    `git am --committer-date-is-author-date` follows -- an amend would otherwise stamp
    "now" and make the rollout unreproducible again. The author date needs no such care:
    `--amend` keeps it unless `--reset-author` is given.

    :param author:  "Name <address>", passed to `git commit --author`
    """

    author_date = subprocess.run(
        ["git", "-C", repo_dir, "log", "-1", "--format=%aI"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    env = dict(os.environ, GIT_COMMITTER_DATE=author_date)
    if filenames:
        subprocess.run(["git", "-C", repo_dir, "add", *filenames], check=True)
    subprocess.run(
        ["git", "-C", repo_dir, *sign_args[:2], "commit", "--amend", "--no-edit",
         *(["--author", author] if author else []),
         *(["-S"] if sign_args else []), "--no-verify"],
        check=True, env=env, capture_output=True,
    )


def patch_author(patch_path: str) -> tuple:
    """
    The author a patch names, as (display name, address).

    Read with the `email` package rather than by hand: `git format-patch` folds a long
    `From:` header over two lines and writes non-ASCII names as RFC 2047 encoded words.
    Both have to be undone before the name can be compared to anything.
    """

    with open(patch_path, "rb") as fp:
        parser = email.parser.BytesParser(policy=email.policy.default)
        header = parser.parse(fp, headersonly=True)["From"]

    if header is None or not header.addresses:
        return "", ""
    address = header.addresses[0]
    return address.display_name, address.addr_spec


def restore_patch_author(repo_dir: str, patch_path: str, sign_args: list):
    """
    Put the author of the commit at HEAD back when `git am` dropped it.

    `git mailinfo`, which `git am` parses the mail header with, discards a display name
    longer than 60 characters and falls back to the bare address -- without a warning, and
    for a header it wrote itself. The commit then reads as authored by
    `d13-...-wiederstands_a@fair-debate-users.org` rather than by
    `fair debate user d13-fragging-ist-valide-form-des-wiederstands a`.

    That is not an exotic case here. A party's name is built from the debate key, so any
    key beyond a few words crosses the line: four of the eleven fixture collections are
    affected, and so were two of the four live debates. It is also invisible in the
    rollout output, and the patches themselves are correct -- the loss happens entirely on
    the reading side, which is why it survived this long.

    The comparison IS the check, so no length threshold is hard-coded: a git that stops
    truncating simply makes this a no-op.
    """

    name, address = patch_author(patch_path)
    if not name:
        # `git am` derives a name from the address in that case, and so would we
        return

    current = subprocess.run(
        ["git", "-C", repo_dir, "log", "-1", "--format=%an"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if current == name:
        return

    amend_head(repo_dir, sign_args, author=f"{name} <{address}>")


@utils.preserve_cwd
def rollout_patches(repo_dir: str, patch_dir: str, start=0, limit=None,
                    settings: PlatformSettings = None, debate_key: str = None):
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
      rollout produced different commit hashes for identical content;
    * `git am` keeps the author only if its display name is at most 60 characters long and
      replaces it with the bare address otherwise, so the one thing a patch does carry got
      lost for every party whose debate key is more than a few words -- see
      `restore_patch_author()`, which puts it back.

    Two files are written here rather than taken from the patches, and both are amended
    INTO the root commit rather than added in one of their own -- that is where
    `create_repo()` puts them for a repo the platform opens itself, and a separate metadata
    commit would show up on the integrity page as a row carrying no contribution:

    * `allowed_signers`, which names the signing key. Frozen into checked-in patch data, a
      key change would invalidate every collection at once. Written only when a key is
      configured, so a run without secrets keeps working.
    * `README.md`, whose addresses belong to the instance doing the serving. A fixture
      built on a developer machine would otherwise tell every reader to visit localhost.

    :param debate_key:  named in the README; defaults to the directory name, which is what
                        `unpack_repos()` uses as the key anyway.
    """

    if settings is None:
        settings = platform_settings

    patch_dir = os.path.abspath(patch_dir)
    # resolved before the `chdir` below, after which a relative path would silently point
    # somewhere else -- and the `git -C <repo_dir>` calls further down would follow it
    repo_dir = os.path.abspath(repo_dir)
    os.makedirs(repo_dir, exist_ok=True)
    os.chdir(repo_dir)

    patch_files = glob.glob(pjoin(patch_dir, f"*.patch"))
    patch_files.sort()

    patch_files_limited = patch_files[start:limit]

    patch_files_str = " ".join(patch_files_limited)

    from_scratch = not os.path.isdir(pjoin(repo_dir, ".git")) and start == 0
    if not os.path.isdir(pjoin(repo_dir, ".git")):
        os.system("git init")

    apply_platform_identity(repo_dir, settings)

    # `-S` signs, and the date option keeps the rollout reproducible. Both are passed per
    # call rather than written into the repo config: the key path depends on the machine
    # (see `apply_platform_identity`), and configuring the date behaviour would change it
    # for every later commit in that repo too.
    sign_args = []
    if settings.signing_key_path:
        sign_args = ["-c", f"user.signingkey={settings.signing_key_path}", "-S"]

    def apply(files):
        # one `git am` per patch rather than one for the batch: a dropped author has to be
        # put back before the next commit is built on top, see `restore_patch_author()`
        argv = ["git", *sign_args[:2], "am", "--committer-date-is-author-date"]
        if sign_args:
            argv.append("-S")
        for path in files:
            os.system(" ".join(argv) + " " + shlex.quote(path))
            restore_patch_author(repo_dir, path, sign_args)

    if from_scratch and patch_files_limited:
        # apply the first patch, put the instance-dependent files into that same commit,
        # then apply the rest. Writing them before `git am` is not an option: the first
        # patch creates `README.md` itself, and git refuses to overwrite an untracked file.
        apply(patch_files_limited[:1])

        with open(pjoin(repo_dir, README_FILENAME), "w") as fp:
            fp.write(build_readme(debate_key or os.path.basename(repo_dir), settings))
        root_files = [README_FILENAME]

        if settings.signing_key_path and write_allowed_signers(repo_dir, settings):
            root_files.append(ALLOWED_SIGNERS_FILENAME)

        amend_head(repo_dir, sign_args, filenames=root_files)
        apply(patch_files_limited[1:])
    else:
        apply(patch_files_limited)

    # A rolled-out repo is served exactly like a published one, so it needs the same dumb-HTTP
    # index -- and it needs it here, because nothing else will write one until someone
    # publishes a contribution to this debate. Until then the clone URL the integrity page
    # advertises would simply fail. Note this must come after the amend above: it rewrites the
    # root commit, and an `info/refs` written before that would point at a hash that is gone.
    prepare_repo_for_serving(repo_dir)


def add_to_index(repo, path: str):
    """
    Stage one file, addressed by absolute path.

    Not `repo.index.add()`, although that is the obvious call: GitPython's index writer
    chdirs into the working tree for the duration (`git.index.util.set_git_working_dir`)
    and then `lstat`s the file through a *relative* path. Both are process-global, so two
    threads staging files in two different repos can make each other look at the wrong
    directory. `git add` gets the working directory as an argument of its own subprocess
    and cannot be disturbed that way.
    """

    repo.git.add(path)


def create_repo(repo_host_dir: str, debate_key: str, initial_files: dict[str, str] = None):
    """
    :param repo_host_dir:   str; absolute path
    :param debate_key:      str
    :param initial_files:   dict; {fname: content, ...}; defaults to just the README

    The README is built here rather than passed in, so that a repo the platform opens and
    a repo unpacked by `rollout_patches()` carry the same text. It used to be rendered from
    a django template in the web app, which is how every existing repo ended up saying
    "Visit <debate_url>" -- the placeholders were filled with their own names.

    Everything here addresses the repo by absolute path and nothing changes the process's
    working directory. That is a requirement, not a style choice: the platform calls this
    from a request handler, and a web server may well run two of those at once. The
    earlier version did `os.chdir(repo_dir)`, then `os.system("git init")` and
    `open(fname, "w")` relative to it -- process-global state that a second thread
    silently redirects. Measured with two threads, one of the two repos came out broken;
    with eight, all eight did: `git init` running in a *foreign* directory, two of them
    colliding in the same one ("could not lock config file"), files written next to the
    wrong repo. What reached the caller were unrelated-looking errors deep in git
    ("unable to create temporary file", "Reference at 'HEAD' does not exist"), which is
    why this cost a debugging session before it was found.
    """

    if initial_files is None:
        initial_files = {
            README_FILENAME: build_readme(debate_key),
            # `kind: opened` -- written once, here, and never rewritten. It is what tells a
            # reader (and the integrity page) that this history grew rather than being
            # regenerated, which is the difference that decides how much its fingerprints
            # are worth.
            REPO_INFO_FILENAME: build_repo_info(),
        }

    repo_dir = pjoin(repo_host_dir, debate_key)

    # raise an error if directory already exists
    os.makedirs(repo_dir)
    if not os.path.isdir(pjoin(repo_dir, ".git")):
        # `git init <dir>` rather than a chdir plus a bare `git init`: the target is then
        # part of the command instead of being implied by process state
        subprocess.run(["git", "init", "--quiet", repo_dir], capture_output=True, timeout=30, check=True)

    repo = git.Repo(repo_dir)
    apply_platform_identity(repo_dir)

    for fname, content in initial_files.items():
        with open(pjoin(repo_dir, fname), "w") as fp:
            fp.write(content)
        add_to_index(repo, pjoin(repo_dir, fname))

    # into the initial commit, next to the README: that commit carries repo metadata and
    # no debate content yet, so this is where a file describing the repo belongs. It also
    # means readers get it from the very first commit onwards instead of finding it added
    # somewhere in the middle of a debate's history.
    if write_allowed_signers(repo_dir):
        add_to_index(repo, pjoin(repo_dir, ALLOWED_SIGNERS_FILENAME))

    msg = "first commit"
    author = get_author(name="fair debate system")
    # through `commit_index`, not `repo.index.commit`, so this commit is signed like every
    # other one. It is the commit carrying README and allowed_signers -- the files the
    # whole verification rests on; leaving exactly those unsigned would be backwards.
    commit_index(repo, repo_dir, msg, author)


ALLOWED_SIGNERS_FILENAME = "allowed_signers"
README_FILENAME = "README.md"

# The one template. `create_repo()` uses it for a repo the platform opens itself and
# `rollout_patches()` for one it unpacks, because a reader must not be able to tell the two
# apart -- both are handed out through the same bundle and clone endpoints.
README_TEMPLATE_PATH = pjoin(os.path.dirname(__file__), "repo_files", README_FILENAME)

REPO_INFO_FILENAME = "REPO_INFO.yaml"


def source_fingerprint(source_path: str) -> str:
    """
    The sha256 of a source file's bytes.

    Deliberately the content hash and not the git commit the file sat in: a debate is
    usually rebuilt from a source that has just been edited and not committed yet, so at
    build time HEAD names the state *before* the change. The content hash has no such
    ordering problem, needs no repository around the file, and can be recomputed by anyone
    holding the source.
    """
    with open(source_path, "rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


def read_repo_info(repo_host_dir: str, debate_key: str) -> dict:
    """
    The `REPO_INFO.yaml` of one repo, or {} when it has none.

    Absence is a normal answer and not an error: the patch collections predating this file
    (`d02`..`d06`, `d1-lorem_ipsum` and the script-built fixtures) carry no provenance and
    cannot be given one retroactively -- there is no source to name. A caller must be able
    to say "not recorded" rather than having to guess.
    """
    path = pjoin(repo_host_dir, debate_key, REPO_INFO_FILENAME)
    try:
        with open(path) as fp:
            data = yaml.safe_load(fp)
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def build_repo_info(source_path: str = None, when: str = None,
                    settings: PlatformSettings = None) -> str:
    """
    The content of `REPO_INFO.yaml`: what made this repository.

    Every repo carries it, and the `kind` field says which of the two kinds this is:

    * ``opened`` -- a live debate. The platform created the repo once and the debate grew
      into it by appending. This is the normal case and the one the integrity page can
      take at face value.
    * ``built`` -- an artifact. A fixture debate is generated from a single-file source by
      `fdmd build-debate-repo`, and every rebuild replaces the whole commit chain: new
      fingerprints, new signatures, and the previous ones gone. Without this file the
      integrity page presents that chain as the history of the debate, and a fingerprint
      somebody noted resolves to nothing with no explanation on offer. Recording the
      source and the build date does not make old fingerprints resolvable -- that is a
      separate and larger question -- but it stops the page claiming more than it knows.

    Note what is NOT in here for a built repo: nothing that depends on the instance
    serving it. `rollout_patches()` keeps hashes reproducible across rollouts
    (`--committer-date-is-author-date`), so a platform version in checked-in patch data
    would give every fixture debate a fresh chain of fingerprints on every deploy -- which
    is the very damage this file exists to document. `platform_version` therefore appears
    only in the ``opened`` case, where the repo is written once and never rebuilt.

    :param source_path: the single-file source, for a built repo; None for an opened one
    :param when:        ISO timestamp, defaults to now (UTC)
    """

    if settings is None:
        settings = platform_settings

    if when is None:
        now = datetime.datetime.now(datetime.timezone.utc)
        when = now.replace(microsecond=0).isoformat()

    info = {
        "kind": "built" if source_path else "opened",
        "date": when,
        "fdmd_version": fdmd_version,
    }

    if source_path:
        # the last two components, not the bare basename: every source file is called
        # `source.md` and the directory above it is what names the debate
        source_path = os.path.abspath(source_path)
        rel_name = pjoin(os.path.basename(os.path.dirname(source_path)),
                         os.path.basename(source_path))
        info["source"] = {
            "path": rel_name,
            "sha256": source_fingerprint(source_path),
        }
    elif settings.platform_version:
        info["platform_version"] = settings.platform_version

    header = (
        "# What made this repository. See README.md, section \"Where this comes from\".\n"
        "# `kind: built` means the history is regenerated whenever the source changes;\n"
        "# `kind: opened` means the debate grew into this repo by appending.\n"
    )
    return header + yaml.safe_dump(info, sort_keys=False, allow_unicode=True)


def build_readme(debate_key: str, settings: PlatformSettings = None) -> str:
    """
    The README a debate repo carries, filled in for this instance.

    It is written by whoever creates the repo rather than shipped inside the patch
    collections, for the same reason as `allowed_signers`: the addresses in it belong to
    the instance doing the serving, and a fixture built on a developer machine would
    otherwise tell every reader to visit localhost.

    Correcting it later needs no history rewrite -- it is an ordinary commit on top, whose
    message says why. Only the *first* version of the file is fixed, not the file.
    """

    if settings is None:
        settings = platform_settings

    with open(README_TEMPLATE_PATH) as fp:
        template = fp.read()

    return template.format(
        debate_key=debate_key,
        platform_name=settings.platform_name,
        debate_url=settings.debate_url_template.format(debate_key=debate_key),
        background_url=settings.background_url,
    )


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
