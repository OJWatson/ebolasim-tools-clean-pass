"""Python interface for the EbolaSim C model."""

from .parameters import parameter_reference
from .pars import Pars, demo_pars, load_pars
from .results import Results, compare_results, plot_compare, read_results
from .sim import Sim, resolve_executable

try:
    from ._version import __version__
except ImportError:  # pragma: no cover - source tree fallback
    from ebolasim_tools._version import __version__

__all__ = [
    "Pars",
    "Results",
    "Sim",
    "__version__",
    "compare_results",
    "demo_pars",
    "load_pars",
    "parameter_reference",
    "plot_compare",
    "read_results",
    "resolve_executable",
]
