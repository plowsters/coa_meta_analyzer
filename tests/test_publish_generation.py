import hashlib
import json
import time
import uuid

import pytest

import coa_client_extract.publish as pub
from coa_client_extract.manifest import build_manifest
from coa_client_extract.publish import (
    GenerationWriter, POINTER_NAME, PublishError, ResolveError,
    prune_generations, resolve_active_generation,
)


def _base():
    return build_manifest(backend_name="fake", backend_version="v1", stormlib_version=None,
                          client_root="/x", client_build="3.3.5a+patch-CZZ",
                          outputs={}, archive_plan={"schema_version": "coa-client-archive-plan-v1"})


def _binding():
    return {"source_dbc": {"Spell": {"sha256": "a" * 64, "header": {"records": 208431, "record_size": 936},
                                     "archive": "patch-T.MPQ"}},
            "policy_sha256": "p" * 64, "anchor_set_sha256": "an" * 32, "enum_policy_sha256": "en" * 32}


def _publish(root, *, spell_id=1, inv=None):
    w = GenerationWriter(root)
    w.add_jsonl("coa_client_spell_coa.jsonl",
                [{"schema_version": "coa-client-spell-v2", "spell_id": spell_id}],
                schema_version="coa-client-spell-v2")
    w.add_json("coa_client_spell_projection.manifest.json",
               {"schema_version": "coa-client-spell-projection-v2"},
               schema_version="coa-client-spell-projection-v2")
    m = w.publish(base_manifest=_base(), binding=_binding(),
                  unknown_symbol_inventory=inv or {"power_type": [7], "school_bits": []})
    return w, m


def _repoint(root, gen_id, mutate):
    """Mutate a published manifest and re-sign the pointer, so child-level validation (not the manifest
    hash) is what a negative test exercises."""
    gen_dir = root / f"gen-{gen_id}"
    m = json.loads((gen_dir / "manifest.json").read_text())
    mutate(m)
    body = (json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    (gen_dir / "manifest.json").write_bytes(body)
    ptr = json.loads((root / POINTER_NAME).read_text())
    ptr["manifest_sha256"] = hashlib.sha256(body).hexdigest()
    (root / POINTER_NAME).write_text(json.dumps(ptr, indent=2, sort_keys=True) + "\n")


def test_publish_and_resolve_roundtrip(tmp_path):
    _w, m = _publish(tmp_path)
    assert m["schema_version"] == "coa-client-extract-manifest-v2"
    assert m["predecessor_generation_id"] is None
    assert isinstance(m["published_at"], int)
    assert m["unknown_symbol_inventory"] == {"power_type": [7], "school_bits": []}
    assert m["binding"]["policy_sha256"] == "p" * 64
    # outputs is a deterministic {name: sha256} index view over children
    assert m["outputs"] == {name: meta["sha256"] for name, meta in m["children"].items()}

    resolved = resolve_active_generation(tmp_path)
    assert resolved["generation_id"] == m["generation_id"]
    assert set(resolved["children"]) == {"coa_client_spell_coa.jsonl", "coa_client_spell_projection.manifest.json"}
    assert resolved["children"]["coa_client_spell_coa.jsonl"].is_file()


def test_all_ten_v1_manifest_fields_are_superset(tmp_path):
    _w, m = _publish(tmp_path)
    for k in ("schema_version", "wrapper_version", "backend", "backend_version", "stormlib_version",
              "client_root", "client_build", "extraction_date", "archive_plan", "outputs"):
        assert k in m


def test_collision_exist_ok_false(tmp_path, monkeypatch):
    monkeypatch.setattr(pub.uuid, "uuid4", lambda: uuid.UUID(int=0x1234))
    GenerationWriter(tmp_path)                      # claims gen-<fixed>
    with pytest.raises(FileExistsError):
        GenerationWriter(tmp_path)                  # same id -> exist_ok=False


def test_writer_rejects_unsafe_and_duplicate_child(tmp_path):
    w = GenerationWriter(tmp_path)
    with pytest.raises(PublishError, match="unsafe"):
        w.add_jsonl("../evil.jsonl", [], schema_version="x")
    with pytest.raises(PublishError, match="reserved"):
        w.add_jsonl("manifest.json", [], schema_version="x")
    w.add_jsonl("a.jsonl", [{"schema_version": "x"}], schema_version="x")
    with pytest.raises(PublishError, match="duplicate"):
        w.add_jsonl("a.jsonl", [], schema_version="x")


def test_content_collision_safety(tmp_path):
    _w1, m1 = _publish(tmp_path, spell_id=111)
    a_child = tmp_path / f"gen-{m1['generation_id']}" / "coa_client_spell_coa.jsonl"
    a_bytes = a_child.read_bytes()
    _w2, m2 = _publish(tmp_path, spell_id=222)
    assert m2["generation_id"] != m1["generation_id"]
    assert a_child.read_bytes() == a_bytes          # B's publish left A's bytes intact
    assert m2["predecessor_generation_id"] == m1["generation_id"]


def test_resolve_rejects_manifest_hash_tamper(tmp_path):
    _w, m = _publish(tmp_path)
    manifest = tmp_path / f"gen-{m['generation_id']}" / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b"  ")   # change bytes, not the pointer hash
    with pytest.raises(ResolveError, match="manifest sha256"):
        resolve_active_generation(tmp_path)


