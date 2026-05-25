import json
from pathlib import Path

import yaml

from ebolasim_tools.bundled import detect_platform_id, stage_bundled_executable
from ebolasim_tools.cli import main
from ebolasim_tools.command import build_command_plan
from ebolasim_tools.manifest import ManifestInputs, ManifestOutputs, RunManifest
from ebolasim_tools.nordkivu import inspect_bundle, manifest_from_bundle


def make_bundle(root: Path) -> Path:
    ebola = root / "Ebola"
    (ebola / "Parameters").mkdir(parents=True)
    (ebola / "Data").mkdir()
    (ebola / "Parameters" / "p_188.txt").write_text("[Update timestep]\n1\n", encoding="utf-8")
    (ebola / "Data" / "Density.bin").write_bytes(b"density")
    (ebola / "Data" / "Network.bin").write_bytes(b"network")
    (ebola / "run.bat").write_text("ebola-spatial.exe /P:p_188.txt\n", encoding="utf-8")
    return ebola


def test_inspect_bundle(tmp_path):
    ebola = make_bundle(tmp_path)
    report = inspect_bundle(tmp_path)
    assert report.ok
    assert report.ebola_dir == ebola.as_posix()
    assert len(report.parameter_files) == 1
    assert len(report.density_files) == 1


def test_manifest_from_bundle(tmp_path):
    ebola = make_bundle(tmp_path)
    manifest = manifest_from_bundle(tmp_path, paramset=188)
    assert manifest.inputs.network_mode == "load"
    assert manifest.paramset == 188
    assert manifest.source.bundle_root == ebola.as_posix()


def test_manifest_from_bundle_parses_lowercase_batch_flags(tmp_path):
    ebola = make_bundle(tmp_path)
    (ebola / "launch.bat").write_text(
        "%EXE% 188 1.17 24 2500 10 6 1000 5000 2000 10000 0 450 40 0 1\n",
        encoding="utf-8",
    )
    (ebola / "run.bat").write_text(
        "\n".join(
            [
                "set DATA_DIR=Ebola\\Data",
                "set OUT_DIR=Ebola\\Output",
                "set A=%1",
                "set B=%2",
                "set C=%3",
                "set D=%4",
                "%WORKING_DIR%\\ebola-spatial.exe /p:%DATA_DIR%\\p_188.txt "
                "/o:%OUT_DIR%\\paramset_%A% /d:%DATA_DIR%\\Density.bin "
                "/l:%DATA_DIR%\\Network.bin /r:%B% /clp1:%C% /clp2:%D% "
                "98798150 729101 17389101 4797132",
            ]
        ),
        encoding="utf-8",
    )

    manifest = manifest_from_bundle(tmp_path, paramset=188)

    assert manifest.source.kind == "nordkivu_batch"
    assert manifest.inputs.parameter_file == "Data/p_188.txt"
    assert manifest.inputs.network_mode == "load"
    assert manifest.legacy_args.r0_scale == "1.17"
    assert manifest.legacy_args.clp == {1: "24", 2: "2500"}
    assert manifest.seeds == [98798150, 729101, 17389101, 4797132]


def test_manifest_from_bundle_detects_ebola2_root_and_save_network(tmp_path):
    ebola2 = tmp_path / "bundle" / "Ebola2"
    data = ebola2 / "Ervebo" / "Gavi" / "Data"
    run = ebola2 / "Ervebo" / "Gavi" / "Run"
    pop = ebola2 / "Ervebo" / "Populations"
    for directory in [data, run, pop]:
        directory.mkdir(parents=True)
    (data / "p_R1.80_NordKivu_HCWring_midAccept.txt").write_text("p\n", encoding="utf-8")
    (data / "preFPNordKivu_HCWring_singleAdUnit.txt").write_text("pre\n", encoding="utf-8")
    (pop / "NordKivu_MSF_LS2018.bin").write_bytes(b"density")
    (pop / "NordKivu_MSF_Network_HCW_singleAdUnt.bin").write_bytes(b"network")
    (run / "launch_NordKivu_MidAccept_singleAdUnit.bat").write_text(
        "%EXE% 1 1.17 24 2500 10 6 1000 5000 2000 10000 0 450 40 0 1\n",
        encoding="utf-8",
    )
    (run / "run_NordKivu_MidAccept_singleAdUnit.bat").write_text(
        "\n".join(
            [
                r"set DATA_DIR=\\wpia-hn\Ebola\Ervebo\Gavi\Data",
                r"set OUT_DIR=\\wpia-hn\Ebola\Ervebo\Gavi\Output_MidAccept_singleAdUnit",
                r"set POP_DIR=\\wpia-hn\Ebola\Ervebo\Populations",
                "set A=%1",
                "set B=%2",
                "set C=%3",
                r"%WORKING_DIR%\ebola-spatial.exe "
                r"/P:%DATA_DIR%\p_R1.80_NordKivu_HCWring_midAccept.txt "
                r"/PP:%DATA_DIR%\preFPNordKivu_HCWring_singleAdUnit.txt "
                r"/O:%OUT_DIR%\paramset_%A% "
                r"/D:%POP_DIR%\NordKivu_MSF_LS2018.bin "
                r"/S:%POP_DIR%\NordKivu_MSF_Network_HCW_singleAdUnt.bin "
                r"/R:%B% /CLP1:%C% 98798150 729101 17389101 4797132",
            ]
        ),
        encoding="utf-8",
    )

    manifest = manifest_from_bundle(tmp_path / "bundle", paramset=1)

    assert manifest.source.kind == "nordkivu_batch"
    assert manifest.source.bundle_root == ebola2.as_posix()
    assert manifest.inputs.parameter_file.startswith("Ervebo/Gavi/Data/")
    assert manifest.inputs.network_mode == "save"
    assert manifest.outputs.output_base == "Ervebo/Gavi/Output_MidAccept_singleAdUnit/paramset_1"


