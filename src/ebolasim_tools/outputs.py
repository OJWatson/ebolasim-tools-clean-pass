"""Read, summarise and optionally plot legacy model outputs."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OutputTable:
    path: str
    columns: list[str]
    rows: list[dict[str, str]]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def numeric_column(self, name: str) -> list[float]:
        values: list[float] = []
        for row in self.rows:
            try:
                values.append(float(row[name]))
            except (KeyError, ValueError):
                continue
        return values

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "columns": self.columns,
            "row_count": self.row_count,
            "rows": self.rows,
        }


@dataclass(frozen=True)
class OutputSummary:
    root: str
    files: list[str]
    tables: list[dict[str, Any]]
    main_csv: str | None
    rows: int | None
    final_time: float | None
    total_incidence: float | None
    max_infectious: float | None
    final_susceptible: float | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def _choose_delimiter(header_line: str) -> str:
    return "\t" if header_line.count("\t") > header_line.count(",") else ","


def _unique_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for index, raw in enumerate(columns):
        name = raw.strip() or f"column_{index}"
        count = seen.get(name, 0)
        seen[name] = count + 1
        unique.append(name if count == 0 else f"{name}_{count + 1}")
    return unique


def read_output_table(path: str | Path) -> OutputTable:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return OutputTable(path=p.as_posix(), columns=[], rows=[])
    delimiter = _choose_delimiter(lines[0])
    reader = csv.reader(lines, delimiter=delimiter)
    raw_columns = next(reader, [])
    columns = _unique_columns(raw_columns)
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        row: dict[str, str] = {}
        for idx, column in enumerate(columns):
            row[column] = raw_row[idx] if idx < len(raw_row) else ""
        for idx in range(len(columns), len(raw_row)):
            row[f"extra_{idx - len(columns) + 1}"] = raw_row[idx]
        rows.append(row)
    return OutputTable(path=p.as_posix(), columns=columns, rows=rows)


def find_output_files(root: str | Path) -> list[Path]:
    p = Path(root)
    if p.is_file():
        return [p]
    if not p.exists():
        raise FileNotFoundError(p)
    return sorted(path for path in p.rglob("*.csv") if path.is_file())


def _choose_main_table(tables: list[OutputTable]) -> OutputTable | None:
    candidates = [table for table in tables if {"t", "S"}.issubset(set(table.columns))]
    if candidates:
        return max(candidates, key=lambda table: table.row_count)
    return tables[0] if tables else None


def summarise_outputs(root: str | Path) -> OutputSummary:
    files = find_output_files(root)
    tables: list[OutputTable] = []
    warnings: list[str] = []
    for path in files:
        try:
            tables.append(read_output_table(path))
        except Exception as exc:  # pragma: no cover - defensive, retained in summary
            warnings.append(f"could not parse {path}: {exc}")
    main = _choose_main_table(tables)
    final_time = total_incidence = max_infectious = final_susceptible = None
    rows = None
    main_path = None
    if main is not None:
        rows = main.row_count
        main_path = main.path
        if main.rows:
            last = main.rows[-1]
            try:
                final_time = float(last.get("t", "nan"))
            except ValueError:
                final_time = None
            try:
                final_susceptible = float(last.get("S", "nan"))
            except ValueError:
                final_susceptible = None
            inc_values = main.numeric_column("incI") or main.numeric_column("incC")
            total_incidence = sum(inc_values) if inc_values else None
            inf_values = main.numeric_column("I")
            max_infectious = max(inf_values) if inf_values else None
    return OutputSummary(
        root=Path(root).as_posix(),
        files=[path.as_posix() for path in files],
        tables=[
            {"path": table.path, "columns": table.columns, "rows": table.row_count}
            for table in tables
        ],
        main_csv=main_path,
        rows=rows,
        final_time=final_time,
        total_incidence=total_incidence,
        max_infectious=max_infectious,
        final_susceptible=final_susceptible,
        warnings=warnings,
    )


def plot_output_timeseries(
    csv_path: str | Path, output_path: str | Path, *, y_column: str = "I"
) -> Path:
    """Create a simple timeseries plot. Requires matplotlib to be installed."""

    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    table = read_output_table(csv_path)
    times = table.numeric_column("t")
    values = table.numeric_column(y_column)
    if not times or not values:
        raise ValueError(f"columns t and {y_column} must contain numeric values")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    plt.figure()
    plt.plot(times, values)
    plt.xlabel("t")
    plt.ylabel(y_column)
    plt.tight_layout()
    plt.savefig(target)
    plt.close()
    return target


__all__ = [
    "OutputSummary",
    "OutputTable",
    "find_output_files",
    "plot_output_timeseries",
    "read_output_table",
    "summarise_outputs",
]
