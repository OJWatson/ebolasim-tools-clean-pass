#!/usr/bin/env python3
"""Generate the packaged parameter reference from upstream ``ReadParams()``.

This script is intentionally deterministic: exact parameter names come from the
upstream C source, while descriptions are conservative wording derived from the
name and grouped by model subsystem.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

CALL_RE = re.compile(
    r"(?P<function>GetInputParameter2?|GetInputParameter)\s*"
    r"\([^\"\n]*\"(?P<name>[^\"]+)\"\s*,\s*\"(?P<format>%[^\"]+)\""
)


CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Contact tracing", ("contact tracing", "contact traced", "contact trace")),
    (
        "Vaccination and prophylaxis",
        (
            "vacc",
            "immunisation",
            "immunization",
            "sia",
            "prophylaxis",
            "ring",
            "doses",
            "phial",
        ),
    ),
    (
        "Clinical pathways and outcomes",
        (
            "hospital",
            "hospitalisation",
            "hospitalization",
            "etu",
            "case detection",
            "detected",
            "mortality",
            "funeral",
            "burial",
            "symptom",
            "latent",
            "death",
            "infectious period",
            "infectiousness profile",
            "incubation",
        ),
    ),
    (
        "Transmission",
        (
            "reproduction",
            "infectiousness",
            "susceptibility",
            "spatial contact",
            "seasonality",
            "prevalence dependent",
            "mutation",
            "transmission",
            "attack rate",
        ),
    ),
    ("Households", ("household", "income")),
    (
        "Administrative units and countries",
        ("administrative", "adunit", "country", "province", "capital city"),
    ),
    ("Age and demography", ("age", "waifw", "demography", "immunity", "routine")),
    (
        "Places, travel, and mixing groups",
        (
            "place",
            "school",
            "airport",
            "air travel",
            "hotel",
            "journey",
            "travel",
            "key worker",
            "key workers",
            "mixing",
        ),
    ),
    (
        "Interventions and behaviour",
        (
            "closure",
            "social distancing",
            "quarantine",
            "isolation",
            "treatment",
            "intervention",
            "compliant",
        ),
    ),
    (
        "Seeding and importation",
        ("seed", "initial infection", "infecteds", "import", "imported"),
    ),
    (
        "Spatial grid, kernels, and maps",
        (
            "kernel",
            "spatial",
            "micro-cell",
            "cell",
            "bitmap",
            "grid",
            "longitude",
            "latitude",
            "road",
            "radius",
            "bounding box",
        ),
    ),
    ("Outputs and diagnostics", ("output", "record", "file", "matrix", "summary")),
]


def _clean_code_line(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("//"):
        return ""
    return stripped.split("//", 1)[0].strip()


def _parameter_type(format_code: str) -> str:
    if format_code == "%i":
        return "integer"
    if format_code == "%lf":
        return "floating point"
    if format_code == "%s":
        return "string"
    return format_code


def _category(name: str) -> str:
    lower = name.lower()
    for category, needles in CATEGORY_RULES:
        if any(needle in lower for needle in needles):
            return category
    return "Core simulation control"


def _noun_phrase(name: str) -> str:
    text = name.strip()
    prefixes = (
        "Include ",
        "Do ",
        "Output ",
        "Number of ",
        "Proportion of ",
        "Relative ",
        "Duration of ",
        "Delay to ",
        "Start time for ",
        "Time to ",
        "Minimum ",
        "Maximum ",
        "Mean ",
        "Median ",
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text[:1].lower() + text[1:]


def _description(name: str, type_name: str) -> str:
    lower = name.lower()
    subject = _noun_phrase(name)
    if name.startswith("Include "):
        return f"Toggle controlling whether {subject} is included in the simulation."
    if name.startswith("Do "):
        return f"Toggle controlling whether the model applies {subject}."
    if name.startswith("Output "):
        return f"Toggle or setting controlling whether {subject} is written to output files."
    if name.startswith("Number of "):
        return f"Count used by the model for {subject}."
    if name.startswith("Proportion of "):
        return f"Fraction or probability assigned to {subject}."
    if name.startswith("Relative "):
        return f"Multiplier relative to baseline for {subject}."
    if name.startswith("Duration of "):
        return f"Duration, in model time units unless otherwise stated, for {subject}."
    if name.startswith("Delay to "):
        return f"Delay, in model time units unless otherwise stated, before {subject}."
    if name.startswith("Start time for "):
        return f"Model time at which {subject} starts."
    if name.startswith("Time to ") or name.startswith("Time when "):
        return f"Model time controlling when {subject} occurs."
    if name.startswith("Minimum "):
        return f"Lower bound used for {subject}."
    if name.startswith("Maximum "):
        return f"Upper bound used for {subject}."
    if name.startswith("Mean "):
        return f"Mean value used for {subject}."
    if name.startswith("Median "):
        return f"Median value used for {subject}."
    if "distribution" in lower or "profile" in lower or "matrix" in lower:
        return f"Vector or matrix parameter defining the {subject}."
    if "rate" in lower:
        return f"Rate parameter controlling {subject}."
    if "threshold" in lower:
        return f"Threshold value controlling {subject}."
    if "probability" in lower:
        return f"Probability assigned to {subject}."
    if "scale" in lower or "scaling" in lower:
        return f"Scale parameter for {subject}."
    return f"{type_name.capitalize()} parameter controlling {subject}."


def _default_from_line(code: str) -> str | None:
    match = re.search(r"\)\)\s*([A-Za-z_][A-Za-z0-9_.\[\]]*)\s*=\s*([^;]+);", code)
    if match:
        return match.group(2).strip()
    return None


def _target_from_line(code: str) -> str | None:
    match = re.search(r"\(void\s*\*\)\s*&?\s*\(?\s*([A-Za-z_][A-Za-z0-9_.]*)", code)
    if not match:
        return None
    return match.group(1)


def extract_parameter_reference(source: Path) -> list[dict[str, Any]]:
    entries: OrderedDict[str, dict[str, Any]] = OrderedDict()
    lines = source.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line_number, raw_line in enumerate(lines, 1):
        code = _clean_code_line(raw_line)
        if not code:
            continue
        match = CALL_RE.search(code)
        if not match:
            continue
        name = match.group("name")
        format_code = match.group("format")
        function = match.group("function")
        required = function == "GetInputParameter"
        type_name = _parameter_type(format_code)
        entry = entries.setdefault(
            name,
            {
                "name": name,
                "category": _category(name),
                "type": type_name,
                "format": format_code,
                "required": required,
                "default": _default_from_line(code),
                "c_target": _target_from_line(code),
                "source_lines": [],
                "description": _description(name, type_name),
            },
        )
        entry["required"] = bool(entry["required"] or required)
        if entry["default"] is None:
            entry["default"] = _default_from_line(code)
        if entry["c_target"] is None:
            entry["c_target"] = _target_from_line(code)
        entry["source_lines"].append(line_number)
    return list(entries.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to upstream SpatialSim.c after package patches have been applied.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("src/ebolasim/data/parameter_reference.json"),
    )
    args = parser.parse_args()
    reference = extract_parameter_reference(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(reference, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(reference)} parameters to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
