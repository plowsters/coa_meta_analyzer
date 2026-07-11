import struct

import pytest

from coa_client_extract.errors import DbcDriftError
from coa_client_extract.wdbc import DbcLayout, FieldSpec, parse_dbc


def _build_dbc(rows, field_count, record_size, strings=b"\x00"):
    # rows: list of tuples of 4-byte-packable cells already encoded as bytes
    record_count = len(rows)
    header = struct.pack(
        "<4sIIII", b"WDBC", record_count, field_count, record_size, len(strings)
    )
    body = b"".join(rows)
    return header + body + strings


def _layout():
    return DbcLayout(
        name="Toy",
        expected_field_count=3,
        expected_record_size=12,
        columns={
            "id": FieldSpec(0, "uint32"),
            "name": FieldSpec(1, "str"),
            "value": FieldSpec(2, "int32"),
        },
    )


def test_parses_records_and_strings():
    strings = b"\x00Adrenal Venom\x00"
    name_offset = 1  # position of "Adrenal Venom" within the string block
    row = struct.pack("<Iii", 805775, name_offset, -5)
    data = _build_dbc([row], field_count=3, record_size=12, strings=strings)

    table = parse_dbc(data, _layout())

    assert table.record_count == 1
    assert table.drift is False
    assert table.rows[0] == {"id": 805775, "name": "Adrenal Venom", "value": -5}


def test_drift_flagged_when_header_field_count_differs():
    row = struct.pack("<IiI", 1, 0, 0)
    # header claims 4 fields / 16 bytes but layout expects 3 / 12
    data = _build_dbc([row + b"\x00\x00\x00\x00"], field_count=4, record_size=16)

    table = parse_dbc(data, _layout())
    assert table.drift is True  # tolerant read still returns the columns of interest

    with pytest.raises(DbcDriftError):
        parse_dbc(data, _layout(), strict=True)


def test_truncated_file_raises():
    row = struct.pack("<IiI", 1, 0, 0)
    data = _build_dbc([row], field_count=3, record_size=12)[:-6]  # chop string block + tail
    with pytest.raises(DbcDriftError):
        parse_dbc(data, _layout())


def test_unknown_field_kind_raises_value_error():
    # An unrecognized cell kind is a layout-definition bug and must be rejected loudly,
    # not silently decoded as int32 (and it must surface even with zero records).
    bad_layout = DbcLayout(
        name="Toy", expected_field_count=3, expected_record_size=12,
        columns={"id": FieldSpec(0, "uint32"), "mystery": FieldSpec(1, "int16")},
    )
    data = _build_dbc([], field_count=3, record_size=12)
    with pytest.raises(ValueError):
        parse_dbc(data, bad_layout)


def test_column_index_beyond_record_boundary_raises():
    # A column whose index reaches past its own record must raise DbcDriftError, scoped to
    # the per-record boundary (not the end of all records).
    layout = DbcLayout(
        name="Toy", expected_field_count=2, expected_record_size=8,
        columns={"id": FieldSpec(0, "uint32"), "past_end": FieldSpec(2, "uint32")},
    )
    rows = [struct.pack("<II", 1, 10), struct.pack("<II", 2, 20)]  # two 8-byte records
    data = _build_dbc(rows, field_count=2, record_size=8)
    with pytest.raises(DbcDriftError):
        parse_dbc(data, layout)


def test_real_spell_family_layouts_are_self_consistent():
    from coa_client_extract.dbc_layouts import SPELL_FAMILY

    for layout in SPELL_FAMILY.values():
        assert layout.expected_record_size == layout.expected_field_count * 4
        for spec in layout.columns.values():
            assert spec.index < layout.expected_field_count
