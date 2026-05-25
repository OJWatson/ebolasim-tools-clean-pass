from ebolasim_tools import (
    ManifestInputs,
    ManifestOutputs,
    RunManifest,
    build_command_plan,
    read_manifest,
    validate_argv,
    validate_manifest,
    write_manifest,
)
from ebolasim_tools.command import parse_legacy_args


def make_manifest():
    return RunManifest(
        inputs=ManifestInputs(
            parameter_file="params/p.txt",
            preparameter_file="params/pre.txt",
            density_file="inputs/density.bin",
            network_file="inputs/network.bin",
            network_mode="save",
        ),
        outputs=ManifestOutputs(output_base="outputs/run.0", output_dir="outputs"),
        seeds=[1, 2, 3, 4],
    )


def test_manifest_round_trip(tmp_path):
    path = tmp_path / "run.yml"
    manifest = make_manifest()
    write_manifest(manifest, path)
    loaded = read_manifest(path)
    assert loaded.inputs.parameter_file == "params/p.txt"
    assert loaded.outputs.output_base == "outputs/run.0"
    assert loaded.seeds == [1, 2, 3, 4]


def test_manifest_validation_ok():
    ok, errors = validate_manifest(make_manifest())
    assert ok
    assert errors == []


def test_manifest_validation_bad_network_mode():
    manifest = RunManifest(
        inputs=ManifestInputs(parameter_file="p", density_file="d", network_mode="bad"),
        outputs=ManifestOutputs(output_base="o"),
        seeds=[1, 2, 3],
    )
    ok, errors = validate_manifest(manifest)
    assert not ok
    assert any("network_mode" in error for error in errors)
    assert any("four" in error for error in errors)


def test_command_plan_resolves_paths_from_manifest_parent(tmp_path):
    root = tmp_path / "scenario"
    root.mkdir()
    path = root / "run.yml"
    write_manifest(make_manifest(), path)
    plan = build_command_plan(path, executable="./exe")
    assert plan.executable == "./exe"
    assert f"/P:{root / 'params/p.txt'}" in plan.arguments
    assert f"/S:{root / 'inputs/network.bin'}" in plan.arguments
    assert plan.validation.ok


def test_command_plan_can_use_explicit_root(tmp_path):
    root = tmp_path / "root"
    plan = build_command_plan(make_manifest(), executable="exe", root=root, threads=4)
    assert plan.environment == {"OMP_NUM_THREADS": "4"}
    assert f"/D:{root / 'inputs/density.bin'}" in plan.arguments


def test_validate_argv_detects_missing_fields():
    report = validate_argv(["/P:p", "1", "2"])
    assert not report.ok
    assert report.seed_count == 2
    assert report.network_mode is None


def test_parse_legacy_args_preserves_school_save_case():
    parsed = parse_legacy_args(["/S:network.bin", "/s:schools.txt", "/CLP2:5", "1", "2", "3", "4"])
    assert parsed.save_network_file == "network.bin"
    assert parsed.school_file == "schools.txt"
    assert parsed.clp == {2: "5"}
