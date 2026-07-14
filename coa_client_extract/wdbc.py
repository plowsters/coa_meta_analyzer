from __future__ import annotations

import struct
from dataclasses import dataclass

from .errors import DbcDriftError

_HEADER = struct.Struct("<4sIIII")  # magic, records, fields, record_size, string_block_size
_MAGIC = b"WDBC"
_CELL = 4  # 3.3.5a DBC cells are 4 bytes
_VALID_KINDS = frozenset({"int32", "uint32", "float", "str"})


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

    # An unrecognized cell kind is a layout-definition bug (caller error), not client drift;
    # validate once up front so it surfaces even for a zero-record table.
    for col, spec in layout.columns.items():
        if spec.kind not in _VALID_KINDS:
            raise ValueError(
                f"{layout.name}: column {col!r} has unknown FieldSpec.kind {spec.kind!r} "
                f"(expected one of {sorted(_VALID_KINDS)})"
            )

    rows: list[dict] = []
    for i in range(record_count):
        base = records_start + i * record_size
        record_end = base + record_size
        row: dict = {}
        for col, spec in layout.columns.items():
            off = base + spec.index * _CELL
            if off + _CELL > record_end:
                raise DbcDriftError(f"{layout.name}: column {col!r} index out of record bounds")
            if spec.kind == "str":
                (soff,) = struct.unpack_from("<I", data, off)
                row[col] = _read_cstr(string_block, soff)
            elif spec.kind == "float":
                (row[col],) = struct.unpack_from("<f", data, off)
            elif spec.kind == "uint32":
                (row[col],) = struct.unpack_from("<I", data, off)
            else:  # "int32" — the only remaining valid kind after the check above
                (row[col],) = struct.unpack_from("<i", data, off)
        rows.append(row)

    return DbcTable(layout.name, field_count, record_size, record_count, rows, drift)


@dataclass(frozen=True)
class PositionalDbc:
    field_count: int          # logical field count from the header (may exceed cell_count)
    cell_count: int           # record_size // 4 — the number of addressable 4-byte cells
    record_size: int
    record_count: int
    rows: list[dict]          # each row: {cell_index: uint32_value}
    strings: bytes            # retained string block, for name/icon correlation
    drift: bool

    def read_string(self, offset: int) -> str:
        if offset <= 0 or offset >= len(self.strings):
            return ""
        end = self.strings.find(b"\x00", offset)
        if end < 0:
            end = len(self.strings)
        return self.strings[offset:end].decode("utf-8", "replace")


def parse_positional(data: bytes, expected_field_count: int, expected_record_size: int,
                     *, strict: bool = False) -> PositionalDbc:
    """Decode every record as raw {cell_index: uint32} cells plus the string block, without a named
    layout. Used for wide custom tables (CharacterAdvancement) addressed by index during decode.

    Note the logical/raw distinction: the real CharacterAdvancement header reports field_count 179
    while record_size 692 holds only 173 four-byte cells. Cells are addressed 0..cell_count-1;
    field_count is preserved for provenance and drift, not for indexing."""
    if len(data) < _HEADER.size:
        raise DbcDriftError("file smaller than DBC header")
    magic, record_count, field_count, record_size, string_size = _HEADER.unpack_from(data, 0)
    if magic != _MAGIC:
        raise DbcDriftError(f"bad magic {magic!r}, expected WDBC")
    if record_size % _CELL != 0:
        raise DbcDriftError(f"record_size {record_size} not a multiple of {_CELL}")
    records_start = _HEADER.size
    string_start = records_start + record_count * record_size
    expected_len = string_start + string_size
    if len(data) < expected_len:
        raise DbcDriftError(f"truncated ({len(data)} bytes, expected >= {expected_len})")
    drift = field_count != expected_field_count or record_size != expected_record_size
    if drift and strict:
        raise DbcDriftError(
            f"field_count {field_count} / record_size {record_size} != expected "
            f"{expected_field_count} / {expected_record_size}")
    strings = data[string_start:string_start + string_size]
    cell_count = record_size // _CELL
    rows: list[dict] = []
    for i in range(record_count):
        base = records_start + i * record_size
        rows.append({c: struct.unpack_from("<I", data, base + c * _CELL)[0] for c in range(cell_count)})
    return PositionalDbc(field_count, cell_count, record_size, record_count, rows, strings, drift)
