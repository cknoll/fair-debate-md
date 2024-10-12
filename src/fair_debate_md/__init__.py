from .release import __version__

try:
    from . import core
    from . import fixtures
    from .core import *
except ImportError:
    # necessary during installation
    pass
