"""Patch inventory and application helpers for the legacy C/C++ source."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PatchSpec:
    id: str
    file: str
    source_files: list[str] = field(default_factory=list)
    model_logic_change: bool = False
    compile_only: bool = False
    compatibility_fix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchInventory:
    patch_dir: str
    patches: list[PatchSpec]

    def to_dict(self) -> dict[str, Any]:
        return {"patch_dir": self.patch_dir, "patches": [p.to_dict() for p in self.patches]}

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


@dataclass(frozen=True)
class PatchResult:
    patch: str
    returncode: int
    stdout: str
    stderr: str
    applied: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchApplication:
    source_dir: str
    patch_dir: str
    ok: bool
    results: list[PatchResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_dir": self.source_dir,
            "patch_dir": self.patch_dir,
            "ok": self.ok,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def bundled_patch_dir() -> Path:
    """Return the directory containing bundled patch files."""

    return Path(__file__).resolve().parent / "legacy_patches"


def read_patch_inventory(patch_dir: str | Path | None = None) -> PatchInventory:
    root = Path(patch_dir) if patch_dir is not None else bundled_patch_dir()
    yml = root / "patches.yml"
    if yml.exists():
        payload = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        patches = [PatchSpec(**item) for item in payload.get("patches", [])]
    else:
        patches = [PatchSpec(id=p.stem, file=p.name) for p in sorted(root.glob("*.patch"))]
    return PatchInventory(patch_dir=root.as_posix(), patches=patches)


def list_patch_files(patch_dir: str | Path | None = None) -> list[Path]:
    inventory = read_patch_inventory(patch_dir)
    root = Path(inventory.patch_dir)
    return [root / spec.file for spec in inventory.patches]


def copy_source_tree(
    source_dir: str | Path, target_dir: str | Path, *, overwrite: bool = False
) -> Path:
    source = Path(source_dir)
    target = Path(target_dir)
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"target source directory already exists: {target}")
        shutil.rmtree(target)
    ignore = shutil.ignore_patterns(".git", "build", "runs", "*.exe", "*.obj", "*.pdb")
    shutil.copytree(source, target, ignore=ignore)
    return target


def normalise_patch_target_line_endings(source_dir: str | Path) -> None:
    """Convert known legacy text source files in a copied tree to LF endings."""

    root = Path(source_dir)
    for pattern in ("*.c", "*.h", "*.cpp", "*.hpp"):  # keep this to source-like files only
        for path in root.glob(pattern):
            data = path.read_bytes()
            normalised = data.replace(b"\r\n", b"\n")
            if normalised != data:
                path.write_bytes(normalised)


def apply_patches(
    source_dir: str | Path,
    *,
    patch_dir: str | Path | None = None,
    reverse: bool = False,
    dry_run: bool = False,
    patch_binary: str = "patch",
    normalise_line_endings: bool = True,
) -> PatchApplication:
    """Apply the ordered Linux portability patches to a source directory."""

    source = Path(source_dir)
    root = Path(patch_dir) if patch_dir is not None else bundled_patch_dir()
    results: list[PatchResult] = []
    if shutil.which(patch_binary) is None:
        raise RuntimeError(f"patch executable not found: {patch_binary}")
    if normalise_line_endings and not reverse and not dry_run:
        normalise_patch_target_line_endings(source)
    for patch_file in list_patch_files(root):
        cmd = [patch_binary, "-p1", "-i", patch_file.as_posix()]
        if reverse:
            cmd.insert(1, "-R")
        if dry_run:
            cmd.insert(1, "--dry-run")
        proc = subprocess.run(cmd, cwd=source, text=True, capture_output=True, check=False)
        results.append(
            PatchResult(
                patch=patch_file.name,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                applied=proc.returncode == 0,
            )
        )
        if proc.returncode != 0:
            break
    return PatchApplication(
        source_dir=source.as_posix(),
        patch_dir=root.as_posix(),
        ok=all(result.applied for result in results),
        results=results,
    )


__all__ = [
    "PatchApplication",
    "PatchInventory",
    "PatchResult",
    "PatchSpec",
    "apply_patches",
    "bundled_patch_dir",
    "copy_source_tree",
    "list_patch_files",
    "read_patch_inventory",
    "normalise_patch_target_line_endings",
]