def test_resolve_rejects_child_bytes_tamper(tmp_path):
    _w, m = _publish(tmp_path)
    child = tmp_path / f"gen-{m['generation_id']}" / "coa_client_spell_coa.jsonl"
    child.write_bytes(b'{"schema_version": "coa-client-spell-v2", "spell_id": 999}\n')
    with pytest.raises(ResolveError, match="sha256 mismatch"):
        resolve_active_generation(tmp_path)


def test_resolve_rejects_missing_child(tmp_path):
    _w, m = _publish(tmp_path)
    (tmp_path / f"gen-{m['generation_id']}" / "coa_client_spell_coa.jsonl").unlink()
    with pytest.raises(ResolveError, match="missing"):
        resolve_active_generation(tmp_path)


def test_resolve_rejects_record_count_mismatch(tmp_path):
    _w, m = _publish(tmp_path)
    _repoint(tmp_path, m["generation_id"],
             lambda mm: mm["children"]["coa_client_spell_coa.jsonl"].update({"records": 99}))
    with pytest.raises(ResolveError, match="record count mismatch"):
        resolve_active_generation(tmp_path)


def test_resolve_rejects_byte_length_mismatch(tmp_path):
    _w, m = _publish(tmp_path)
    _repoint(tmp_path, m["generation_id"],
             lambda mm: mm["children"]["coa_client_spell_coa.jsonl"].update({"byte_length": 999999}))
    with pytest.raises(ResolveError, match="byte_length mismatch"):
        resolve_active_generation(tmp_path)


def test_resolve_rejects_child_path_traversal(tmp_path):
    _w, m = _publish(tmp_path)
    _repoint(tmp_path, m["generation_id"],
             lambda mm: mm["children"].update({"../escape.jsonl": {"sha256": "x", "byte_length": 0,
                                                                   "records": 0, "schema_version": "y"}}))
    with pytest.raises(ResolveError, match="unsafe child name"):
        resolve_active_generation(tmp_path)


def test_resolve_rejects_missing_child_schema(tmp_path):
    _w, m = _publish(tmp_path)
    _repoint(tmp_path, m["generation_id"],
             lambda mm: mm["children"]["coa_client_spell_coa.jsonl"].update({"schema_version": ""}))
    with pytest.raises(ResolveError, match="schema_version"):
        resolve_active_generation(tmp_path)


def test_resolve_rejects_pointer_generation_mismatch(tmp_path):
    _w, m = _publish(tmp_path)
    ptr = tmp_path / POINTER_NAME
    doc = json.loads(ptr.read_text())
    doc["generation_id"] = "deadbeef" * 4          # points to a non-existent generation
    ptr.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ResolveError):
        resolve_active_generation(tmp_path)


def test_prune_keeps_current_and_predecessor_when_quiescent(tmp_path):
    _w1, m1 = _publish(tmp_path)
    _w2, m2 = _publish(tmp_path)
    _w3, m3 = _publish(tmp_path)
    later = time.time_ns() + 10 * 10**9
    result = prune_generations(tmp_path, grace_seconds=1.0, quiescent=True, now_ns=later)
    assert set(result["kept"]) == {m3["generation_id"], m2["generation_id"]}
    assert result["removed"] == [f"gen-{m1['generation_id']}"]
    assert not (tmp_path / f"gen-{m1['generation_id']}").exists()
    assert (tmp_path / f"gen-{m2['generation_id']}").exists()


def test_prune_is_noop_without_quiescent_window(tmp_path):
    _w1, m1 = _publish(tmp_path)
    _w2, m2 = _publish(tmp_path)
    _w3, m3 = _publish(tmp_path)
    later = time.time_ns() + 10 * 10**9
    result = prune_generations(tmp_path, grace_seconds=1.0, quiescent=False, now_ns=later)
    assert result["removed"] == []                 # documented best-effort: deletes nothing
    assert result["prunable"] == [f"gen-{m1['generation_id']}"]
    assert (tmp_path / f"gen-{m1['generation_id']}").exists()
