"""Portable run manifests for the legacy ebolasim executable."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

MANIFEST_SCHEMA_VERSION = 1
DEFAULT_ENGINE = "legacy_exec"
DEFAULT_COUNTRY = "COUNTRY_WA"
DEFAULT_SEEDS = [98798150, 729101, 1234567, 7654321]


def _drop_empty(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None and v != {} and v != []}


def normalise_country(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return DEFAULT_COUNTRY
    text = str(value).strip().upper()
    if text.startswith("COUNTRY_"):
        return text
    return f"COUNTRY_{text}"


def normalise_path(value: str | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip('"').strip("'").replace("\\", "/")
    marker = "/Ebola/"
    if marker in text:
        return "Ebola/" + text.split(marker, 1)[1]
    if text.startswith("//") and "Ebola/" in text:
        return "Ebola/" + text.split("Ebola/", 1)[1]
    return text


@dataclass(frozen=True)
class ManifestInputs:
    parameter_file: str
    density_file: str
    preparameter_file: str | None = None
    network_file: str | None = None
    network_mode: str | None = None
    air_travel_file: str | None = None
    school_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty(asdict(self))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ManifestInputs:
        return cls(
            parameter_file=str(data["parameter_file"]),
            density_file=str(data["density_file"]),
            preparameter_file=normalise_path(data.get("preparameter_file")),
            network_file=normalise_path(data.get("network_file")),
            network_mode=None
            if data.get("network_mode") is None
            else str(data.get("network_mode")),
            air_travel_file=normalise_path(data.get("air_travel_file")),
            school_file=normalise_path(data.get("school_file")),
        )


@dataclass(frozen=True)
class ManifestOutputs:
    output_base: str
    output_dir: str | None = None
    reference_output_dir: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty(asdict(self))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ManifestOutputs:
        return cls(
            output_base=str(data["output_base"]),
            output_dir=normalise_path(data.get("output_dir")),
            reference_output_dir=normalise_path(data.get("reference_output_dir")),
        )


@dataclass(frozen=True)
class ManifestLegacyArgs:
    r0_scale: str | None = "1.0"
    clp: dict[int, str] = field(default_factory=lambda: {1: "0", 2: "0"})
    extra_flags: dict[str, list[str]] = field(default_factory=dict)
    extra_positionals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "r0_scale": self.r0_scale,
                "CLP": {str(k): str(v) for k, v in sorted(self.clp.items())},
                "extra_flags": self.extra_flags,
                "extra_positionals": self.extra_positionals,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> ManifestLegacyArgs:
        if not data:
            return cls()
        raw_clp = data.get("CLP", data.get("clp", {}))
        if not isinstance(raw_clp, Mapping):
            raise ValueError("legacy_args.CLP must be a mapping")
        return cls(
            r0_scale=None if data.get("r0_scale") is None else str(data.get("r0_scale")),
            clp={int(k): str(v) for k, v in raw_clp.items()},
            extra_flags={
                str(k): [str(x) for x in v] for k, v in dict(data.get("extra_flags", {})).items()
            },
            extra_positionals=[str(x) for x in data.get("extra_positionals", [])],
        )


@dataclass(frozen=True)
class ManifestSource:
    kind: str = "manual"
    bundle_root: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty(asdict(self))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> ManifestSource:
        data = {} if data is None else data
        return cls(
            kind=str(data.get("kind", "manual")),
            bundle_root=normalise_path(data.get("bundle_root")),
            notes=None if data.get("notes") is None else str(data.get("notes")),
        )


@dataclass(frozen=True)
class RunManifest:
    inputs: ManifestInputs
    outputs: ManifestOutputs
    schema_version: int = MANIFEST_SCHEMA_VERSION
    engine: str = DEFAULT_ENGINE
    country: str = DEFAULT_COUNTRY
    threads: int | None = 1
    paramset: int | None = None
    executable: str | None = "ebola-spatial-linux"
    legacy_args: ManifestLegacyArgs = field(default_factory=ManifestLegacyArgs)
    seeds: list[int] = field(default_factory=lambda: list(DEFAULT_SEEDS))
    source: ManifestSource = field(default_factory=ManifestSource)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "schema_version": self.schema_version,
                "engine": self.engine,
                "country": normalise_country(self.country),
                "threads": self.threads,
                "paramset": self.paramset,
                "executable": self.executable,
                "inputs": self.inputs.to_dict(),
                "outputs": self.outputs.to_dict(),
                "legacy_args": self.legacy_args.to_dict(),
                "seeds": list(self.seeds),
                "source": self.source.to_dict(),
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunManifest:
        return cls(
            schema_version=int(data.get("schema_version", MANIFEST_SCHEMA_VERSION)),
            engine=str(data.get("engine", DEFAULT_ENGINE)),
            country=normalise_country(data.get("country")),
            threads=None if data.get("threads") is None else int(data.get("threads")),
            paramset=None if data.get("paramset") is None else int(data.get("paramset")),
            executable=None if data.get("executable") is None else str(data.get("executable")),
            inputs=ManifestInputs.from_dict(data["inputs"]),
            outputs=ManifestOutputs.from_dict(data["outputs"]),
            legacy_args=ManifestLegacyArgs.from_dict(data.get("legacy_args")),
            seeds=[int(x) for x in data.get("seeds", DEFAULT_SEEDS)],
            source=ManifestSource.from_dict(data.get("source")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False)

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_yaml(), encoding="utf-8")
        return target


def read_manifest(path: str | Path) -> RunManifest:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"manifest did not contain a mapping: {path}")
    return RunManifest.from_dict(payload)


def write_manifest(manifest: RunManifest, path: str | Path) -> Path:
    return manifest.write(path)


def validate_manifest(manifest: RunManifest) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if manifest.engine != DEFAULT_ENGINE:
        errors.append(f"unsupported engine: {manifest.engine}")
    if not manifest.inputs.parameter_file:
        errors.append("inputs.parameter_file is required")
    if not manifest.inputs.density_file:
        errors.append("inputs.density_file is required")
    mode = manifest.inputs.network_mode
    if mode not in {None, "load", "save"}:
        errors.append("inputs.network_mode must be load, save, or omitted")
    if mode and not manifest.inputs.network_file:
        errors.append("inputs.network_file is required when network_mode is set")
    if len(manifest.seeds) != 4:
        errors.append("exactly four random seeds are required")
    if manifest.threads is not None and manifest.threads < 1:
        errors.append("threads must be positive")
    return not errors, errors


__all__ = [
    "DEFAULT_COUNTRY",
    "DEFAULT_ENGINE",
    "DEFAULT_SEEDS",
    "MANIFEST_SCHEMA_VERSION",
    "ManifestInputs",
    "ManifestLegacyArgs",
    "ManifestOutputs",
    "ManifestSource",
    "RunManifest",
    "normalise_country",
    "normalise_path",
    "read_manifest",
    "validate_manifest",
    "write_manifest",
]
