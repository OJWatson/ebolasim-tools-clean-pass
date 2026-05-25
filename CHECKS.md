# Verification for package consolidation pass

Environment: Linux sandbox, Python 3.13.

Commands run before packaging:

```bash
pytest -q
python -m compileall -q src tests
PYTHONPATH=src python -m ebolasim_tools build /mnt/data/ebolasim_pkg_pass/legacy-src/original --out /mnt/data/ebolasim_clean_checks/build --overwrite --pretty
PYTHONPATH=src python -m ebolasim_tools example tiny /mnt/data/ebolasim_clean_checks/tiny --overwrite --pretty
PYTHONPATH=src python -m ebolasim_tools run /mnt/data/ebolasim_clean_checks/tiny/manifest-save.yml --exe /mnt/data/ebolasim_clean_checks/build/ebola-spatial-linux --root /mnt/data/ebolasim_clean_checks/tiny --out /mnt/data/ebolasim_clean_checks/run-save --timeout 30 --pretty
PYTHONPATH=src python -m ebolasim_tools inspect bundle /mnt/data/ebola_bundle_check --pretty
PYTHONPATH=src python -m ebolasim_tools manifest from-nordkivu /mnt/data/ebola_bundle_check --paramset 188 --out /mnt/data/ebolasim_clean_checks/nordkivu.yml --pretty
```

Results:

```text
pytest: 37 passed
compileall: passed
real legacy build: ok=true, classification=compiled, returncode=0
real tiny executable run: ok=true, classification=completed_with_outputs, returncode=0, output files=3
Nord Kivu bundle inspection: ok=true, parameter files=1, density files=1, network files=1
Nord Kivu manifest creation: paramset=188, CLP values=13, seeds=[98798150, 729101, 17389101, 4797132]
```

The compiled executable hash from the build check was:

```text
d2f78e8a93aa469e10fd69695ccbc6acc98aa050620dc66508df6cc663137901
```

`ruff` and `mkdocs` were also attempted, but neither command is installed in this sandbox.
