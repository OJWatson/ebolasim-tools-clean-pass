# Building on Linux

Use `ebolasim build` with a user-supplied legacy source tree. The command copies the source into the build directory, applies the six Linux portability patches, then compiles `SpatialSim.c` as C++ together with `binio.cpp` using `g++`.

```bash
ebolasim build /path/to/legacy-source --out build/linux --overwrite --pretty
```

The build metadata records the exact compiler command, stdout, stderr, target path and executable hash.
