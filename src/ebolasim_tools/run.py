"""Subprocess runner for the legacy executable."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .command import build_command_plan
from .manifest import RunManifest, read_manifest
from .outputs import summarise_outputs


@dataclass(frozen=True)
class RunResult:
    ok: bool
    classification: str
    command: list[str]
    shell_command: str
    cwd: str
    environment: dict[str, str]
    returncode: int | None
    timed_out: bool
    elapsed_seconds: float
    stdout_path: str
    stderr_path: str
    metadata_path: str
    output_dir: str
    output_files: list[str]
    output_summary: dict[str, Any] | None
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    python: str = field(default_factory=lambda: sys.version.split()[0])
    platform: str = field(default_factory=platform.platform)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def _tail(text: str, count: int = 40) -> list[str]:
    return text.splitlines()[-count:]


def _resolve_manifest(manifest: RunManifest | str | Path) -> tuple[RunManifest, Path | None]:
    if isinstance(manifest, RunManifest):
        return manifest, None
    path = Path(manifest)
    return read_manifest(path), path


def _output_dir_from_manifest(manifest: RunManifest, root: Path) -> Path:
    if manifest.outputs.output_dir:
        p = Path(manifest.outputs.output_dir)
        return p if p.is_absolute() else root / p
    base = Path(manifest.outputs.output_base)
    return base.parent if base.is_absolute() else root / base.parent


def classify_run(
    returncode: int | None, timed_out: bool, output_files: list[str], stderr: str
) -> str:
    if timed_out:
        return "timed_out"
    if returncode is None:
        return "not_executed"
    if returncode != 0:
        if "Unable to find parameter" in stderr:
            return "missing_parameter"
        if "Unable to open" in stderr:
            return "missing_runtime_input"
        return "nonzero_exit"
    if not output_files:
        return "completed_without_outputs"
    return "completed_with_outputs"


def run_model(
    manifest: RunManifest | str | Path,
    *,
    executable: str | Path | None = None,
    root: str | Path | None = None,
    run_dir: str | Path = "runs/model-run",
    timeout: int | float | None = None,
    threads: int | None = None,
    dry_run: bool = False,
) -> RunResult:
    """Run the legacy executable from a manifest and capture reproducibility metadata."""

    run_manifest, manifest_path = _resolve_manifest(manifest)
    scenario_root = (
        Path(root) if root is not None else (manifest_path.parent if manifest_path else Path.cwd())
    )
    work = Path(run_dir)
    work.mkdir(parents=True, exist_ok=True)
    output_dir = _output_dir_from_manifest(run_manifest, scenario_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = work / "stdout.log"
    stderr_path = work / "stderr.log"
    metadata_path = work / "run_metadata.json"
    plan = build_command_plan(
        run_manifest,
        executable=executable,
        root=scenario_root,
        working_directory=scenario_root,
        threads=threads,
    )
    env = os.environ.copy()
    env.update(plan.environment)
    start = time.monotonic()
    stdout = ""
    stderr = ""
    returncode: int | None = None
    timed_out = False
    if not dry_run:
        try:
            proc = subprocess.run(
                plan.command,
                cwd=scenario_root,
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            returncode = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (
                exc.stdout
                if isinstance(exc.stdout, str)
                else (exc.stdout or b"").decode("utf-8", errors="replace")
            )
            stderr = (
                exc.stderr
                if isinstance(exc.stderr, str)
                else (exc.stderr or b"").decode("utf-8", errors="replace")
            )
    elapsed = time.monotonic() - start
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    output_files = sorted(path.as_posix() for path in output_dir.rglob("*") if path.is_file())
    summary = None
    if output_files:
        try:
            summary = summarise_outputs(output_dir).to_dict()
        except Exception:
            summary = None
    classification = classify_run(returncode, timed_out, output_files, stderr)
    result = RunResult(
        ok=classification == "completed_with_outputs" or dry_run,
        classification="dry_run" if dry_run else classification,
        command=plan.command,
        shell_command=plan.shell_command,
        cwd=scenario_root.as_posix(),
        environment=plan.environment,
        returncode=returncode,
        timed_out=timed_out,
        elapsed_seconds=elapsed,
        stdout_path=stdout_path.as_posix(),
        stderr_path=stderr_path.as_posix(),
        metadata_path=metadata_path.as_posix(),
        output_dir=output_dir.as_posix(),
        output_files=output_files,
        output_summary=summary,
        stdout_tail=_tail(stdout),
        stderr_tail=_tail(stderr),
    )
    metadata_path.write_text(result.to_json(pretty=True) + "\n", encoding="utf-8")
    return result


__all__ = ["RunResult", "classify_run", "run_model"]
