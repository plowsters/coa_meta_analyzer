from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

WOW_CONSTANTS_SCHEMA_VERSION = "coa-wow-constants-v1"
WOW_CONSTANTS_MANIFEST_SCHEMA = "coa-wow-constants-manifest-v1"
_REQUIRED_RULE_LABELS = ("authority", "ascension_verification", "applies_to")


class WowConstantsLoadError(ValueError):
    pass


class WowConstantsRepository:
    """Loads coa-wow-constants-v1 (verifying its sibling manifest), validates structure, and looks up
    RAW values by coordinate with provenance. It performs no calculation (no rating->%, GCD, crit, or
    regen math) and never maps a CoA class-type id into a wow_class_id."""

    def __init__(self, tables, class_axis, rules, rating_enum, provenance):
        self._tables, self._class_axis = tables, class_axis
        self._rules, self._rating_enum, self._provenance = rules, rating_enum, provenance

    @classmethod
    def load(cls, path: str | Path) -> "WowConstantsRepository":
        path = Path(path)
        body = path.read_bytes()
        manifest_path = path.with_name("coa_wow_constants.manifest.json")
        if not manifest_path.is_file():
            raise WowConstantsLoadError("missing sibling manifest")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("schema_version") != WOW_CONSTANTS_MANIFEST_SCHEMA:
            raise WowConstantsLoadError("bad manifest schema_version")
        art = manifest.get("artifact", {})
        if art.get("path") != path.name:
            raise WowConstantsLoadError("manifest artifact path mismatch")
        if art.get("sha256") != hashlib.sha256(body).hexdigest():
            raise WowConstantsLoadError("manifest artifact hash mismatch (tampered or stale)")
        if art.get("byte_length") != len(body):
            raise WowConstantsLoadError("manifest byte_length mismatch")
        doc = json.loads(body)
        if manifest.get("client_build") != doc.get("client_build"):
            raise WowConstantsLoadError("manifest/artifact client_build mismatch")
        return cls.from_dict(doc)

    @classmethod
    def from_dict(cls, doc: dict) -> "WowConstantsRepository":
        if doc.get("schema_version") != WOW_CONSTANTS_SCHEMA_VERSION:
            raise WowConstantsLoadError(f"unsupported schema_version {doc.get('schema_version')!r}")
        class_axis = doc.get("class_axis") or {}
        rating_enum = (doc.get("enum_maps") or {}).get("rating_enum") or {}
        supported = set((rating_enum.get("supported") or {}))
        indexed: dict[str, dict] = {}
        for key, table in (doc.get("game_tables") or {}).items():
            axes = tuple(table.get("axes") or ())
            if not axes:
                raise WowConstantsLoadError(f"{key}: missing axes")
            seen: dict[tuple, float] = {}
            for entry in table.get("entries") or []:
                value = entry.get("value")
                if value is None or not math.isfinite(value):
                    raise WowConstantsLoadError(f"{key}: non-finite/missing value")
                if "rating_id" in entry and str(entry["rating_id"]) not in supported:
                    raise WowConstantsLoadError(f"{key}: unmapped rating_id {entry['rating_id']}")
                coord = tuple(entry[a] for a in axes)
                if coord in seen:
                    raise WowConstantsLoadError(f"{key}: duplicate coordinate {coord}")
                seen[coord] = float(value)
            counts = table.get("counts") or {}
            if "emitted_entries" in counts and counts["emitted_entries"] != len(seen):
                raise WowConstantsLoadError(f"{key}: counts.emitted_entries != number of entries")
            indexed[key] = {"axes": axes, "class_indexed": bool(table.get("class_indexed")),
                            "source_dbc": table.get("source_dbc"), "by_coord": seen}
        rules = doc.get("rules") or {}
        for name, rule in rules.items():
            if any(label not in rule for label in _REQUIRED_RULE_LABELS):
                raise WowConstantsLoadError(f"rule {name!r} missing a required label")
        return cls(indexed, class_axis, rules, rating_enum, doc.get("provenance") or {})

    # -- lookups (raw values; no computation) --
    def _lookup(self, key: str, coord: tuple) -> float:
        table = self._tables.get(key)
        if table is None:
            raise LookupError(f"no table {key!r}")
        try:
            return table["by_coord"][coord]
        except KeyError:
            raise LookupError(f"{key}: no value at {dict(zip(table['axes'], coord))}")

    def _require_wow_class(self, wow_class_id: int) -> None:
        observed = set(self._class_axis.get("observed_client_ids") or [])
        if wow_class_id not in observed:
            raise LookupError(f"wow_class_id {wow_class_id} not in ChrClasses namespace {sorted(observed)}; "
                              f"class context is M1.16's to resolve")

    def combat_rating_ratio(self, rating_id: int, level: int) -> float:
        return self._lookup("combat_ratings", (rating_id, level))

    def class_combat_rating_scalar(self, *, wow_class_id: int, rating_id: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("class_combat_rating_scalar", (wow_class_id, rating_id))

    def melee_crit_per_agi(self, *, wow_class_id: int, level: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("melee_crit_per_agi", (wow_class_id, level))

    def melee_crit_base(self, *, wow_class_id: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("melee_crit_base", (wow_class_id,))

    def spell_crit_per_int(self, *, wow_class_id: int, level: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("spell_crit_per_int", (wow_class_id, level))

    def spell_crit_base(self, *, wow_class_id: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("spell_crit_base", (wow_class_id,))

    def mana_regen_per_spirit(self, *, wow_class_id: int, level: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("mana_regen_per_spirit", (wow_class_id, level))

    def default_power_type(self, wow_class_id: int) -> str:
        mapping = self._class_axis.get("default_power_type_by_wow_class_id") or {}
        if str(wow_class_id) not in mapping:
            raise LookupError(f"no default power type for wow_class_id {wow_class_id}")
        return mapping[str(wow_class_id)]

    def rule(self, key: str) -> dict:
        if key not in self._rules:
            raise LookupError(f"no rule {key!r}")
        return dict(self._rules[key])

    def rating_name(self, rating_id: int) -> str:
        name = (self._rating_enum.get("supported") or {}).get(str(rating_id))
        if name is None:
            raise LookupError(f"unmapped rating_id {rating_id}")
        return name

    def table_provenance(self, key: str) -> dict:
        table = self._tables.get(key)
        if table is None:
            raise LookupError(f"no table {key!r}")
        src = table.get("source_dbc")
        return dict((self._provenance.get("source_dbcs") or {}).get(src, {}))
