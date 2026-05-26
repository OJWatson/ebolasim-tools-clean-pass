"""Private compatibility namespace for older ebolasim-tools imports.

New user code should import :mod:`ebolasim`.
"""

from ._version import __version__
from .params import ParameterSet

__all__ = ["ParameterSet", "__version__"]
