from __future__ import annotations

from dataclasses import dataclass

# Verified against the real client (2026-07-13). Ids are CharacterAdvancementClassTypes row ids.
PLAYABLE_COA_IDS = range(14, 35)      # 14..34 inclusive = 21 playable CoA classes
COA_SENTINEL_ID = 35                  # ConquestOfAzeroth: umbrella sentinel, NOT playable
_REBORN_IDS = range(36, 47)
_META_IDS = {12, 13}                  # General, Hero
_STOCK_IDS = range(2, 12)             # Hunter..DeathKnight

# Curated alpha->display aliases (presentation metadata only; never change class_type_id or
# attribution). Alpha classes revamped into current classes; owner- and Builder-confirmed.
DISPLAY_ALIASES: dict[int, str] = {22: "Bloodmage", 16: "Felsworn", 21: "Templar"}
_ALIAS_EVIDENCE = ("builder_class_name", "project_owner_confirmation")


@dataclass(frozen=True)
class ClassType:
    class_type_id: int
    internal: str            # raw client name (independently recoverable identity)
    display: str             # internal, unless a curated alias overrides it
    kind: str                # coa_class | coa_system | reborn | stock | meta | unknown
    display_source: str = "client"
    display_evidence: tuple[str, ...] = ()


def _kind(cid: int) -> str:
    if cid == COA_SENTINEL_ID:
        return "coa_system"
    if cid in PLAYABLE_COA_IDS:
        return "coa_class"
    if cid in _REBORN_IDS:
        return "reborn"
    if cid in _META_IDS:
        return "meta"
    if cid in _STOCK_IDS:
        return "stock"
    return "unknown"     # outside every known band: possible new class / drift, never silently stock


def resolve_class_types(table) -> dict[int, ClassType]:
    out: dict[int, ClassType] = {}
    for row in table.rows:
        cid = row["id"]
        internal = row.get("name") or ""
        if cid in DISPLAY_ALIASES:
            out[cid] = ClassType(cid, internal, DISPLAY_ALIASES[cid], _kind(cid),
                                  "curated_alias", _ALIAS_EVIDENCE)
        else:
            out[cid] = ClassType(cid, internal, internal, _kind(cid))
    return out


def resolve_tab_types(table) -> dict[int, str]:
    return {row["id"]: (row.get("name") or "") for row in table.rows}


def assert_playable_cardinality(resolved: dict[int, ClassType]) -> None:
    playable = [c for c in resolved.values() if c.kind == "coa_class"]
    if len(playable) != 21:
        raise ValueError(
            f"expected 21 playable CoA classes, resolved {len(playable)}: "
            f"{sorted(c.class_type_id for c in playable)}"
        )
