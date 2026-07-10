from __future__ import annotations

import struct
from dataclasses import dataclass

from .errors import DbcDriftError

_HEADER = struct.Struct("<4sIIII")  # magic, records, fields, record_size, string_block_size
_MAGIC = b"WDBC"
_CELL = 4  # 3.3.5a DBC cells are 4 bytes


@dataclass(frozen=True)
class FieldSpec:
    index: int
    kind: str  # "int32" | "uint32" | "float" | "str"


@dataclass(frozen=True)
class DbcLayout:
    name: str
    expected_field_count: int
    expected_record_size: int
    columns: dict[str, FieldSpec]


@dataclass(frozen=True)
class DbcTable:
    layout_name: str
    field_count: int
    record_size: int
    record_count: int
    rows: list[dict]
    drift: bool


def _read_cstr(block: bytes, offset: int) -> str:
    end = block.find(b"\x00", offset)
    if end < 0:
        end = len(block)
    return block[offset:end].decode("utf-8", errors="replace")


def parse_dbc(data: bytes, layout: DbcLayout, *, strict: bool = False) -> DbcTable:
    if len(data) < _HEADER.size:
        raise DbcDriftError(f"{layout.name}: file smaller than DBC header")
    magic, record_count, field_count, record_size, string_size = _HEADER.unpack_from(data, 0)
    if magic != _MAGIC:
        raise DbcDriftError(f"{layout.name}: bad magic {magic!r}, expected WDBC")

    drift = field_count != layout.expected_field_count or record_size != layout.expected_record_size
    if drift and strict:
        raise DbcDriftError(
            f"{layout.name}: field_count {field_count} / record_size {record_size} "
            f"!= expected {layout.expected_field_count} / {layout.expected_record_size}"
        )

    records_start = _HEADER.size
    string_start = records_start + record_count * record_size
    expected_len = string_start + string_size
    if len(data) < expected_len:
        raise DbcDriftError(
            f"{layout.name}: truncated ({len(data)} bytes, expected >= {expected_len})"
        )
    string_block = data[string_start:string_start + string_size]

    rows: list[dict] = []
    for i in range(record_count):
        base = records_start + i * record_size
        row: dict = {}
        for col, spec in layout.columns.items():
            off = base + spec.index * _CELL
            if off + _CELL > string_start:
                raise DbcDriftError(f"{layout.name}: column {col!r} index out of record bounds")
            if spec.kind == "str":
                (soff,) = struct.unpack_from("<I", data, off)
                row[col] = _read_cstr(string_block, soff)
            elif spec.kind == "float":
                (row[col],) = struct.unpack_from("<f", data, off)
            elif spec.kind == "uint32":
                (row[col],) = struct.unpack_from("<I", data, off)
            else:  # int32
                (row[col],) = struct.unpack_from("<i", data, off)
        rows.append(row)

    return DbcTable(layout.name, field_count, record_size, record_count, rows, drift)
