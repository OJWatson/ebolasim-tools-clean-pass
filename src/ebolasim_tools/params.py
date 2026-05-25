"""Read and write legacy ebolasim parameter files.

The legacy model uses a simple bracketed text format::

    [Parameter name]
    value line

Values may span several lines. This module preserves parameter order and keeps
values as text so round trips do not invent scientific meaning.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Iterable, Iterator, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ParameterFormatError(ValueError):
    """Raised when a legacy parameter file cannot be parsed."""


def _normalise_value(value: Any) -> str:
    if isinstance(value, str):
        return value.rstrip("\n")
    if isinstance(value, Iterable) and not isinstance(value, bytes | bytearray | dict):
        return " ".join(str(item) for item in value)
    return str(value)


@dataclass(frozen=True)
class ParameterEntry:
    """One named legacy parameter value."""

    name: str
    value: str

    @property
    def tokens(self) -> list[str]:
        return self.value.split()

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "value": self.value}


class ParameterSet(MutableMapping[str, str]):
    """Ordered mapping for legacy bracketed parameter files."""

    def __init__(self, values: dict[str, Any] | Iterable[tuple[str, Any]] | None = None) -> None:
        self._values: OrderedDict[str, str] = OrderedDict()
        if values is None:
            return
        iterator = values.items() if isinstance(values, dict) else values
        for key, value in iterator:
            self[str(key)] = _normalise_value(value)

    def __getitem__(self, key: str) -> str:
        return self._values[key]

    def __setitem__(self, key: str, value: Any) -> None:
        text = str(key).strip()
        if not text:
            raise ValueError("parameter name cannot be empty")
        if "[" in text or "]" in text:
            raise ValueError("parameter name cannot contain square brackets")
        self._values[text] = _normalise_value(value)

    def __delitem__(self, key: str) -> None:
        del self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def entries(self) -> list[ParameterEntry]:
        return [ParameterEntry(name, value) for name, value in self._values.items()]

    def copy(self) -> ParameterSet:
        return ParameterSet(self._values.items())

    def get_int(self, name: str, default: int | None = None) -> int | None:
        if name not in self._values:
            return default
        return int(self._values[name].split()[0])

    def get_float(self, name: str, default: float | None = None) -> float | None:
        if name not in self._values:
            return default
        return float(self._values[name].split()[0])

    def get_numbers(self, name: str) -> list[float]:
        return [float(item) for item in self._values[name].split()]

    def update_values(self, values: dict[str, Any] | Iterable[tuple[str, Any]]) -> ParameterSet:
        clone = self.copy()
        iterator = values.items() if isinstance(values, dict) else values
        for key, value in iterator:
            clone[key] = value
        return clone

    def to_text(self) -> str:
        blocks: list[str] = []
        for name, value in self._values.items():
            blocks.append(f"[{name}]\n{value.rstrip()}\n")
        return "".join(blocks)

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_text(), encoding="utf-8")
        return target

    def to_dict(self) -> dict[str, str]:
        return dict(self._values)

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)

    @classmethod
    def read(cls, path: str | Path) -> ParameterSet:
        return cls.from_text(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_text(cls, text: str) -> ParameterSet:
        params = cls()
        current_name: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_name, current_lines
            if current_name is not None:
                params[current_name] = "\n".join(current_lines).strip()
            current_name = None
            current_lines = []

        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                if current_name is not None and current_lines:
                    current_lines.append("")
                continue
            if line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("["):
                if not line.endswith("]"):
                    raise ParameterFormatError(
                        f"line {line_no}: parameter header lacks closing bracket"
                    )
                flush()
                current_name = line[1:-1].strip()
                if not current_name:
                    raise ParameterFormatError(f"line {line_no}: empty parameter name")
                current_lines = []
                continue
            if current_name is None:
                raise ParameterFormatError(
                    f"line {line_no}: value encountered before a parameter header"
                )
            current_lines.append(raw_line.strip())
        flush()
        return params


# The compact, simulator-compatible tiny defaults are used by examples.py but
# exposed here because many users only need to start with a parameter set.
def tiny_parameter_set(
    *,
    population: int = 24,
    sampling_time: int = 7,
    realisations: int = 1,
    reproduction_number: float = 4.0,
) -> ParameterSet:
    """Return a small legacy parameter set that can drive the tiny example."""

    age_distribution = " ".join("0.0588235294" for _ in range(17))
    values: list[tuple[str, Any]] = [
        ("Update timestep", 1),
        ("Sampling timestep", 1),
        ("Sampling time", sampling_time),
        ("Population size", population),
        ("Number of realisations", realisations),
        ("Number of spatial cells", 16),
        ("Number of micro-cells per spatial cell width", 1),
        ("Include households", 0),
        ("Include administrative units within countries", 1),
        ("Number of level 1 administrative units to include", 2),
        ("Divisor for level 1 administrative units", 1),
        ("Mask for level 1 administrative units", 1000000000),
        ("List of level 1 administrative units to include", "1 2"),
        ("Output incidence by administrative unit", 1),
        ("Include age", 1),
        ("Output age file", 1),
        ("Age distribution of population", age_distribution),
        ("Kernel type", 1),
        ("Kernel scale", 1.0),
        ("Include spatial transmission", 1),
        ("Include places", 1),
        ("Number of types of places", 1),
        ("Minimum age for age group 1 in place types", 0),
        ("Maximum age for age group 1 in place types", 100),
        ("Proportion of age group 1 in place types", 0.5),
        ("Kernel shape params for place types", 1),
        ("Kernel scale params for place types", 1),
        ("Kernel 3rd param for place types", 0),
        ("Kernel 4th param for place types", 0),
        ("Mean size of place types", 6),
        ("Param 1 of place group size distribution", 6),
        ("Proportion of between group place links", 0),
        ("Place overlap matrix", 1),
        ("Relative transmission rates for place types", 0.2),
        ("Number of seed locations", 1),
        ("Initial number of infecteds", 1),
        ("Location of initial infecteds", "0.5 0.5"),
        ("Maximum population in microcell of initial infection", 1000000),
        ("Randomise initial infection location", 1),
        ("All initial infections located in same microcell", 0),
        ("Administrative unit to seed initial infection into", 0),
        ("Reproduction number", reproduction_number),
        ("Infectious period", 3.0),
        ("Model time varying infectiousness", 1),
        ("Include mortality", 0),
        ("Include funeral transmission", 0),
        ("Include hospitalisation", 0),
        ("Do interrupt interventions", 0),
        ("Do prevalence dependent transmission", 0),
        ("Include latent period", 1),
        ("Latent period", 1.0),
        ("Include symptoms", 0),
        ("Bounding box for bitmap", "0 0 1 1"),
        ("Spatial domain for simulation", "0 0 1 1"),
        ("Grid size", 0.25),
        ("Use long/lat coord system", 0),
        ("Bitmap scale", 1),
        ("Bitmap y:x aspect scaling", 1),
        ("Output bitmap", 0),
        ("Output every realisation", 1),
        ("Only output non-extinct realisations", 0),
        ("Output summary results", 0),
        ("Target country", 1),
        ("Target country 2", 1),
        ("Target country 3", 1),
        ("Restrict treatment to target country", 0),
        ("Only treat mixing groups within places", 0),
        ("Treatment radius", 0),
        ("Number of resistance levels", 0),
        ("Vaccination start time", 100000),
        ("Proportion of population vaccinated", 0),
        ("Do geographic vaccination", 0),
        ("Vaccination radius", 0),
        ("Minimum radius from case to vaccinate", 0),
        ("Include contact tracing", 0),
        ("Include capital city effect", 0),
        ("Initial rate of importation of infections", 0),
        ("Changed rate of importation of infections", 0),
        ("Length of importation time profile provided", 0),
        ("Import to specific location", 0),
        ("Record infection events", 0),
        ("Limit number of infections", 0),
        ("Proportion of infections allowed across country borders", 1),
        ("Output origin destination matrix", 0),
    ]
    return ParameterSet(values)


__all__ = [
    "ParameterEntry",
    "ParameterFormatError",
    "ParameterSet",
    "tiny_parameter_set",
]
