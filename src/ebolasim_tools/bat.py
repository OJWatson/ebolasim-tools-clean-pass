"""Small helpers for Windows batch files that launch the legacy model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BatchCommand:
    raw: str
    tokens: list[str]


_PARAMSET_RE = re.compile(r"paramset[_ -]?(\d+)|p[_-]?(\d+)\.txt", re.IGNORECASE)


def _split_batch_line(line: str) -> list[str]:
    # This intentionally handles the simple quoted-token shape used by the model
    # batch files without trying to implement cmd.exe.
    import shlex

    return shlex.split(line.strip(), posix=False)


def parse_batch_commands(path: str | Path) -> list[BatchCommand]:
    commands: list[BatchCommand] = []
    for raw in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.lower().startswith(("rem", "::", "echo ")):
            continue
        if "ebola" in line.lower() or "/P:" in line or "/O:" in line:
            commands.append(BatchCommand(raw=line, tokens=_split_batch_line(line)))
    return commands


def infer_paramset_from_text(text: str) -> int | None:
    match = _PARAMSET_RE.search(text)
    if not match:
        return None
    value = match.group(1) or match.group(2)
    return int(value)


def find_batch_files(root: str | Path) -> list[Path]:
    return sorted(path for path in Path(root).rglob("*.bat") if path.is_file())


def find_paramset_files(root: str | Path) -> list[Path]:
    patterns = ["p_*.txt", "paramset*.txt", "*param*.txt"]
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in Path(root).rglob(pattern) if path.is_file())
    return sorted(files)


__all__ = [
    "BatchCommand",
    "find_batch_files",
    "find_paramset_files",
    "infer_paramset_from_text",
    "parse_batch_commands",
]
