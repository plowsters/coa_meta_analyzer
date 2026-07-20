# tests/test_mechanics_v2.py
import pytest
from coa_meta.mechanics import mechanic_from_raw, MechanicsLoadError, MECHANICS_SCHEMA_VERSION


def _rec(**over):
    base = {"schema_version": "coa-mechanics-v2", "spell_id": 5, "name": "X", "kind": "ability"}
    base.update(over)
    return base


def test_schema_version_is_v2():
    assert MECHANICS_SCHEMA_VERSION == "coa-mechanics-v2"


def test_unknown_costs_is_none_not_empty_dict():
    r = mechanic_from_raw(_rec(costs=None, field_readiness={"costs": {"status": "unavailable",
                          "reason_code": "pending_e1_operand"}}))
    assert r.costs is None                                     # unknown != free {}
    assert r.field_readiness["costs"]["status"] == "unavailable"
    # missing != default: costs serializes as an explicit null, never dropped
    assert "costs" in r.to_dict() and r.to_dict()["costs"] is None


def test_verified_empty_costs_survives():
    r = mechanic_from_raw(_rec(costs={}, field_readiness={"costs": {"status": "verified_empty",
                          "reason_code": "proven_empty"}}))
    assert r.costs == {} and r.field_readiness["costs"]["status"] == "verified_empty"


def test_contradictory_readiness_is_rejected():
    # verified_empty must carry a (possibly empty) set-valued value; costs=None contradicts it.
    with pytest.raises(MechanicsLoadError, match="readiness invariant"):
        mechanic_from_raw(_rec(costs=None, field_readiness={"costs": {"status": "verified_empty",
                          "reason_code": "not_extracted"}}))


def test_bad_status_or_reason_code_is_rejected():
    with pytest.raises(MechanicsLoadError, match="status"):
        mechanic_from_raw(_rec(field_readiness={"costs": {"status": "made_up", "reason_code": "not_extracted"}}))
    with pytest.raises(MechanicsLoadError, match="reason_code"):
        mechanic_from_raw(_rec(field_readiness={"costs": {"status": "unavailable", "reason_code": "made_up"}}))


def test_field_readiness_is_optional():
    # a record with no field_readiness is valid (defaults to {}); costs defaults to null.
    r = mechanic_from_raw(_rec())
    assert r.field_readiness == {}
    assert r.costs is None


def test_v1_is_rejected():
    with pytest.raises(MechanicsLoadError, match="coa-mechanics-v2"):
        mechanic_from_raw({"schema_version": "coa-mechanics-v1", "spell_id": 1, "name": "n", "kind": "k"})
