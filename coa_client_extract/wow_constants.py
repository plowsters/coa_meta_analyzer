from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

AUTHORED_INPUTS = ("wow_rules", "rating_enum", "power_type_enum",
                   "gt_axis_policy", "wotlk_reference_anchors")
_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class AuthoredInput:
    name: str
    payload: dict
    version: str
    sha256: str


def load_authored_input(name: str, *, root: Path | None = None) -> AuthoredInput:
    path = (root or _DATA_DIR) / f"{name}_v1.json"
    raw = path.read_bytes()
    payload = json.loads(raw)
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{path.name}: missing string 'version'")
    return AuthoredInput(name=name, payload=payload, version=version,
                         sha256=hashlib.sha256(raw).hexdigest())


from .dbc_layouts import GameTableLayout
from .wdbc import GameTable


def load_axis_policy(payload: dict) -> tuple[dict[str, GameTableLayout], int, int]:
    level_stride = int(payload["level_stride"])
    rating_stride = int(payload["rating_stride"])
    defaults = payload.get("defaults", {})
    layouts: dict[str, GameTableLayout] = {}
    for group in ("tables", "recon_gated"):
        for key, spec in payload.get(group, {}).items():
            layouts[key] = GameTableLayout(
                key=key, source_dbc=spec["source_dbc"],
                physical_form=spec.get("physical_form", defaults["physical_form"]),
                key_source=spec.get("key_source", defaults["key_source"]),
                expected_field_count=int(spec.get("expected_field_count", defaults["expected_field_count"])),
                expected_record_size=int(spec.get("expected_record_size", defaults["expected_record_size"])),
                value_cell=int(spec.get("value_cell", defaults["value_cell"])),
                id_cell=spec.get("id_cell", defaults["id_cell"]),
                index_kind=spec["index_kind"], axes=tuple(spec["axes"]),
                class_indexed=bool(spec["class_indexed"]), supported=spec.get("supported", {}),
                index_offset=int(spec.get("index_offset", 0)),
                semantics=spec.get("semantics", "proven"))
    return layouts, level_stride, rating_stride


def _build_index(layout: GameTableLayout, table: GameTable) -> dict[int, float]:
    if layout.key_source == "explicit_id":
        index: dict[int, float] = {}
        for r in table.rows:
            if r["id"] in index:
                raise ValueError(f"{layout.key}: duplicate explicit id {r['id']}")
            index[r["id"]] = r["value"]
        return index
    return {r["ordinal"]: r["value"] for r in table.rows}


def map_table_entries(layout: GameTableLayout, table: GameTable, *, class_roster: list[int],
                      level_stride: int, rating_stride: int) -> tuple[list[dict], dict]:
    """Invert the reference index into explicit-coordinate entries. Uses the explicit id as the
    index when the physical form carries one (validating uniqueness), else the row ordinal.
    Never derives class width from a count."""
    by_index = _build_index(layout, table)
    entries: list[dict] = []

    def emit(index: int, coords: dict) -> None:
        if index in by_index:
            entries.append({**coords, "value": by_index[index]})

    if layout.index_kind == "rating_by_level":
        for rating_id in range(layout.supported["rating_id"]["min"], layout.supported["rating_id"]["max"] + 1):
            for level in range(layout.supported["level"]["min"], layout.supported["level"]["max"] + 1):
                emit(rating_id * level_stride + (level - 1), {"rating_id": rating_id, "level": level})
    elif layout.index_kind == "class_rating_scalar":
        for wow_class_id in class_roster:
            for rating_id in range(layout.supported["rating_id"]["min"], layout.supported["rating_id"]["max"] + 1):
                emit((wow_class_id - 1) * rating_stride + rating_id + layout.index_offset,
                     {"wow_class_id": wow_class_id, "rating_id": rating_id})
    elif layout.index_kind == "class_by_level":
        for wow_class_id in class_roster:
            for level in range(layout.supported["level"]["min"], layout.supported["level"]["max"] + 1):
                emit((wow_class_id - 1) * level_stride + (level - 1), {"wow_class_id": wow_class_id, "level": level})
    elif layout.index_kind == "class_only":
        for wow_class_id in class_roster:
            emit(wow_class_id - 1, {"wow_class_id": wow_class_id})
    else:
        raise ValueError(f"unknown index_kind {layout.index_kind!r}")

    counts = {"source_records": table.record_count, "emitted_entries": len(entries),
              "padding_records": table.record_count - len(entries)}
    return entries, counts
