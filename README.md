# ebolasim-tools

A lightweight Python wrapper for the legacy file-based `ebola-spatial` C/C++ model.

This package deliberately treats the model as an external executable. It helps with the surrounding workflow:

- apply the small Linux portability patch set;
- compile the legacy source into a Linux executable;
- read and write legacy parameter files;
- create a tiny simulator-compatible example bundle;
- write portable run manifests;
- build the exact legacy command line;
- run the executable with captured stdout, stderr and metadata;
- summarise CSV outputs;
- inspect density and saved-network binary headers.

It does not redistribute the original model source. CI/release automation fetches a pinned public upstream
archive, applies this package's patch set, compiles the Linux executable, and bundles that executable in
release artifacts and platform wheels.

## Quickstart

```bash
python -m pip install -e .

# Show lock metadata for the pinned public upstream source.
ebolasim upstream show --pretty

# Fetch and verify the pinned upstream source archive.
ebolasim upstream fetch --out build/upstream --pretty

# Build the original model source on Linux (either fetched or user-provided).
# Use result.source_dir from `ebolasim upstream fetch` output.
ebolasim build /path/to/fetched/source --out build/linux --overwrite --pretty

# Generate a small example input bundle.
ebolasim example tiny examples/tiny --overwrite --pretty

# Inspect the command without running.
ebolasim command examples/tiny/manifest-save.yml --exe build/linux/ebola-spatial-linux --pretty

# Run the compiled executable against the tiny example.
ebolasim run examples/tiny/manifest-save.yml \
  --exe build/linux/ebola-spatial-linux \
  --root examples/tiny \
  --out runs/tiny-save \
  --timeout 30 \
  --pretty

# Summarise generated outputs.
ebolasim outputs summary examples/tiny/outputs/save --pretty

# Check whether this installation already includes a bundled executable.
ebolasim bundled --pretty
```

## Public Python API

```python
from ebolasim_tools import build_model, write_tiny_example, run_model, summarise_outputs

build = build_model("/path/to/source", build_dir="build/linux", overwrite=True)
example = write_tiny_example("examples/tiny", overwrite=True)
run = run_model(example.save_manifest, executable=build.executable, root=example.root, run_dir="runs/tiny")
summary = summarise_outputs("examples/tiny/outputs/save")
```

## CI and release build pipeline

`tools/ci/build_release_bundle.py` is the canonical make-like pipeline used by GitHub Actions:

1. fetch the pinned upstream archive from `legacy-src/upstream.lock.yml`;
2. verify source archive SHA256 and extract source;
3. apply bundled patches and compile `ebola-spatial-linux`;
4. run a seeded tiny simulation smoke check;
5. stage the executable as package data under `src/ebolasim_tools/_bundled/<platform>/`;
6. write reproducibility metadata and checksums to `dist/release-bundle/`.

The CI workflow reruns this bundle build twice and compares binary SHA256 values for reproducibility.

## Remaining completion plan

The outstanding steps to finish this workstream are tracked in `docs/ci-release-completion-plan.md`.

## What changed in this package pass

The previous phase-specific command set has been removed from the public package. The maintained surface is now the user workflow: build, patch, parameters, manifests, commands, runs, outputs, binary inspection and examples.

Historical phase artefacts and generated run folders are not included in the source package. The useful
Linux patch set is preserved under `legacy-src/patches` and as package data.
