"""Build the upstream EbolaSim C/C++ executable on Linux."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .manifest import normalise_country
from .patches import PatchApplication, apply_patches, copy_source_tree

REQUIRED_SOURCE_FILES = ("SpatialSim.c", "SpatialSim.h", "binio.cpp", "binio.h")


@dataclass(frozen=True)
class SourceInspection:
    source_dir: str
    exists: bool
    required_files: dict[str, bool]
    missing: list[str]

    @property
    def ok(self) -> bool:
        return self.exists and not self.missing

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


@dataclass(frozen=True)
class BuildConfig:
    source_dir: str
    build_dir: str
    target: str = "ebola-spatial-linux"
    country: str = "COUNTRY_WA"
    compiler: str = "g++"
    standard: str = "gnu++17"
    optimisation: str = "-O2"
    openmp: bool = True
    apply_patches: bool = True
    extra_cxxflags: list[str] = field(default_factory=list)
    extra_ldflags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    classification: str
    config: BuildConfig
    source_inspection: SourceInspection
    patched_source_dir: str | None
    patch_application: dict[str, Any] | None
    command: list[str]
    shell_command: str
    returncode: int | None
    timed_out: bool
    stdout: str
    stderr: str
    stdout_path: str
    stderr_path: str
    executable: str
    executable_exists: bool
    executable_sha256: str | None
    metadata_path: str
    diagnostics: list[str]
    python: str = field(default_factory=lambda: sys.version.split()[0])
    platform: str = field(default_factory=platform.platform)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "classification": self.classification,
            "config": self.config.to_dict(),
            "source_inspection": self.source_inspection.to_dict(),
            "patched_source_dir": self.patched_source_dir,
            "patch_application": self.patch_application,
            "command": self.command,
            "shell_command": self.shell_command,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "executable": self.executable,
            "executable_exists": self.executable_exists,
            "executable_sha256": self.executable_sha256,
            "metadata_path": self.metadata_path,
            "diagnostics": self.diagnostics,
            "python": self.python,
            "platform": self.platform,
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def inspect_source(source_dir: str | Path) -> SourceInspection:
    root = Path(source_dir)
    required = {name: (root / name).is_file() for name in REQUIRED_SOURCE_FILES}
    missing = [name for name, exists in required.items() if not exists]
    return SourceInspection(root.as_posix(), root.exists(), required, missing)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_command(
    *,
    source_dir: str | Path,
    executable: str | Path,
    country: str = "COUNTRY_WA",
    compiler: str = "g++",
    standard: str = "gnu++17",
    optimisation: str = "-O2",
    openmp: bool = True,
    extra_cxxflags: Sequence[str] = (),
    extra_ldflags: Sequence[str] = (),
) -> list[str]:
    src = Path(source_dir)
    exe = Path(executable)
    flags = [optimisation, f"-std={standard}", "-DUNIX", f"-D{normalise_country(country)}"]
    if openmp:
        flags.append("-fopenmp")
    flags.extend(str(x) for x in extra_cxxflags)
    ldflags = []
    if openmp:
        ldflags.append("-fopenmp")
    ldflags.append("-lm")
    ldflags.extend(str(x) for x in extra_ldflags)
    return [
        compiler,
        *flags,
        "-x",
        "c++",
        (src / "SpatialSim.c").as_posix(),
        (src / "binio.cpp").as_posix(),
        "-o",
        exe.as_posix(),
        *ldflags,
    ]


def classify_build(
    returncode: int | None,
    inspection: SourceInspection,
    executable: Path,
    stderr: str,
    *,
    timed_out: bool = False,
) -> str:
    if not inspection.ok:
        return "source_incomplete"
    if timed_out:
        return "timed_out"
    if returncode is None:
        return "not_executed"
    if returncode != 0:
        if "fatal error" in stderr.lower():
            return "compiler_fatal_error"
        return "compiler_failed"
    if not executable.exists():
        return "executable_missing_after_success"
    return "compiled"


def _timeout_stream(value: str | bytes | None) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace")


def build_model(
    source_dir: str | Path,
    *,
    build_dir: str | Path = "build/model-linux",
    target: str = "ebola-spatial-linux",
    country: str = "COUNTRY_WA",
    compiler: str | None = None,
    standard: str = "gnu++17",
    optimisation: str = "-O2",
    openmp: bool = True,
    patch: bool = True,
    patch_dir: str | Path | None = None,
    timeout: int | float | None = 180,
    extra_cxxflags: Sequence[str] = (),
    extra_ldflags: Sequence[str] = (),
    overwrite: bool = False,
) -> BuildResult:
    """Patch and compile the upstream source, returning captured build metadata."""

    source = Path(source_dir)
    build = Path(build_dir)
    if build.exists() and any(build.iterdir()) and overwrite:
        shutil.rmtree(build)
    build.mkdir(parents=True, exist_ok=True)
    out = build / target
    stdout_path = build / "build.stdout.log"
    stderr_path = build / "build.stderr.log"
    metadata_path = build / "build_metadata.json"
    config = BuildConfig(
        source_dir=source.as_posix(),
        build_dir=build.as_posix(),
        target=target,
        country=normalise_country(country),
        compiler=compiler or os.environ.get("CXX", "g++"),
        standard=standard,
        optimisation=optimisation,
        openmp=openmp,
        apply_patches=patch,
        extra_cxxflags=[str(x) for x in extra_cxxflags],
        extra_ldflags=[str(x) for x in extra_ldflags],
    )
    inspection = inspect_source(source)
    diagnostics: list[str] = []
    patched_source: Path | None = None
    patch_application: PatchApplication | None = None
    compile_source = source
    if not inspection.ok:
        diagnostics.append("missing required source files: " + ", ".join(inspection.missing))
    elif patch:
        patched_source = copy_source_tree(source, build / "patched-source", overwrite=True)
        patch_application = apply_patches(patched_source, patch_dir=patch_dir)
        if not patch_application.ok:
            diagnostics.append("one or more patches failed")
        compile_source = patched_source
    cmd = build_command(
        source_dir=compile_source,
        executable=out,
        country=config.country,
        compiler=config.compiler,
        standard=standard,
        optimisation=optimisation,
        openmp=openmp,
        extra_cxxflags=extra_cxxflags,
        extra_ldflags=extra_ldflags,
    )
    stdout = ""
    stderr = ""
    returncode: int | None = None
    timed_out = False
    if inspection.ok and (not patch or (patch_application is not None and patch_application.ok)):
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
            stdout = proc.stdout
            stderr = proc.stderr
            returncode = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = _timeout_stream(exc.stdout)
            stderr = _timeout_stream(exc.stderr)
            diagnostics.append(f"compiler timed out after {timeout} seconds")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    exe_hash = _sha256(out) if out.exists() else None
    classification = classify_build(returncode, inspection, out, stderr, timed_out=timed_out)
    result = BuildResult(
        ok=classification == "compiled",
        classification=classification,
        config=config,
        source_inspection=inspection,
        patched_source_dir=None if patched_source is None else patched_source.as_posix(),
        patch_application=None if patch_application is None else patch_application.to_dict(),
        command=cmd,
        shell_command=" ".join(cmd),
        returncode=returncode,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
        stdout_path=stdout_path.as_posix(),
        stderr_path=stderr_path.as_posix(),
        executable=out.as_posix(),
        executable_exists=out.exists(),
        executable_sha256=exe_hash,
        metadata_path=metadata_path.as_posix(),
        diagnostics=diagnostics,
    )
    metadata_path.write_text(result.to_json(pretty=True) + "\n", encoding="utf-8")
    return result


__all__ = [
    "BuildConfig",
    "BuildResult",
    "REQUIRED_SOURCE_FILES",
    "SourceInspection",
    "build_command",
    "build_model",
    "classify_build",
    "inspect_source",
]
