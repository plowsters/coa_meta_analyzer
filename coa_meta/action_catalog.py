from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .domain import TalentNode
from .mechanics import MechanicEffect, MechanicRecord
from .mechanics_repository import MechanicsRepository


@dataclass(frozen=True)
class CatalogAction:
    action_key: str
    entry_id: int
    spell_id: int
    name: str
    costs: dict[str, float]
    generates: dict[str, float]
    spends: dict[str, float]
    cooldown_ms: int
    gcd_ms: int
    cast_time_ms: int | None
    range_yards: float | None
    duration_ms: int | None
    tick_interval_ms: int | None
    effects: tuple[MechanicEffect, ...]
    tags: tuple[str, ...]
    mechanic_kind: str
    confidence: str
    role_classification: str
    source: str
    warnings: tuple[str, ...] = tuple()
    mechanic: MechanicRecord | None = None
    node: TalentNode | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_key": self.action_key,
            "entry_id": self.entry_id,
            "spell_id": self.spell_id,
            "name": self.name,
            "costs": dict(self.costs),
            "generates": dict(self.generates),
            "spends": dict(self.spends),
            "cooldown_ms": self.cooldown_ms,
            "gcd_ms": self.gcd_ms,
            "cast_time_ms": self.cast_time_ms,
            "range_yards": self.range_yards,
            "duration_ms": self.duration_ms,
            "tick_interval_ms": self.tick_interval_ms,
            "effects": [effect.to_dict() for effect in self.effects],
            "tags": list(self.tags),
            "mechanic_kind": self.mechanic_kind,
            "confidence": self.confidence,
            "role_classification": self.role_classification,
            "source": self.source,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ActionCatalog:
    actions_by_key: dict[str, CatalogAction]
    actions_by_spell_id: dict[int, CatalogAction]
    warnings: tuple[str, ...]
    coverage_summary: dict[str, float | int]

    @property
    def actions(self) -> tuple[CatalogAction, ...]:
        return tuple(self.actions_by_key.values())


def build_action_catalog(
    selected_nodes: tuple[TalentNode, ...] | list[TalentNode],
    mechanics_repo: MechanicsRepository,
    *,
    role: str,
    encounter: str,
) -> ActionCatalog:
    actions: list[CatalogAction] = []
    warnings: list[str] = []
    passive_skipped = 0
    missing_mechanics = 0

    for node in selected_nodes:
        mechanic = mechanics_repo.get_spell_id(int(node.spell_id or 0)) if node.spell_id else None
        if node.is_passive or mechanic and mechanic.kind == "passive":
            passive_skipped += 1
            continue

        if mechanic is None:
            missing_mechanics += 1
            warnings.append(f"missing_mechanics:{node.spell_id}")
            actions.append(_fallback_action(node, role))
            continue

        actions.append(_action_from_mechanic(node, mechanic, role))

    actions_by_key = {action.action_key: action for action in actions}
    actions_by_spell_id = {action.spell_id: action for action in actions}
    selected_count = len(tuple(selected_nodes))
    coverage = (
        round((selected_count - passive_skipped - missing_mechanics) / max(selected_count - passive_skipped, 1) * 100, 2)
        if selected_count
        else 0.0
    )

    return ActionCatalog(
        actions_by_key=actions_by_key,
        actions_by_spell_id=actions_by_spell_id,
        warnings=tuple(warnings),
        coverage_summary={
            "selected_node_count": selected_count,
            "executable_action_count": len(actions),
            "passive_skipped_count": passive_skipped,
            "missing_mechanics_count": missing_mechanics,
            "mechanics_coverage_pct": coverage,
        },
    )


def classify_action_role(mechanic: MechanicRecord, *, role: str) -> str:
    effect_types = {effect.effect_type for effect in mechanic.effects}
    effect_tags = {tag for effect in mechanic.effects for tag in effect.tags}
    mechanic_tags = effect_tags | {mechanic.kind}

    if role == "support" and ("support" in effect_tags or "aura_apply" in effect_types):
        return "support"
    if "heal" in effect_types:
        return "heal"
    if effect_types & {"damage_reduction", "shield", "absorb"} or mechanic_tags & {"tank", "mitigation"}:
        return "mitigation"
    if effect_types & {"damage"} or mechanic.kind == "debuff":
        return "damage"
    if effect_types & {"summon", "aura_apply", "stat_modify"} or mechanic.kind in {"pet_action", "cooldown"}:
        return "utility"
    return "unknown"


def _action_from_mechanic(node: TalentNode, mechanic: MechanicRecord, role: str) -> CatalogAction:
    return CatalogAction(
        action_key=_action_key(mechanic.name or node.name),
        entry_id=node.entry_id,
        spell_id=int(node.spell_id or mechanic.spell_id),
        name=mechanic.name or node.name,
        costs=dict(mechanic.costs),
        generates=dict(mechanic.generates),
        spends=dict(mechanic.spends),
        cooldown_ms=mechanic.cooldown_ms or 0,
        gcd_ms=mechanic.gcd_ms if mechanic.gcd_ms is not None else 1500,
        cast_time_ms=mechanic.cast_time_ms,
        range_yards=mechanic.range_yards,
        duration_ms=mechanic.duration_ms,
        tick_interval_ms=mechanic.tick_interval_ms or _first_tick_interval(mechanic.effects),
        effects=mechanic.effects,
        tags=tuple(dict.fromkeys((*node.tags, *(tag for effect in mechanic.effects for tag in effect.tags)))),
        mechanic_kind=mechanic.kind,
        confidence=mechanic.confidence,
        role_classification=classify_action_role(mechanic, role=role),
        source="mechanics",
        warnings=tuple(),
        mechanic=mechanic,
        node=node,
    )


def _fallback_action(node: TalentNode, role: str) -> CatalogAction:
    return CatalogAction(
        action_key=_action_key(node.name),
        entry_id=node.entry_id,
        spell_id=int(node.spell_id or 0),
        name=node.name,
        costs={},
        generates={},
        spends={},
        cooldown_ms=0,
        gcd_ms=1500,
        cast_time_ms=None,
        range_yards=None,
        duration_ms=None,
        tick_interval_ms=None,
        effects=tuple(),
        tags=node.tags,
        mechanic_kind="unknown",
        confidence="low",
        role_classification="unknown",
        source="fallback",
        warnings=(f"missing_mechanics:{node.spell_id}",),
        mechanic=None,
        node=node,
    )


def _first_tick_interval(effects: tuple[MechanicEffect, ...]) -> int | None:
    for effect in effects:
        if effect.tick_interval_ms is not None:
            return effect.tick_interval_ms
    return None


def _action_key(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    return value or "action"
