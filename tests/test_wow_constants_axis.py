import struct

import pytest

from coa_client_extract.wow_constants import load_authored_input, load_axis_policy, map_table_entries
from coa_client_extract.wdbc import parse_gametable


def _implicit(values):
    return struct.pack("<4sIIII", b"WDBC", len(values), 1, 4, 0) + b"".join(
        struct.pack("<f", v) for v in values)


def _explicit(pairs):  # list of (id, value)
    body = b"".join(struct.pack("<If", i, v) for i, v in pairs)
    return struct.pack("<4sIIII", b"WDBC", len(pairs), 2, 8, 0) + body


def _policy():
    return load_axis_policy(load_authored_input("gt_axis_policy").payload)


def test_rating_by_level_drops_padding():
    layouts, ls, rs = _policy()
    table = parse_gametable(_implicit([float(i) for i in range(32 * 100)]),
                            physical_form="implicit_row", expected_field_count=1, expected_record_size=4)
    entries, counts = map_table_entries(layouts["combat_ratings"], table, class_roster=[],
                                        level_stride=ls, rating_stride=rs)
    assert counts == {"source_records": 3200, "emitted_entries": 2500, "padding_records": 700}
    assert next(e for e in entries if e["rating_id"] == 6 and e["level"] == 60)["value"] == 659.0


def test_class_rating_scalar_plus_one_offset_and_sparse_roster():
    # The frozen real-client policy declares gtOCTClassCombatRatingScalar as explicit_id (id@0,
    # value@1); build the fixture to match, with value == id so the +1-offset index is asserted.
    layouts, ls, rs = _policy()
    assert layouts["class_combat_rating_scalar"].key_source == "explicit_id"
    table = parse_gametable(_explicit([(k, float(k)) for k in range(12 * 32)]),
                            physical_form="explicit_id", expected_field_count=2, expected_record_size=8,
                            value_cell=1, id_cell=0)
    entries, _ = map_table_entries(layouts["class_combat_rating_scalar"], table, class_roster=[1, 2, 11],
                                   level_stride=ls, rating_stride=rs)
    assert next(e for e in entries if e["wow_class_id"] == 1 and e["rating_id"] == 6)["value"] == 7.0
    assert all(e["wow_class_id"] != 10 for e in entries)


def test_explicit_id_uses_id_not_ordinal_and_rejects_duplicates():
    layouts, ls, rs = _policy()
    layout = layouts["combat_ratings"].__class__(
        **{**layouts["combat_ratings"].__dict__, "physical_form": "explicit_id",
           "key_source": "explicit_id", "expected_field_count": 2, "expected_record_size": 8,
           "value_cell": 1, "id_cell": 0})
    pairs = [(659, 99.0), (0, 1.0)]
    table = parse_gametable(_explicit(pairs), physical_form="explicit_id", expected_field_count=2,
                            expected_record_size=8, value_cell=1, id_cell=0)
    entries, _ = map_table_entries(layout, table, class_roster=[], level_stride=ls, rating_stride=rs)
    assert next(e for e in entries if e["rating_id"] == 6 and e["level"] == 60)["value"] == 99.0
    dup = parse_gametable(_explicit([(5, 1.0), (5, 2.0)]), physical_form="explicit_id",
                          expected_field_count=2, expected_record_size=8, value_cell=1, id_cell=0)
    with pytest.raises(ValueError):
        map_table_entries(layout, dup, class_roster=[], level_stride=ls, rating_stride=rs)
