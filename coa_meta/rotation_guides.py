from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ROTATION_GUIDE_SCHEMA_VERSION = "coa-rotation-guide-v1"
VALID_RELIABILITY = {"high", "medium", "low"}
VALID_SOURCES = {"theorycraft", "simulated", "empirical", "blended"}


@dataclass(frozen=True)
class RotationGuideRule:
    rule_id: str
    section: str
    text: str
    ability_name: str
    spell_id: int | None = None
    entry_id: int | None = None
    icon: str | None = None
    db_url: str | None = None
    condition: str = ""
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "section": self.section,
            "text": self.text,
            "ability_name": self.ability_name,
            "spell_id": self.spell_id,
            "entry_id": self.entry_id,
            "icon": self.icon,
            "db_url": self.db_url,
            "condition": self.condition,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class ActionUsageSummary:
    action_key: str
    ability_name: str
    count: int
    first_used_ms: int | None = None
    last_used_ms: int | None = None
    uptime_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_key": self.action_key,
            "ability_name": self.ability_name,
            "count": self.count,
            "first_used_ms": self.first_used_ms,
            "last_used_ms": self.last_used_ms,
            "uptime_pct": self.uptime_pct,
        }


@dataclass(frozen=True)
class RotationSimulationSummary:
    source: str
    role: str
    encounter: str
    duration_ms: int
    objective_score: float
    reliability: str
    action_count: int
    unsupported_condition_count: int
    unsupported_effect_count: int
    warnings: tuple[str, ...] = tuple()

    def __post_init__(self) -> None:
        _validate_reliability(self.reliability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "role": self.role,
            "encounter": self.encounter,
            "duration_ms": self.duration_ms,
            "objective_score": self.objective_score,
            "reliability": self.reliability,
            "action_count": self.action_count,
            "unsupported_condition_count": self.unsupported_condition_count,
            "unsupported_effect_count": self.unsupported_effect_count,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class RotationGuide:
    source: str
    role: str
    encounter: str
    build_id: str
    simulation_summary: RotationSimulationSummary
    opener: tuple[RotationGuideRule, ...] = tuple()
    core_loop: tuple[RotationGuideRule, ...] = tuple()
    priority_rules: tuple[RotationGuideRule, ...] = tuple()
    cooldown_rules: tuple[RotationGuideRule, ...] = tuple()
    proc_rules: tuple[RotationGuideRule, ...] = tuple()
    defensive_rules: tuple[RotationGuideRule, ...] = tuple()
    healing_rules: tuple[RotationGuideRule, ...] = tuple()
    support_rules: tuple[RotationGuideRule, ...] = tuple()
    aoe_adjustments: tuple[RotationGuideRule, ...] = tuple()
    movement_notes: tuple[str, ...] = tuple()
    ability_sequence: tuple[str, ...] = tuple()
    action_usage: tuple[ActionUsageSummary, ...] = tuple()
    reliability: str = "medium"
    warnings: tuple[str, ...] = tuple()

    def __post_init__(self) -> None:
        _validate_reliability(self.reliability)
        if self.source not in VALID_SOURCES:
            raise ValueError(f"Invalid rotation guide source: {self.source}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ROTATION_GUIDE_SCHEMA_VERSION,
            "source": self.source,
            "role": self.role,
            "encounter": self.encounter,
            "build_id": self.build_id,
            "simulation_summary": self.simulation_summary.to_dict(),
            "opener": _rule_list(self.opener),
            "core_loop": _rule_list(self.core_loop),
            "priority_rules": _rule_list(self.priority_rules),
            "cooldown_rules": _rule_list(self.cooldown_rules),
            "proc_rules": _rule_list(self.proc_rules),
            "defensive_rules": _rule_list(self.defensive_rules),
            "healing_rules": _rule_list(self.healing_rules),
            "support_rules": _rule_list(self.support_rules),
            "aoe_adjustments": _rule_list(self.aoe_adjustments),
            "movement_notes": list(self.movement_notes),
            "ability_sequence": list(self.ability_sequence),
            "action_usage": [item.to_dict() for item in self.action_usage],
            "reliability": self.reliability,
            "warnings": list(self.warnings),
        }


def _rule_list(rules: tuple[RotationGuideRule, ...]) -> list[dict[str, Any]]:
    return [rule.to_dict() for rule in rules]


def _validate_reliability(value: str) -> None:
    if value not in VALID_RELIABILITY:
        raise ValueError(f"Invalid rotation reliability: {value}")
