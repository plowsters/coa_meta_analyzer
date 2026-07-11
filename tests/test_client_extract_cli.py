import json
from pathlib import Path

from coa_client_extract.archive_backend import FakeArchiveBackend
from coa_client_extract.cli import main, regenerate


def _client(tmp_path: Path) -> Path:
    data = tmp_path / "Data"
    data.mkdir()
    for name in ("common.MPQ", "patch.MPQ", "patch-C.MPQ"):
        (data / name).write_bytes(b"MPQ\x1a")
    (data / "Content").mkdir()
    (data / "Content" / "SpellRankData.json").write_text('[{"Spell":805775,"Rank":1}]')
    return data


def _fake_backend():
    import struct
    strings = b"\x00Adrenal Venom\x00"
    spell = struct.pack("<IIII", 805775, 1, 3, 5)
    cast = struct.pack("<II", 3, 1500)
    dur = struct.pack("<II", 5, 18000)

    def dbc(rows, fc, rs, s=b"\x00"):
        return struct.pack("<4sIIII", b"WDBC", len(rows), fc, rs, len(s)) + b"".join(rows) + s

    entries = {
        "DBFilesClient\\Spell.dbc": [(Path("common.MPQ"), dbc([spell], 4, 16, strings))],
        "DBFilesClient\\SpellCastTimes.dbc": [(Path("common.MPQ"), dbc([cast], 2, 8))],
        "DBFilesClient\\SpellDuration.dbc": [(Path("common.MPQ"), dbc([dur], 2, 8))],
        "DBFilesClient\\SpellRange.dbc": [(Path("common.MPQ"), dbc([struct.pack("<I", 1) + b"\x00" * 152], 39, 156))],
    }
    return FakeArchiveBackend(entries)


def _synthetic_layouts():
    from coa_client_extract.wdbc import DbcLayout, FieldSpec

    return {
        "Spell": DbcLayout("Spell", 4, 16, {
            "id": FieldSpec(0, "uint32"), "name": FieldSpec(1, "str"),
            "casting_time_index": FieldSpec(2, "uint32"), "duration_index": FieldSpec(3, "uint32"),
        }),
        "SpellCastTimes": DbcLayout("SpellCastTimes", 2, 8, {"id": FieldSpec(0, "uint32"), "base_ms": FieldSpec(1, "int32")}),
        "SpellDuration": DbcLayout("SpellDuration", 2, 8, {"id": FieldSpec(0, "uint32"), "base_ms": FieldSpec(1, "int32")}),
        "SpellRange": DbcLayout("SpellRange", 39, 156, {"id": FieldSpec(0, "uint32")}),
    }


def test_regenerate_writes_artifacts_with_injected_backend(tmp_path):
    # Inject synthetic layouts matching the fake backend's DBC bytes; real layouts are
    # exercised by the Task 10 acceptance test. Asserts orchestration end to end.
    out = tmp_path / "out"
    manifest = regenerate(_client(tmp_path), out, backend=_fake_backend(), layouts=_synthetic_layouts())
    assert manifest["schema_version"] == "coa-client-extract-manifest-v1"
    assert (out / "coa_client_spell.jsonl").is_file()
    assert (out / "coa_client_content.jsonl").is_file()
    assert (out / "coa_client_archive_plan.json").is_file()
    assert (out / "coa_client_extract_manifest.json").is_file()
    spell = json.loads((out / "coa_client_spell.jsonl").read_text().splitlines()[0])
    assert spell["spell_id"] == 805775
    assert spell["coa_attribution"]["status"] == "unknown"
    # fake fixture resolves Spell.dbc to common.MPQ (base family); 805775 is high-range
    assert spell["coa_attribution"]["archive_family"] == "base"
    assert spell["coa_attribution"]["id_range"] == "high"
    # every contributing table records the archive that supplied it
    assert set(spell["provenance"]["source_dbcs"]) == {
        "Spell", "SpellCastTimes", "SpellDuration", "SpellRange"
    }
    # build descriptor derived from the discovered plan's top patch (patch-C.MPQ)
    assert manifest["client_build"] == "3.3.5a+patch-C"


def test_main_fails_closed_without_stormlib(tmp_path, capsys):
    out = tmp_path / "out"
    code = main([
        "regenerate", "--client-root", str(_client(tmp_path)), "--out", str(out),
        "--stormlib", "/nonexistent/libstorm.so.999",
    ])
    assert code == 2
    assert not out.exists() or not any(out.iterdir())
    err = capsys.readouterr().err
    assert "StormLib" in err
