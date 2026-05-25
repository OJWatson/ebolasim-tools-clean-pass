"""Lightweight Python wrapper for the legacy ebolasim executable."""

from ._version import __version__
from .binary import DensityHeader, NetworkHeader, inspect_density_header, inspect_network_header
from .build import BuildResult, SourceInspection, build_model, inspect_source
from .bundled import (
    BUNDLED_DIRNAME,
    DEFAULT_BUNDLED_TARGET,
    BundledBinary,
    detect_platform_id,
    resolve_bundled_executable,
)
from .command import (
    CommandPlan,
    LegacyArguments,
    build_command_plan,
    parse_legacy_args,
    validate_argv,
)
from .examples import TinyExample, TinyExampleSpec, tiny_parameters, write_tiny_example
from .manifest import (
    ManifestInputs,
    ManifestLegacyArgs,
    ManifestOutputs,
    ManifestSource,
    RunManifest,
    read_manifest,
    validate_manifest,
    write_manifest,
)
from .nordkivu import BundleInspection, inspect_bundle, manifest_from_bundle
from .outputs import OutputSummary, OutputTable, read_output_table, summarise_outputs
from .params import ParameterSet, tiny_parameter_set
from .patches import apply_patches, read_patch_inventory
from .run import RunResult, run_model
from .upstream import UpstreamFetchResult, UpstreamLock, fetch_upstream_source, read_upstream_lock

__all__ = [
    "BUNDLED_DIRNAME",
    "__version__",
    "apply_patches",
    "BuildResult",
    "build_command_plan",
    "build_model",
    "BundledBinary",
    "BundleInspection",
    "CommandPlan",
    "DEFAULT_BUNDLED_TARGET",
    "detect_platform_id",
    "DensityHeader",
    "fetch_upstream_source",
    "inspect_bundle",
    "inspect_density_header",
    "inspect_network_header",
    "inspect_source",
    "LegacyArguments",
    "ManifestInputs",
    "ManifestLegacyArgs",
    "ManifestOutputs",
    "ManifestSource",
    "manifest_from_bundle",
    "NetworkHeader",
    "OutputSummary",
    "OutputTable",
    "ParameterSet",
    "parse_legacy_args",
    "read_manifest",
    "read_output_table",
    "read_patch_inventory",
    "read_upstream_lock",
    "resolve_bundled_executable",
    "RunManifest",
    "RunResult",
    "run_model",
    "SourceInspection",
    "summarise_outputs",
    "TinyExample",
    "TinyExampleSpec",
    "tiny_parameter_set",
    "tiny_parameters",
    "UpstreamFetchResult",
    "UpstreamLock",
    "validate_argv",
    "validate_manifest",
    "write_manifest",
    "write_tiny_example",
]
