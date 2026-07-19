from __future__ import annotations

import struct

from .archive_plan import family_of
from .recordview import DbcView
from .spell_layout import FieldPolicy, SpellPolicy
from .spell_proof import (
    FieldProof, absent_envelope, make_domain_gated_envelope, make_envelope, make_join,
    make_string_observation, refine_enum, refine_mask,
)

SCHEMA = "coa-client-spell-v2"
_CUSTOM_ID_FLOOR = 100_000


def _proof(fp: FieldPolicy) -> FieldProof:
    # integrity is a runtime property: the view opened cleanly (open_view/require_dense already
    # enforced structural integrity), so integrity is verified; layout+interpretation come from
    # the human-authored, hash-bound policy.
    return FieldProof("verified", fp.layout, fp.interpretation)


def _decode_scalar(raw: int, kind: str):
    if kind == "int32":
        return struct.unpack("<i", struct.pack("<I", raw))[0]
    if kind == "float":
        return struct.unpack("<f", struct.pack("<I", raw))[0]
    return raw  # uint32


def _bits(mask: int):
    return [1 << b for b in range(32) if (mask >> b) & 1]


def _emit_gated(rec, fp: FieldPolicy, key, obs, refine, sink):
    """Emit a per-value domain-gated scalar enum (power_type). Returns the normalized value (or None)
    and records the observation in `obs`. An out-of-domain value keeps its raw, withholds normalized,
    and appends the unknown symbol to `sink` for the extract-level inventory."""
    if fp.cell is None:
        obs[key] = absent_envelope(proof=_proof(fp), evidence_ref=fp.evidence, state="unresolved").to_dict()
        return None
    raw = rec.u32(fp.cell)
    env = make_domain_gated_envelope(raw, kind=fp.kind, proof=_proof(fp), evidence_ref=fp.evidence, refine=refine)
    obs[key] = env.to_dict()
    if env.decoded is not None:
        return env.decoded["value"]
    if env.decoded_reason == "value_out_of_domain":
        sink.append(_decode_scalar(raw, fp.kind))
    return None


def _emit_join(rec, jname, join, spell_fields, policy, side_views, side_id_maps):
    idx_fp: FieldPolicy = spell_fields[join.index_field]
    if idx_fp.cell is None:
        # Un-adjudicated join: the index column is unproven, so there is nothing to resolve. Emit an
        # honest unresolved marker (raw retained is impossible — no cell), normalized stays null.
        env = absent_envelope(proof=_proof(idx_fp), state="unresolved",
                              evidence_ref=f"join {jname}: {idx_fp.evidence}")
        return None, env.to_dict()

    side_fields = policy.tables[join.side_table]["fields"]
    id_fp: FieldPolicy = side_fields["id"]
    val_fp: FieldPolicy = side_fields[join.side_value_field]
    fk = rec.u32(idx_fp.cell)
    idx_env = make_envelope(fk, kind=idx_fp.kind, proof=_proof(idx_fp), evidence_ref=idx_fp.evidence)

    if fk == 0:
        jo = make_join({"index": idx_env}, resolution="index_zero", decode=lambda c: None)
        return None, jo.to_dict()
    side_rec = side_id_maps.get(join.side_table, {}).get(fk)
    if side_rec is None:
        jo = make_join({"index": idx_env}, resolution="side_row_missing", decode=lambda c: None)
        return None, jo.to_dict()

    side_id_env = make_envelope(side_rec.u32(id_fp.cell), kind=id_fp.kind,
                                proof=_proof(id_fp), evidence_ref=id_fp.evidence)
    val_env = make_envelope(side_rec.u32(val_fp.cell), kind=val_fp.kind,
                            proof=_proof(val_fp), evidence_ref=val_fp.evidence)
    components = {"index": idx_env, "side_id": side_id_env, "side_value": val_env}
    jo = make_join(components, resolution="resolved",
                   decode=lambda c: c["side_value"].decoded["value"] if c["side_value"].decoded else None)
    return jo.decoded, jo.to_dict()


