from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

DEFAULT_FILES: dict[str, str] = {
    "SpellRankData.json": "spell_rank",
    "SpellToStatSuggestionData.json": "spell_stat_suggestion",
    "SpellToRoleSuggestionData.json": "spell_role_suggestion",
    "ItemVariationData.json": "item_variation",
    "CharacterAdvancementData.json": "character_advancement",
}
_INVESTIGATE = {"character_advancement"}


def _id_fields(entry: dict) -> dict:
    out: dict = {}
    if "Spell" in entry:
        out["spell_id"] = entry["Spell"]
    if "Item" in entry:
        out["item_id"] = entry["Item"]
    return out


def read_content_records(content_dir: Path, *, files: dict[str, str] | None = None) -> list[dict]:
    files = files if files is not None else DEFAULT_FILES
    today = date.today().isoformat()
    records: list[dict] = []
    for filename, kind in files.items():
        path = content_dir / filename
        if not path.is_file():
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw.decode("utf-8"))
        entries = payload if isinstance(payload, list) else payload.get("data", [])
        for entry in entries:
            ids = _id_fields(entry)
            values = {k: v for k, v in entry.items() if k not in ("Spell", "Item")}
            record = {
                "schema_version": "coa-client-content-v1",
                "content_kind": kind,
                **ids,
                "values": values,
                "provenance": {
                    "source_file": filename,
                    "file_sha256": digest,
                    "extraction_date": today,
                },
                "coa_attribution": {"status": "unknown"},
            }
            if kind in _INVESTIGATE:
                record["coa_attribution"]["note"] = "investigate: may be classless/Area-52 system"
            records.append(record)
    return records
