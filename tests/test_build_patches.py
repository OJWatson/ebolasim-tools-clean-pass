from ebolasim_tools.build import build_command, build_model, inspect_source
from ebolasim_tools.patches import copy_source_tree, read_patch_inventory


def test_patch_inventory_contains_seven_patches():
    inventory = read_patch_inventory()
    assert len(inventory.patches) == 7
    assert inventory.patches[0].file.endswith(".patch")
    assert any(not patch.compile_only for patch in inventory.patches)


def test_inspect_source_detects_missing_files(tmp_path):
    report = inspect_source(tmp_path)
    assert not report.ok
    assert "SpatialSim.c" in report.missing


def test_inspect_source_ok_for_minimal_tree(tmp_path):
    for name in ["SpatialSim.c", "SpatialSim.h", "binio.cpp", "binio.h"]:
        (tmp_path / name).write_text("", encoding="utf-8")
    report = inspect_source(tmp_path)
    assert report.ok
    assert report.missing == []


def test_build_command_contains_model_sources(tmp_path):
    cmd = build_command(source_dir=tmp_path, executable=tmp_path / "exe", country="WA")
    assert "g++" == cmd[0]
    assert "-DUNIX" in cmd
    assert "-DCOUNTRY_WA" in cmd
    assert (tmp_path / "SpatialSim.c").as_posix() in cmd
    assert (tmp_path / "binio.cpp").as_posix() in cmd


def test_copy_source_tree_excludes_build_noise(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "SpatialSim.c").write_text("x", encoding="utf-8")
    (source / "build").mkdir()
    (source / "build" / "junk").write_text("x", encoding="utf-8")
    target = copy_source_tree(source, tmp_path / "copy")
    assert (target / "SpatialSim.c").is_file()
    assert not (target / "build" / "junk").exists()


def test_build_model_returns_structured_timeout(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ["SpatialSim.c", "SpatialSim.h", "binio.cpp", "binio.h"]:
        (source / name).write_text("", encoding="utf-8")
    compiler = tmp_path / "slow_compiler.py"
    compiler.write_text(
        "#!/usr/bin/env python3\nimport time\ntime.sleep(1)\n",
        encoding="utf-8",
    )
    compiler.chmod(0o755)

    result = build_model(
        source,
        build_dir=tmp_path / "build",
        compiler=compiler.as_posix(),
        patch=False,
        timeout=0.01,
    )

    assert not result.ok
    assert result.classification == "timed_out"
    assert result.timed_out is True
    assert result.returncode is None
