"""Command-line interface for the public ebolasim wrapper."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ._version import __version__
from .binary import inspect_density_header, inspect_network_header
from .build import build_model, inspect_source
from .command import build_command_plan
from .examples import write_tiny_example
from .manifest import read_manifest, validate_manifest
from .nordkivu import inspect_bundle, manifest_from_bundle
from .outputs import plot_output_timeseries, summarise_outputs
from .params import ParameterSet, tiny_parameter_set
from .patches import apply_patches, copy_source_tree, read_patch_inventory
from .run import run_model


def _print(payload: Any, *, pretty: bool = False) -> None:
    if hasattr(payload, "to_json"):
        print(payload.to_json(pretty=pretty))
    else:
        print(json.dumps(payload, indent=2 if pretty else None, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ebolasim",
        description="Build, configure, run and read the legacy ebolasim executable.",
    )
    parser.add_argument("--version", action="version", version=f"ebolasim-tools {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Print environment and package metadata.")
    health.add_argument("--pretty", action="store_true")

    patches = sub.add_parser("patches", help="Show bundled Linux source patches.")
    patches.add_argument("--patch-dir", type=Path)
    patches.add_argument("--pretty", action="store_true")

    patch = sub.add_parser(
        "patch-source", help="Copy a source tree and apply bundled Linux patches."
    )
    patch.add_argument("source_dir", type=Path)
    patch.add_argument("--out", required=True, type=Path)
    patch.add_argument("--patch-dir", type=Path)
    patch.add_argument("--overwrite", action="store_true")
    patch.add_argument("--pretty", action="store_true")

    build = sub.add_parser("build", help="Patch and compile the legacy source on Linux.")
    build.add_argument("source_dir", type=Path)
    build.add_argument("--out", required=True, type=Path, help="Build directory.")
    build.add_argument("--target", default="ebola-spatial-linux")
    build.add_argument("--country", default="COUNTRY_WA")
    build.add_argument("--compiler", default=None)
    build.add_argument("--standard", default="gnu++17")
    build.add_argument("--optimisation", default="-O2")
    build.add_argument("--no-openmp", action="store_true")
    build.add_argument("--no-patch", action="store_true")
    build.add_argument("--timeout", type=float, default=180)
    build.add_argument("--overwrite", action="store_true")
    build.add_argument("--pretty", action="store_true")

    inspect = sub.add_parser("inspect", help="Inspect source, bundle, density or network files.")
    inspect_sub = inspect.add_subparsers(dest="inspect_command", required=True)
    inspect_source_p = inspect_sub.add_parser("source", help="Inspect a legacy source tree.")
    inspect_source_p.add_argument("source_dir", type=Path)
    inspect_source_p.add_argument("--pretty", action="store_true")
    inspect_density = inspect_sub.add_parser("density", help="Inspect a density binary header.")
    inspect_density.add_argument("path", type=Path)
    inspect_density.add_argument("--pretty", action="store_true")
    inspect_network = inspect_sub.add_parser(
        "network", help="Inspect a saved-network binary header."
    )
    inspect_network.add_argument("path", type=Path)
    inspect_network.add_argument("--pretty", action="store_true")
    inspect_bundle_p = inspect_sub.add_parser("bundle", help="Inspect a Nord Kivu-style bundle.")
    inspect_bundle_p.add_argument("root", type=Path)
    inspect_bundle_p.add_argument("--pretty", action="store_true")

    example = sub.add_parser("example", help="Write example input bundles.")
    example_sub = example.add_subparsers(dest="example_command", required=True)
    tiny = example_sub.add_parser("tiny", help="Write the TinyDistrict example.")
    tiny.add_argument("out", type=Path)
    tiny.add_argument("--overwrite", action="store_true")
    tiny.add_argument("--pretty", action="store_true")

    params = sub.add_parser("params", help="Read and write legacy parameter files.")
    params_sub = params.add_subparsers(dest="params_command", required=True)
    params_show = params_sub.add_parser("show", help="Read a parameter file as JSON.")
    params_show.add_argument("path", type=Path)
    params_show.add_argument("--pretty", action="store_true")
    params_tiny = params_sub.add_parser("tiny", help="Write a default tiny parameter file.")
    params_tiny.add_argument("out", type=Path)
    params_tiny.add_argument("--population", type=int, default=24)
    params_tiny.add_argument("--sampling-time", type=int, default=7)
    params_tiny.add_argument("--realisations", type=int, default=1)
    params_tiny.add_argument("--pretty", action="store_true")
    params_set = params_sub.add_parser("set", help="Set one parameter and write a new file.")
    params_set.add_argument("path", type=Path)
    params_set.add_argument("name")
    params_set.add_argument("value")
    params_set.add_argument("--out", required=True, type=Path)
    params_set.add_argument("--pretty", action="store_true")

    manifest = sub.add_parser("manifest", help="Read, validate or create manifests.")
    manifest_sub = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_show = manifest_sub.add_parser("show", help="Print a manifest.")
    manifest_show.add_argument("path", type=Path)
    manifest_show.add_argument("--json", action="store_true")
    manifest_show.add_argument("--pretty", action="store_true")
    manifest_validate = manifest_sub.add_parser("validate", help="Validate a manifest.")
    manifest_validate.add_argument("path", type=Path)
    manifest_validate.add_argument("--pretty", action="store_true")
    manifest_nk = manifest_sub.add_parser(
        "from-nordkivu", help="Create a best-effort manifest from a Nord Kivu bundle."
    )
    manifest_nk.add_argument("root", type=Path)
    manifest_nk.add_argument("--paramset", type=int, default=188)
    manifest_nk.add_argument("--out", required=True, type=Path)
    manifest_nk.add_argument("--threads", type=int, default=1)
    manifest_nk.add_argument("--executable", default="ebola-spatial-linux")
    manifest_nk.add_argument("--pretty", action="store_true")

    command = sub.add_parser("command", help="Build the concrete legacy argv from a manifest.")
    command.add_argument("manifest", type=Path)
    command.add_argument("--exe", type=Path)
    command.add_argument("--root", type=Path)
    command.add_argument("--threads", type=int)
    command.add_argument("--pretty", action="store_true")

    run = sub.add_parser("run", help="Run the legacy executable from a manifest.")
    run.add_argument("manifest", type=Path)
    run.add_argument("--exe", required=True, type=Path)
    run.add_argument("--root", type=Path)
    run.add_argument("--out", required=True, type=Path, help="Run metadata/log directory.")
    run.add_argument("--timeout", type=float)
    run.add_argument("--threads", type=int)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--pretty", action="store_true")

    outputs = sub.add_parser("outputs", help="Summarise or plot model outputs.")
    outputs_sub = outputs.add_subparsers(dest="outputs_command", required=True)
    outputs_summary = outputs_sub.add_parser("summary", help="Summarise CSV outputs.")
    outputs_summary.add_argument("root", type=Path)
    outputs_summary.add_argument("--pretty", action="store_true")
    outputs_plot = outputs_sub.add_parser("plot", help="Plot a single CSV timeseries.")
    outputs_plot.add_argument("csv", type=Path)
    outputs_plot.add_argument("--out", required=True, type=Path)
    outputs_plot.add_argument("--y", default="I")
    outputs_plot.add_argument("--pretty", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        _print(
            {
                "package": "ebolasim-tools",
                "version": __version__,
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            },
            pretty=args.pretty,
        )
        return 0

    if args.command == "patches":
        _print(read_patch_inventory(args.patch_dir), pretty=args.pretty)
        return 0

    if args.command == "patch-source":
        target = copy_source_tree(args.source_dir, args.out, overwrite=args.overwrite)
        result = apply_patches(target, patch_dir=args.patch_dir)
        _print(result, pretty=args.pretty)
        return 0 if result.ok else 1

    if args.command == "build":
        result = build_model(
            args.source_dir,
            build_dir=args.out,
            target=args.target,
            country=args.country,
            compiler=args.compiler,
            standard=args.standard,
            optimisation=args.optimisation,
            openmp=not args.no_openmp,
            patch=not args.no_patch,
            timeout=args.timeout,
            overwrite=args.overwrite,
        )
        _print(result, pretty=args.pretty)
        return 0 if result.ok else 1

    if args.command == "inspect":
        if args.inspect_command == "source":
            _print(inspect_source(args.source_dir).to_dict(), pretty=args.pretty)
        elif args.inspect_command == "density":
            _print(inspect_density_header(args.path), pretty=args.pretty)
        elif args.inspect_command == "network":
            _print(inspect_network_header(args.path), pretty=args.pretty)
        elif args.inspect_command == "bundle":
            _print(inspect_bundle(args.root), pretty=args.pretty)
        return 0

    if args.command == "example" and args.example_command == "tiny":
        _print(write_tiny_example(args.out, overwrite=args.overwrite), pretty=args.pretty)
        return 0

    if args.command == "params":
        if args.params_command == "show":
            _print(ParameterSet.read(args.path), pretty=args.pretty)
            return 0
        if args.params_command == "tiny":
            params = tiny_parameter_set(
                population=args.population,
                sampling_time=args.sampling_time,
                realisations=args.realisations,
            )
            params.write(args.out)
            _print({"path": args.out.as_posix(), "parameters": len(params)}, pretty=args.pretty)
            return 0
        if args.params_command == "set":
            params = ParameterSet.read(args.path).update_values({args.name: args.value})
            params.write(args.out)
            _print(
                {"path": args.out.as_posix(), "parameter": args.name, "value": args.value},
                pretty=args.pretty,
            )
            return 0

    if args.command == "manifest":
        if args.manifest_command == "show":
            manifest = read_manifest(args.path)
            if args.json:
                _print(manifest, pretty=args.pretty)
            else:
                print(manifest.to_yaml())
            return 0
        if args.manifest_command == "validate":
            manifest = read_manifest(args.path)
            ok, errors = validate_manifest(manifest)
            _print({"ok": ok, "errors": errors}, pretty=args.pretty)
            return 0 if ok else 1
        if args.manifest_command == "from-nordkivu":
            manifest = manifest_from_bundle(
                args.root,
                paramset=args.paramset,
                output=args.out,
                executable=args.executable,
                threads=args.threads,
            )
            _print(manifest, pretty=args.pretty)
            return 0

    if args.command == "command":
        plan = build_command_plan(
            args.manifest, executable=args.exe, root=args.root, threads=args.threads
        )
        _print(plan, pretty=args.pretty)
        return 0 if plan.validation.ok else 1

    if args.command == "run":
        result = run_model(
            args.manifest,
            executable=args.exe,
            root=args.root,
            run_dir=args.out,
            timeout=args.timeout,
            threads=args.threads,
            dry_run=args.dry_run,
        )
        _print(result, pretty=args.pretty)
        return 0 if result.ok else 1

    if args.command == "outputs":
        if args.outputs_command == "summary":
            _print(summarise_outputs(args.root), pretty=args.pretty)
            return 0
        if args.outputs_command == "plot":
            path = plot_output_timeseries(args.csv, args.out, y_column=args.y)
            _print({"path": path.as_posix()}, pretty=args.pretty)
            return 0

    parser.error("unhandled command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
