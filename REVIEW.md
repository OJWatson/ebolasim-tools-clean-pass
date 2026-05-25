# Review: ebolasim-tools clean pass (local)

## Findings (highest severity first)

1. **High - Nord Kivu batch parsing is case-sensitive and silently drops launch-derived settings**
   - Code checks only uppercase `/P:` when locating the run command and stores flag keys without normalizing case, then requires uppercase `P/O/D` (`src/ebolasim_tools/nordkivu.py:157`, `src/ebolasim_tools/nordkivu.py:176`, `src/ebolasim_tools/nordkivu.py:183`).
   - If batch files use lowercase flags (valid in Windows batch usage), `_parse_run_batch_manifest` returns `None` and `manifest_from_bundle` falls back to defaults (`src/ebolasim_tools/nordkivu.py:230`, `src/ebolasim_tools/nordkivu.py:243`). This can drop CLP and seed values and change behavior.
   - I reproduced this locally: same bundle with lowercase flags produced `source.kind=nordkivu_bundle` and default CLP/seeds, while uppercase flags produced `source.kind=nordkivu_batch` with parsed CLP/seeds.
   - Test gap: current fixture only uses uppercase `/P:` (`tests/test_nordkivu_cli.py:15`).

2. **Medium - Linux saved-network headers are effectively never detected as linux format**
   - `inspect_network_header` first sets `windows_long_i32` whenever the first 12 bytes look plausible, then only allows `linux_long_i64` when state is still `empty_or_unknown` (`src/ebolasim_tools/binary.py:137`, `src/ebolasim_tools/binary.py:141`, `src/ebolasim_tools/binary.py:146`).
   - This makes linux-format detection unreachable for normal headers; a crafted `<iqq>` header was reported as `windows_long_i32`.
   - Test gap: only empty and Windows paths are covered (`tests/test_examples_binary.py:44`, `tests/test_examples_binary.py:51`).

3. **Medium - `build_model` does not handle compiler timeout and raises instead of returning structured result**
   - `subprocess.run(..., timeout=timeout)` is not wrapped in a `TimeoutExpired` handler (`src/ebolasim_tools/build.py:242`).
   - On timeout, the function raises and does not return `BuildResult`/metadata as callers would expect from the API contract.

4. **Low - Configured lint gate currently fails on source tree**
   - Ruff is configured in `pyproject.toml` (`pyproject.toml:51`) but `python -m ruff check src tests` fails (example violations in `src/ebolasim_tools/__init__.py:3` and `src/ebolasim_tools/__init__.py:6`).

## Verification commands run

- `python -m pytest -q` -> **pass** (`37 passed`, warnings from matplotlib/pyparsing deprecations)
- `python -m compileall -q src tests` -> **pass**
- `python -m ruff check src tests` -> **fail** (lint violations)
- `python -m mypy src/ebolasim_tools` -> **fail** (`No module named mypy` in this environment)
- `python -m build` -> **fail** (`No module named build` in this environment)
- `python3.11 -m pytest -q` -> **fail** (`No module named pytest` in this environment)
- `python3.11 -m compileall -q src tests` -> **pass**
- `python3.11 -m ruff check src tests` -> **fail** (`No module named ruff` in this environment)
- `python3.11 -m mypy src/ebolasim_tools` -> **fail** (`No module named mypy` in this environment)
- `python3.11 -m build` -> **fail** (`No module named build` in this environment)
- `PYTHONPATH=src python -m ebolasim_tools health --pretty` -> **pass**
- `PYTHONPATH=src python -m ebolasim_tools example tiny /tmp/ebolasim_tools_cleanpass_smoke/tiny --pretty` -> **pass**
- `PYTHONPATH=src python -m ebolasim_tools manifest validate /tmp/ebolasim_tools_cleanpass_smoke/tiny/manifest-save.yml --pretty` -> **pass** (`ok: true`)

## Notes

- Review performed locally only. No remote publishing or push actions were performed.
- Package metadata requires Python `>=3.11` (`pyproject.toml:10`), but the only interpreter in this environment with preinstalled pytest/ruff tooling was `python` 3.10.12.
