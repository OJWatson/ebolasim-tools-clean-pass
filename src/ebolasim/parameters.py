"""Reference information for exact EbolaSim C model parameter names."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class ParameterReferenceEntry:
    """One parameter accepted by the upstream C model's ``ReadParams()``."""

    name: str
    category: str
    type: str
    format: str
    required: bool
    default: str | None
    c_target: str | None
    source_lines: tuple[int, ...]
    description: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ParameterReferenceEntry:
        return cls(
            name=str(payload["name"]),
            category=str(payload["category"]),
            type=str(payload["type"]),
            format=str(payload["format"]),
            required=bool(payload["required"]),
            default=None if payload.get("default") is None else str(payload["default"]),
            c_target=None if payload.get("c_target") is None else str(payload["c_target"]),
            source_lines=tuple(int(item) for item in payload.get("source_lines", [])),
            description=str(payload["description"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "type": self.type,
            "format": self.format,
            "required": self.required,
            "default": self.default,
            "c_target": self.c_target,
            "source_lines": list(self.source_lines),
            "description": self.description,
        }


def parameter_reference() -> list[ParameterReferenceEntry]:
    """Return the packaged exact-name parameter reference.

    The names come from the pinned upstream C model's ``ReadParams()``
    implementation after the package patch set has been applied. They are not
    Python aliases.
    """

    data = resources.files("ebolasim.data").joinpath("parameter_reference.json")
    payload = json.loads(data.read_text(encoding="utf-8"))
    return [ParameterReferenceEntry.from_dict(item) for item in payload]


def parameter_reference_markdown() -> str:
    """Render the complete parameter reference as a Markdown table."""

    lines = [
        "| Parameter | Category | Type | Required | Default | Description |",
        "|---|---|---|---|---|---|",
    ]
    for entry in parameter_reference():
        default = "" if entry.default is None else f"`{entry.default}`"
        required = "yes" if entry.required else "no"
        lines.append(
            f"| `{entry.name}` | {entry.category} | {entry.type} | {required} | "
            f"{default} | {entry.description} |"
        )
    return "\n".join(lines)


__all__ = [
    "ParameterReferenceEntry",
    "parameter_reference",
    "parameter_reference_markdown",
]
