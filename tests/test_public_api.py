from pathlib import Path

import pytest

import ebolasim as es


def make_fake_executable(path: Path) -> Path:
    script = r"""#!/usr/bin/env python3
import sys
from pathlib import Path

output_base = None
for arg in sys.argv[1:]:
    if arg.startswith("/O:"):
        output_base = arg[3:]
if output_base is None:
    print("missing output", file=sys.stderr)
    raise SystemExit(2)
base = Path(output_base)
base.parent.mkdir(parents=True, exist_ok=True)
(base.with_suffix(".0.csv")).write_text(
    "t,S,L,I,R,D,incI\n0,23,1,0,0,0,1\n1,22,0,1,1,0,0\n",
    encoding="utf-8",
)
(Path(str(base) + ".0.adunit.csv")).write_text("t,A\n0,1\n", encoding="utf-8")
(Path(str(base) + ".0.age.csv")).write_text("t,age0\n0,1\n", encoding="utf-8")
(Path(str(base) + ".0.keyworker.csv")).write_text("t,K\n0,0\n", encoding="utf-8")
(Path(str(base) + ".0.seeds.csv")).write_text("1,2\n", encoding="utf-8")
print("fake run completed")
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def test_public_api_is_small():
    assert set(es.__all__) == {
        "Pars",
        "Results",
        "Sim",
        "__version__",
        "compare_results",
        "demo_pars",
        "load_pars",
        "parameter_reference",
        "plot_compare",
        "read_results",
        "resolve_executable",
    }


def test_demo_pars_exact_names_and_raw_round_trip(tmp_path):
    pars = es.demo_pars(
        {
            "Population size": 100,
            "Number of realisations": 3,
            "Sampling time": 14,
            "Reproduction number": 1.7,
        }
    )
    updated = pars.set(
        {
            "Include contact tracing": 1,
            "Output age file": 0,
            "Do geographic vaccination": 1,
            "Proportion of population vaccinated": 0.25,
        }
    )
    assert pars.raw.get_int("Population size") == 100
    assert updated.raw.get_int("Include contact tracing") == 1
    assert updated.raw.get_int("Output age file") == 0
    assert updated.raw["Proportion of population vaccinated"] == "0.25"

    path = updated.write(tmp_path / "parameters.txt")
    loaded = es.load_pars(path)

    assert loaded.raw.get_int("Number of realisations") == 3
    assert loaded.raw.get_float("Reproduction number") == 1.7


def test_parameter_reference_uses_exact_c_names():
    rows = es.parameter_reference()
    names = {row.name for row in rows}

    assert len(rows) > 400
    assert "Population size" in names
    assert "Reproduction number" in names
    assert "population" not in names
    assert all(row.description for row in rows)


def test_sim_command_and_script(tmp_path):
    exe = make_fake_executable(tmp_path / "fake_exec.py")
    sim = es.Sim(
        es.demo_pars(
            {
                "Population size": 24,
                "Number of realisations": 1,
                "Sampling time": 7,
            }
        ),
        label="baseline",
        outdir=tmp_path / "sim",
        exe=exe,
        threads=2,
    )

    plan = sim.command()
    assert plan.command[0] == exe.as_posix()
    assert plan.environment == {"OMP_NUM_THREADS": "2"}
    assert any(arg.startswith("/P:") for arg in plan.arguments)

    script = sim.write_script(tmp_path / "submit.sh")
    text = script.read_text(encoding="utf-8")
    assert "OMP_NUM_THREADS=2" in text
    assert exe.as_posix() in text


def test_sim_run_and_results(tmp_path):
    exe = make_fake_executable(tmp_path / "fake_exec.py")
    sim = es.Sim(
        es.demo_pars(
            {
                "Population size": 24,
                "Number of realisations": 1,
                "Sampling time": 7,
            }
        ),
        label="baseline",
        outdir=tmp_path / "sim",
        exe=exe,
    ).run(timeout=5)

    assert sim.returncode == 0
    assert sim.results is not None
    assert sim.summary is not None
    assert sim.summary["total_incidence"] == 1.0
    assert sim.results.main is not None
    assert len(sim.results.by_admin_unit) == 1
    assert len(sim.results.by_age) == 1

    rows = es.compare_results([sim])
    assert rows[0]["label"] == "baseline"
    assert rows[0]["total_incidence"] == 1.0


def test_results_plot_requires_matplotlib(tmp_path):
    pytest.importorskip("matplotlib")
    exe = make_fake_executable(tmp_path / "fake_exec.py")
    sim = es.Sim(
        es.demo_pars(
            {
                "Population size": 24,
                "Number of realisations": 1,
                "Sampling time": 7,
            }
        ),
        outdir=tmp_path / "sim",
        exe=exe,
    )
    sim.run(timeout=5)
    fig = sim.plot()
    assert fig is not None
