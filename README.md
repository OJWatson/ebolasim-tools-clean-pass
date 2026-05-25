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

It does not redistribute the original model source. Provide the legacy source tree yourself when building.

## Quickstart

```bash
python -m pip install -e .

# Build the original model source on Linux.
ebolasim build /path/to/ebolasim_public-master --out build/linux --overwrite --pretty

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
```

## Public Python API

```python
from ebolasim_tools import build_model, write_tiny_example, run_model, summarise_outputs

build = build_model("/path/to/source", build_dir="build/linux", overwrite=True)
example = write_tiny_example("examples/tiny", overwrite=True)
run = run_model(example.save_manifest, executable=build.executable, root=example.root, run_dir="runs/tiny")
summary = summarise_outputs("examples/tiny/outputs/save")
```

## What changed in this package pass

The previous phase-specific command set has been removed from the public package. The maintained surface is now the user workflow: build, patch, parameters, manifests, commands, runs, outputs, binary inspection and examples.

Historical phase artefacts, generated run folders and compiled binaries are not included in the source package. The useful Linux patch set is preserved under `legacy-src/patches` and as package data.