def build_spell_v2_records(spell_view: DbcView, side_views: dict, *, policy: SpellPolicy,
                           provenance: dict) -> tuple[list[dict], dict]:
    """Build coa-client-spell-v2 records straight from RecordView cells under a hash-bound policy.

    Every DBC-derived value carries a `field_observations` entry (Envelope / StringObservation /
    JoinObservation) with raw + proof; the normalized `mechanics`/`name` values are copied FROM those
    observations so a populated normalized value always has a matching eligible observation. power_type
    and school_mask are per-value domain-gated; an unseen enum/bit withholds the normalized value
    (raw retained) and is tallied in the returned unknown_symbol_inventory."""
    sf = policy.tables["Spell"]["fields"]
    allowed_pt = policy.enum_policy["power_types"]
    allowed_bits = policy.enum_policy["school_bits"]
    inv_pt: list[int] = []
    inv_bits: list[int] = []

    effective = provenance.get("effective_archive", "")
    archive_family = family_of(effective) if effective else "unknown"

    side_id_maps: dict[str, dict] = {}
    for name, view in side_views.items():
        if view is None:
            continue
        m: dict[int, object] = {}
        for r in view.records():
            m.setdefault(r.u32(0), r)
        side_id_maps[name] = m

    records: list[dict] = []
    for rec in spell_view.records():
        obs: dict = {}
        mech: dict = {}
        id_fp = sf["id"]
        spell_id = rec.u32(id_fp.cell)
        obs["spell_id"] = make_envelope(spell_id, kind=id_fp.kind, proof=_proof(id_fp),
                                        evidence_ref=id_fp.evidence).to_dict()

        name_fp = sf["name"]
        name_val = None
        if name_fp.cell is not None:
            off = rec.u32(name_fp.cell)
            resolved = spell_view.read_string(off)   # strict: name is a proven string field
            sob = make_string_observation(off, resolved, proof=_proof(name_fp), evidence_ref=name_fp.evidence)
            obs["name"] = sob.to_dict()
            name_val = sob.resolved

        mech["power_type"] = _emit_gated(rec, sf["power_type"], "power_type", obs,
                                         lambda v: refine_enum(v, allowed_pt), inv_pt)
        mech["school_mask"] = _emit_school(rec, sf["school_mask"], obs, allowed_bits, inv_bits)

        desc_fp = sf.get("description")
        if desc_fp is not None and desc_fp.cell is not None:
            off = rec.u32(desc_fp.cell)
            resolved = spell_view.read_string(off)
            obs["description"] = make_string_observation(
                off, resolved, proof=_proof(desc_fp), evidence_ref=desc_fp.evidence).to_dict()

        for jname, join in policy.joins.items():
            mech[jname], obs[jname] = _emit_join(rec, jname, join, sf, policy, side_views, side_id_maps)

        records.append({
            "schema_version": SCHEMA,
            "spell_id": spell_id,
            "name": name_val,
            "mechanics": mech,
            "field_observations": obs,
            "provenance": {**provenance, "policy_sha256": policy.sha256},
            "coa_attribution": {
                "status": "unknown",
                "archive_family": archive_family,
                "id_range": "high" if spell_id >= _CUSTOM_ID_FLOOR else "base",
            },
        })

    inventory = {"power_type": sorted(set(inv_pt)), "school_bits": sorted(set(inv_bits))}
    return records, inventory


def _emit_school(rec, fp: FieldPolicy, obs, allowed_bits, sink):
    if fp.cell is None:
        obs["school_mask"] = absent_envelope(proof=_proof(fp), evidence_ref=fp.evidence,
                                             state="unresolved").to_dict()
        return None
    raw = rec.u32(fp.cell)
    env = make_domain_gated_envelope(raw, kind=fp.kind, proof=_proof(fp), evidence_ref=fp.evidence,
                                     refine=lambda v: refine_mask(v, allowed_bits))
    obs["school_mask"] = env.to_dict()
    if env.decoded is not None:
        return env.decoded["value"]
    if env.decoded_reason == "value_out_of_domain":
        sink.extend(b for b in _bits(raw) if b not in allowed_bits)
    return None
