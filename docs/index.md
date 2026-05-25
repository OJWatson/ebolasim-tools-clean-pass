# ebolasim-tools

`ebolasim-tools` is a thin Python wrapper around the legacy `ebola-spatial` executable. It does not reimplement the model. It prepares inputs, builds command lines, runs the executable and reads outputs.

Main commands:

```text
ebolasim upstream show
ebolasim upstream fetch --out build/upstream
ebolasim build SOURCE_DIR --out build/linux
ebolasim bundled
ebolasim example tiny examples/tiny
ebolasim command examples/tiny/manifest-save.yml --exe build/linux/ebola-spatial-linux
ebolasim run examples/tiny/manifest-save.yml --exe build/linux/ebola-spatial-linux --root examples/tiny --out runs/tiny
ebolasim outputs summary examples/tiny/outputs/save
```
