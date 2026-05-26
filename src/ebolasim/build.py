"""Maintainer helpers for fetching, patching, compiling and bundling the C model."""

from __future__ import annotations

from pathlib import Path

from ebolasim_tools.build import BuildResult, build_model
from ebolasim_tools.bundled import (
    BundledBinary,
    detect_platform_id,
    resolve_bundled_executable,
    stage_bundled_executable,
)
from ebolasim_tools.patches import PatchApplication, apply_patches, read_patch_inventory
from ebolasim_tools.upstream import UpstreamFetchResult, UpstreamLock, fetch_upstream_source
from ebolasim_tools.upstream import read_upstream_lock as read_source_lock


def fetch_source(**kwargs) -> UpstreamFetchResult:
    return fetch_upstream_source(**kwargs)


def build_executable(source_dir: str | Path, **kwargs) -> BuildResult:
    return build_model(source_dir, **kwargs)


def bundle_executable(executable: str | Path, **kwargs) -> Path:
    kwargs.setdefault("package_root", Path(__file__).resolve().parent)
    return stage_bundled_executable(executable, **kwargs)


__all__ = [
    "BuildResult",
    "BundledBinary",
    "PatchApplication",
    "UpstreamFetchResult",
    "UpstreamLock",
    "apply_patches",
    "build_executable",
    "bundle_executable",
    "detect_platform_id",
    "fetch_source",
    "read_patch_inventory",
    "read_source_lock",
    "resolve_bundled_executable",
]
