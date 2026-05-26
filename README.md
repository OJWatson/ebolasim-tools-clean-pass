# ebolasim

Python interface for running the EbolaSim C model from exact C-model parameter
files.

The package does not rewrite the model. It gives users a small Python API for
creating parameter files, running the compiled executable, reading outputs,
plotting trajectories, and comparing scenarios. Maintainer tools fetch the
pinned upstream source, apply the package patch set, compile the Linux x86_64
executable, and bundle it into release wheels.

## Install And Develop With uv

```bash
uv sync --extra dev --extra docs --extra plot
uv run pytest -q
uv run mkdocs build --strict
uv build
```

For a fresh wheel smoke test:

```bash
uv build
uv venv build/wheel-smoke --python 3.11
uv pip install --python build/wheel-smoke/bin/python dist/*.whl
build/wheel-smoke/bin/python -c "import ebolasim as es; print(es.resolve_executable(required=False))"
```

## Quickstart

Use the exact parameter names accepted by the C model:

```python
import ebolasim as es

pars = es.demo_pars().set({
    "Population size": 2400,
    "Number of realisations": 20,
    "Sampling time": 90,
    "Reproduction number": 1.6,
    "Initial number of infecteds": 1,
    "Output incidence by administrative unit": 1,
    "Output age file": 1,
})

sim = es.Sim(pars, label="baseline", outdir="runs/baseline")
sim.run()
print(sim.summary)
sim.plot()
```

Compare scenarios:

```python
scenario = pars.copy().set({
    "Reproduction number": 2.0,
    "Include contact tracing": 1,
})

baseline = es.Sim(pars, label="baseline", outdir="runs/baseline").run()
higher_r0 = es.Sim(scenario, label="higher_r0", outdir="runs/higher_r0").run()

rows = es.compare_results([baseline, higher_r0])
es.plot_compare([baseline, higher_r0])
```

Inspect the command for cluster submission without running:

```python
sim = es.Sim(
    es.demo_pars({"Number of realisations": 100}),
    outdir="runs/cluster_job",
    threads=4,
)
print(sim.command().shell_command)
sim.write_script("runs/cluster_job/submit.sh")
```

## Command Line

The CLI also uses exact C-model names:

```bash
uv run ebolasim params write parameters.txt \
  --set "Population size=2400" \
  --set "Number of realisations=20" \
  --set "Sampling time=90"

uv run ebolasim command --out runs/demo --threads 4 \
  --set "Population size=2400" \
  --set "Number of realisations=20" \
  --set "Sampling time=90"

uv run ebolasim run --out runs/demo --threads 4 --pretty \
  --set "Population size=24" \
  --set "Number of realisations=1" \
  --set "Sampling time=7"
```

Release wheels can include a bundled Linux x86_64 executable. If no bundled
executable is available for your platform, pass `exe=...` in Python or `--exe`
on the command line.

## Maintainer Source Pipeline

```bash
uv run ebolasim source show --pretty
uv run ebolasim source fetch --out build/upstream --pretty
uv run ebolasim source build build/upstream/extract/ebolasim_public-... \
  --out build/linux \
  --overwrite
uv run python tools/ci/build_release_bundle.py --overwrite
```

The release pipeline fetches the pinned upstream source from
`model-src/upstream.lock.yml`, verifies SHA256, applies the bundled Linux patch
set, compiles `ebola-spatial-linux`, runs a small `ebolasim.Sim` smoke check,
stages the binary under `src/ebolasim/_bundled/<platform>/`, and writes
provenance metadata and checksums.
