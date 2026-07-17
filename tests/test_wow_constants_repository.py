import hashlib
import json
import math

import pytest

from coa_meta.wow_constants import WowConstantsRepository, WowConstantsLoadError

COA_CLASS_TYPE_ID = 33


def _doc(**over):
    doc = {
        "schema_version": "coa-wow-constants-v1", "client_build": "3.3.5a+patch-M",
        "provenance": {"source_dbcs": {"gtCombatRatings": {"sha256": "z"}}},
        "class_axis": {"namespace": "chr_classes", "observed_client_ids": [1, 8, 11],
                       "default_power_type_by_wow_class_id": {"8": "mana"}},
        "enum_maps": {"rating_enum": {"version": "cr", "supported": {"10": "crit_spell"}},
                      "power_type": {"version": "p", "map": {"0": "mana"}}},
        "game_tables": {
            "combat_ratings": {"source_dbc": "gtCombatRatings", "axes": ["rating_id", "level"],
                "class_indexed": False, "counts": {"emitted_entries": 1},
                "entries": [{"rating_id": 10, "level": 60, "value": 14.0}]},
            "class_combat_rating_scalar": {"source_dbc": "gtOCTClassCombatRatingScalar",
                "axes": ["wow_class_id", "rating_id"], "class_indexed": True,
                "counts": {"emitted_entries": 1}, "entries": [{"wow_class_id": 8, "rating_id": 10, "value": 1.0}]}},
        "rules": {"gcd_floor_ms": {"value": 1000, "authority": "wotlk_reference",
                                   "ascension_verification": "unverified", "applies_to": ["all_spells"]}}}
    doc.update(over)
    return doc


def _write_pair(tmp_path, doc, *, tamper=False):
    art = tmp_path / "coa_wow_constants.json"
    body = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()
    art.write_bytes(body)
    manifest = {"schema_version": "coa-wow-constants-manifest-v1",
                "artifact": {"path": "coa_wow_constants.json",
                             "sha256": hashlib.sha256(body if not tamper else b"x").hexdigest(),
                             "byte_length": len(body)},
                "client_build": doc["client_build"]}
    (tmp_path / "coa_wow_constants.manifest.json").write_text(json.dumps(manifest))
    return art


def test_rejects_wrong_schema_version():
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.from_dict(_doc(schema_version="coa-wow-constants-v2"))


def test_all_required_lookups_and_power_map():
    repo = WowConstantsRepository.from_dict(_doc())
    assert repo.combat_rating_ratio(10, 60) == 14.0
    assert repo.class_combat_rating_scalar(wow_class_id=8, rating_id=10) == 1.0
    assert repo.default_power_type(8) == "mana"
    assert repo.rating_name(10) == "crit_spell"
    assert repo.table_provenance("combat_ratings")["sha256"] == "z"


def test_class_lookup_is_keyword_only_and_rejects_coa_id():
    repo = WowConstantsRepository.from_dict(_doc())
    with pytest.raises(TypeError):
        repo.class_combat_rating_scalar(8, 10)
    with pytest.raises(LookupError):
        repo.class_combat_rating_scalar(wow_class_id=COA_CLASS_TYPE_ID, rating_id=10)


def test_missing_coordinate_and_non_finite_and_duplicate():
    repo = WowConstantsRepository.from_dict(_doc())
    with pytest.raises(LookupError):
        repo.combat_rating_ratio(10, 61)
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.from_dict(_doc(game_tables={"combat_ratings": {"axes": ["rating_id", "level"],
            "class_indexed": False, "entries": [{"rating_id": 10, "level": 60, "value": math.inf}]}}))
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.from_dict(_doc(game_tables={"combat_ratings": {"axes": ["rating_id", "level"],
            "class_indexed": False, "entries": [{"rating_id": 10, "level": 60, "value": 1.0},
                                                {"rating_id": 10, "level": 60, "value": 2.0}]}}))


def test_rule_missing_labels_rejected():
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.from_dict(_doc(rules={"x": {"value": 1}}))


def test_load_verifies_manifest_hash(tmp_path):
    art = _write_pair(tmp_path, _doc())
    repo = WowConstantsRepository.load(art)
    assert repo.combat_rating_ratio(10, 60) == 14.0


def test_load_rejects_tampered_manifest(tmp_path):
    art = _write_pair(tmp_path, _doc(), tamper=True)
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.load(art)
