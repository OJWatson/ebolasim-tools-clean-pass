"""Build concrete command lines for the legacy executable."""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .manifest import RunManifest, read_manifest

_CLP_RE = re.compile(r"^/CLP(\d+):(.+)$", re.IGNORECASE)
_FLAG_RE = re.compile(r"^/([^:]+):(.*)$")


@dataclass(frozen=True)
class LegacyArguments:
    parameter_file: str | None = None
    preparameter_file: str | None = None
    output_base: str | None = None
    density_file: str | None = None
    load_network_file: str | None = None
    save_network_file: str | None = None
    air_travel_file: str | None = None
    school_file: str | None = None
    r0_scale: str | None = None
    clp: dict[int, str] = field(default_factory=dict)
    seeds: list[int] = field(default_factory=list)
    extra_flags: dict[str, list[str]] = field(default_factory=dict)
    extra_positionals: list[str] = field(default_factory=list)

    def to_argv(self) -> list[str]:
        args: list[str] = []
        if self.parameter_file is not None:
            args.append(f"/P:{self.parameter_file}")
        if self.preparameter_file is not None:
            args.append(f"/PP:{self.preparameter_file}")
        if self.output_base is not None:
            args.append(f"/O:{self.output_base}")
        if self.density_file is not None:
            args.append(f"/D:{self.density_file}")
        if self.load_network_file is not None:
            args.append(f"/L:{self.load_network_file}")
        if self.save_network_file is not None:
            args.append(f"/S:{self.save_network_file}")
        if self.air_travel_file is not None:
            args.append(f"/A:{self.air_travel_file}")
        if self.school_file is not None:
            args.append(f"/s:{self.school_file}")
        if self.r0_scale is not None:
            args.append(f"/R:{self.r0_scale}")
        for key in sorted(self.clp):
            args.append(f"/CLP{key}:{self.clp[key]}")
        for key in sorted(self.extra_flags):
            for value in self.extra_flags[key]:
                args.append(f"/{key}:{value}")
        args.extend(str(seed) for seed in self.seeds)
        args.extend(self.extra_positionals)
        return args

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommandValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    network_mode: str | None = None
    seed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommandPlan:
    executable: str
    arguments: list[str]
    environment: dict[str, str] = field(default_factory=dict)
    working_directory: str | None = None
    output_base: str | None = None
    manifest_path: str | None = None

    @property
    def command(self) -> list[str]:
        return [self.executable, *self.arguments]

    @property
    def argv(self) -> list[str]:
        return self.command

    @property
    def shell_command(self) -> str:
        return shlex.join(self.command)

    @property
    def validation(self) -> CommandValidation:
        return validate_argv(self.arguments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executable": self.executable,
            "arguments": list(self.arguments),
            "command": self.command,
            "shell_command": self.shell_command,
            "environment": dict(self.environment),
            "working_directory": self.working_directory,
            "output_base": self.output_base,
            "manifest_path": self.manifest_path,
            "validation": self.validation.to_dict(),
        }

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def parse_legacy_args(arguments: Iterable[str]) -> LegacyArguments:
    parameter_file = preparameter_file = output_base = density_file = None
    load_network_file = save_network_file = air_travel_file = school_file = r0_scale = None
    clp: dict[int, str] = {}
    extra_flags: dict[str, list[str]] = {}
    seeds: list[int] = []
    extra_positionals: list[str] = []
    for token in arguments:
        arg = str(token)
        clp_match = _CLP_RE.match(arg)
        if clp_match:
            clp[int(clp_match.group(1))] = clp_match.group(2)
            continue
        flag_match = _FLAG_RE.match(arg)
        if flag_match:
            raw_flag = flag_match.group(1)
            flag = raw_flag.upper()
            value = flag_match.group(2)
            if flag == "P":
                parameter_file = value
            elif flag == "PP":
                preparameter_file = value
            elif flag == "O":
                output_base = value
            elif flag == "D":
                density_file = value
            elif flag == "L":
                load_network_file = value
            elif raw_flag == "s":
                school_file = value
            elif flag == "S":
                save_network_file = value
            elif flag == "A":
                air_travel_file = value
            elif flag == "R":
                r0_scale = value
            else:
                extra_flags.setdefault(flag, []).append(value)
            continue
        try:
            seeds.append(int(arg))
        except ValueError:
            extra_positionals.append(arg)
    return LegacyArguments(
        parameter_file=parameter_file,
        preparameter_file=preparameter_file,
        output_base=output_base,
        density_file=density_file,
        load_network_file=load_network_file,
        save_network_file=save_network_file,
        air_travel_file=air_travel_file,
        school_file=school_file,
        r0_scale=r0_scale,
        clp=clp,
        seeds=seeds,
        extra_flags=extra_flags,
        extra_positionals=extra_positionals,
    )


