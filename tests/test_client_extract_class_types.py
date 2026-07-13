import pytest

from coa_client_extract.class_types import (
    ClassType, resolve_class_types, resolve_tab_types,
    assert_playable_cardinality, DISPLAY_ALIASES, COA_SENTINEL_ID,
)


class _Table:
    """Minimal stand-in for wdbc.DbcTable: only .rows is used here."""
    def __init__(self, rows): self.rows = rows


def _class_rows():
    # (id, name) pairs mirroring CharacterAdvancementClassTypes bands.
    named = {
        2: "Hunter", 11: "DeathKnight", 12: "General", 13: "Hero",
        14: "Barbarian", 15: "WitchDoctor", 16: "DemonHunter", 21: "Monk",
        22: "SonOfArugal", 33: "Venomancer", 34: "Runemaster",
        35: "ConquestOfAzeroth", 36: "RebornHunter", 46: "RebornGeneral",
    }
    # fill the whole 2..46 range so the cardinality check has all playable ids
    for i in range(2, 47):
        named.setdefault(i, f"Class{i}")
    return _Table([{"id": i, "name": named[i]} for i in sorted(named)])


def test_resolves_kind_bands_and_sentinel():
    resolved = resolve_class_types(_class_rows())
    assert resolved[33].kind == "coa_class"
    assert resolved[33].display == "Venomancer"
    assert resolved[COA_SENTINEL_ID].kind == "coa_system"   # 35, non-playable
    assert resolved[36].kind == "reborn"
    assert resolved[2].kind == "stock"
    assert resolved[12].kind == "meta"                       # General/Hero


def test_unknown_class_id_is_unknown_not_stock():
    # an id outside every known band must be "unknown" (flagged), never silently bucketed "stock"
    resolved = resolve_class_types(_Table([{"id": 99, "name": "Mystery"}]))
    assert resolved[99].kind == "unknown"


def test_applies_curated_display_aliases_without_touching_identity():
    resolved = resolve_class_types(_class_rows())
    assert resolved[22].internal == "SonOfArugal"
    assert resolved[22].display == "Bloodmage"
    assert resolved[16].display == "Felsworn"
    assert resolved[21].display == "Templar"
    assert set(DISPLAY_ALIASES) == {22, 16, 21}


def test_cardinality_exactly_21_playable():
    resolved = resolve_class_types(_class_rows())
    assert_playable_cardinality(resolved)   # must not raise


def test_cardinality_raises_when_not_21():
    rows = [r for r in _class_rows().rows if r["id"] != 34]  # drop one playable class
    with pytest.raises(ValueError, match="expected 21 playable"):
        assert_playable_cardinality(resolve_class_types(_Table(rows)))


def test_tab_types_resolve_names():
    tabs = _Table([{"id": 1, "name": "Class"}, {"id": 49, "name": "Brewing"}])
    assert resolve_tab_types(tabs) == {1: "Class", 49: "Brewing"}
