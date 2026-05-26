"""Parameter helpers for the EbolaSim C model's bracketed text files."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ebolasim_tools.params import ParameterSet, tiny_parameter_set


@dataclass(frozen=True)
class Pars:
    """Wrapper around the C model's exact bracketed parameter file names."""

    raw: ParameterSet

    def __getitem__(self, key: str) -> str:
        return self.raw[key]

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self.raw

    def copy(self) -> Pars:
        return Pars(self.raw.copy())

    def set(self, values: Mapping[str, Any] | None = None, **kwargs: Any) -> Pars:
        """Return a copy with exact C parameter names updated.

        Use a mapping because most parameter names contain spaces, for example::

            pars.set({"Population size": 2400, "Reproduction number": 1.6})
        """

        if kwargs:
            names = ", ".join(sorted(kwargs))
            raise TypeError(
                "Pars.set() uses exact C parameter names via a mapping, not Python aliases. "
                f"Pass a dictionary instead of keyword arguments: {names}"
            )
        clone = self.copy()
        for key, value in (values or {}).items():
            clone.raw[str(key)] = value
        return clone

    def write(self, path: str | Path) -> Path:
        return self.raw.write(path)

    def to_dict(self) -> dict[str, str]:
        return self.raw.to_dict()

    def to_frame(self) -> Any:
        try:
            import pandas as pd  # type: ignore[import-not-found, import-untyped]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("Pars.to_frame() requires pandas to be installed") from exc
        return pd.DataFrame(
            [{"parameter": entry.name, "value": entry.value} for entry in self.raw.entries()]
        )


def demo_pars(overrides: Mapping[str, Any] | None = None) -> Pars:
    """Create a small synthetic parameter set using exact C parameter names."""

    pars = Pars(
        tiny_parameter_set(
            population=2400,
            realisations=20,
            sampling_time=90,
            reproduction_number=1.6,
        )
    )
    return pars.set(overrides) if overrides else pars


def load_pars(path: str | Path) -> Pars:
    """Load a C model parameter file."""

    return Pars(ParameterSet.read(path))


__all__ = ["Pars", "demo_pars", "load_pars"]
