import pytest

from coa_client_extract.spell_proof import (
    FieldProof, raw_decode_eligible, semantic_promotion_eligible, compose_proof,
    Envelope, make_envelope, absent_envelope, make_domain_gated_envelope,
    make_join, make_string_observation, refine_enum, refine_mask)


def test_proof_states_and_gates():
    v = FieldProof("verified", "verified", "verified")
    raw = FieldProof("verified", "verified", "unproven")
    ref = FieldProof("verified", "reference", "verified")
    assert raw_decode_eligible(v) and semantic_promotion_eligible(v)
    assert raw_decode_eligible(raw) and not semantic_promotion_eligible(raw)
    assert not raw_decode_eligible(ref)                       # reference layout never passes
    with pytest.raises(ValueError):
        FieldProof("verified", "verified", "bogus")


def test_full_predicate_decode_gate():
    withheld = FieldProof("unproven", "verified", "verified")   # integrity unproven -> no decode
    d = make_envelope(4294967294, kind="int32", proof=withheld, evidence_ref="e").to_dict()
    assert d["decoded"] is None and d["decoded_reason"] == "proof_withheld"
    full = FieldProof("verified", "verified", "verified")
    d2 = make_envelope(4294967294, kind="int32", proof=full, evidence_ref="e").to_dict()
    assert d2["decoded"] == {"kind": "int32", "value": -2} and d2["decoded_reason"] == "decoded"


def test_non_finite_distinct_from_withheld():
    full = FieldProof("verified", "verified", "verified")
    d = make_envelope(0x7F800000, kind="float", proof=full, evidence_ref="e").to_dict()
    assert d["decoded"] is None and d["decoded_reason"] == "non_finite" and d["raw_u32"] == 0x7F800000


def test_envelope_validation_and_token_guard():
    full = FieldProof("verified", "verified", "verified")
    with pytest.raises(ValueError): make_envelope(True, kind="int32", proof=full, evidence_ref="e")
    with pytest.raises(ValueError): make_envelope(2**32, kind="int32", proof=full, evidence_ref="e")
    with pytest.raises(ValueError): make_envelope(-1, kind="int32", proof=full, evidence_ref="e")
    with pytest.raises(ValueError): make_envelope(0, kind="int16", proof=full, evidence_ref="e")
    with pytest.raises(ValueError): make_envelope(0, kind="int32", proof=full, evidence_ref="")
    with pytest.raises(TypeError):
        Envelope("present", 0, None, "decoded", full, "e")   # direct construction is blocked


def test_absent_envelope_has_no_fake_raw():
    p = FieldProof("verified", "verified", "unproven")
    d = absent_envelope(proof=p, evidence_ref="e", state="not_applicable").to_dict()
    assert d["state"] == "not_applicable" and d["raw_u32"] is None and d["decoded_reason"] == "not_present"
    with pytest.raises(ValueError):
        absent_envelope(proof=p, evidence_ref="e", state="present")


def test_compose_proof_is_weakest_facet():
    a = FieldProof("verified", "verified", "verified")
    assert compose_proof(a, FieldProof("verified", "unproven", "verified")).layout == "unproven"
    assert compose_proof(a, FieldProof("verified", "verified", "contradicted")).interpretation == "contradicted"
    assert compose_proof(a, a).to_dict() == a.to_dict()


def test_refine_enum_and_mask():
    assert refine_enum(0, {-2, 0, 1, 2, 3, 4, 5, 6}) == (0, True)
    assert refine_enum(7, {-2, 0, 1, 2, 3, 4, 5, 6}) == (None, False)
    assert refine_mask(20, {1, 2, 4, 8, 16, 32, 64}) == (20, True)     # 4|16 is a valid combination
    assert refine_mask(0, {1, 2, 4, 8, 16, 32, 64}) == (0, True)       # no school
    assert refine_mask(128, {1, 2, 4, 8, 16, 32, 64}) == (None, False)  # unknown bit


def test_domain_gated_envelope_records_out_of_domain():
    full = FieldProof("verified", "verified", "verified")
    bits = {1, 2, 4, 8, 16, 32, 64}
    ok = make_domain_gated_envelope(4, kind="uint32", proof=full, evidence_ref="e",
                                    refine=lambda v: refine_mask(v, bits)).to_dict()
    assert ok["decoded"] == {"kind": "uint32", "value": 4}
    bad = make_domain_gated_envelope(128, kind="uint32", proof=full, evidence_ref="e",
                                     refine=lambda v: refine_mask(v, bits)).to_dict()
    assert bad["decoded"] is None and bad["decoded_reason"] == "value_out_of_domain" and bad["raw_u32"] == 128


def test_string_observation():
    full = FieldProof("verified", "verified", "verified")
    d = make_string_observation(1, "Fireball", proof=full, evidence_ref="e").to_dict()
    assert d["raw_offset"] == 1 and d["resolved"] == "Fireball" and d["decoded_reason"] == "decoded"
    raw = FieldProof("verified", "verified", "unproven")
    d2 = make_string_observation(1, "x", proof=raw, evidence_ref="e").to_dict()
    assert d2["resolved"] is None and d2["decoded_reason"] == "proof_withheld"
    with pytest.raises(ValueError):
        make_string_observation(1, 123, proof=full, evidence_ref="e")   # resolved must be str


def test_join_states_and_validation():
    full = FieldProof("verified", "verified", "verified")
    comps = {"idx": make_envelope(28, kind="uint32", proof=full, evidence_ref="e"),
             "val": make_envelope(1500, kind="int32", proof=full, evidence_ref="e")}
    resolved = make_join(comps, resolution="resolved",
                         decode=lambda c: c["val"].decoded["value"]).to_dict()
    assert resolved["state"] == "resolved" and resolved["decoded"] == 1500
    naz = make_join(comps, resolution="index_zero", decode=lambda c: 1).to_dict()
    assert naz["state"] == "not_applicable" and naz["decoded_reason"] == "index_zero"
    miss = make_join(comps, resolution="side_row_missing", decode=lambda c: 1).to_dict()
    assert miss["state"] == "unresolved" and miss["decoded_reason"] == "side_row_missing"
    with pytest.raises(ValueError): make_join({}, resolution="resolved", decode=lambda c: 1)
    with pytest.raises(ValueError):                              # malformed fails closed, never publishes
        make_join(comps, resolution="malformed_reference", decode=lambda c: 1)


def test_join_withheld_when_a_component_proof_is_weak():
    weak = {"idx": make_envelope(28, kind="uint32",
                                 proof=FieldProof("verified", "verified", "unproven"), evidence_ref="e")}
    j = make_join(weak, resolution="resolved", decode=lambda c: 1500).to_dict()
    assert j["decoded"] is None and j["decoded_reason"] == "proof_withheld"
