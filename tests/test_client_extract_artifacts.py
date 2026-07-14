import json
import struct
from pathlib import Path

from coa_client_extract.artifacts import build_client_spell_records, write_json, write_jsonl
from coa_client_extract.manifest import build_manifest
from coa_client_extract.wdbc import DbcLayout, FieldSpec, parse_dbc


def _dbc(rows, field_count, record_size, strings=b"\x00"):
    header = struct.pack("<4sIIII", b"WDBC", len(rows), field_count, record_size, len(strings))
    return header + b"".join(rows) + strings


def _spell_table():
    strings = b"\x00Adrenal Venom\x00"
    row = struct.pack("<IIII", 805775, 1, 3, 5)  # id, name_off, cast_idx, dur_idx
    layout = DbcLayout("Spell", 4, 16, {
        "id": FieldSpec(0, "uint32"),
        "name": FieldSpec(1, "str"),
        "casting_time_index": FieldSpec(2, "uint32"),
        "duration_index": FieldSpec(3, "uint32"),
    })
    return parse_dbc(_dbc([row], 4, 16, strings), layout)


def _index_table(idx, base_ms):
    row = struct.pack("<II", idx, base_ms)
    layout = DbcLayout("X", 2, 8, {"id": FieldSpec(0, "uint32"), "base_ms": FieldSpec(1, "int32")})
    return parse_dbc(_dbc([row], 2, 8), layout)


def test_build_spell_records_joins_family_and_defers_attribution():
    records = build_client_spell_records(
        _spell_table(), _index_table(3, 1500), _index_table(5, 18000), None,
        provenance={"effective_archive": "patch-CA.MPQ", "extraction_date": "2026-07-10"},
    )
    rec = records[0]
    assert rec["schema_version"] == "coa-client-spell-v1"
    assert rec["spell_id"] == 805775
    assert rec["name"] == "Adrenal Venom"
    assert rec["mechanics"]["cast_time_ms"] == 1500
    assert rec["mechanics"]["duration_ms"] == 18000
    # attribution deferred, but raw signals recorded for M1.14B
    assert rec["coa_attribution"]["status"] == "unknown"
    assert rec["coa_attribution"]["archive_family"] == "coa"  # patch-CA.MPQ -> CoA family
    assert rec["coa_attribution"]["id_range"] == "high"  # 805775 >= 100000


def test_raw_signals_reflect_base_family_and_low_id():
    # A base-archive supplier and a low spell id must map to the base signals.
    strings = b"\x00Fireball\x00"
    row = struct.pack("<IIII", 133, 1, 3, 5)  # spell id 133 (< 100000)
    layout = DbcLayout("Spell", 4, 16, {
        "id": FieldSpec(0, "uint32"), "name": FieldSpec(1, "str"),
        "casting_time_index": FieldSpec(2, "uint32"), "duration_index": FieldSpec(3, "uint32"),
    })
    spell = parse_dbc(_dbc([row], 4, 16, strings), layout)
    records = build_client_spell_records(
        spell, None, None, None,
        provenance={"effective_archive": "common.MPQ", "extraction_date": "2026-07-10"},
    )
    assert records[0]["coa_attribution"]["archive_family"] == "base"
    assert records[0]["coa_attribution"]["id_range"] == "base"


def test_drift_marks_low_confidence():
    # A Spell table whose header disagrees with the layout (drift) must stamp low confidence.
    strings = b"\x00Adrenal Venom\x00"
    row = struct.pack("<IIII", 805775, 1, 3, 5) + b"\x00\x00\x00\x00"  # 5 cells -> 20-byte record
    layout = DbcLayout("Spell", 4, 16, {  # layout still expects 4 fields / 16 bytes -> drift
        "id": FieldSpec(0, "uint32"), "name": FieldSpec(1, "str"),
        "casting_time_index": FieldSpec(2, "uint32"), "duration_index": FieldSpec(3, "uint32"),
    })
    drifted = parse_dbc(_dbc([row], 5, 20, strings), layout)
    assert drifted.drift is True

    records = build_client_spell_records(
        drifted, None, None, None,
        provenance={"effective_archive": "patch-CA.MPQ", "extraction_date": "2026-07-10"},
    )
    assert records[0]["provenance"]["schema_match_confidence"] == "low"


def test_write_jsonl_returns_sha256(tmp_path):
    out = tmp_path / "spell.jsonl"
    digest = write_jsonl([{"a": 1}, {"b": 2}], out)
    assert len(digest) == 64
    lines = out.read_text().strip().splitlines()
    assert json.loads(lines[0]) == {"a": 1}


def test_manifest_shape(tmp_path):
    doc = build_manifest(
        backend_name="fake", backend_version="fake-v1", stormlib_version=None,
        client_root="/x", client_build="unknown",
        outputs={"coa_client_spell.jsonl": "deadbeef"}, archive_plan={"schema_version": "coa-client-archive-plan-v1"},
    )
    assert doc["schema_version"] == "coa-client-extract-manifest-v1"
    assert doc["wrapper_version"] == "coa-stormlib-v1"
    assert doc["outputs"]["coa_client_spell.jsonl"] == "deadbeef"


