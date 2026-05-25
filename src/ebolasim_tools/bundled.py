"""Helpers for packaging and resolving bundled legacy executables."""

from __future__ import annotations

import json
import platform
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BUNDLED_DIRNAME = "_bundled"
DEFAULT_BUNDLED_TARGET = "ebola-spatial-linux"


@dataclass(frozen=True)
class BundledBinary:
    ok: bool
    platform_id: str
    target: str
    path: str | None
    diagnostics: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def bundled_root(package_root: str | Path | None = None) -> Path:
    root = Path(package_root) if package_root is not None else Path(__file__).resolve().parent
    return root / BUNDLED_DIRNAME


def detect_platform_id() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        machine = "x86_64"
    elif machine in {"aarch64", "arm64"}:
        machine = "aarch64"
    return f"{platform.system().lower()}-{machine}"


def resolve_bundled_executable(
    *,
    platform_id: str | None = None,
    target: str = DEFAULT_BUNDLED_TARGET,
    package_root: str | Path | None = None,
) -> BundledBinary:
    pid = platform_id or detect_platform_id()
    root = bundled_root(package_root)
    path = root / pid / target
    diagnostics: list[str] = []
    if not path.is_file():
        diagnostics.append(f"bundled executable not found for {pid}: {path}")
    elif not path.stat().st_mode & 0o111:
        diagnostics.append(f"bundled executable is not marked executable: {path}")
    return BundledBinary(
        ok=not diagnostics,
        platform_id=pid,
        target=target,
        path=path.as_posix() if path.exists() else None,
        diagnostics=diagnostics,
    )


def stage_bundled_executable(
    executable: str | Path,
    *,
    platform_id: str | None = None,
    target: str = DEFAULT_BUNDLED_TARGET,
    package_root: str | Path | None = None,
    metadata_files: list[str | Path] | None = None,
) -> Path:
    src = Path(executable)
    if not src.is_file():
        raise FileNotFoundError(src)
    pid = platform_id or detect_platform_id()
    root = bundled_root(package_root) / pid
    root.mkdir(parents=True, exist_ok=True)
    dest = root / target
    shutil.copy2(src, dest)
    dest.chmod(dest.stat().st_mode | 0o111)
    for metadata in metadata_files or []:
        metadata_path = Path(metadata)
        if metadata_path.is_file():
            shutil.copy2(metadata_path, root / metadata_path.name)
    return dest


__all__ = [
    "BUNDLED_DIRNAME",
    "BundledBinary",
    "DEFAULT_BUNDLED_TARGET",
    "bundled_root",
    "detect_platform_id",
    "resolve_bundled_executable",
    "stage_bundled_executable",
]
