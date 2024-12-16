import os
import errno
import subprocess
import shutil
import functools
from contextlib import contextmanager
from colorama import Style, Back, Fore
import git

from ipydex import IPS


def hl(txt, k="g"):
    colors = {
        "g": Back.GREEN,
        "y": Back.YELLOW,
        "r": Back.RED,
    }

    start = colors[k]
    end = Style.RESET_ALL
    txt2 = txt.replace("\n", f"{end}\n{start}")

    return f"{start}{txt2}{end}"


def compare_strings(str1, str2, n=25):
    # Find the index of the first difference
    idx = next((i for i in range(min(len(str1), len(str2))) if str1[i] != str2[i]), None)

    if idx is None:
        if len(str1) == len(str2):
            print("The strings are identical.")
            return
        idx = min(len(str1), len(str2))

    # Calculate the start and end indices for context
    start = max(0, idx - n)
    end = min(max(len(str1), len(str2)), idx + n + 1)

    # Print the context
    print(f"First difference at index {idx}:")
    print(f"{str1[start:idx]}{hl(str1[idx:end], 'g')}")
    print(f"{str2[start:idx]}{hl(str2[idx:end], 'y')}")


def preserve_cwd(function):
    """
    This is a decorator that ensures that the current working directory is unchanged during the function call.
    """

    @functools.wraps(function)
    def decorator(*args, **kwargs):
        cwd = os.getcwd()
        try:
            return function(*args, **kwargs)
        finally:
            os.chdir(cwd)

    return decorator


@contextmanager
def preserve_cwd_cm():
    original_cwd = os.getcwd()
    try:
        yield
    finally:
        os.chdir(original_cwd)


def tolerant_rmtree(target_path):
    """try to delete a tree, and do nothing if it is already absent"""

    try:
        shutil.rmtree(target_path)
    except OSError as exc:  # python >2.5
        if exc.errno == errno.ENOENT:
            pass
        else:
            raise


def get_cmd_output(cmd: str | list[str]) -> str:

    if isinstance(cmd, str):
        cmd_list = cmd.split(" ")
    else:
        cmd_list = cmd
    assert isinstance(cmd_list, list)
    res = subprocess.run(cmd_list, capture_output=True)
    res.exited = res.returncode
    res.stdout = res.stdout.decode("utf8")
    res.stderr = res.stderr.decode("utf8")

    return res.stdout


def get_number_of_commits(repo_dir):
    repo = git.Repo(repo_dir)
    assert not repo.is_dirty(), f"Repo is dirty: {repo_dir}"
    return len(list(repo.iter_commits()))
