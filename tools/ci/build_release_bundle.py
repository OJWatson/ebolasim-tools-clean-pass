#!/usr/bin/env python3
"""Build, verify, and stage a release-ready bundled EbolaSim executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from ebolasim import Sim, __version__, demo_pars
from ebolasim.build import (
    build_executable,
    bundle_executable,
    detect_platform_id,
    fetch_source,
    read_patch_inventory,
)

SUPPORTED_RELEASE_PLATFORM = "linux-x86_64"


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


def _json_sha256(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def _patch_inventory_digest(patch_inventory_data: dict[str, Any]) -> str:
    patch_dir = Path(patch_inventory_data["patch_dir"])
    patch_hashes = {}
    for patch in patch_inventory_data["patches"]:
        patch_file = patch_dir / patch["file"]
        patch_hashes[patch["file"]] = _sha256(patch_file)
    payload = {"patches": patch_inventory_data["patches"], "patch_file_sha256": patch_hashes}
    return _json_sha256(payload)


def _write_checksums(root: Path) -> Path:
    checksums = root / "checksums.txt"
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path == checksums:
            continue
        lines.append(f"{_sha256(path)}  {path.relative_to(root).as_posix()}")
    _write_text(checksums, "\n".join(lines) + "\n")
    return checksums


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("model-src/upstream.lock.yml"))
    parser.add_argument("--workdir", type=Path, default=Path("build/ci-release"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("dist/release-bundle"))
    parser.add_argument("--package-root", type=Path, default=Path("src/ebolasim"))
    parser.add_argument("--platform-id")
    parser.add_argument("--target", default="ebola-spatial-linux")
    parser.add_argument("--country", default="COUNTRY_WA")
    parser.add_argument("--build-timeout", type=float, default=180)
    parser.add_argument("--run-timeout", type=float, default=30)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--allow-placeholders", action="store_true")
    parser.add_argument("--allow-unsupported-platform", action="store_true")
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
    if platform_id != SUPPORTED_RELEASE_PLATFORM and not args.allow_unsupported_platform:
        print(
            json.dumps(
                {
                    "ok": False,
                    "platform_id": platform_id,
                    "diagnostics": [
                        "first release pipeline supports linux-x86_64 only",
                        f"pass --platform-id {SUPPORTED_RELEASE_PLATFORM} on Linux x86_64 "
                        "or --allow-unsupported-platform for local experiments",
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    fetch = fetch_source(
        output_dir=args.workdir / "upstream",
        lock_path=args.lock,
        overwrite=True,
        allow_placeholders=args.allow_placeholders,
    )
    if not fetch.ok or not fetch.source_dir:
        print(fetch.to_json(pretty=True))
        return 1

    build = build_executable(
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

    sim = Sim(
        demo_pars(
            {
                "Population size": 24,
                "Number of realisations": 1,
                "Sampling time": 7,
            }
        ),
        label="bundle_smoke",
        outdir=args.workdir / "demo",
        exe=build.executable,
    ).run(timeout=args.run_timeout)
    run = sim.run_result
    if run is None or not run.ok:
        if run is not None:
            print(run.to_json(pretty=True))
        else:
            print(json.dumps({"ok": False, "diagnostics": ["simulation did not start"]}, indent=2))
        return 1

    patch_inventory = read_patch_inventory()
    patch_inventory_data = patch_inventory.to_dict()
    patch_inventory_digest = _patch_inventory_digest(patch_inventory_data)
    patch_application_path = args.workdir / "patch_application.json"
    _write_text(
        patch_application_path,
        json.dumps(build.patch_application or {}, indent=2, sort_keys=True) + "\n",
    )
    bundle_metadata_path = args.workdir / "bundle_metadata.json"
    build_binary_sha256 = _sha256(Path(build.executable))
    bundle_metadata = {
        "ok": True,
        "package": "ebolasim",
        "package_version": __version__,
        "platform_id": platform_id,
        "target": args.target,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "upstream_repository": fetch.lock.repository,
        "upstream_ref_type": fetch.lock.ref_type,
        "upstream_ref": fetch.lock.ref,
        "upstream_archive_url": fetch.lock.archive_url,
        "upstream_archive_sha256": fetch.archive_sha256,
        "patch_inventory_digest": patch_inventory_digest,
        "patch_inventory": patch_inventory_data,
        "build_classification": build.classification,
        "build_executable_sha256": build_binary_sha256,
        "run_classification": run.classification,
        "run_output_files": len(run.output_files),
        "run_output_summary": run.output_summary,
    }
    _write_text(bundle_metadata_path, _bundle_summary(**bundle_metadata))

    staged = bundle_executable(
        build.executable,
        platform_id=platform_id,
        target=args.target,
        package_root=args.package_root,
        metadata_files=[
            args.lock,
            build.metadata_path,
            fetch.metadata_path,
            run.metadata_path,
            patch_application_path,
            bundle_metadata_path,
        ],
    )

    platform_bundle = args.bundle_dir / platform_id
    bundle_binary = platform_bundle / args.target
    _copy(staged, bundle_binary)
    _copy(Path(build.metadata_path), platform_bundle / "build_metadata.json")
    _copy(Path(fetch.metadata_path), platform_bundle / "upstream_fetch.json")
    _copy(Path(run.metadata_path), platform_bundle / "run_metadata.json")
    _copy(patch_application_path, platform_bundle / "patch_application.json")
    _copy(bundle_metadata_path, platform_bundle / "bundle_metadata.json")
    _copy(args.lock, platform_bundle / "upstream.lock.yml")
    checksums_path = _write_checksums(platform_bundle)
    summary = {
        "ok": True,
        "platform_id": platform_id,
        "target": args.target,
        "bundle_dir": args.bundle_dir.as_posix(),
        "staged_binary": staged.as_posix(),
        "bundle_binary": bundle_binary.as_posix(),
        "bundle_metadata": (platform_bundle / "bundle_metadata.json").as_posix(),
        "checksums": checksums_path.as_posix(),
        "build_metadata": build.metadata_path,
        "fetch_metadata": fetch.metadata_path,
        "run_metadata": run.metadata_path,
        "patch_application": patch_application_path.as_posix(),
        "patch_inventory_digest": patch_inventory_digest,
        "upstream_archive_sha256": fetch.archive_sha256,
        "binary_sha256": build_binary_sha256,
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
