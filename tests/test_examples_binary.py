import struct
from pathlib import Path

import pytest

from ebolasim_tools import read_manifest, write_tiny_example
from ebolasim_tools.binary import inspect_density_header, inspect_network_header, write_density_file
from ebolasim_tools.examples import TinyExampleSpec, tiny_parameters


def test_write_tiny_example_creates_expected_files(tmp_path):
    example = write_tiny_example(tmp_path / "tiny")
    assert Path(example.parameter_file).is_file()
    assert Path(example.density_file).is_file()
    assert Path(example.network_file).is_file()
    assert "manifest-save.yml" in example.files
    assert "manifest-load.yml" in example.files


def test_write_tiny_example_refuses_nonempty_directory(tmp_path):
    target = tmp_path / "tiny"
    target.mkdir()
    (target / "x").write_text("x")
    with pytest.raises(FileExistsError):
        write_tiny_example(target)


def test_tiny_example_manifests_are_valid(tmp_path):
    example = write_tiny_example(tmp_path / "tiny")
    save = read_manifest(example.save_manifest)
    load = read_manifest(example.load_manifest)
    assert save.inputs.network_mode == "save"
    assert load.inputs.network_mode == "load"
    assert save.outputs.output_base.endswith("paramset_1.0")


def test_density_header_from_tiny_example(tmp_path):
    example = write_tiny_example(tmp_path / "tiny")
    header = inspect_density_header(example.density_file)
    assert header.ok
    assert header.record_count == 16
    assert header.preview_records[0].population > 0


def test_empty_network_header_is_unknown(tmp_path):
    example = write_tiny_example(tmp_path / "tiny")
    header = inspect_network_header(example.network_file)
    assert not header.ok
    assert header.detected_format == "empty_or_unknown"


def test_network_header_windows_format(tmp_path):
    path = tmp_path / "network.bin"
    path.write_bytes(
        (4).to_bytes(4, "little", signed=True)
        + (11).to_bytes(4, "little", signed=True)
        + (22).to_bytes(4, "little", signed=True)
        + b"\x00" * 32
    )
    header = inspect_network_header(path)
    assert header.ok
    assert header.detected_format == "windows_long_i32"
    assert header.seed1_windows_long_i32 == 11


def test_network_header_linux_long64_format(tmp_path):
    path = tmp_path / "network-linux.bin"
    path.write_bytes(struct.pack("<iqq", 4, 11, 22) + b"\x00" * 32)
    header = inspect_network_header(path)
    assert header.ok
    assert header.detected_format == "linux_long_i64"
    assert header.seed1_linux_long_i64 == 11
    assert header.seed2_linux_long_i64 == 22


def test_write_density_file_custom_records(tmp_path):
    path = write_density_file(tmp_path / "density.bin", [(0.1, 0.2, 3.0, 1, 7)])
    header = inspect_density_header(path)
    assert header.record_count == 1
    assert header.preview_records[0].admin_unit == 7


def test_tiny_parameters_can_be_customised():
    spec = TinyExampleSpec(population=40, sampling_time=3, realisations=2)
    params = tiny_parameters(spec)
    assert params.get_int("Population size") == 40
    assert params.get_int("Sampling time") == 3
    assert params.get_int("Number of realisations") == 2
