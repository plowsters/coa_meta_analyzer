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
