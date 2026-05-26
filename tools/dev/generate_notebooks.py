#!/usr/bin/env python3
"""Write the project documentation notebooks.

The notebooks are intentionally generated from plain Python data so they remain
reviewable and deterministic despite the verbose ``.ipynb`` JSON format.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

KERNEL_METADATA = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "pygments_lexer": "ipython3"},
}


def md(source: str) -> dict[str, Any]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": textwrap.dedent(source).strip() + "\n",
    }


def code(source: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": textwrap.dedent(source).strip() + "\n",
    }


def notebook(cells: list[dict[str, Any]]) -> dict[str, Any]:
    for index, cell in enumerate(cells, start=1):
        cell["id"] = f"cell-{index:03d}"
    return {"cells": cells, "metadata": KERNEL_METADATA, "nbformat": 4, "nbformat_minor": 5}


def write_notebook(path: Path, cells: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notebook(cells), indent=2) + "\n", encoding="utf-8")


def getting_started() -> list[dict[str, Any]]:
    return [
        md(
            """
            # Getting started

            `ebolasim` is a Python interface to the EbolaSim C model. The
            workflow is deliberately small: create a parameter file using the
            exact names accepted by the C model, create a `Sim`, run it, and
            read or plot the outputs.

            The examples below use a synthetic demo population. Release wheels
            for Linux x86_64 can include the compiled executable. Source
            checkouts without a bundled executable can still create parameters
            and cluster commands.
            """
        ),
        code(
            """
            import ebolasim as es

            pars = es.demo_pars().set({
                "Population size": 2400,
                "Number of realisations": 20,
                "Sampling time": 90,
                "Reproduction number": 1.6,
                "Initial number of infecteds": 1,
                "Output incidence by administrative unit": 1,
                "Output age file": 1,
            })

            {
                "parameters": len(pars.raw),
                "population": pars.raw["Population size"],
                "realisations": pars.raw["Number of realisations"],
                "days": pars.raw["Sampling time"],
                "r0": pars.raw["Reproduction number"],
            }
            """
        ),
        md(
            """
            The object is still a faithful C-model parameter file. Writing it
            creates the bracketed text format read by `ReadParams()` upstream.
            """
        ),
        code(
            """
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmp:
                path = pars.write(Path(tmp) / "parameters.txt")
                print(path.read_text(encoding="utf-8").splitlines()[:12])
            """
        ),
        md(
            """
            A small smoke run is useful for local checks and CI. If the current
            environment does not have a bundled executable, this cell still
            shows the exact command that would be submitted to a cluster.
            """
        ),
        code(
            """
            smoke_pars = es.demo_pars({
                "Population size": 24,
                "Number of realisations": 1,
                "Sampling time": 7,
                "Reproduction number": 1.6,
            })

            with tempfile.TemporaryDirectory() as tmp:
                smoke = es.Sim(
                    smoke_pars,
                    label="smoke",
                    outdir=Path(tmp) / "notebook-smoke",
                    threads=1,
                )
                executable = es.resolve_executable(required=False)

                if executable is None:
                    plan = smoke.command()
                    print("No bundled executable is installed in this environment.")
                    print(plan.shell_command)
                    summary = None
                else:
                    smoke.run(timeout=30)
                    summary = smoke.summary

            summary
            """
        ),
        code(
            """
            if smoke.results is None:
                print("Plot skipped because the model executable was not available.")
            else:
                smoke.plot(y="I")
            """
        ),
        md(
            """
            Scenario comparisons use ordinary parameter copies. The important
            habit is that all names remain exact C-model names.
            """
        ),
        code(
            """
            higher_r0_pars = pars.copy().set({
                "Reproduction number": 2.0,
                "Include contact tracing": 1,
            })

            with tempfile.TemporaryDirectory() as tmp:
                run_root = Path(tmp)
                baseline = es.Sim(pars, label="baseline", outdir=run_root / "baseline", threads=4)
                higher_r0 = es.Sim(
                    higher_r0_pars,
                    label="higher_r0",
                    outdir=run_root / "higher_r0",
                    threads=4,
                )
                commands = [baseline.command().shell_command, higher_r0.command().shell_command]

            commands
            """
        ),
    ]


def parameters() -> list[dict[str, Any]]:
    return [
        md(
            """
            # Parameters

            EbolaSim parameter files use exact bracketed names. This package
            does not rename them: the strings shown here are the names searched
            for by the upstream C model in `ReadParams()`.

            Some parameters are always required when the relevant code path is
            reached. Others are optional and have defaults assigned by the C
            code. The reference table is generated from the pinned upstream
            source after the package patch set has been applied.
            """
        ),
        code(
            """
            import collections
            import ebolasim as es

            reference = es.parameter_reference()
            counts = collections.Counter(row.category for row in reference)
            {
                "parameter_count": len(reference),
                "required_when_read": sum(row.required for row in reference),
                "categories": dict(sorted(counts.items())),
            }
            """
        ),
        md(
            """
            Start from `demo_pars()` for a runnable synthetic example, then set
            exact names with a dictionary.
            """
        ),
        code(
            """
            pars = es.demo_pars().set({
                "Population size": 2400,
                "Number of realisations": 20,
                "Sampling time": 90,
                "Reproduction number": 1.6,
                "Include contact tracing": 1,
                "Contact tracing start time": 21,
                "Do geographic vaccination": 1,
                "Vaccination start time": 30,
                "Proportion of population vaccinated": 0.25,
            })

            {name: pars.raw[name] for name in [
                "Population size",
                "Number of realisations",
                "Sampling time",
                "Reproduction number",
                "Include contact tracing",
                "Do geographic vaccination",
                "Proportion of population vaccinated",
            ]}
            """
        ),
        md(
            """
            ## Complete Reference

            The descriptions are conservative summaries derived from the
            upstream parameter names and grouped by subsystem. The exact name,
            type, required/default status, and source line are the auditable
            parts to use when editing parameter files.
            """
        ),
        code(
            """
            from IPython.display import Markdown
            from ebolasim.parameters import parameter_reference_markdown

            Markdown(parameter_reference_markdown())
            """
        ),
    ]


def maintainers() -> list[dict[str, Any]]:
    return [
        md(
            """
            # Maintainers

            Release wheels can include a Linux x86_64 executable built from the
            pinned upstream C model. The public user workflow is Python-first;
            this notebook explains the maintainer machinery that makes the
            bundled executable auditable.
            """
        ),
        code(
            """
            from ebolasim.build import detect_platform_id, read_patch_inventory, read_source_lock

            lock = read_source_lock()
            patches = read_patch_inventory()
            {
                "platform_id": detect_platform_id(),
                "lock_placeholder": lock.is_placeholder,
                "repository": lock.repository,
                "ref_type": lock.ref_type,
                "ref": lock.ref,
                "patches": [patch["file"] for patch in patches.to_dict()["patches"]],
            }
            """
        ),
        md(
            """
            ## The CI Pipeline In Package Functions

            The release pipeline repeats these steps:

            1. `read_source_lock()` reads `model-src/upstream.lock.yml`.
            2. `fetch_source()` downloads the pinned archive and verifies SHA256.
            3. `apply_patches()` applies the patch inventory in order.
            4. `build_executable()` compiles `ebola-spatial-linux`.
            5. `ebolasim.Sim(...).run()` performs a small smoke simulation.
            6. `bundle_executable()` stages the binary inside `src/ebolasim/_bundled/linux-x86_64/`.
            7. `tools/ci/build_release_bundle.py` writes metadata, checksums,
               and a separate GitHub release bundle.

            Run the same path locally with uv:
            """
        ),
        code(
            """
            commands = [
                "uv sync --extra dev --extra docs --extra plot",
                "uv run ebolasim source show --pretty",
                "uv run ebolasim source fetch --out build/upstream --pretty",
                "uv run ebolasim source build "
                "build/upstream/extract/ebolasim_public-... "
                "--out build/linux --overwrite",
                "uv run python tools/ci/build_release_bundle.py "
                "--overwrite --package-root src/ebolasim",
                "uv build",
            ]
            print("\\n".join(commands))
            """
        ),
        md(
            """
            ## Updating The Source Lock

            Keep both lock files synchronized:

            - `model-src/upstream.lock.yml`
            - `src/ebolasim/_patches/upstream.lock.yml`

            Record the upstream repository URL, exact commit or tag, archive
            URL, SHA256 command output, reason for selecting the ref, CI bundle
            artifact review, and a fresh wheel install smoke run.

            A release tag must be `vX.Y.Z` and match both `pyproject.toml` and
            `ebolasim.__version__`.
            """
        ),
    ]


def ebola2() -> list[dict[str, Any]]:
    return [
        md(
            """
            # Ebola2 validation

            This notebook documents a replay of `ignore/Ebola2.zip`, a local
            reference bundle containing input files, batch launch files, and
            previous EbolaSim outputs for a single-administrative-unit North
            Kivu run.

            The zip is intentionally not committed. The committed evidence in
            `docs/vignettes/ebola2/evidence` records how paramsets 1 and 2 were
            rerun with this package, compares all 10,000 reference CSVs, and
            stores a compact subset of reference/generated files for review.
            """
        ),
        code(
            """
            from collections import Counter
            import csv
            import importlib.util
            import json
            import os
            from pathlib import Path
            import sys

            import matplotlib.pyplot as plt

            def find_repo_root(start=None):
                start = Path.cwd() if start is None else Path(start)
                for candidate in [start, *start.parents]:
                    if (candidate / "pyproject.toml").is_file():
                        return candidate
                raise RuntimeError("could not locate repository root")

            ROOT = find_repo_root()
            EVIDENCE = ROOT / "docs/vignettes/ebola2/evidence"
            REPLAY_PATH = ROOT / "docs/vignettes/ebola2/replay_ebola2.py"
            spec = importlib.util.spec_from_file_location("ebola2_replay_notebook", REPLAY_PATH)
            replay = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = replay
            spec.loader.exec_module(replay)

            summary = json.loads((EVIDENCE / "comparison_summary.json").read_text(encoding="utf-8"))
            {
                "overall_status": summary["overall_status"],
                "paramsets": summary["paramsets_requested"],
                "reference_files_checked": sum(
                    item["comparison"]["files_expected"]
                    for item in summary["paramsets"]
                ),
                "mismatches": sum(
                    item["comparison"]["mismatch_count"]
                    for item in summary["paramsets"]
                ),
            }
            """
        ),
        md(
            """
            When `ignore/Ebola2.zip` is present, the replay script extracts it
            into an ignored work directory, reads the Windows batch files, and
            rewrites only the output paths so reference outputs are never
            overwritten.
            """
        ),
        code(
            """
            zip_path = ROOT / "ignore/Ebola2.zip"
            if zip_path.is_file():
                extracted = replay.safe_extract_zip(
                    zip_path,
                    ROOT / "artifacts/ebola2-notebook/extracted",
                )
                bundle_root = replay.find_ebola_dir(extracted)
                print(f"Bundle root: {bundle_root}")
                batch_files = sorted(
                    path.relative_to(bundle_root)
                    for path in bundle_root.rglob("*.bat")
                )
                print("Batch files:")
                for path in batch_files:
                    print(f"  {path}")
            else:
                print(
                    "ignore/Ebola2.zip is not present in this environment; "
                    "using committed evidence."
                )
            """
        ),
        md(
            """
            The generated command plans preserve `/P`, `/PP`, `/D`, `/S`, `/R`,
            `/CLP1..13`, the four seeds, and `OMP_NUM_THREADS`. The only
            intentional rewrite is `/O`, which points to an ignored generated
            output directory.
            """
        ),
        code(
            """
            command_plans = []
            for paramset in (1, 2):
                path = EVIDENCE / "commands" / f"paramset_{paramset}.json"
                command_plans.append(json.loads(path.read_text(encoding="utf-8")))

            [
                {
                    "paramset": plan["paramset"],
                    "threads": plan["environment"]["OMP_NUM_THREADS"],
                    "r_scale": next(arg for arg in plan["command"] if arg.startswith("/R:")),
                    "first_clp": next(arg for arg in plan["command"] if arg.startswith("/CLP1:")),
                    "last_clp": next(arg for arg in plan["command"] if arg.startswith("/CLP13:")),
                    "seeds": plan["command"][-4:],
                }
                for plan in command_plans
            ]
            """
        ),
        md(
            """
            The full comparison report checks every expected CSV. The subset
            below recomputes direct byte/numeric comparisons for committed
            reference/generated pairs: realisations 0 and 999, all five output
            file types, for paramsets 1 and 2.
            """
        ),
        code(
            """
            subset_rows = []
            for paramset in (1, 2):
                for realisation in replay.SELECTED_REALISATIONS:
                    for suffix in replay.OUTPUT_SUFFIXES:
                        filename = replay.paramset_output_name(paramset, realisation, suffix)
                        reference = (
                            EVIDENCE
                            / "output_subset/reference"
                            / f"paramset_{paramset}"
                            / filename
                        )
                        generated = (
                            EVIDENCE
                            / "output_subset/generated"
                            / f"paramset_{paramset}"
                            / filename
                        )
                        comparison = replay.compare_output_file(
                            reference,
                            generated,
                            tolerance=1e-9,
                        )
                        subset_rows.append(comparison.to_dict())

            Counter(row["status"] for row in subset_rows)
            """
        ),
        code(
            """
            def read_series(path, x="t", y="incI"):
                with Path(path).open("r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle)
                    rows = list(reader)
                return [float(row[x]) for row in rows], [float(row[y]) for row in rows]

            fig, ax = plt.subplots(figsize=(8, 4))
            for paramset in (1, 2):
                for kind, style in (("reference", "-"), ("generated", "--")):
                    path = (
                        EVIDENCE
                        / f"output_subset/{kind}"
                        / f"paramset_{paramset}"
                        / f"paramset_{paramset}.0.csv"
                    )
                    t, inc = read_series(path, y="incI")
                    ax.plot(t, inc, style, label=f"paramset {paramset} {kind}")

            ax.set_xlabel("Day")
            ax.set_ylabel("Incident infections")
            ax.legend()
            fig.tight_layout()
            fig
            """
        ),
        md(
            """
            To rerun the full validation locally, provide the zip and opt in to
            the slow replay. This is deliberately not a default CI step.
            """
        ),
        code(
            """
            if os.environ.get("EBOLASIM_RUN_EBOLA2") == "1" and zip_path.is_file():
                exit_code = replay.main([
                    "--zip", zip_path.as_posix(),
                    "--workdir", (ROOT / "artifacts/ebola2-replay").as_posix(),
                    "--evidence-dir", EVIDENCE.as_posix(),
                    "--paramsets", "1", "2",
                    "--threads", "4",
                ])
                print(f"Replay exit code: {exit_code}")
            else:
                print(
                    "Full replay skipped. Set EBOLASIM_RUN_EBOLA2=1 "
                    "and provide ignore/Ebola2.zip."
                )
            """
        ),
    ]


def main() -> int:
    docs = Path("docs")
    write_notebook(docs / "index.ipynb", getting_started())
    write_notebook(docs / "parameters.ipynb", parameters())
    write_notebook(docs / "maintainers.ipynb", maintainers())
    write_notebook(docs / "vignettes/ebola2/comparison.ipynb", ebola2())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
