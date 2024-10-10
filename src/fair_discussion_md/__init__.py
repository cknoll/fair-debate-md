from .release import __version__

try:
    from . import core
    from .core import *
except ImportError:
    # necessary during installation
    pass
