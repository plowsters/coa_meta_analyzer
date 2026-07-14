from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .archive_plan import family_of
from .wdbc import DbcTable

# Spell ids at or above this floor are custom high-range content; below it is stock
# 3.3.5a/base-game range. A coarse, purely mechanical magnitude band — a raw attribution
# signal only. M1.14B owns the actual id-range attribution policy.
_CUSTOM_ID_FLOOR = 100_000


def _index_lookup(table: DbcTable | None, value_key: str) -> dict[int, int]:
    if table is None:
        return {}
    return {row["id"]: row[value_key] for row in table.rows}


def build_client_spell_records(
    spell: DbcTable,
    cast_times: DbcTable | None,
    durations: DbcTable | None,
    ranges: DbcTable | None,
    *,
    provenance: dict,
) -> list[dict]:
    cast_by_idx = _index_lookup(cast_times, "base_ms")
    dur_by_idx = _index_lookup(durations, "base_ms")
    range_max = {row["id"]: row.get("max_yd") for row in ranges.rows} if ranges else {}
    range_min = {row["id"]: row.get("min_yd") for row in ranges.rows} if ranges else {}

    # The whole Spell table is supplied by one effective archive, so its family is a
    # record-independent raw signal recorded on every row for M1.14B to consume.
    effective = provenance.get("effective_archive", "")
    archive_family = family_of(effective) if effective else "unknown"

    records: list[dict] = []
    for row in spell.rows:
        mechanics = {
            "school_mask": row.get("school_mask"),
            "power_type": row.get("power_type"),
            "cast_time_ms": cast_by_idx.get(row.get("casting_time_index")),
            "duration_ms": dur_by_idx.get(row.get("duration_index")),
            "range_min_yd": range_min.get(row.get("range_index")),
            "range_max_yd": range_max.get(row.get("range_index")),
            "category": row.get("category"),
            "spell_icon_id": row.get("spell_icon_id"),
        }
        records.append({
            "schema_version": "coa-client-spell-v1",
            "spell_id": row["id"],
            "name": row.get("name", ""),
            "mechanics": mechanics,
            "provenance": {
                **provenance,
                "schema_match_confidence": "low" if spell.drift else "high",
            },
            "coa_attribution": {
                "status": "unknown",  # M1.14A records raw signals; M1.14B decides
                "archive_family": archive_family,
                "id_range": "high" if row["id"] >= _CUSTOM_ID_FLOOR else "base",
            },
        })
    return records


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_jsonl(records: list[dict], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records)
    data = payload.encode("utf-8")
    path.write_bytes(data)
    return _sha256_bytes(data)


def write_json(doc: dict, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(data)
    return _sha256_bytes(data)


def _attribution_block(attr) -> dict:
    """One participation block from a SpellAttribution, or the low/absent default."""
    if attr is None:
        return {"is_coa": False, "modes": [], "exclusive_mode": None, "confidence": "low"}
    r = attr.result
    return {"is_coa": r.is_coa, "modes": list(r.modes),
            "exclusive_mode": r.exclusive_mode, "confidence": r.confidence}


def build_advancement_records(nodes, *, provenance: dict, spell_names: dict | None = None,
                              attribution: dict | None = None) -> list[dict]:
    spell_names = spell_names or {}
    attribution = attribution or {}
    records = []
    for n in nodes:
        records.append({
            "schema_version": "coa-client-advancement-v1",
            "node_id": n.node_id,
            "spell_id": n.spell_id,
            "name": spell_names.get(n.spell_id, ""),   # current name from coa-client-spell-v1 join
            "class": {"class_type_id": n.class_type_id, "internal": n.class_internal,
                      "display": n.class_display, "kind": n.class_kind},
            "tab": {"tab_type_id": n.tab_type_id, "name": n.tab_name},
            "entry_type": n.entry_type,
            "essence_kind": n.essence_kind,
            "legality": n.legality,
            "field_confidence": n.field_confidence,
            "raw": {"cols": dict(n.raw)},              # index-keyed {cell_index: value} audit map
            "provenance": dict(provenance),
            "coa_attribution": _attribution_block(attribution.get(n.spell_id)),
        })
    return records


def build_class_type_records(class_types) -> list[dict]:
    out = []
    for ct in class_types.values():
        out.append({
            "schema_version": "coa-client-class-types-v1",
            "class_type_id": ct.class_type_id,
            "internal": ct.internal, "display": ct.display, "kind": ct.kind,
            "display_source": ct.display_source,
            "display_evidence": list(ct.display_evidence),
        })
    return out


def build_tab_type_records(tab_types) -> list[dict]:
    """Emit coa-client-tab-types-v1 from the resolved {tab_type_id: name} map."""
    return [{"schema_version": "coa-client-tab-types-v1", "tab_type_id": tid, "name": name}
            for tid, name in sorted(tab_types.items())]


def build_essence_raw_records(essence, *, provenance: dict) -> list[dict]:
    """Emit CharacterAdvancementEssence RAW as coa-client-essence-v1.

    This table is per-level/per-tier essence *progression* data, NOT per-class caps (caps are the
    documented uniform constants AE 26 / TE 25). Its per-level semantics are undecoded, so M1.14B
    ships the raw index-keyed cells + provenance for auditability; the parity report reflects this as
    `readiness.leveling_progression_ready: false` (an M1.15 leveling gate) and it NEVER blocks any
    max-level readiness dimension or `full_builder_retirement_ready`. No column meaning is asserted here."""
    return [{"schema_version": "coa-client-essence-v1", "cols": dict(row),
             "provenance": dict(provenance)} for row in essence.rows]


def fill_spell_attribution(spell_records, attribution) -> list[dict]:
    for rec in spell_records:
        # Retain the M1.14A raw signals (archive_family/id_range) as provenance (spec: archive
        # family is kept as raw provenance only), and replace the M1.14A `status: unknown`.
        raw = rec.get("coa_attribution", {})
        keep = {k: raw[k] for k in ("archive_family", "id_range") if k in raw}
        attr = attribution.get(rec.get("spell_id"))
        block = _attribution_block(attr)
        block.update(keep)
        rec["coa_attribution"] = block
        # Stable multi-membership: attach the aggregated memberships[] (never a scalar that flips
        # to an array, never discarded). Absent attribution -> empty list.
        rec["memberships"] = list(attr.memberships) if attr is not None else []
    return spell_records
