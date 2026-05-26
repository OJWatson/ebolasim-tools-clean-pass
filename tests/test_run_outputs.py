from pathlib import Path

import pytest

from ebolasim_tools.bundled import BundledBinary
from ebolasim_tools.examples import write_tiny_example
from ebolasim_tools.outputs import (
    find_output_files,
    plot_output_timeseries,
    read_output_table,
    summarise_outputs,
)
from ebolasim_tools.run import run_model


def make_fake_executable(path: Path) -> Path:
    script = r"""#!/usr/bin/env python3
import os
import sys
from pathlib import Path

output_base = None
for arg in sys.argv[1:]:
    if arg.startswith('/O:'):
        output_base = arg[3:]
if output_base is None:
    print('missing output', file=sys.stderr)
    raise SystemExit(2)
path = Path(output_base + '.csv')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text('t,S,L,I,R,D,incI\n0,23,1,0,0,0,1\n1,22,0,1,1,0,0\n', encoding='utf-8')
print('fake run completed')
print('fake stderr', file=sys.stderr)
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def test_run_model_with_fake_executable(tmp_path):
    example = write_tiny_example(tmp_path / "tiny")
    exe = make_fake_executable(tmp_path / "fake_exec.py")
    result = run_model(
        example.save_manifest,
        executable=exe,
        root=example.root,
        run_dir=tmp_path / "run",
        timeout=5,
    )
    assert result.ok
    assert result.classification == "completed_with_outputs"
    assert result.returncode == 0
    assert Path(result.stdout_path).is_file()
    assert Path(result.stderr_path).is_file()
    assert result.output_summary is not None
    assert result.output_summary["total_incidence"] == 1.0


def test_run_model_uses_bundled_executable_when_exe_omitted(tmp_path, monkeypatch):
    example = write_tiny_example(tmp_path / "tiny")
    exe = make_fake_executable(tmp_path / "bundled_exec.py")

    def fake_resolve_bundled_executable():
        return BundledBinary(
            ok=True,
            platform_id="linux-x86_64",
            target="ebola-spatial-linux",
            path=exe.as_posix(),
            diagnostics=[],
        )

    monkeypatch.setattr(
        "ebolasim_tools.run.resolve_bundled_executable", fake_resolve_bundled_executable
    )

    result = run_model(example.save_manifest, root=example.root, run_dir=tmp_path / "run")

    assert result.ok
    assert result.command[0] == exe.as_posix()
    assert any("using bundled executable" in item for item in result.diagnostics)


def test_run_model_explicit_executable_takes_precedence(tmp_path, monkeypatch):
    example = write_tiny_example(tmp_path / "tiny")
    exe = make_fake_executable(tmp_path / "explicit_exec.py")

    def unexpected_resolve():
        raise AssertionError("bundled executable should not be resolved")

    monkeypatch.setattr("ebolasim_tools.run.resolve_bundled_executable", unexpected_resolve)

    result = run_model(
        example.save_manifest,
        executable=exe,
        root=example.root,
        run_dir=tmp_path / "run",
    )

    assert result.ok
    assert result.command[0] == exe.as_posix()


def test_run_model_without_exe_fails_clearly_when_bundle_missing(tmp_path, monkeypatch):
    example = write_tiny_example(tmp_path / "tiny")

    def fake_resolve_bundled_executable():
        return BundledBinary(
            ok=False,
            platform_id="linux-x86_64",
            target="ebola-spatial-linux",
            path=None,
            diagnostics=["bundled executable not found for linux-x86_64"],
        )

    monkeypatch.setattr(
        "ebolasim_tools.run.resolve_bundled_executable", fake_resolve_bundled_executable
    )

    result = run_model(example.save_manifest, root=example.root, run_dir=tmp_path / "run")

    assert not result.ok
    assert result.classification == "execution_failed"
    assert any("pass executable/--exe" in item for item in result.diagnostics)
    assert "pass executable/--exe" in Path(result.stderr_path).read_text(encoding="utf-8")


def test_run_model_dry_run(tmp_path):
    example = write_tiny_example(tmp_path / "tiny")
    result = run_model(
        example.save_manifest,
        executable="missing",
        root=example.root,
        run_dir=tmp_path / "run",
        dry_run=True,
    )
    assert result.ok
    assert result.classification == "dry_run"
    assert result.returncode is None
    assert result.command[0] == "missing"


def test_run_model_missing_parameter_classification(tmp_path):
    example = write_tiny_example(tmp_path / "tiny")
    exe = tmp_path / "bad.py"
    exe.write_text(
        (
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('Unable to find parameter `X`', file=sys.stderr)\n"
            "sys.exit(1)\n"
        ),
        encoding="utf-8",
    )
    exe.chmod(0o755)
    result = run_model(
        example.save_manifest,
        executable=exe,
        root=example.root,
        run_dir=tmp_path / "run",
        timeout=5,
    )
    assert not result.ok
    assert result.classification == "missing_parameter"


def test_read_output_table_and_summary(tmp_path):
    csv = tmp_path / "out.csv"
    csv.write_text("t,S,I,incI\n0,10,0,1\n1,9,1,2\n", encoding="utf-8")
    table = read_output_table(csv)
    assert table.row_count == 2
    assert table.numeric_column("incI") == [1.0, 2.0]
    summary = summarise_outputs(tmp_path)
    assert summary.rows == 2
    assert summary.total_incidence == 3.0
    assert summary.max_infectious == 1.0
    assert find_output_files(tmp_path) == [csv]


def test_plot_output_timeseries_if_matplotlib_available(tmp_path):
    pytest.importorskip("matplotlib")
    csv = tmp_path / "out.csv"
    csv.write_text("t,I\n0,0\n1,2\n", encoding="utf-8")
    out = plot_output_timeseries(csv, tmp_path / "plot.png")
    assert out.is_file()