def validate_argv(arguments: Iterable[str]) -> CommandValidation:
    args = [str(x) for x in arguments]
    parsed = parse_legacy_args(args)
    errors: list[str] = []
    warnings: list[str] = []
    if not parsed.parameter_file:
        errors.append("missing /P: parameter file")
    if not parsed.output_base:
        errors.append("missing /O: output base")
    if not parsed.density_file:
        errors.append("missing /D: density file")
    has_load = parsed.load_network_file is not None
    has_save = parsed.save_network_file is not None
    if has_load and has_save:
        errors.append("only one of /L: or /S: may be supplied")
    network_mode = "load" if has_load else "save" if has_save else None
    if network_mode is None:
        warnings.append("no network load/save flag supplied")
    if len(parsed.seeds) != 4:
        errors.append(f"expected four seed values, found {len(parsed.seeds)}")
    return CommandValidation(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        network_mode=network_mode,
        seed_count=len(parsed.seeds),
    )


def _coerce_manifest(
    manifest: RunManifest | Mapping[str, Any] | str | Path,
) -> tuple[RunManifest, str | None]:
    if isinstance(manifest, RunManifest):
        return manifest, None
    if isinstance(manifest, Mapping):
        return RunManifest.from_dict(manifest), None
    path = Path(manifest)
    return read_manifest(path), path.as_posix()


def _resolve_path(value: str | Path | None, root: Path | None) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\\", "/")
    path = Path(text)
    if root is not None and not path.is_absolute():
        parts = path.parts
        if parts and parts[0].lower().startswith("ebola"):
            if (root / "Ervebo").is_dir() and len(parts) > 1:
                return root.joinpath(*parts[1:]).as_posix()
            candidate = root.joinpath(*parts)
            if candidate.exists():
                return candidate.as_posix()
            for child in sorted(root.glob("Ebola*"), key=lambda item: item.name.lower()):
                if child.is_dir() and (child / "Ervebo").is_dir() and len(parts) > 1:
                    return child.joinpath(*parts[1:]).as_posix()
        return (root / path).as_posix()
    return path.as_posix()


def arguments_from_manifest(
    manifest: RunManifest, *, root: str | Path | None = None, output_base: str | Path | None = None
) -> LegacyArguments:
    root_path = None if root is None else Path(root)
    network_mode = manifest.inputs.network_mode
    network_file = _resolve_path(manifest.inputs.network_file, root_path)
    return LegacyArguments(
        parameter_file=_resolve_path(manifest.inputs.parameter_file, root_path),
        preparameter_file=_resolve_path(manifest.inputs.preparameter_file, root_path),
        output_base=_resolve_path(output_base or manifest.outputs.output_base, root_path),
        density_file=_resolve_path(manifest.inputs.density_file, root_path),
        load_network_file=network_file if network_mode == "load" else None,
        save_network_file=network_file if network_mode == "save" else None,
        air_travel_file=_resolve_path(manifest.inputs.air_travel_file, root_path),
        school_file=_resolve_path(manifest.inputs.school_file, root_path),
        r0_scale=manifest.legacy_args.r0_scale,
        clp=dict(manifest.legacy_args.clp),
        seeds=list(manifest.seeds),
        extra_flags={k: list(v) for k, v in manifest.legacy_args.extra_flags.items()},
        extra_positionals=list(manifest.legacy_args.extra_positionals),
    )


def build_command_plan(
    manifest: RunManifest | Mapping[str, Any] | str | Path,
    *,
    executable: str | Path | None = None,
    root: str | Path | None = None,
    working_directory: str | Path | None = None,
    output_base: str | Path | None = None,
    threads: int | None = None,
    no_env: bool = False,
) -> CommandPlan:
    run_manifest, manifest_path = _coerce_manifest(manifest)
    manifest_parent = Path(manifest_path).parent if manifest_path else None
    root_path = Path(root) if root is not None else manifest_parent
    args = arguments_from_manifest(run_manifest, root=root_path, output_base=output_base)
    effective_threads = threads if threads is not None else run_manifest.threads
    env = (
        {}
        if no_env or effective_threads is None
        else {"OMP_NUM_THREADS": str(int(effective_threads))}
    )
    exe = str(executable or run_manifest.executable or "ebola-spatial-linux")
    return CommandPlan(
        executable=exe,
        arguments=args.to_argv(),
        environment=env,
        working_directory=None if working_directory is None else str(working_directory),
        output_base=args.output_base,
        manifest_path=manifest_path,
    )


__all__ = [
    "CommandPlan",
    "CommandValidation",
    "LegacyArguments",
    "arguments_from_manifest",
    "build_command_plan",
    "parse_legacy_args",
    "validate_argv",
]
