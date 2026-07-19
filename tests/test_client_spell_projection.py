import json

import pytest

from coa_client_extract.artifacts import write_client_spell_projection


def _coa_rec(spell_id, is_coa, conf="high", modes=("coa",), withheld=False):
    """A minimal coa-client-spell-v2 record for the projection writer: it reads coa_attribution,
    spell_id, and (for the value-gate summary) field_observations."""
    if withheld:
        pt_obs = {"state": "present", "raw_u32": 7, "decoded": None, "decoded_reason": "value_out_of_domain"}
        pt_norm = None
    else:
        pt_obs = {"state": "present", "raw_u32": 3, "decoded": {"kind": "int32", "value": 3},
                  "decoded_reason": "decoded"}
        pt_norm = 3
    return {
        "schema_version": "coa-client-spell-v2", "spell_id": spell_id, "name": f"S{spell_id}",
        "mechanics": {"school_mask": 8, "power_type": pt_norm},
        "field_observations": {"power_type": pt_obs},
        "coa_attribution": {"is_coa": is_coa, "modes": list(modes),
                            "exclusive_mode": modes[0] if modes else None, "confidence": conf},
    }


def test_projection_keeps_only_is_coa_and_writes_v2_manifest(tmp_path):
    records = [_coa_rec(1, True), _coa_rec(2, False, conf="low", modes=()),
               _coa_rec(3, True, conf="medium", withheld=True)]
    manifest = write_client_spell_projection(
        records, tmp_path, source_path="coa_client_spell.jsonl", source_sha="abc", source_bytes=100,
        client_build="3.3.5a+patch-CZZ", extractor_commit="deadbeef")
    proj = [json.loads(l) for l in (tmp_path / "coa_client_spell_coa.jsonl").read_text().splitlines() if l.strip()]
    assert sorted(r["spell_id"] for r in proj) == [1, 3]
    assert manifest["schema_version"] == "coa-client-spell-projection-v2"
    assert manifest["counts"]["projected_records"] == 2
    assert manifest["counts"]["by_confidence"] == {"high": 1, "medium": 1}
    # per-value gate summary replaces the retired table-level schema_match_confidence certification
    assert manifest["value_gate_summary"] == {"records_with_withheld_value": 1, "records_all_in_domain": 1}
    assert manifest["source_artifact"]["sha256"] == "abc"
    written = json.loads((tmp_path / "coa_client_spell_projection.manifest.json").read_text())
    assert written["projection"]["sha256"] == manifest["projection"]["sha256"]


def test_projection_rejects_duplicate_spell_ids(tmp_path):
    records = [_coa_rec(1, True), _coa_rec(1, True)]
    with pytest.raises(ValueError, match="duplicate spell_ids"):
        write_client_spell_projection(records, tmp_path, source_path="x", source_sha="a", source_bytes=1,
                                      client_build="b", extractor_commit="c")
