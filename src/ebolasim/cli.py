"""Command-line interface for ebolasim."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .build import build_executable, fetch_source, read_patch_inventory, read_source_lock
from .pars import Pars, demo_pars, load_pars
from .results import read_results
from .sim import Sim, resolve_executable


def _print(payload: Any, *, pretty: bool = False) -> None:
    if hasattr(payload, "to_json"):
        print(payload.to_json(pretty=pretty))
    else:
        print(json.dumps(payload, indent=2 if pretty else None, sort_keys=True, default=str))


def _add_par_args(parser: argparse.ArgumentParser, *, allow_file: bool = True) -> None:
    if allow_file:
        parser.add_argument(
            "--parameters",
            type=Path,
            help="Existing bracketed parameter file to use instead of demo defaults.",
        )
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help=(
            "Override an exact C model parameter name. Quote names with spaces, e.g. "
            '--set "Population size=2400". May be repeated.'
        ),
    )


def _parse_overrides(items: Sequence[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"parameter override must be NAME=VALUE: {item}")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"parameter override has an empty name: {item}")
        values[name] = value.strip()
    return values


def _pars_from_args(args: argparse.Namespace) -> Pars:
    pars = load_pars(args.parameters) if getattr(args, "parameters", None) else demo_pars()
    return pars.set(_parse_overrides(args.overrides))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ebolasim",
        description="Run and maintain the EbolaSim C model from Python.",
    )
    parser.add_argument("--version", action="version", version=f"ebolasim {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Print environment and package metadata.")
    health.add_argument("--pretty", action="store_true")

    executable = sub.add_parser("executable", help="Show the bundled executable path.")
    executable.add_argument("--pretty", action="store_true")

    params = sub.add_parser("params", help="Read or write model parameter files.")
    params_sub = params.add_subparsers(dest="params_command", required=True)
    params_write = params_sub.add_parser("write", help="Write demo parameters.")
    params_write.add_argument("out", type=Path)
    _add_par_args(params_write, allow_file=False)
    params_write.add_argument("--pretty", action="store_true")
    params_show = params_sub.add_parser("show", help="Read a parameter file.")
    params_show.add_argument("path", type=Path)
    params_show.add_argument("--pretty", action="store_true")

    command = sub.add_parser("command", help="Print the command for a demo simulation.")
    command.add_argument("--out", required=True, type=Path)
    command.add_argument("--label", default="demo")
    command.add_argument("--threads", type=int, default=1)
    command.add_argument("--exe", type=Path)
    _add_par_args(command)
    command.add_argument("--pretty", action="store_true")

    run = sub.add_parser("run", help="Run a demo simulation.")
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--label", default="demo")
    run.add_argument("--threads", type=int, default=1)
    run.add_argument("--exe", type=Path)
    run.add_argument("--timeout", type=float)
    _add_par_args(run)
    run.add_argument("--pretty", action="store_true")

    outputs = sub.add_parser("outputs", help="Read model outputs.")
    outputs_sub = outputs.add_subparsers(dest="outputs_command", required=True)
    outputs_summary = outputs_sub.add_parser("summary", help="Summarise an output directory.")
    outputs_summary.add_argument("root", type=Path)
    outputs_summary.add_argument("--pretty", action="store_true")

    source = sub.add_parser("source", help="Maintainer tools for the upstream C model.")
    source_sub = source.add_subparsers(dest="source_command", required=True)
    source_show = source_sub.add_parser("show", help="Show the pinned source lock.")
    source_show.add_argument("--lock", type=Path)
    source_show.add_argument("--pretty", action="store_true")
    source_fetch = source_sub.add_parser("fetch", help="Fetch and verify the pinned source.")
    source_fetch.add_argument("--out", required=True, type=Path)
    source_fetch.add_argument("--lock", type=Path)
    source_fetch.add_argument("--overwrite", action="store_true")
    source_fetch.add_argument("--pretty", action="store_true")
    source_build = source_sub.add_parser("build", help="Patch and compile the C model.")
    source_build.add_argument("source_dir", type=Path)
    source_build.add_argument("--out", required=True, type=Path)
    source_build.add_argument("--overwrite", action="store_true")
    source_build.add_argument("--pretty", action="store_true")

    patches = sub.add_parser("patches", help="Show bundled source patches.")
    patches.add_argument("--pretty", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        _print(
            {
                "package": "ebolasim",
                "version": __version__,
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            },
            pretty=args.pretty,
        )
        return 0

    if args.command == "executable":
        try:
            path = resolve_executable()
            _print({"ok": True, "path": path.as_posix() if path else None}, pretty=args.pretty)
            return 0
        except FileNotFoundError as exc:
            _print({"ok": False, "diagnostics": [str(exc)]}, pretty=args.pretty)
            return 1

    if args.command == "params":
        if args.params_command == "write":
            try:
                pars = _pars_from_args(args)
            except ValueError as exc:
                parser.error(str(exc))
            path = pars.write(args.out)
            _print({"path": path.as_posix(), "parameters": len(pars.raw)}, pretty=args.pretty)
            return 0
        if args.params_command == "show":
            _print(load_pars(args.path).to_dict(), pretty=args.pretty)
            return 0

    if args.command == "command":
        try:
            pars = _pars_from_args(args)
        except ValueError as exc:
            parser.error(str(exc))
        sim = Sim(
            pars,
            label=args.label,
            outdir=args.out,
            threads=args.threads,
            exe=args.exe,
        )
        _print(sim.command(), pretty=args.pretty)
        return 0

    if args.command == "run":
        try:
            pars = _pars_from_args(args)
        except ValueError as exc:
            parser.error(str(exc))
        sim = Sim(
            pars,
            label=args.label,
            outdir=args.out,
            threads=args.threads,
            exe=args.exe,
        )
        sim.run(timeout=args.timeout)
        _print(
            {
                "ok": sim.run_result.ok if sim.run_result else False,
                "classification": None if sim.run_result is None else sim.run_result.classification,
                "outdir": sim.root.as_posix(),
                "summary": sim.summary,
            },
            pretty=args.pretty,
        )
        return 0 if sim.run_result and sim.run_result.ok else 1

    if args.command == "outputs":
        _print(read_results(args.root).summary, pretty=args.pretty)
        return 0

    if args.command == "source":
        if args.source_command == "show":
            _print(read_source_lock(args.lock), pretty=args.pretty)
            return 0
        if args.source_command == "fetch":
            fetch_result = fetch_source(
                output_dir=args.out, lock_path=args.lock, overwrite=args.overwrite
            )
            _print(fetch_result, pretty=args.pretty)
            return 0 if fetch_result.ok else 1
        if args.source_command == "build":
            build_result = build_executable(
                args.source_dir, build_dir=args.out, overwrite=args.overwrite
            )
            _print(build_result, pretty=args.pretty)
            return 0 if build_result.ok else 1

    if args.command == "patches":
        _print(read_patch_inventory(), pretty=args.pretty)
        return 0

    parser.error("unhandled command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