from coa_client_extract.artifacts import (
    build_advancement_records, build_class_type_records, build_tab_type_records,
    build_essence_raw_records, fill_spell_attribution,
)
from coa_client_extract.advancement import AdvancementNode
from coa_client_extract.attribution import AttributionResult, SpellAttribution
from coa_client_extract.class_types import ClassType


def _node():
    return AdvancementNode(
        node_id=6086, spell_id=805775, class_type_id=33, class_internal="Venomancer",
        class_display="Venomancer", class_kind="coa_class", tab_type_id=1, tab_name="Class",
        entry_type="Ability", essence_kind="ability",
        legality={"ae_cost": 1, "connected_node_ids": [6096, 7235], "required_ids": []},
        field_confidence={"ae_cost": "high", "connected_node_ids": "high"},
        raw={0: 6086, 5: 805775, 32: 33},
    )


def test_advancement_record_shape():
    attr = {805775: SpellAttribution(AttributionResult(True, ("coa",), "coa", "high"), [])}
    recs = build_advancement_records([_node()], provenance={"client_build": "3.3.5a+patch-CZZ"},
                                     spell_names={805775: "Adrenal Venom"}, attribution=attr)
    r = recs[0]
    assert r["schema_version"] == "coa-client-advancement-v1"
    assert r["node_id"] == 6086 and r["spell_id"] == 805775
    assert r["name"] == "Adrenal Venom"                 # joined from the client spell artifact
    assert r["class"]["display"] == "Venomancer" and r["class"]["kind"] == "coa_class"
    assert r["tab"] == {"tab_type_id": 1, "name": "Class"}
    assert r["legality"]["connected_node_ids"] == [6096, 7235]
    assert r["field_confidence"]["ae_cost"] == "high"
    assert r["raw"]["cols"] == {0: 6086, 5: 805775, 32: 33}    # index-keyed audit map
    assert r["provenance"]["client_build"] == "3.3.5a+patch-CZZ"
    assert r["coa_attribution"] == {"is_coa": True, "modes": ["coa"],
                                    "exclusive_mode": "coa", "confidence": "high"}


def test_advancement_record_attribution_absent_is_low():
    r = build_advancement_records([_node()], provenance={})[0]
    assert r["coa_attribution"] == {"is_coa": False, "modes": [],
                                    "exclusive_mode": None, "confidence": "low"}


def test_class_type_record_records_alias_provenance():
    cts = {22: ClassType(22, "SonOfArugal", "Bloodmage", "coa_class", "curated_alias",
                         ("builder_class_name", "project_owner_confirmation"))}
    r = build_class_type_records(cts)[0]
    assert r["schema_version"] == "coa-client-class-types-v1"
    assert r["internal"] == "SonOfArugal" and r["display"] == "Bloodmage"
    assert r["kind"] == "coa_class"
    assert r["display_source"] == "curated_alias"
    assert r["display_evidence"] == ["builder_class_name", "project_owner_confirmation"]


def test_tab_type_record_shape():
    recs = build_tab_type_records({1: "Class", 49: "Brewing"})
    assert {x["tab_type_id"]: x["name"] for x in recs} == {1: "Class", 49: "Brewing"}
    assert all(x["schema_version"] == "coa-client-tab-types-v1" for x in recs)


def test_fill_spell_attribution_replaces_unknown_and_keeps_raw_signals():
    spells = [{"schema_version": "coa-client-spell-v1", "spell_id": 805775,
               "coa_attribution": {"status": "unknown", "archive_family": "other", "id_range": "high"}}]
    membership = {"mode": "coa", "class_type_id": 33, "tab_name": "Class", "node_id": 6086}
    attr = {805775: SpellAttribution(
        AttributionResult(True, ("coa",), "coa", "high"), [membership])}
    rec = fill_spell_attribution(spells, attr)[0]
    a = rec["coa_attribution"]
    assert a["is_coa"] is True and a["modes"] == ["coa"] and a["exclusive_mode"] == "coa"
    assert a["archive_family"] == "other" and a["id_range"] == "high"   # raw signals retained
    assert "status" not in a
    assert rec["memberships"] == [membership]           # memberships attached, never discarded


def test_fill_spell_attribution_absent_spell_is_low():
    spells = [{"spell_id": 999, "coa_attribution": {"status": "unknown"}}]
    rec = fill_spell_attribution(spells, {})[0]
    assert rec["coa_attribution"] == {"is_coa": False, "modes": [],
                                      "exclusive_mode": None, "confidence": "low"}
    assert rec["memberships"] == []


def test_essence_raw_records_preserve_cells_and_provenance():
    # CharacterAdvancementEssence is per-level progression, extracted RAW (undecoded semantics);
    # caps are the documented constants AE 26 / TE 25, NOT decoded here.
    class _Ess:
        rows = [{0: 1, 1: 60, 2: 26}, {0: 2, 1: 61, 2: 25}]
    recs = build_essence_raw_records(_Ess(), provenance={"client_build": "3.3.5a+patch-CZZ"})
    assert len(recs) == 2
    assert recs[0]["schema_version"] == "coa-client-essence-v1"
    assert recs[0]["cols"] == {0: 1, 1: 60, 2: 26}      # raw cells, no column meaning asserted
    assert recs[0]["provenance"]["client_build"] == "3.3.5a+patch-CZZ"
