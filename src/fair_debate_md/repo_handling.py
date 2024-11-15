import os
from . import utils
import glob

from ipydex import IPS

pjoin = os.path.join


@utils.preserve_cwd
def rollout_patches(repo_dir: str, patch_dir: str, start=0, limit=None):
    patch_dir = patch_dir = os.path.abspath(patch_dir)
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
