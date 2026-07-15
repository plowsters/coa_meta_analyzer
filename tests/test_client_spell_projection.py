from coa_client_extract.artifacts import build_client_spell_records
from coa_client_extract.wdbc import DbcTable


def _table(name, rows, drift=False):
    return DbcTable(layout_name=name, field_count=1, record_size=4, record_count=len(rows), rows=rows, drift=drift)


def _spell_family(*, spell_drift=False, cast_drift=False):
    spell = _table("Spell", [{
        "id": 805775, "name": "Adrenal Venom", "school_mask": 8, "power_type": 3,
        "casting_time_index": 1, "duration_index": 1, "range_index": 1,
        "category": 0, "spell_icon_id": 4583,
    }], drift=spell_drift)
    cast = _table("SpellCastTimes", [{"id": 1, "base_ms": 0}], drift=cast_drift)
    dur = _table("SpellDuration", [{"id": 1, "base_ms": 12000}])
    rng = _table("SpellRange", [{"id": 1, "min_yd": 0, "max_yd": 30}])
    return spell, cast, dur, rng


def test_per_table_confidence_high_when_no_drift():
    spell, cast, dur, rng = _spell_family()
    rec = build_client_spell_records(spell, cast, dur, rng, provenance={"effective_archive": "patch-T.MPQ"})[0]
    by_dbc = rec["provenance"]["schema_match_confidence_by_dbc"]
    assert by_dbc == {"Spell": "high", "SpellCastTimes": "high", "SpellDuration": "high", "SpellRange": "high"}


def test_per_table_confidence_low_for_drifted_table_only():
    spell, cast, dur, rng = _spell_family(cast_drift=True)
    rec = build_client_spell_records(spell, cast, dur, rng, provenance={"effective_archive": "patch-T.MPQ"})[0]
    by_dbc = rec["provenance"]["schema_match_confidence_by_dbc"]
    assert by_dbc["SpellCastTimes"] == "low"
    assert by_dbc["Spell"] == "high"
    assert by_dbc["SpellDuration"] == "high"
    assert by_dbc["SpellRange"] == "high"


def test_per_table_confidence_low_for_spell_drift():
    spell, cast, dur, rng = _spell_family(spell_drift=True)
    rec = build_client_spell_records(spell, cast, dur, rng, provenance={"effective_archive": "patch-T.MPQ"})[0]
    by_dbc = rec["provenance"]["schema_match_confidence_by_dbc"]
    assert by_dbc["Spell"] == "low"
    assert by_dbc["SpellCastTimes"] == "high"  # only Spell drifted; side-tables stay high


def test_absent_table_is_low_confidence():
    spell, cast, dur, rng = _spell_family()
    rec = build_client_spell_records(spell, cast, dur, None, provenance={"effective_archive": "patch-T.MPQ"})[0]
    assert rec["provenance"]["schema_match_confidence_by_dbc"]["SpellRange"] == "low"
