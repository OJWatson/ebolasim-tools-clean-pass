"""Small binary probes for C model density and saved-network files."""

from __future__ import annotations

import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DENSITY_SENTINEL = 0xF0F0F0F0
DENSITY_HEADER = struct.Struct("<II")
DENSITY_RECORD = struct.Struct("<dddii")
NETWORK_WINDOWS_HEADER = struct.Struct("<iii")
NETWORK_LINUX_LONG64_HEADER = struct.Struct("<iqq")
MAX_PLAUSIBLE_SEED = 2_147_483_647


class BinaryFormatError(ValueError):
    """Raised when a C model binary probe cannot read the requested file."""


@dataclass(frozen=True)
class DensityRecordPreview:
    x: float
    y: float
    population: float
    country: int
    admin_unit: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DensityHeader:
    path: str
    size_bytes: int
    sentinel: int | None
    record_count: int | None
    record_size_bytes: int
    expected_size_bytes: int | None
    size_matches_record_count: bool | None
    preview_records: list[DensityRecordPreview]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return self.sentinel == DENSITY_SENTINEL and self.size_matches_record_count is not False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.ok
        payload["sentinel_hex"] = None if self.sentinel is None else hex(self.sentinel)
        payload["preview_records"] = [record.to_dict() for record in self.preview_records]
        return payload

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


@dataclass(frozen=True)
class NetworkHeader:
    path: str
    size_bytes: int
    n_place_types_windows: int | None
    seed1_windows_long_i32: int | None
    seed2_windows_long_i32: int | None
    seed1_linux_long_i64: int | None
    seed2_linux_long_i64: int | None
    detected_format: str
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return self.detected_format != "empty_or_unknown"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.ok
        return payload

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None, sort_keys=True)


def inspect_density_header(path: str | Path, *, preview: int = 3) -> DensityHeader:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    size = p.stat().st_size
    warnings: list[str] = []
    sentinel: int | None = None
    count: int | None = None
    expected: int | None = None
    matches: bool | None = None
    records: list[DensityRecordPreview] = []
    with p.open("rb") as handle:
        header = handle.read(DENSITY_HEADER.size)
        if len(header) < DENSITY_HEADER.size:
            warnings.append("file is shorter than the density header")
        else:
            sentinel, count = DENSITY_HEADER.unpack(header)
            expected = DENSITY_HEADER.size + count * DENSITY_RECORD.size
            matches = expected == size
            if sentinel != DENSITY_SENTINEL:
                warnings.append("density sentinel does not match 0xf0f0f0f0")
            if not matches:
                warnings.append("file size does not match the declared record count")
            for _ in range(max(0, min(preview, count))):
                raw = handle.read(DENSITY_RECORD.size)
                if len(raw) != DENSITY_RECORD.size:
                    break
                records.append(DensityRecordPreview(*DENSITY_RECORD.unpack(raw)))
    return DensityHeader(
        path=p.as_posix(),
        size_bytes=size,
        sentinel=sentinel,
        record_count=count,
        record_size_bytes=DENSITY_RECORD.size,
        expected_size_bytes=expected,
        size_matches_record_count=matches,
        preview_records=records,
        warnings=warnings,
    )


def inspect_network_header(path: str | Path) -> NetworkHeader:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    size = p.stat().st_size
    data = p.read_bytes()[: NETWORK_LINUX_LONG64_HEADER.size]
    warnings: list[str] = []
    npt_w = seed1_w = seed2_w = None
    seed1_l = seed2_l = None
    detected = "empty_or_unknown"
    windows_plausible = False
    linux_plausible = False
    if len(data) >= NETWORK_WINDOWS_HEADER.size:
        npt_w, seed1_w, seed2_w = NETWORK_WINDOWS_HEADER.unpack(data[: NETWORK_WINDOWS_HEADER.size])
        windows_payload = size - NETWORK_WINDOWS_HEADER.size
        windows_plausible = 1 <= npt_w <= 64 and windows_payload >= 0
    else:
        warnings.append("file is shorter than a Windows saved-network header")
    if len(data) >= NETWORK_LINUX_LONG64_HEADER.size:
        npt_l, seed1_l, seed2_l = NETWORK_LINUX_LONG64_HEADER.unpack(
            data[: NETWORK_LINUX_LONG64_HEADER.size]
        )
        linux_plausible = (
            1 <= npt_l <= 64
            and 0 <= seed1_l <= MAX_PLAUSIBLE_SEED
            and 0 <= seed2_l <= MAX_PLAUSIBLE_SEED
        )
    if linux_plausible:
        detected = "linux_long_i64"
        if windows_plausible:
            warnings.append("header is also plausible as Windows; preferring Linux long64")
    elif windows_plausible:
        detected = "windows_long_i32"
    return NetworkHeader(
        path=p.as_posix(),
        size_bytes=size,
        n_place_types_windows=npt_w,
        seed1_windows_long_i32=seed1_w,
        seed2_windows_long_i32=seed2_w,
        seed1_linux_long_i64=seed1_l,
        seed2_linux_long_i64=seed2_l,
        detected_format=detected,
        warnings=warnings,
    )


def write_density_file(
    path: str | Path, records: list[tuple[float, float, float, int, int]]
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        handle.write(DENSITY_HEADER.pack(DENSITY_SENTINEL, len(records)))
        for record in records:
            handle.write(DENSITY_RECORD.pack(*record))
    return target


__all__ = [
    "BinaryFormatError",
    "DENSITY_SENTINEL",
    "DensityHeader",
    "DensityRecordPreview",
    "NetworkHeader",
    "inspect_density_header",
    "inspect_network_header",
    "write_density_file",
]
