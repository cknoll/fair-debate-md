import os
from . import utils
import glob
import git

from ipydex import IPS

pjoin = os.path.join


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

    for fname, content in initial_files.items():
        with open(fname, "w") as fp:
            fp.write(content)
        repo.index.add(fname)

    msg = "first commit"
    author = get_author(name="fair debate system")
    repo.index.commit(message=msg, author=author)


def get_author(debate_key: str = None, author_role: str = None, name: str = None):

    if name is None:
        name = f"fair debate user {debate_key} {author_role}"
        email = f"{debate_key}_{author_role}@fair-debate-users.org"
    else:
        email = f'{name.replace(" ", "_")}@fair-debate-users.org'

    author = git.Actor(name=name, email=email)
    return author
