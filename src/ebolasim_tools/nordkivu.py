"""Lightweight adapter for an existing Nord Kivu-style Ebola bundle."""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .bat import find_batch_files, find_paramset_files
from .manifest import (
    ManifestInputs,
    ManifestLegacyArgs,
    ManifestOutputs,
    ManifestSource,
    RunManifest,
    write_manifest,
)

_PERCENT_VAR_RE = re.compile(r"%([^%]+)%")


@dataclass(frozen=True)
class BundleInspection:
    root: str
    ebola_dir: str | None
    batch_files: list[str]
    parameter_files: list[str]
    density_files: list[str]
    network_files: list[str]
    output_dirs: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return (
            self.ebola_dir is not None and bool(self.parameter_files) and bool(self.density_files)
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.ok
        return payload

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def find_ebola_dir(root: str | Path) -> Path | None:
    base = Path(root)
    if base.name.lower().startswith("ebola"):
        return base
    direct = base / "Ebola"
    if direct.is_dir():
        return direct
    for path in sorted(base.glob("Ebola*"), key=lambda item: item.name.lower()):
        if path.is_dir():
            return path
    for path in sorted(base.rglob("Ebola*"), key=lambda item: item.as_posix().lower()):
        if path.is_dir():
            return path
    return None


def inspect_bundle(root: str | Path) -> BundleInspection:
    base = Path(root)
    ebola = find_ebola_dir(base)
    search_root = ebola or base
    batch_files = find_batch_files(search_root)
    parameter_files = find_paramset_files(search_root)
    all_bins = sorted(path for path in search_root.rglob("*.bin") if path.is_file())
    network_files = [
        path for path in all_bins if "network" in path.name.lower() or "net" in path.name.lower()
    ]
    density_files = [path for path in all_bins if path not in network_files]
    output_dirs = sorted(
        path for path in search_root.rglob("*") if path.is_dir() and "output" in path.name.lower()
    )
    warnings: list[str] = []
    if ebola is None:
        warnings.append("could not find an Ebola directory")
    if not parameter_files:
        warnings.append("no parameter files were found")
    if not density_files:
        warnings.append("no density binary files were found")
    return BundleInspection(
        root=base.as_posix(),
        ebola_dir=None if ebola is None else ebola.as_posix(),
        batch_files=[p.as_posix() for p in batch_files],
        parameter_files=[p.as_posix() for p in parameter_files],
        density_files=[p.as_posix() for p in density_files],
        network_files=[p.as_posix() for p in network_files],
        output_dirs=[p.as_posix() for p in output_dirs],
        warnings=warnings,
    )


def _choose_param_file(files: list[str], paramset: int | None) -> str:
    if not files:
        raise FileNotFoundError("no parameter files were found")
    if paramset is not None:
        markers = [f"{paramset}", f"_{paramset}", f"-{paramset}"]
        for item in files:
            name = Path(item).name
            if any(marker in name for marker in markers):
                return item
    return files[0]


def _rel(path: str, root: Path) -> str:
    p = Path(path)
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def _read_batch_sets(path: Path, ebola_root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.lower().startswith("set ") or "=" not in line:
            continue
        key, value = line[4:].split("=", 1)
        values[key.strip().upper()] = _windows_path_to_bundle_relative(value.strip(), ebola_root)
    return values


def _windows_path_to_bundle_relative(value: str, ebola_root: Path) -> str:
    text = value.strip().strip('"').replace("\\", "/")
    for marker in ("/Ebola/", "/Ebola2/"):
        if marker in text:
            return text.split(marker, 1)[1]
    for prefix in ("Ebola/", "Ebola2/"):
        if text.startswith(prefix):
            return text.split(prefix, 1)[1]
    # Already relative or a variable-like token.
    return text


def _paramset_token(token: str) -> int | None:
    try:
        value = float(token)
    except ValueError:
        return None
    if not value.is_integer():
        return None
    return int(value)


def _selected_launch_values(batch_files: list[Path], paramset: int | None) -> list[str] | None:
    launch_files = [p for p in batch_files if "launch" in p.name.lower()]
    for launch in launch_files:
        for raw in launch.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("::") or line.lower().startswith("rem"):
                continue
            tokens = shlex.split(line, posix=False)
            for idx, token in enumerate(tokens):
                token_paramset = _paramset_token(token)
                if token_paramset is not None and (paramset is None or token_paramset == paramset):
                    return tokens[idx:]
    return None


def _substitute_percent_vars(text: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip().upper()
        return variables.get(key, match.group(0))

    return _PERCENT_VAR_RE.sub(replace, text)


def _normalise_batch_flag_key(raw: str) -> str:
    return "s" if raw == "s" else raw.upper()


def _parse_run_batch_manifest(
    root: Path, batch_files: list[Path], paramset: int | None
) -> RunManifest | None:
    run_files = [p for p in batch_files if "run" in p.name.lower()]
    if not run_files:
        return None
    run_file = run_files[0]
    variables = _read_batch_sets(run_file, root)
    selected = _selected_launch_values(batch_files, paramset)
    if selected:
        names = list("ABCDEFGHIJKLMNO")
        variables.update({name: value for name, value in zip(names, selected, strict=False)})
    command_line = None
    for raw in run_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "ebola-spatial" in raw.lower() and re.search(r"/p:", raw, flags=re.IGNORECASE):
            command_line = _substitute_percent_vars(raw.strip(), variables)
            break
    if command_line is None:
        return None
    tokens = shlex.split(command_line, posix=False)
    args = tokens[1:] if tokens else []
    flags: dict[str, str] = {}
    clp: dict[int, str] = {}
    seeds: list[int] = []
    for token in args:
        if token.startswith("/") and ":" in token and token[1:].upper().startswith("CLP"):
            left, value = token[1:].split(":", 1)
            try:
                clp[int(left[3:])] = value
            except ValueError:
                pass
            continue
        if token.startswith("/") and ":" in token:
            key, value = token[1:].split(":", 1)
            flags[_normalise_batch_flag_key(key)] = _windows_path_to_bundle_relative(value, root)
            continue
        try:
            seeds.append(int(token))
        except ValueError:
            pass
    if not {"P", "O", "D"}.issubset(flags):
        return None
    network_mode = "load" if "L" in flags else "save" if "S" in flags else None
    network_file = flags.get("L") or flags.get("S")
    output_base = flags["O"]
    resolved_paramset = int(variables["A"]) if variables.get("A", "").isdigit() else paramset
    return RunManifest(
        inputs=ManifestInputs(
            parameter_file=flags["P"],
            preparameter_file=flags.get("PP"),
            density_file=flags["D"],
            network_file=network_file,
            network_mode=network_mode,
            air_travel_file=flags.get("A"),
            school_file=flags.get("s"),
        ),
        outputs=ManifestOutputs(output_base=output_base, output_dir=str(Path(output_base).parent)),
        executable="ebola-spatial-linux",
        threads=None,
        paramset=resolved_paramset,
        legacy_args=ManifestLegacyArgs(r0_scale=flags.get("R", "1.0"), clp=clp or {1: "0", 2: "0"}),
        seeds=seeds[-4:] if len(seeds) >= 4 else [98798150, 729101, 1234567, 7654321],
        source=ManifestSource(kind="nordkivu_batch", bundle_root=root.as_posix()),
        metadata={"run_batch": run_file.as_posix(), "launch_values": selected or []},
    )


def manifest_from_bundle(
    root: str | Path,
    *,
    paramset: int | None = 188,
    output: str | Path | None = None,
    executable: str = "ebola-spatial-linux",
    threads: int = 1,
) -> RunManifest:
    """Create a best-effort manifest from a Nord Kivu-style bundle.

    When launch/run batch files are present, the selected paramset row is used
    to fill R, CLP values and seed arguments. Otherwise the function falls back
    to the discovered parameter, density and network files.
    """

    inspection = inspect_bundle(root)
    if inspection.ebola_dir is None:
        raise FileNotFoundError("could not find an Ebola directory in the bundle")
    ebola = Path(inspection.ebola_dir)
    batch_paths = [Path(p) for p in inspection.batch_files]
    parsed = _parse_run_batch_manifest(ebola, batch_paths, paramset)
    if parsed is not None:
        manifest = RunManifest(
            inputs=parsed.inputs,
            outputs=parsed.outputs,
            executable=executable,
            threads=threads,
            paramset=parsed.paramset,
            legacy_args=parsed.legacy_args,
            seeds=parsed.seeds,
            source=parsed.source,
            metadata={"inspection": inspection.to_dict(), **parsed.metadata},
        )
    else:
        parameter = _choose_param_file(inspection.parameter_files, paramset)
        if not inspection.density_files:
            raise FileNotFoundError("no density binary files were found")
        density = inspection.density_files[0]
        network = inspection.network_files[0] if inspection.network_files else "Network.bin"
        manifest = RunManifest(
            inputs=ManifestInputs(
                parameter_file=_rel(parameter, ebola),
                density_file=_rel(density, ebola),
                network_file=_rel(network, ebola) if Path(network).is_absolute() else network,
                network_mode="load" if inspection.network_files else "save",
            ),
            outputs=ManifestOutputs(
                output_base=f"outputs/paramset_{paramset or 1}.0", output_dir="outputs"
            ),
            executable=executable,
            threads=threads,
            paramset=paramset,
            legacy_args=ManifestLegacyArgs(r0_scale="1.0", clp={1: "0", 2: "0"}),
            source=ManifestSource(kind="nordkivu_bundle", bundle_root=ebola.as_posix()),
            metadata={"inspection": inspection.to_dict()},
        )
    if output is not None:
        write_manifest(manifest, output)
    return manifest


__all__ = ["BundleInspection", "find_ebola_dir", "inspect_bundle", "manifest_from_bundle"]
