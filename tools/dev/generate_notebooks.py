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
            Use these exact C parameter file keys when calling `Pars.set()` or
            editing a parameter file; they are not Python aliases.

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
            upstream parameter names and grouped by subsystem. The exact C
            parameter file key is what appears inside square brackets in a
            parameter file. The C target shows the upstream variable populated
            by that key where it could be extracted from `ReadParams()`.
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


def sadv() -> list[dict[str, Any]]:
    return [
        md(
            """
            # Single admin unit validation

            This notebook validates the package against a full single
            administrative unit EbolaSim run, not the tiny synthetic demo data.
            The reference scenario contains 900,000 individuals and was run
            with the public `mrc-ide/ebolasim_public` codebase, the associated
            input parameter files, demography/population input, and network
            input from `ignore/Ebola2.zip`.

            The zip is intentionally not committed. The committed evidence in
            `docs/vignettes/sadv/evidence` includes command metadata, a
            comparison summary, and selected reference/generated outputs for
            paramsets 1 and 2. That lets the docs and tests compare package
            output against the reference run without putting the full private
            bundle in git.
            """
        ),
        code(
            """
            import csv
            import importlib.util
            import json
            import os
            import sys
            from collections import Counter
            from pathlib import Path

            import matplotlib.pyplot as plt

            from ebolasim import read_results, resolve_executable
            from ebolasim_tools.command import build_command_plan
            from ebolasim_tools.manifest import (
                ManifestInputs,
                ManifestModelArgs,
                ManifestOutputs,
                ManifestSource,
                RunManifest,
            )
            from ebolasim_tools.run import run_model

            def find_repo_root(start=None):
                start = Path.cwd() if start is None else Path(start)
                for candidate in [start, *start.parents]:
                    if (candidate / "pyproject.toml").is_file():
                        return candidate
                raise RuntimeError("could not locate repository root")

            ROOT = find_repo_root()
            EVIDENCE = ROOT / "docs/vignettes/sadv/evidence"
            REPLAY_PATH = ROOT / "docs/vignettes/sadv/replay_sadv.py"
            spec = importlib.util.spec_from_file_location("sadv_replay_notebook", REPLAY_PATH)
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
            The original run is described by Windows batch files in the zip.
            The replay reads those files, preserves `/P`, `/PP`, `/D`, `/S`,
            `/R`, `/CLP1..13`, the four random seeds, and `OMP_NUM_THREADS`,
            and rewrites only `/O` so reference outputs are never overwritten.
            """
        ),
        code(
            """
            zip_path = ROOT / "ignore/Ebola2.zip"
            bundle_root = None
            if zip_path.is_file():
                extracted = replay.safe_extract_zip(
                    zip_path,
                    ROOT / "artifacts/sadv-notebook/extracted",
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
            The two committed paramsets differ only in the reproduction-number
            scale passed to `/R`: paramset 1 uses `1.17`, and paramset 2 uses
            `1`. Both use the same parameter file placeholders, CLP launch
            substitutions, and random seeds.
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
            The CLP values replace `#1..#13` placeholders in the parameter
            file. They control the operational scenario layered on top of the
            fixed demography and network inputs.

            | Placeholder | Meaning |
            |---|---|
            | `#1` | ETU bed capacity values |
            | `#2` | Contact tracing capacity values |
            | `#3` | Detected cases required to trigger outbreak alert |
            | `#4` | Mean detection delay |
            | `#5..#10` | Vaccine delivery capacity, stock, and timing values |
            | `#11` | Burial capacity values |
            | `#12` | Pre-outbreak HCW/FLW vaccination proportion |
            | `#13` | Relative susceptibility of vaccinated HCWs/FLWs |
            """
        ),
        md(
            """
            A user-facing package workflow does not need to parse the batch
            files directly once these inputs are known. Build a `RunManifest`
            that points at the real C-model input files, turn it into a command
            plan for inspection, then call `run_model()` and read the outputs.
            """
        ),
        code(
            """
            PARAMETER_FILE = "Ervebo/Gavi/Data/p_R1.80_NordKivu_HCWring_midAccept.txt"
            PREPARAMETER_FILE = "Ervebo/Gavi/Data/preFPNordKivu_HCWring_singleAdUnit.txt"
            DENSITY_FILE = "Ervebo/Populations/NordKivu_MSF_LS2018.bin"
            NETWORK_FILE = "Ervebo/Populations/NordKivu_MSF_Network_HCW_singleAdUnt.bin"
            SEEDS = [98798150, 729101, 17389101, 4797132]

            def manifest_for_paramset(paramset, root, output_root):
                plan = next(item for item in command_plans if item["paramset"] == paramset)
                launch_values = plan["launch_values"]
                output_dir = Path(output_root) / f"paramset_{paramset}"
                return RunManifest(
                    inputs=ManifestInputs(
                        parameter_file=PARAMETER_FILE,
                        preparameter_file=PREPARAMETER_FILE,
                        density_file=DENSITY_FILE,
                        network_file=NETWORK_FILE,
                        network_mode="save",
                    ),
                    outputs=ManifestOutputs(
                        output_base=(output_dir / f"paramset_{paramset}").as_posix(),
                        output_dir=output_dir.as_posix(),
                    ),
                    paramset=paramset,
                    threads=4,
                    model_args=ManifestModelArgs(
                        r0_scale=launch_values[1],
                        clp={
                            index: value
                            for index, value in enumerate(launch_values[2:], start=1)
                        },
                    ),
                    seeds=SEEDS,
                    source=ManifestSource(
                        kind="single_admin_unit_validation",
                        bundle_root=Path(root).as_posix(),
                    ),
                    metadata={"source_bundle": "ignore/Ebola2.zip"},
                )

            example_root = bundle_root if bundle_root is not None else ROOT / "Ebola2"
            example_manifest = manifest_for_paramset(
                1,
                example_root,
                ROOT / "artifacts/sadv-package-run/generated",
            )
            example_plan = build_command_plan(
                example_manifest,
                executable=resolve_executable(required=False) or "ebola-spatial-linux",
                root=example_root,
                working_directory=example_root,
                threads=example_manifest.threads,
            )

            {
                "parameter_file": example_manifest.inputs.parameter_file,
                "density_file": example_manifest.inputs.density_file,
                "network_file": example_manifest.inputs.network_file,
                "r0_scale": example_manifest.model_args.r0_scale,
                "clp_count": len(example_manifest.model_args.clp),
                "seeds": example_manifest.seeds,
                "shell_command": example_plan.shell_command,
            }
            """
        ),
        code(
            """
            if os.environ.get("EBOLASIM_RUN_SADV") == "1" and bundle_root is not None:
                result = run_model(
                    example_manifest,
                    executable=resolve_executable(),
                    root=bundle_root,
                    run_dir=ROOT / "artifacts/sadv-package-run/logs/paramset_1",
                    timeout=120,
                    threads=example_manifest.threads,
                )
                results = read_results(result.output_dir)
                {
                    "classification": result.classification,
                    "output_files": len(result.output_files),
                    "summary": results.summary,
                }
            else:
                print(
                    "Package-run cell skipped. Set EBOLASIM_RUN_SADV=1 "
                    "and provide ignore/Ebola2.zip to execute it."
                )
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
            if os.environ.get("EBOLASIM_RUN_SADV") == "1" and zip_path.is_file():
                exit_code = replay.main([
                    "--zip", zip_path.as_posix(),
                    "--workdir", (ROOT / "artifacts/sadv-replay").as_posix(),
                    "--evidence-dir", EVIDENCE.as_posix(),
                    "--paramsets", "1", "2",
                    "--threads", "4",
                ])
                print(f"Replay exit code: {exit_code}")
            else:
                print(
                    "Full replay skipped. Set EBOLASIM_RUN_SADV=1 "
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
    write_notebook(docs / "vignettes/sadv/comparison.ipynb", sadv())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
