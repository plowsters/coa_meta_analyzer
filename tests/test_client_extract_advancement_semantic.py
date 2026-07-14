import struct

from coa_client_extract.errors import DbcSemanticError, ExtractError
from coa_client_extract.wdbc import parse_positional
from coa_client_extract.dbc_layouts import (
    CHARACTER_ADVANCEMENT_CLASS_TYPES, CharacterAdvancementLayout, CHARACTER_ADVANCEMENT,
)


def test_semantic_error_is_extract_error():
    assert issubclass(DbcSemanticError, ExtractError)


def test_class_types_layout_headers_match_observed_client():
    lt = CHARACTER_ADVANCEMENT_CLASS_TYPES
    assert lt.expected_field_count == 23
    assert lt.expected_record_size == 92
    assert lt.columns["id"].index == 0
    assert lt.columns["name"].index == 1          # verified on real client


def test_advancement_layout_defaults_to_anchors_only():
    lt = CHARACTER_ADVANCEMENT
    assert (lt.node_id_col, lt.spell_id_col, lt.class_type_col) == (0, 5, 32)
    # unresolved fields default to None/() and no field is proven until the decode fills confidence
    assert lt.ae_cost_col is None
    assert lt.connected_node_cols == ()
    assert lt.confidence == {}


def test_parse_positional_returns_index_keyed_rows_and_strings():
    import pytest
    from coa_client_extract.errors import DbcDriftError
    strings = b"\x00Adrenal Venom\x00"
    rec0 = struct.pack("<III", 6086, 1, 805775)   # col1 = string offset 1 -> "Adrenal Venom"
    rec1 = struct.pack("<III", 6096, 0, 12345)
    data = struct.pack("<4sIIII", b"WDBC", 2, 3, 12, len(strings)) + rec0 + rec1 + strings
    raw = parse_positional(data, 3, 12)
    assert raw.drift is False
    assert raw.cell_count == 3 and raw.record_size == 12
    assert raw.rows[0] == {0: 6086, 1: 1, 2: 805775}
    assert raw.rows[1][0] == 6096
    assert raw.strings == strings                 # string block retained for name/icon correlation
    assert raw.read_string(1) == "Adrenal Venom"


def test_parse_positional_rejects_truncation():
    import pytest
    from coa_client_extract.errors import DbcDriftError
    # header claims 2 records * 12 bytes + 4-byte string block, but body is short
    data = struct.pack("<4sIIII", b"WDBC", 2, 3, 12, 4) + struct.pack("<III", 1, 0, 0)
    with pytest.raises(DbcDriftError, match="truncated"):
        parse_positional(data, 3, 12)


def test_parse_positional_rejects_non_divisible_record_size():
    import pytest
    from coa_client_extract.errors import DbcDriftError
    data = struct.pack("<4sIIII", b"WDBC", 0, 3, 13, 0)   # 13 not divisible by 4
    with pytest.raises(DbcDriftError, match="record_size"):
        parse_positional(data, 3, 13)


def test_parse_positional_strict_raises_on_drift():
    import pytest
    from coa_client_extract.errors import DbcDriftError
    data = struct.pack("<4sIIII", b"WDBC", 0, 99, 12, 0)  # field_count 99 != expected 3
    assert parse_positional(data, 3, 12).drift is True    # non-strict: flagged
    with pytest.raises(DbcDriftError):
        parse_positional(data, 3, 12, strict=True)
