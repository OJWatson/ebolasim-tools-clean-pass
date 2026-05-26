"""Read, summarise and plot EbolaSim output CSV files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ebolasim_tools.outputs import (
    OutputTable,
    find_output_files,
    read_output_table,
    summarise_outputs,
)


def _kind(path: Path) -> str:
    name = path.name
    if name.endswith(".adunit.csv"):
        return "admin_unit"
    if name.endswith(".age.csv"):
        return "age"
    if name.endswith(".keyworker.csv"):
        return "keyworker"
    if name.endswith(".seeds.csv"):
        return "seeds"
    return "main"


@dataclass
class Results:
    """Container for model output files."""

    root: Path
    tables: dict[str, list[OutputTable]] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def read(cls, root: str | Path) -> Results:
        output_root = Path(root)
        grouped: dict[str, list[OutputTable]] = {
            "main": [],
            "admin_unit": [],
            "age": [],
            "keyworker": [],
            "seeds": [],
        }
        for path in find_output_files(output_root):
            grouped.setdefault(_kind(path), []).append(read_output_table(path))
        return cls(
            root=output_root, tables=grouped, summary=summarise_outputs(output_root).to_dict()
        )

    @property
    def main(self) -> OutputTable | None:
        return self.tables.get("main", [None])[0] if self.tables.get("main") else None

    @property
    def by_admin_unit(self) -> list[OutputTable]:
        return self.tables.get("admin_unit", [])

    @property
    def by_age(self) -> list[OutputTable]:
        return self.tables.get("age", [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root.as_posix(),
            "summary": self.summary,
            "tables": {
                kind: [
                    {"path": table.path, "rows": table.row_count, "columns": table.columns}
                    for table in tables
                ]
                for kind, tables in self.tables.items()
            },
            "counts": {kind: len(tables) for kind, tables in self.tables.items()},
        }

    def to_pandas(self) -> dict[str, Any]:
        try:
            import pandas as pd  # type: ignore[import-not-found, import-untyped]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("Results.to_pandas() requires pandas to be installed") from exc
        frames: dict[str, Any] = {}
        for kind, tables in self.tables.items():
            rows: list[dict[str, str]] = []
            for table in tables:
                for row in table.rows:
                    rows.append({"source": table.path, **row})
            frames[kind] = pd.DataFrame(rows)
        return frames

    def plot(self, *, y: str = "I", out: str | Path | None = None) -> Any:
        if self.main is None:
            raise ValueError("no main output CSV is available to plot")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]

        times = self.main.numeric_column("t")
        values = self.main.numeric_column(y)
        if not times or not values:
            raise ValueError(f"main output does not contain numeric columns t and {y}")
        fig, ax = plt.subplots()
        ax.plot(times, values)
        ax.set_xlabel("Day")
        ax.set_ylabel(y)
        fig.tight_layout()
        if out is not None:
            fig.savefig(out)
        return fig


def read_results(root: str | Path) -> Results:
    """Read model outputs from a directory."""

    return Results.read(root)


def _as_results(item: Results | Any) -> Results:
    if isinstance(item, Results):
        return item
    if hasattr(item, "results") and item.results is not None:
        return item.results
    raise TypeError("expected a Results object or a completed Sim")


def compare_results(items: list[Results | Any]) -> list[dict[str, Any]]:
    """Return compact summary rows for several simulations."""

    rows = []
    for index, item in enumerate(items):
        results = _as_results(item)
        label = getattr(item, "label", f"sim_{index + 1}")
        rows.append({"label": label, **results.summary})
    return rows


def plot_compare(items: list[Results | Any], *, y: str = "I", out: str | Path | None = None) -> Any:
    """Plot the first main trajectory from several completed simulations."""

    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    fig, ax = plt.subplots()
    for index, item in enumerate(items):
        results = _as_results(item)
        table = results.main
        if table is None:
            continue
        label = getattr(item, "label", f"sim_{index + 1}")
        ax.plot(table.numeric_column("t"), table.numeric_column(y), label=label)
    ax.set_xlabel("Day")
    ax.set_ylabel(y)
    ax.legend()
    fig.tight_layout()
    if out is not None:
        fig.savefig(out)
    return fig


__all__ = ["Results", "compare_results", "plot_compare", "read_results"]