def test_command_plan_resolves_logical_ebola_prefix_to_ebola2(tmp_path):
    ebola2 = tmp_path / "Ebola2"
    (ebola2 / "Ervebo" / "Gavi" / "Data").mkdir(parents=True)
    (ebola2 / "Ervebo" / "Populations").mkdir(parents=True)
    manifest = RunManifest(
        inputs=ManifestInputs(
            parameter_file="Ebola/Ervebo/Gavi/Data/p.txt",
            density_file="Ebola/Ervebo/Populations/density.bin",
            network_file="Ebola/Ervebo/Populations/network.bin",
            network_mode="save",
        ),
        outputs=ManifestOutputs(
            output_base="Ebola/Ervebo/Gavi/Output/paramset_1",
            output_dir="Ebola/Ervebo/Gavi/Output",
        ),
        seeds=[1, 2, 3, 4],
    )

    plan = build_command_plan(manifest, executable="exe", root=tmp_path)

    assert plan.arguments[0] == f"/P:{ebola2.as_posix()}/Ervebo/Gavi/Data/p.txt"
    assert plan.output_base == f"{ebola2.as_posix()}/Ervebo/Gavi/Output/paramset_1"


def test_cli_health(capsys):
    assert main(["health", "--pretty"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["package"] == "ebolasim-tools"


def test_cli_example_and_manifest(tmp_path, capsys):
    target = tmp_path / "tiny"
    assert main(["example", "tiny", str(target), "--pretty"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == target.as_posix()
    assert main(["manifest", "validate", str(target / "manifest-save.yml"), "--pretty"]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["ok"] is True


def test_cli_params_tiny_and_set(tmp_path, capsys):
    p = tmp_path / "p.txt"
    p2 = tmp_path / "p2.txt"
    assert main(["params", "tiny", str(p), "--population", "30", "--pretty"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["parameters"] > 60
    assert (
        main(["params", "set", str(p), "Number of realisations", "2", "--out", str(p2), "--pretty"])
        == 0
    )
    payload2 = json.loads(capsys.readouterr().out)
    assert payload2["value"] == "2"


def test_cli_command_dry_run(tmp_path, capsys):
    from ebolasim_tools import write_tiny_example

    example = write_tiny_example(tmp_path / "tiny")
    assert (
        main(["command", example.save_manifest, "--exe", "exe", "--root", example.root, "--pretty"])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["validation"]["ok"] is True
    assert payload["command"][0] == "exe"


def test_cli_upstream_show(tmp_path, capsys):
    lock = tmp_path / "upstream.lock.yml"
    lock.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "upstream": {
                    "name": "ebolasim_public",
                    "repository": "https://example.invalid/ebolasim_public",
                    "ref_type": "commit",
                    "ref": "1234567890abcdef1234567890abcdef12345678",
                    "archive_url": "file:///tmp/upstream.tar.gz",
                    "archive_sha256": "a" * 64,
                    "strip_prefix": "upstream-src",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert main(["upstream", "show", "--lock", str(lock), "--pretty"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "ebolasim_public"
    assert payload["ref_type"] == "commit"


def test_cli_bundled_ok(tmp_path, capsys):
    package_root = tmp_path / "pkg"
    executable = tmp_path / "ebola-spatial-linux"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    stage_bundled_executable(
        executable,
        platform_id=detect_platform_id(),
        package_root=package_root,
    )
    assert (
        main(
            [
                "bundled",
                "--package-root",
                str(package_root),
                "--platform-id",
                detect_platform_id(),
                "--pretty",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
