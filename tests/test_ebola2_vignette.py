from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


def load_vignette():
    path = Path(__file__).resolve().parents[1] / "docs/vignettes/ebola2/replay_ebola2.py"
    spec = importlib.util.spec_from_file_location("ebola2_replay_vignette", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_ebola2_fixture(root: Path) -> Path:
    ebola2 = root / "Ebola2"
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
    clp_args = " ".join(
        f"/CLP{index}:%{letter}%" for index, letter in enumerate("CDEFGHIJKLMNO", 1)
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
                "set D=%4",
                "set E=%5",
                "set F=%6",
                "set G=%7",
                "set H=%8",
                "set I=%9",
                "set J=%10",
                "set K=%11",
                "set L=%12",
                "set M=%13",
                "set N=%14",
                "set O=%15",
                r"%WORKING_DIR%\ebola-spatial.exe "
                r"/P:%DATA_DIR%\p_R1.80_NordKivu_HCWring_midAccept.txt "
                r"/PP:%DATA_DIR%\preFPNordKivu_HCWring_singleAdUnit.txt "
                r"/O:%OUT_DIR%\paramset_%A% "
                r"/D:%POP_DIR%\NordKivu_MSF_LS2018.bin "
                r"/S:%POP_DIR%\NordKivu_MSF_Network_HCW_singleAdUnt.bin "
                rf"/R:%B% {clp_args} 98798150 729101 17389101 4797132",
            ]
        ),
        encoding="utf-8",
    )
    return ebola2


def test_build_job_preserves_ebola2_launch_values(tmp_path):
    vignette = load_vignette()
    ebola2 = make_ebola2_fixture(tmp_path)
    generated_root = tmp_path / "generated"
    executable = tmp_path / "ebola-spatial-linux"
    executable.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    job = vignette.build_job(
        ebola2,
        generated_root,
        paramset=1,
        executable=executable.as_posix(),
        threads=4,
    )

    assert job.environment == {"OMP_NUM_THREADS": "4"}
    assert job.command[0] == executable.as_posix()
    assert any(
        arg.endswith("/Ervebo/Gavi/Data/p_R1.80_NordKivu_HCWring_midAccept.txt")
        for arg in job.command
    )
    assert any(
        arg.endswith("/Ervebo/Gavi/Data/preFPNordKivu_HCWring_singleAdUnit.txt")
        for arg in job.command
    )
    assert any(arg.endswith("/Ervebo/Populations/NordKivu_MSF_LS2018.bin") for arg in job.command)
    assert any(
        arg.endswith("/Ervebo/Populations/NordKivu_MSF_Network_HCW_singleAdUnt.bin")
        for arg in job.command
    )
    assert (
        f"/O:{(generated_root / 'paramset_1' / 'paramset_1').resolve().as_posix()}" in job.command
    )
    assert "/R:1.17" in job.command
    assert "/CLP1:24" in job.command
    assert "/CLP13:1" in job.command
    assert job.command[-4:] == ["98798150", "729101", "17389101", "4797132"]


def test_compare_output_file_exact_and_numeric_tolerance(tmp_path):
    vignette = load_vignette()
    reference = tmp_path / "reference.csv"
    generated = tmp_path / "generated.csv"
    reference.write_text("a,b\n1,2\n", encoding="utf-8")
    generated.write_text("a,b\n1,2\n", encoding="utf-8")

    exact = vignette.compare_output_file(reference, generated, tolerance=1e-9)

    assert exact.status == "byte_identical"
    assert exact.byte_identical
    assert exact.numeric_equivalent

    generated.write_text("a,b\n1.0000000001,2\n", encoding="utf-8")

    tolerant = vignette.compare_output_file(reference, generated, tolerance=1e-9)

    assert tolerant.status == "numeric_equivalent"
    assert not tolerant.byte_identical
    assert tolerant.numeric_equivalent
    assert tolerant.max_abs_diff < 1e-9


def test_compare_output_file_detects_failures(tmp_path):
    vignette = load_vignette()
    reference = tmp_path / "reference.csv"
    generated = tmp_path / "generated.csv"
    reference.write_text("a,b\n1,2\n", encoding="utf-8")

    missing = vignette.compare_output_file(reference, None, tolerance=1e-9)
    assert missing.status == "missing_generated"

    generated.write_text("a,c\n1,2\n", encoding="utf-8")
    schema = vignette.compare_output_file(reference, generated, tolerance=1e-9)
    assert schema.status == "schema_mismatch"

    generated.write_text("a,b\n1,3\n", encoding="utf-8")
    numeric = vignette.compare_output_file(reference, generated, tolerance=1e-9)
    assert numeric.status == "numeric_mismatch"
    assert numeric.first_difference["column"] == 1


def test_compare_paramset_outputs_reports_inventory(tmp_path):
    vignette = load_vignette()
    reference_dir = tmp_path / "reference"
    generated_dir = tmp_path / "generated"
    reference_dir.mkdir()
    generated_dir.mkdir()
    (reference_dir / "paramset_1.0.csv").write_text("a\n1\n", encoding="utf-8")
    (generated_dir / "paramset_1.0.csv").write_text("a\n1\n", encoding="utf-8")
    (generated_dir / "paramset_1.extra.csv").write_text("a\n1\n", encoding="utf-8")

    summary = vignette.compare_paramset_outputs(
        reference_dir,
        generated_dir,
        paramset=1,
        tolerance=1e-9,
    )

    assert summary["files_expected"] == 1
    assert summary["files_generated"] == 2
    assert summary["extra_generated_files"] == ["paramset_1.extra.csv"]


@pytest.mark.slow
def test_full_ebola2_replay_gated():
    if os.environ.get("EBOLASIM_RUN_EBOLA2") != "1":
        pytest.skip("set EBOLASIM_RUN_EBOLA2=1 to run the full local Ebola2 replay")
    vignette = load_vignette()
    repo_root = Path(__file__).resolve().parents[1]
    zip_path = repo_root / "ignore/Ebola2.zip"
    if not zip_path.is_file():
        pytest.skip("ignore/Ebola2.zip is not available")

    assert (
        vignette.main(
            [
                "--zip",
                zip_path.as_posix(),
                "--workdir",
                (repo_root / "artifacts/ebola2-replay").as_posix(),
                "--evidence-dir",
                (repo_root / "docs/vignettes/ebola2/evidence").as_posix(),
                "--paramsets",
                "1",
                "2",
                "--threads",
                "4",
            ]
        )
        == 0
    )
