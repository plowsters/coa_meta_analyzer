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


def test_real_spell_family_layouts_are_self_consistent():
    from coa_client_extract.dbc_layouts import SPELL_FAMILY

    for layout in SPELL_FAMILY.values():
        assert layout.expected_record_size == layout.expected_field_count * 4
        for spec in layout.columns.values():
            assert spec.index < layout.expected_field_count
