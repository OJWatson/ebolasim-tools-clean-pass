import hashlib
import io
import tarfile
from pathlib import Path

import yaml

from ebolasim_tools.bundled import (
    detect_platform_id,
    resolve_bundled_executable,
    stage_bundled_executable,
)
from ebolasim_tools.upstream import fetch_upstream_source, read_upstream_lock


def _make_tarball(path: Path, root: str = "upstream-src") -> str:
    source = {
        "SpatialSim.c": b"int main(){return 0;}\n",
        "SpatialSim.h": b"#pragma once\n",
        "binio.cpp": b"int x = 0;\n",
        "binio.h": b"#pragma once\n",
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, data in source.items():
            info = tarfile.TarInfo(name=f"{root}/{name}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_lock(path: Path, archive_url: str, archive_sha256: str, strip_prefix: str) -> None:
    payload = {
        "schema_version": 1,
        "upstream": {
            "name": "ebolasim_public",
            "repository": "https://example.invalid/ebolasim_public",
            "ref_type": "commit",
            "ref": "1234567890abcdef1234567890abcdef12345678",
            "archive_url": archive_url,
            "archive_sha256": archive_sha256,
            "strip_prefix": strip_prefix,
        },
        "notes": ["test lock"],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_read_upstream_lock(tmp_path):
    tarball = tmp_path / "upstream.tar.gz"
    sha = _make_tarball(tarball)
    lock = tmp_path / "upstream.lock.yml"
    _write_lock(lock, tarball.resolve().as_uri(), sha, "upstream-src")
    loaded = read_upstream_lock(lock)
    assert loaded.ref_type == "commit"
    assert loaded.archive_sha256 == sha
    assert loaded.strip_prefix == "upstream-src"
    assert not loaded.is_placeholder


def test_fetch_upstream_source_from_file_url(tmp_path):
    tarball = tmp_path / "upstream.tar.gz"
    sha = _make_tarball(tarball)
    lock = tmp_path / "upstream.lock.yml"
    _write_lock(lock, tarball.resolve().as_uri(), sha, "upstream-src")

    result = fetch_upstream_source(output_dir=tmp_path / "fetch", lock_path=lock, overwrite=True)

    assert result.ok
    assert result.source_dir is not None
    source = Path(result.source_dir)
    assert (source / "SpatialSim.c").is_file()
    assert result.archive_sha256 == sha
    assert Path(result.metadata_path).is_file()


def test_fetch_upstream_source_hash_mismatch_is_reported(tmp_path):
    tarball = tmp_path / "upstream.tar.gz"
    _ = _make_tarball(tarball)
    lock = tmp_path / "upstream.lock.yml"
    _write_lock(lock, tarball.resolve().as_uri(), "f" * 64, "upstream-src")

    result = fetch_upstream_source(output_dir=tmp_path / "fetch", lock_path=lock, overwrite=True)

    assert not result.ok
    assert result.source_dir is None
    assert any("SHA256 mismatch" in item for item in result.diagnostics)


def test_stage_and_resolve_bundled_executable(tmp_path):
    package_root = tmp_path / "pkg"
    executable = tmp_path / "ebola-spatial-linux"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    metadata = tmp_path / "build_metadata.json"
    metadata.write_text("{}", encoding="utf-8")
    platform_id = detect_platform_id()

    staged = stage_bundled_executable(
        executable,
        platform_id=platform_id,
        package_root=package_root,
        metadata_files=[metadata],
    )
    resolved = resolve_bundled_executable(platform_id=platform_id, package_root=package_root)

    assert staged.is_file()
    assert resolved.ok
    assert resolved.path == staged.as_posix()
    assert (staged.parent / "build_metadata.json").is_file()
