#!/usr/bin/env python3
"""Build, verify, and stage a release-ready bundled EbolaSim executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from ebolasim_tools.build import build_model
from ebolasim_tools.bundled import detect_platform_id, stage_bundled_executable
from ebolasim_tools.examples import write_tiny_example
from ebolasim_tools.run import run_model
from ebolasim_tools.upstream import fetch_upstream_source


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bundle_summary(**kwargs: Any) -> str:
    return json.dumps(kwargs, indent=2, sort_keys=True) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("legacy-src/upstream.lock.yml"))
    parser.add_argument("--workdir", type=Path, default=Path("build/ci-release"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("dist/release-bundle"))
    parser.add_argument("--package-root", type=Path, default=Path("src/ebolasim_tools"))
    parser.add_argument("--platform-id")
    parser.add_argument("--target", default="ebola-spatial-linux")
    parser.add_argument("--country", default="COUNTRY_WA")
    parser.add_argument("--build-timeout", type=float, default=180)
    parser.add_argument("--run-timeout", type=float, default=30)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--allow-placeholders", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workdir.exists() and args.overwrite:
        shutil.rmtree(args.workdir)
    if args.bundle_dir.exists() and args.overwrite:
        shutil.rmtree(args.bundle_dir)
    args.workdir.mkdir(parents=True, exist_ok=True)
    args.bundle_dir.mkdir(parents=True, exist_ok=True)
    platform_id = args.platform_id or detect_platform_id()

    fetch = fetch_upstream_source(
        output_dir=args.workdir / "upstream",
        lock_path=args.lock,
        overwrite=True,
        allow_placeholders=args.allow_placeholders,
    )
    if not fetch.ok or not fetch.source_dir:
        print(fetch.to_json(pretty=True))
        return 1

    build = build_model(
        fetch.source_dir,
        build_dir=args.workdir / "build",
        target=args.target,
        country=args.country,
        timeout=args.build_timeout,
        overwrite=True,
    )
    if not build.ok:
        print(build.to_json(pretty=True))
        return 1

    example = write_tiny_example(args.workdir / "tiny", overwrite=True)
    run = run_model(
        example.save_manifest,
        executable=build.executable,
        root=example.root,
        run_dir=args.workdir / "run-save",
        timeout=args.run_timeout,
    )
    if not run.ok:
        print(run.to_json(pretty=True))
        return 1

    staged = stage_bundled_executable(
        build.executable,
        platform_id=platform_id,
        target=args.target,
        package_root=args.package_root,
        metadata_files=[args.lock, build.metadata_path, fetch.metadata_path, run.metadata_path],
    )

    bundle_binary = args.bundle_dir / platform_id / args.target
    _copy(staged, bundle_binary)
    _copy(Path(build.metadata_path), args.bundle_dir / platform_id / "build_metadata.json")
    _copy(Path(fetch.metadata_path), args.bundle_dir / platform_id / "upstream_fetch.json")
    _copy(Path(run.metadata_path), args.bundle_dir / platform_id / "run_metadata.json")
    _copy(args.lock, args.bundle_dir / platform_id / "upstream.lock.yml")
    _write_text(
        args.bundle_dir / platform_id / "checksums.txt",
        "\n".join(
            [
                f"{_sha256(bundle_binary)}  {bundle_binary.name}",
                f"{_sha256(args.lock)}  upstream.lock.yml",
                f"{_sha256(Path(build.metadata_path))}  build_metadata.json",
                f"{_sha256(Path(fetch.metadata_path))}  upstream_fetch.json",
                f"{_sha256(Path(run.metadata_path))}  run_metadata.json",
            ]
        )
        + "\n",
    )
    summary = {
        "ok": True,
        "platform_id": platform_id,
        "target": args.target,
        "bundle_dir": args.bundle_dir.as_posix(),
        "staged_binary": staged.as_posix(),
        "bundle_binary": bundle_binary.as_posix(),
        "build_metadata": build.metadata_path,
        "fetch_metadata": fetch.metadata_path,
        "run_metadata": run.metadata_path,
        "build_classification": build.classification,
        "run_classification": run.classification,
        "output_files": len(run.output_files),
        "output_summary": run.output_summary,
    }
    _write_text(args.bundle_dir / "bundle_summary.json", _bundle_summary(**summary))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
