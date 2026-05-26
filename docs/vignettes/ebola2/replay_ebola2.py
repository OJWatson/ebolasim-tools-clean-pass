#!/usr/bin/env python3
"""Replay and compare the local Ebola2 reference bundle."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.is_dir() and SRC_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, SRC_ROOT.as_posix())

from ebolasim import read_results, resolve_executable

REFERENCE_OUTPUT_REL = Path("Ervebo/Gavi/Output_MidAccept_singleAdUnit")
SELECTED_REALISATIONS = (0, 999)
OUTPUT_SUFFIXES = ("", ".adunit", ".age", ".keyworker", ".seeds")
PERCENT_VAR_RE = re.compile(r"%([^%]+)%")


@dataclass(frozen=True)
class ReplayJob:
    paramset: int
    command: list[str]
    shell_command: str
    environment: dict[str, str]
    cwd: str
    output_dir: str
    launch_values: list[str]


@dataclass(frozen=True)
class CsvValueComparison:
    status: str
    numeric_equivalent: bool
    row_count_reference: int
    row_count_generated: int
    max_abs_diff: float | None = None
    first_difference: dict[str, Any] | None = None
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FileComparison:
    filename: str
    status: str
    byte_identical: bool
    numeric_equivalent: bool
    reference_sha256: str | None
    generated_sha256: str | None
    row_count_reference: int | None = None
    row_count_generated: int | None = None
    max_abs_diff: float | None = None
    first_difference: dict[str, Any] | None = None
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", dest="zip_path", type=Path, default=Path("ignore/Ebola2.zip"))
    parser.add_argument("--workdir", type=Path, default=Path("artifacts/ebola2-replay"))
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path("docs/vignettes/ebola2/evidence"),
    )
    parser.add_argument("--paramsets", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--exe", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    parser.add_argument("--skip-run", action="store_true")
    parser.add_argument("--fail-on-mismatch", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_ebola_dir(root: str | Path) -> Path | None:
    base = Path(root)
    candidates = [base, base / "Ebola2", base / "Ebola", *base.glob("Ebola*")]
    for candidate in candidates:
        if (candidate / "Ervebo").is_dir():
            return candidate
    for candidate in base.rglob("Ebola*"):
        if (candidate / "Ervebo").is_dir():
            return candidate
    return None


def safe_extract_zip(zip_path: Path, extract_root: Path) -> Path:
    if not zip_path.is_file():
        raise FileNotFoundError(f"Ebola2 zip was not found: {zip_path}")
    extract_root.mkdir(parents=True, exist_ok=True)
    if find_ebola_dir(extract_root) is not None:
        return extract_root
    root_resolved = extract_root.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (extract_root / member.filename).resolve()
            if not target.is_relative_to(root_resolved):
                raise ValueError(f"unsafe zip member path: {member.filename}")
        archive.extractall(extract_root)
    return extract_root


def clean_evidence_dir(evidence_dir: Path) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name in ("commands", "run_metadata", "output_subset", "manifests"):
        target = evidence_dir / name
        if target.exists():
            shutil.rmtree(target)
    for name in ("comparison_summary.json", "comparison_summary.md"):
        target = evidence_dir / name
        if target.exists():
            target.unlink()


def _windows_path_to_relative(value: str) -> str:
    text = value.strip().strip('"').replace("\\", "/")
    for marker in ("/Ebola/", "/Ebola2/"):
        if marker in text:
            return text.split(marker, 1)[1]
    for prefix in ("Ebola/", "Ebola2/"):
        if text.startswith(prefix):
            return text.split(prefix, 1)[1]
    return text


def _read_batch_sets(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.lower().startswith("set ") or "=" not in line:
            continue
        key, value = line[4:].split("=", 1)
        values[key.strip().upper()] = _windows_path_to_relative(value.strip())
    return values


def _substitute(text: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return variables.get(match.group(1).strip().upper(), match.group(0))

    return PERCENT_VAR_RE.sub(replace, text)


def _selected_launch_values(bundle_root: Path, paramset: int) -> list[str]:
    for launch in sorted(bundle_root.rglob("launch*.bat")):
        for raw in launch.read_text(encoding="utf-8", errors="ignore").splitlines():
            tokens = shlex.split(raw.strip(), posix=False)
            for index, token in enumerate(tokens):
                try:
                    token_paramset = int(float(token))
                except ValueError:
                    continue
                if token_paramset == paramset:
                    return tokens[index:]
    raise ValueError(f"could not find launch values for paramset {paramset}")


def _run_batch(bundle_root: Path) -> Path:
    runs = sorted(path for path in bundle_root.rglob("run*.bat") if path.is_file())
    if not runs:
        raise FileNotFoundError("could not find Ebola2 run batch file")
    return runs[0]


def _parse_batch_command(bundle_root: Path, paramset: int) -> tuple[list[str], list[str]]:
    run_file = _run_batch(bundle_root)
    variables = _read_batch_sets(run_file)
    launch_values = _selected_launch_values(bundle_root, paramset)
    names = list("ABCDEFGHIJKLMNO")
    variables.update({name: value for name, value in zip(names, launch_values, strict=False)})
    for raw in run_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "ebola-spatial" not in raw.lower() or "/p:" not in raw.lower():
            continue
        command_line = _substitute(raw.strip(), variables)
        tokens = shlex.split(command_line, posix=False)
        return tokens[1:], launch_values
    raise ValueError(f"could not parse model command from {run_file}")


def _normalise_flag_key(raw: str) -> str:
    return "s" if raw == "s" else raw.upper()


def build_job(
    bundle_root: Path,
    generated_root: Path,
    *,
    paramset: int,
    executable: str,
    threads: int,
) -> ReplayJob:
    args, launch_values = _parse_batch_command(bundle_root, paramset)
    flags: dict[str, str] = {}
    clp: dict[int, str] = {}
    seeds: list[str] = []
    for token in args:
        if token.startswith("/") and ":" in token and token[1:].upper().startswith("CLP"):
            key, value = token[1:].split(":", 1)
            clp[int(key[3:])] = value
        elif token.startswith("/") and ":" in token:
            key, value = token[1:].split(":", 1)
            flags[_normalise_flag_key(key)] = _windows_path_to_relative(value)
        else:
            seeds.append(token)
    output_dir = generated_root / f"paramset_{paramset}"
    output_base = output_dir / f"paramset_{paramset}"
    output_dir.mkdir(parents=True, exist_ok=True)

    def abs_path(flag: str) -> str:
        return (bundle_root / flags[flag]).resolve().as_posix()

    command = [
        executable,
        f"/P:{abs_path('P')}",
        f"/PP:{abs_path('PP')}",
        f"/O:{output_base.resolve().as_posix()}",
        f"/D:{abs_path('D')}",
    ]
    if "L" in flags:
        command.append(f"/L:{abs_path('L')}")
    if "S" in flags:
        command.append(f"/S:{abs_path('S')}")
    if "R" in flags:
        command.append(f"/R:{flags['R']}")
    command.extend(f"/CLP{key}:{clp[key]}" for key in sorted(clp))
    command.extend(seeds[-4:])
    env = {"OMP_NUM_THREADS": str(threads)}
    return ReplayJob(
        paramset=paramset,
        command=command,
        shell_command=shlex.join(command),
        environment=env,
        cwd=bundle_root.as_posix(),
        output_dir=output_dir.as_posix(),
        launch_values=launch_values,
    )


def write_command_plan(job: ReplayJob, evidence_dir: Path) -> None:
    target = evidence_dir / "commands" / f"paramset_{job.paramset}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(job), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classify_run(
    returncode: int | None, timed_out: bool, output_files: list[str], stderr: str
) -> str:
    if timed_out:
        return "timed_out"
    if returncode is None:
        return "execution_failed" if stderr else "not_executed"
    if returncode != 0:
        if "Unable to open" in stderr:
            return "missing_runtime_input"
        return "nonzero_exit"
    return "completed_with_outputs" if output_files else "completed_without_outputs"


def compact_output_summary(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    return {
        "root": summary.get("root"),
        "file_count": len(summary.get("files", [])),
        "main_csv": summary.get("main_csv"),
        "rows": summary.get("rows"),
        "final_time": summary.get("final_time"),
        "total_incidence": summary.get("total_incidence"),
        "max_infectious": summary.get("max_infectious"),
        "final_susceptible": summary.get("final_susceptible"),
        "warnings": summary.get("warnings", []),
    }


def run_job(job: ReplayJob, workdir: Path, *, timeout: float | None) -> dict[str, Any]:
    run_dir = workdir / "runs" / f"paramset_{job.paramset}"
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    env = os.environ.copy()
    env.update(job.environment)
    start = time.monotonic()
    stdout = ""
    stderr = ""
    returncode = None
    timed_out = False
    try:
        proc = subprocess.run(
            job.command,
            cwd=job.cwd,
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
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode()
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode()
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    output_files = sorted(path.as_posix() for path in Path(job.output_dir).rglob("*.csv"))
    try:
        summary = read_results(job.output_dir).summary if output_files else None
    except Exception:
        summary = None
    payload = {
        "ok": classify_run(returncode, timed_out, output_files, stderr) == "completed_with_outputs",
        "classification": classify_run(returncode, timed_out, output_files, stderr),
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": time.monotonic() - start,
        "cwd": job.cwd,
        "command": job.command,
        "shell_command": job.shell_command,
        "environment": job.environment,
        "output_dir": job.output_dir,
        "output_file_count": len(output_files),
        "output_summary": compact_output_summary(summary),
        "stdout_tail": stdout.splitlines()[-40:],
        "stderr_tail": stderr.splitlines()[-40:],
    }
    metadata_path = run_dir / "run_metadata.json"
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_existing_run_summary(
    workdir: Path, evidence_dir: Path, *, paramset: int
) -> dict[str, Any] | None:
    metadata_path = workdir / "runs" / f"paramset_{paramset}" / "run_metadata.json"
    if not metadata_path.is_file():
        return None
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    target = evidence_dir / "run_metadata" / f"paramset_{paramset}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def write_run_summary(
    payload: dict[str, Any], evidence_dir: Path, *, paramset: int
) -> dict[str, Any]:
    target = evidence_dir / "run_metadata" / f"paramset_{paramset}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def choose_delimiter(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        line = handle.readline()
    return "\t" if line.count("\t") > line.count(",") else ","


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return [row for row in csv.reader(handle, delimiter=choose_delimiter(path))]


def _as_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except ValueError:
        return None


def _looks_like_header(row: list[str]) -> bool:
    return bool(row) and any(_as_float(cell) is None for cell in row)


def _difference(
    row: int, column: int, reference: str | None, generated: str | None
) -> dict[str, Any]:
    return {"row": row, "column": column, "reference": reference, "generated": generated}


def compare_csv_values(reference: Path, generated: Path, *, tolerance: float) -> CsvValueComparison:
    try:
        reference_rows = read_csv_rows(reference)
        generated_rows = read_csv_rows(generated)
    except Exception as exc:
        return CsvValueComparison("unreadable_csv", False, 0, 0, diagnostics=[str(exc)])
    reference_has_header = bool(reference_rows) and _looks_like_header(reference_rows[0])
    generated_has_header = bool(generated_rows) and _looks_like_header(generated_rows[0])
    if reference_has_header != generated_has_header:
        return CsvValueComparison(
            "schema_mismatch",
            False,
            max(len(reference_rows) - int(reference_has_header), 0),
            max(len(generated_rows) - int(generated_has_header), 0),
        )
    if reference_has_header and reference_rows[0] != generated_rows[0]:
        return CsvValueComparison(
            "schema_mismatch",
            False,
            len(reference_rows) - 1,
            len(generated_rows) - 1,
            first_difference=_difference(
                0, 0, ",".join(reference_rows[0]), ",".join(generated_rows[0])
            ),
        )
    reference_data = reference_rows[1:] if reference_has_header else reference_rows
    generated_data = generated_rows[1:] if generated_has_header else generated_rows
    if len(reference_data) != len(generated_data):
        return CsvValueComparison(
            "row_count_mismatch",
            False,
            len(reference_data),
            len(generated_data),
        )
    max_abs_diff: float | None = None
    for row_index, (reference_row, generated_row) in enumerate(
        zip(reference_data, generated_data, strict=True)
    ):
        if len(reference_row) != len(generated_row):
            return CsvValueComparison(
                "schema_mismatch",
                False,
                len(reference_data),
                len(generated_data),
                first_difference=_difference(
                    row_index, len(reference_row), str(len(reference_row)), str(len(generated_row))
                ),
            )
        for column_index, (reference_cell, generated_cell) in enumerate(
            zip_longest(reference_row, generated_row)
        ):
            if reference_cell is None or generated_cell is None:
                return CsvValueComparison(
                    "schema_mismatch",
                    False,
                    len(reference_data),
                    len(generated_data),
                    first_difference=_difference(
                        row_index, column_index, reference_cell, generated_cell
                    ),
                )
            reference_float = _as_float(reference_cell)
            generated_float = _as_float(generated_cell)
            if reference_float is not None and generated_float is not None:
                abs_diff = abs(reference_float - generated_float)
                max_abs_diff = abs_diff if max_abs_diff is None else max(max_abs_diff, abs_diff)
                if abs_diff > tolerance:
                    diff = _difference(
                        row_index + int(reference_has_header),
                        column_index,
                        reference_cell,
                        generated_cell,
                    )
                    diff["abs_diff"] = abs_diff
                    return CsvValueComparison(
                        "numeric_mismatch",
                        False,
                        len(reference_data),
                        len(generated_data),
                        max_abs_diff=max_abs_diff,
                        first_difference=diff,
                    )
            elif reference_cell.strip() != generated_cell.strip():
                return CsvValueComparison(
                    "value_mismatch",
                    False,
                    len(reference_data),
                    len(generated_data),
                    max_abs_diff=max_abs_diff,
                    first_difference=_difference(
                        row_index, column_index, reference_cell, generated_cell
                    ),
                )
    return CsvValueComparison(
        "numeric_equivalent",
        True,
        len(reference_data),
        len(generated_data),
        max_abs_diff=max_abs_diff,
    )


def compare_output_file(
    reference: Path, generated: Path | None, *, tolerance: float
) -> FileComparison:
    reference_sha = sha256_file(reference)
    if generated is None or not generated.is_file():
        return FileComparison(
            reference.name, "missing_generated", False, False, reference_sha, None
        )
    generated_sha = sha256_file(generated)
    if reference_sha == generated_sha:
        values = compare_csv_values(reference, generated, tolerance=tolerance)
        return FileComparison(
            reference.name,
            "byte_identical",
            True,
            True,
            reference_sha,
            generated_sha,
            values.row_count_reference,
            values.row_count_generated,
            0.0,
        )
    values = compare_csv_values(reference, generated, tolerance=tolerance)
    return FileComparison(
        reference.name,
        values.status,
        False,
        values.numeric_equivalent,
        reference_sha,
        generated_sha,
        values.row_count_reference,
        values.row_count_generated,
        values.max_abs_diff,
        values.first_difference,
        values.diagnostics,
    )


def compare_paramset_outputs(
    reference_dir: Path, generated_dir: Path, *, paramset: int, tolerance: float
) -> dict[str, Any]:
    reference_files = {
        path.name: path for path in sorted(reference_dir.glob(f"paramset_{paramset}.*.csv"))
    }
    generated_files = {
        path.name: path for path in sorted(generated_dir.glob(f"paramset_{paramset}.*.csv"))
    }
    comparisons = [
        compare_output_file(reference, generated_files.get(name), tolerance=tolerance)
        for name, reference in reference_files.items()
    ]
    status_counts = Counter(item.status for item in comparisons)
    mismatch_statuses = {
        "missing_generated",
        "schema_mismatch",
        "row_count_mismatch",
        "numeric_mismatch",
        "value_mismatch",
        "unreadable_csv",
    }
    return {
        "paramset": paramset,
        "reference_dir": reference_dir.as_posix(),
        "generated_dir": generated_dir.as_posix(),
        "files_expected": len(reference_files),
        "files_generated": len(generated_files),
        "extra_generated_files": sorted(set(generated_files) - set(reference_files)),
        "missing_files": [
            item.filename for item in comparisons if item.status == "missing_generated"
        ],
        "byte_identical_count": status_counts["byte_identical"],
        "numeric_equivalent_count": sum(1 for item in comparisons if item.numeric_equivalent),
        "mismatch_count": sum(1 for item in comparisons if item.status in mismatch_statuses),
        "status_counts": dict(sorted(status_counts.items())),
        "comparisons": [item.to_dict() for item in comparisons],
    }


def paramset_output_name(paramset: int, realisation: int, suffix: str) -> str:
    return f"paramset_{paramset}.{realisation}{suffix}.csv"


def copy_selected_evidence(
    reference_dir: Path, generated_root: Path, evidence_dir: Path, *, paramsets: list[int]
) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for paramset in paramsets:
        generated_dir = generated_root / f"paramset_{paramset}"
        for realisation in SELECTED_REALISATIONS:
            for suffix in OUTPUT_SUFFIXES:
                name = paramset_output_name(paramset, realisation, suffix)
                for label, source_dir in (
                    ("reference", reference_dir),
                    ("generated", generated_dir),
                ):
                    source = source_dir / name
                    if not source.is_file():
                        continue
                    target = evidence_dir / "output_subset" / label / f"paramset_{paramset}" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    copied.append(
                        {"kind": label, "target": target.as_posix(), "sha256": sha256_file(target)}
                    )
    return copied


def _run_completed(item: dict[str, Any], *, skip_run: bool) -> bool:
    if skip_run and item.get("run") is None:
        return True
    run = item.get("run")
    return run is not None and run["classification"] == "completed_with_outputs"


def _coverage_ok(item: dict[str, Any]) -> bool:
    comparison = item["comparison"]
    return (
        not comparison["missing_files"]
        and not comparison["extra_generated_files"]
        and comparison["files_expected"] == comparison["files_generated"]
    )


def _overall_status(paramsets: list[dict[str, Any]], *, skip_run: bool) -> str:
    if not all(_run_completed(item, skip_run=skip_run) for item in paramsets):
        return "run_failure"
    if not all(_coverage_ok(item) for item in paramsets):
        return "coverage_mismatch"
    if any(item["comparison"]["mismatch_count"] for item in paramsets):
        return "completed_with_mismatches"
    return "ok"


def write_summary_markdown(summary: dict[str, Any], target: Path) -> None:
    lines = [
        "# Ebola2 Replay Comparison",
        "",
        f"- Created UTC: `{summary['created_utc']}`",
        f"- Zip: `{summary['zip']}`",
        f"- Workdir: `{summary['workdir']}`",
        f"- Bundle root: `{summary['bundle_root']}`",
        f"- Threads: `{summary['threads']}`",
        f"- Tolerance: `{summary['tolerance']}`",
        f"- Overall status: `{summary['overall_status']}`",
        "",
        "## Paramsets",
        "",
        "| Paramset | Run classification | Expected | Generated | Byte-identical | "
        "Numeric-equivalent | Mismatches |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for item in summary["paramsets"]:
        comparison = item["comparison"]
        run = item.get("run")
        classification = "skipped" if run is None else run["classification"]
        lines.append(
            f"| {item['paramset']} | `{classification}` | {comparison['files_expected']} | "
            f"{comparison['files_generated']} | {comparison['byte_identical_count']} | "
            f"{comparison['numeric_equivalent_count']} | {comparison['mismatch_count']} |"
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_replay(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    zip_path = args.zip_path.resolve()
    workdir = args.workdir.resolve()
    evidence_dir = args.evidence_dir.resolve()
    extracted_root = safe_extract_zip(zip_path, workdir / "extracted")
    bundle_root = find_ebola_dir(extracted_root)
    if bundle_root is None:
        raise FileNotFoundError(f"could not find Ebola2 bundle root under {extracted_root}")
    bundle_root = bundle_root.resolve()
    reference_dir = bundle_root / REFERENCE_OUTPUT_REL
    if not reference_dir.is_dir():
        raise FileNotFoundError(f"reference output directory was not found: {reference_dir}")
    clean_evidence_dir(evidence_dir)
    generated_root = workdir / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    executable = resolve_executable(args.exe).as_posix()
    paramset_payloads: list[dict[str, Any]] = []
    for paramset in args.paramsets:
        generated_dir = generated_root / f"paramset_{paramset}"
        if not args.skip_run and generated_dir.exists():
            shutil.rmtree(generated_dir)
        job = build_job(
            bundle_root,
            generated_root,
            paramset=paramset,
            executable=executable,
            threads=args.threads,
        )
        write_command_plan(job, evidence_dir)
        if args.skip_run:
            run_payload = load_existing_run_summary(workdir, evidence_dir, paramset=paramset)
        else:
            run_payload = write_run_summary(
                run_job(job, workdir, timeout=args.timeout), evidence_dir, paramset=paramset
            )
        comparison = compare_paramset_outputs(
            reference_dir, generated_dir, paramset=paramset, tolerance=args.tolerance
        )
        paramset_payloads.append(
            {
                "paramset": paramset,
                "command_plan": (
                    evidence_dir / "commands" / f"paramset_{paramset}.json"
                ).as_posix(),
                "run": run_payload,
                "comparison": comparison,
            }
        )
    copied = copy_selected_evidence(
        reference_dir, generated_root, evidence_dir, paramsets=list(args.paramsets)
    )
    overall_status = _overall_status(paramset_payloads, skip_run=args.skip_run)
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "elapsed_seconds": time.monotonic() - started,
        "overall_status": overall_status,
        "zip": zip_path.as_posix(),
        "zip_sha256": sha256_file(zip_path),
        "workdir": workdir.as_posix(),
        "evidence_dir": evidence_dir.as_posix(),
        "bundle_root": bundle_root.as_posix(),
        "reference_dir": reference_dir.as_posix(),
        "generated_root": generated_root.as_posix(),
        "paramsets_requested": list(args.paramsets),
        "threads": args.threads,
        "tolerance": args.tolerance,
        "skip_run": args.skip_run,
        "executable": executable,
        "selected_evidence_files": copied,
        "paramsets": paramset_payloads,
    }
    json_target = evidence_dir / "comparison_summary.json"
    json_target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_summary_markdown(summary, evidence_dir / "comparison_summary.md")
    return summary


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_replay(args)
    except Exception as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"overall_status": summary["overall_status"]}, sort_keys=True))
    if summary["overall_status"] == "ok":
        return 0
    if summary["overall_status"] == "completed_with_mismatches":
        return 1 if args.fail_on_mismatch else 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
