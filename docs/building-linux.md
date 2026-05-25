# Building on Linux

There are two supported build paths:

1. CI/release path: fetch a pinned public upstream archive from `legacy-src/upstream.lock.yml`,
   verify SHA256, apply patches, compile, run a smoke simulation, and stage bundled artifacts.
2. Local path: run `ebolasim build` against a user-supplied legacy source tree.

The local `ebolasim build` command copies source into the build directory, applies the six Linux
portability patches, then compiles `SpatialSim.c` as C++ together with `binio.cpp` using `g++`.

```bash
ebolasim upstream show --pretty
ebolasim upstream fetch --out build/upstream --pretty
ebolasim build /path/to/legacy-source --out build/linux --overwrite --pretty
```

The build metadata records the exact compiler command, stdout, stderr, target path and executable hash.

For automation, use:

```bash
PYTHONPATH=src python tools/ci/build_release_bundle.py --overwrite
```
