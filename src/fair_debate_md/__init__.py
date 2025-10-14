from .release import __version__

# the package is imported during installation
# however installation happens in an isolated build environment
# where no dependencies are installed.

# this means: no importing the following modules will fail
# during installation this is OK

try:
    from . import core
    from . import utils
    from . import repo_handling
    from . import fixtures
    from .core import *
except ImportError as ex:
    import os

    if "PIP_BUILD_TRACKER" in os.environ:
        pass
    elif "PEP517_BUILD_BACKEND" in os.environ:
        # this key-value-pair is in os.environ during `python3 -m build`:
        # 'PEP517_BUILD_BACKEND': 'setuptools.build_meta'
        pass
    elif "_PYPROJECT_HOOKS_BUILD_BACKEND" in os.environ:
        pass
    else:
        # print("\n"*5, os.environ, "\n"*5)
        # raise the original exception
        raise
