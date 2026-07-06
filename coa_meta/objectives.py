from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .scoring import ScoreComponent


OBJECTIVE_LABELS: dict[str, tuple[str, str]] = {
    "melee_dps": ("damage", "Projected Damage Index"),
    "ranged_dps": ("damage", "Projected Damage Index"),
    "caster_dps": ("damage", "Projected Damage Index"),
    "healer": ("healing", "Projected Healing Index"),
    "tank": ("survival_threat", "Projected Survival/Threat Index"),
    "support": ("support", "Projected Support Index"),
}


@dataclass(frozen=True)
class RoleObjectiveResult:
    objective_id: str
    role: str
    primary_index: float
    primary_index_label: str
    objective_breakdown: dict[str, float]
    alternate_objective_scores: dict[str, dict[str, Any]]
    warnings: tuple[str, ...] = tuple()

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "role": self.role,
            "primary_index": self.primary_index,
            "primary_index_label": self.primary_index_label,
            "objective_breakdown": dict(self.objective_breakdown),
            "alternate_objective_scores": {
                role: dict(payload) for role, payload in self.alternate_objective_scores.items()
            },
            "warnings": list(self.warnings),
        }


def objective_for_role(
    role: str,
    projected_index: float,
    components: tuple[ScoreComponent, ...],
    *,
    secondary_roles: tuple[str, ...] = tuple(),
) -> RoleObjectiveResult:
    objective_id, label = _objective_label(role)
    breakdown = _component_breakdown(components)
    alternate_scores = {
        secondary: _alternate_payload(secondary, projected_index, breakdown)
        for secondary in secondary_roles
        if secondary != role
    }
    return RoleObjectiveResult(
        objective_id=objective_id,
        role=role,
        primary_index=projected_index,
        primary_index_label=label,
        objective_breakdown=breakdown,
        alternate_objective_scores=alternate_scores,
        warnings=("role_objective_uses_shared_theorycraft_score",),
    )


def _objective_label(role: str) -> tuple[str, str]:
    return OBJECTIVE_LABELS.get(role, OBJECTIVE_LABELS["melee_dps"])


def _component_breakdown(components: tuple[ScoreComponent, ...]) -> dict[str, float]:
    breakdown: dict[str, float] = {}
    for component in components:
        key = f"{component.kind}:{component.key}"
        breakdown[key] = round(breakdown.get(key, 0.0) + float(component.value), 2)
    return dict(sorted(breakdown.items()))


def _alternate_payload(role: str, projected_index: float, breakdown: dict[str, float]) -> dict[str, Any]:
    objective_id, label = _objective_label(role)
    return {
        "objective_id": objective_id,
        "role": role,
        "primary_index": projected_index,
        "primary_index_label": label,
        "objective_breakdown": dict(breakdown),
        "warnings": ["role_objective_uses_shared_theorycraft_score"],
    }
