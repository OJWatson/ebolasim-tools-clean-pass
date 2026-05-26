"""Pinned upstream C model source lock and fetch helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_UPSTREAM_SOURCE_FILES = ("SpatialSim.c", "SpatialSim.h", "binio.cpp", "binio.h")


@dataclass(frozen=True)
class UpstreamLock:
    schema_version: int
    name: str
    repository: str
    ref_type: str
    ref: str
    archive_url: str
    archive_sha256: str
    strip_prefix: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def is_placeholder(self) -> bool:
        return (
            "PLACEHOLDER" in self.repository
            or self.ref == "0" * 40
            or self.archive_sha256 == "0" * 64
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


@dataclass(frozen=True)
class UpstreamFetchResult:
    ok: bool
    lock_path: str
    lock: UpstreamLock
    output_dir: str
    archive_path: str
    expected_archive_sha256: str
    archive_sha256: str
    source_dir: str | None
    diagnostics: list[str]
    metadata_path: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lock"] = self.lock.to_dict()
        return payload

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def default_upstream_lock_path() -> Path:
    env = os.environ.get("EBOLASIM_UPSTREAM_LOCK")
    if env:
        return Path(env)
    module_root = Path(__file__).resolve().parents[2]
    repo_lock = module_root / "model-src" / "upstream.lock.yml"
    if repo_lock.exists():
        return repo_lock
    packaged_lock = (
        Path(__file__).resolve().parents[1] / "ebolasim" / "_patches" / "upstream.lock.yml"
    )
    if packaged_lock.exists():
        return packaged_lock
    return repo_lock


def read_upstream_lock(lock_path: str | Path | None = None) -> UpstreamLock:
    path = default_upstream_lock_path() if lock_path is None else Path(lock_path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"upstream lock must be a mapping: {path}")
    upstream = payload.get("upstream")
    if not isinstance(upstream, dict):
        raise ValueError(f"upstream lock missing top-level 'upstream' mapping: {path}")

    def required_text(key: str) -> str:
        if key not in upstream:
            raise ValueError(f"upstream lock missing upstream.{key}: {path}")
        value = upstream[key]
        if not isinstance(value, str):
            raise ValueError(
                f"upstream lock upstream.{key} must be a string in {path}; "
                f"got {type(value).__name__}"
            )
        text = value.strip()
        if not text:
            raise ValueError(f"upstream lock upstream.{key} cannot be empty: {path}")
        return text

    schema_version = payload.get("schema_version", 1)
    if not isinstance(schema_version, int):
        raise ValueError(f"upstream lock schema_version must be an integer: {path}")
    notes = payload.get("notes", [])
    if notes is None:
        notes = []
    if not isinstance(notes, list):
        raise ValueError(f"upstream lock notes must be a list when present: {path}")
    strip_prefix_value = upstream.get("strip_prefix")
    if strip_prefix_value is not None and not isinstance(strip_prefix_value, str):
        raise ValueError(f"upstream lock upstream.strip_prefix must be a string: {path}")
    lock = UpstreamLock(
        schema_version=schema_version,
        name=required_text("name"),
        repository=required_text("repository"),
        ref_type=required_text("ref_type"),
        ref=required_text("ref"),
        archive_url=required_text("archive_url"),
        archive_sha256=required_text("archive_sha256").lower(),
        strip_prefix=None if strip_prefix_value is None else strip_prefix_value.strip(),
        notes=[str(item) for item in notes],
    )
    if lock.ref_type not in {"commit", "tag", "release"}:
        raise ValueError(f"unsupported ref_type in upstream lock: {lock.ref_type}")
    if not _SHA256_RE.match(lock.archive_sha256):
        raise ValueError("upstream lock archive_sha256 must be 64 lowercase hex characters")
    return lock


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(archive: tarfile.TarFile, target: Path) -> None:
    target_resolved = target.resolve()
    for member in archive.getmembers():
        member_path = (target / member.name).resolve()
        if not str(member_path).startswith(str(target_resolved)):
            raise ValueError(f"archive member escapes target directory: {member.name}")
    archive.extractall(target)


def _resolve_source_dir(extract_dir: Path, strip_prefix: str | None) -> Path | None:
    if strip_prefix:
        candidate = extract_dir / strip_prefix
        if candidate.is_dir():
            return candidate
    dirs = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(dirs) == 1:
        return dirs[0]
    return None


def _missing_required_source_files(source_dir: Path) -> list[str]:
    return [name for name in REQUIRED_UPSTREAM_SOURCE_FILES if not (source_dir / name).is_file()]


def fetch_upstream_source(
    *,
    output_dir: str | Path = "build/upstream-source",
    lock_path: str | Path | None = None,
    overwrite: bool = False,
    timeout: int | float = 120,
    allow_placeholders: bool = False,
) -> UpstreamFetchResult:
    lock_file = default_upstream_lock_path() if lock_path is None else Path(lock_path)
    lock = read_upstream_lock(lock_file)
    diagnostics: list[str] = []
    if lock.is_placeholder and not allow_placeholders:
        diagnostics.append("upstream lock still contains placeholder values")
    output = Path(output_dir)
    if output.exists():
        if overwrite:
            shutil.rmtree(output)
        elif any(output.iterdir()):
            raise FileExistsError(f"output directory already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / "upstream-source.tar.gz"
    extract_dir = output / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    if not diagnostics:
        request = urllib.request.Request(
            lock.archive_url,
            headers={"User-Agent": "ebolasim-source-fetch"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            archive_path.write_bytes(response.read())
    archive_sha256 = _sha256(archive_path) if archive_path.exists() else ""
    if not diagnostics and archive_sha256 != lock.archive_sha256:
        diagnostics.append(
            "archive SHA256 mismatch "
            f"(expected {lock.archive_sha256}, got {archive_sha256 or 'missing'})"
        )
    source_dir: Path | None = None
    if archive_path.exists() and not diagnostics:
        with tarfile.open(archive_path, mode="r:*") as archive:
            _safe_extract(archive, extract_dir)
        source_dir = _resolve_source_dir(extract_dir, lock.strip_prefix)
        if source_dir is None:
            diagnostics.append(
                "could not resolve extracted source directory "
                "(set strip_prefix in upstream.lock.yml)"
            )
        else:
            missing = _missing_required_source_files(source_dir)
            if missing:
                diagnostics.append(
                    "extracted source directory is missing required files: " + ", ".join(missing)
                )
                source_dir = None
    metadata_path = output / "upstream_fetch.json"
    result = UpstreamFetchResult(
        ok=not diagnostics,
        lock_path=lock_file.as_posix(),
        lock=lock,
        output_dir=output.as_posix(),
        archive_path=archive_path.as_posix(),
        expected_archive_sha256=lock.archive_sha256,
        archive_sha256=archive_sha256,
        source_dir=None if source_dir is None else source_dir.as_posix(),
        diagnostics=diagnostics,
        metadata_path=metadata_path.as_posix(),
    )
    metadata_path.write_text(result.to_json(pretty=True) + "\n", encoding="utf-8")
    return result


__all__ = [
    "UpstreamFetchResult",
    "UpstreamLock",
    "REQUIRED_UPSTREAM_SOURCE_FILES",
    "default_upstream_lock_path",
    "fetch_upstream_source",
    "read_upstream_lock",
]
