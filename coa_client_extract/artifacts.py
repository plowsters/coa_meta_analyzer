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
