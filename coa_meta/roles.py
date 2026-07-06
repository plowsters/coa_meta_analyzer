from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .display_names import display_spec_name, slugify_key
from .domain import TalentNode
from .repository import TalentRepository

GuideRole = Literal["melee_dps", "caster_dps", "ranged_dps", "tank", "healer", "support"]
EngineRole = Literal["dps", "tank", "healer_support"]

GUIDE_ROLES: tuple[GuideRole, ...] = ("melee_dps", "caster_dps", "ranged_dps", "tank", "healer", "support")
ENGINE_ROLES: tuple[EngineRole, ...] = ("dps", "tank", "healer_support")
ROLE_OVERRIDE_PATH = Path(__file__).parent / "data" / "role_overrides.json"
SPEC_ROLE_MAP_PATH = Path(__file__).parent / "data" / "spec_roles.json"


@dataclass(frozen=True)
class SpecRoleRecord:
    class_name: str
    source_spec_name: str
    display_spec_name: str
    primary_role: GuideRole
    secondary_roles: tuple[GuideRole, ...]
    engine_role: EngineRole
    complexity: str
    source: str
    confidence: str
    evidence: tuple[str, ...]
    source_urls: tuple[str, ...]
    notes: str = ""

    @property
    def roles(self) -> tuple[GuideRole, ...]:
        return roles_for_filter(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "coa-spec-role-record-v1",
            "class_name": self.class_name,
            "source_spec_name": self.source_spec_name,
            "display_spec_name": self.display_spec_name,
            "primary_role": self.primary_role,
            "secondary_roles": list(self.secondary_roles),
            "roles": list(self.roles),
            "engine_role": self.engine_role,
            "complexity": self.complexity,
            "source": self.source,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "source_urls": list(self.source_urls),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RoleResolution:
    role: GuideRole
    engine_role: EngineRole
    source: str
    confidence: str
    evidence: tuple[str, ...]
    scores: dict[str, float]
    secondary_roles: tuple[GuideRole, ...] = tuple()

    @property
    def roles(self) -> tuple[GuideRole, ...]:
        roles: list[GuideRole] = [self.role]
        for role in self.secondary_roles:
            if role not in roles:
                roles.append(role)
        return tuple(roles)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "coa-role-resolution-v1",
            "role": self.role,
            "primary_role": self.role,
            "secondary_roles": list(self.secondary_roles),
            "roles": list(self.roles),
            "engine_role": self.engine_role,
            "source": self.source,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "scores": dict(sorted(self.scores.items())),
        }


def engine_role_for_guide_role(role: str) -> EngineRole:
    if role in {"melee_dps", "caster_dps", "ranged_dps"}:
        return "dps"
    if role == "tank":
        return "tank"
    if role in {"healer", "support"}:
        return "healer_support"
    if role == "dps":
        return "dps"
    if role == "healer_support":
        return "healer_support"
    raise ValueError(f"Unsupported guide role {role!r}")


def resolve_configured_role(configured_role: str, inferred: RoleResolution) -> RoleResolution:
    if configured_role == "auto":
        return inferred
    if configured_role == "dps":
        if inferred.role in {"melee_dps", "caster_dps", "ranged_dps"}:
            return inferred
        return _configured("melee_dps", "configured broad dps fallback")
    if configured_role == "healer_support":
        if inferred.role in {"healer", "support"}:
            return inferred
        return _configured("healer", "configured broad healer_support fallback")
    if configured_role in GUIDE_ROLES:
        return _configured(configured_role, "configured explicit guide role")
    if configured_role in ENGINE_ROLES:
        return _configured(configured_role, "configured broad engine role")
    raise ValueError(f"Unsupported role {configured_role!r}")


def resolve_spec_role(repository: TalentRepository, scope: Any) -> RoleResolution:
    spec_role = resolve_spec_role_record(scope.class_name, scope.spec_name, scope.spec_key)
    if spec_role:
        role = spec_role.primary_role
        return RoleResolution(
            role=role,
            engine_role=spec_role.engine_role,
            source=spec_role.source,
            confidence=spec_role.confidence,
            evidence=spec_role.evidence,
            scores={role: 100.0, **{secondary: 80.0 for secondary in spec_role.secondary_roles}},
            secondary_roles=spec_role.secondary_roles,
        )
    override = _override_for(scope.class_name, scope.spec_name, scope.spec_key)
    if override:
        role = override["role"]
        return RoleResolution(
            role=role,
            engine_role=engine_role_for_guide_role(role),
            source="curated",
            confidence=str(override.get("confidence") or "medium"),
            evidence=tuple(str(item) for item in override.get("evidence") or []),
            scores={role: 100.0},
        )
    nodes = [
        node
        for node in repository.nodes_for_class(scope.class_name)
        if node.tab_id == scope.spec_id and node.tab_name == scope.spec_name
    ]
    return infer_role_from_nodes(nodes)


def infer_role_from_nodes(nodes: list[TalentNode]) -> RoleResolution:
    scores = _role_scores(nodes)
    role = max(GUIDE_ROLES, key=lambda item: (scores[item], -GUIDE_ROLES.index(item)))
    if scores["tank"] >= 20 and scores["tank"] >= scores["healer"] - 5:
        role = "tank"
    elif scores["healer"] >= 24 and scores["healer"] >= scores["support"] + 4:
        role = "healer"
    elif scores["support"] >= 22 and scores["support"] > scores["healer"]:
        role = "support"
    elif role in {"tank", "healer", "support"} and scores[role] < 10:
        role = _best_dps_role(scores)
    confidence = "medium" if scores[role] >= 12 else "low"
    evidence = tuple(
        f"{key}:{value:.1f}"
        for key, value in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
    )
    return RoleResolution(
        role=role,
        engine_role=engine_role_for_guide_role(role),
        source="inferred",
        confidence=confidence,
        evidence=evidence,
        scores=scores,
    )


def _role_scores(nodes: list[TalentNode]) -> dict[str, float]:
    tags = Counter(tag for node in nodes for tag in node.tags)
    text = " ".join(f"{node.name} {node.description_text}" for node in nodes).lower()
    return {
        "tank": tags["tank"] * 3.0
        + _count_text(
            text,
            (
                r"\btank\b",
                r"\bthreat\b",
                r"\barmor\b",
                r"\bblock\b",
                r"\bparry\b",
                r"\bdodge\b",
                r"damage taken",
            ),
        ),
        "healer": tags["heal"] * 3.0
        + tags["hot"] * 3.0
        + _count_text(
            text,
            (r"\bheal", r"\bhealing\b", r"\bally\b", r"\ballies\b", r"\bparty\b", r"\braid\b"),
        ),
        "support": tags["aura"] * 3.0
        + tags["crowd_control"] * 1.5
        + tags["resource_management"]
        + _count_text(text, (r"\baura\b", r"\bbuff\b", r"\bdebuff\b", r"\bgroup\b", r"\ballies\b")),
        "melee_dps": tags["melee"] * 2.0
        + tags["builder"]
        + tags["spender"]
        + _count_text(text, (r"\bmelee\b", r"\bstrike\b", r"\bfang\b", r"\bblade\b")),
        "caster_dps": tags["dot"] * 1.5
        + tags["proc"]
        + _count_text(
            text,
            (r"\bspell\b", r"\bcast\b", r"\bshadow\b", r"\bnature\b", r"\bfire\b", r"\bfrost\b", r"\barcane\b"),
        ),
        "ranged_dps": tags["ranged"] * 2.4
        + tags["builder"] * 0.6
        + tags["spender"] * 0.6
        + _count_text(
            text,
            (r"\branged\b", r"\bbow\b", r"\bgun\b", r"\bshot\b", r"\barrow\b", r"\barcher", r"\bbolt"),
        ),
    }


def _count_text(text: str, patterns: tuple[str, ...]) -> float:
    return float(sum(len(re.findall(pattern, text)) for pattern in patterns))


def _configured(role: str, evidence: str) -> RoleResolution:
    guide_role = {
        "dps": "melee_dps",
        "healer_support": "healer",
        "tank": "tank",
    }.get(role, role)
    return RoleResolution(
        role=guide_role,
        engine_role=engine_role_for_guide_role(guide_role),
        source="configured",
        confidence="high",
        evidence=(evidence,),
        scores={guide_role: 100.0},
    )


def _best_dps_role(scores: dict[str, float]) -> GuideRole:
    dps_roles: tuple[GuideRole, ...] = ("melee_dps", "caster_dps", "ranged_dps")
    return max(dps_roles, key=lambda item: (scores[item], -GUIDE_ROLES.index(item)))


def load_spec_role_records(path: Path | str = SPEC_ROLE_MAP_PATH) -> tuple[SpecRoleRecord, ...]:
    source_path = Path(path)
    if not source_path.exists():
        return tuple()
    data = json.loads(source_path.read_text(encoding="utf-8"))
    records: list[SpecRoleRecord] = []
    for raw in data.get("specs", []):
        primary_role = _guide_role(str(raw["primary_role"]))
        secondary_roles = tuple(_guide_role(str(role)) for role in raw.get("secondary_roles", []))
        class_name = str(raw["class_name"])
        source_spec_name = str(raw["source_spec_name"])
        display_name = str(raw.get("display_spec_name") or display_spec_name(class_name, source_spec_name))
        records.append(
            SpecRoleRecord(
                class_name=class_name,
                source_spec_name=source_spec_name,
                display_spec_name=display_name,
                primary_role=primary_role,
                secondary_roles=secondary_roles,
                engine_role=_engine_role(str(raw.get("engine_role") or engine_role_for_guide_role(primary_role))),
                complexity=str(raw.get("complexity") or ""),
                source=str(raw.get("source") or "curated"),
                confidence=str(raw.get("confidence") or "medium"),
                evidence=tuple(str(item) for item in raw.get("evidence") or []),
                source_urls=tuple(str(item) for item in raw.get("source_urls") or []),
                notes=str(raw.get("notes") or ""),
            )
        )
    return tuple(records)


def resolve_spec_role_record(class_name: str, spec_name: str, spec_key: str | None = None) -> SpecRoleRecord | None:
    class_key = slugify_key(class_name)
    spec_keys = {slugify_key(spec_name)}
    if spec_key:
        spec_keys.add(slugify_key(spec_key))
    for record in load_spec_role_records():
        if slugify_key(record.class_name) != class_key:
            continue
        if slugify_key(record.source_spec_name) in spec_keys or slugify_key(record.display_spec_name) in spec_keys:
            return record
    return None


def roles_for_filter(record: SpecRoleRecord) -> tuple[GuideRole, ...]:
    roles: list[GuideRole] = [record.primary_role]
    for role in record.secondary_roles:
        if role not in roles:
            roles.append(role)
    return tuple(roles)


def _guide_role(value: str) -> GuideRole:
    if value not in GUIDE_ROLES:
        raise ValueError(f"Unsupported guide role {value!r}")
    return value  # type: ignore[return-value]


def _engine_role(value: str) -> EngineRole:
    if value not in ENGINE_ROLES:
        raise ValueError(f"Unsupported engine role {value!r}")
    return value  # type: ignore[return-value]


def _override_for(class_name: str, spec_name: str, spec_key: str) -> dict[str, Any] | None:
    data = _load_overrides()
    for override in data:
        if override.get("class_name") == class_name and override.get("spec_name") == spec_name:
            return override
    for override in data:
        if override.get("spec_key") == spec_key:
            return override
    return None


def _load_overrides() -> tuple[dict[str, Any], ...]:
    if not ROLE_OVERRIDE_PATH.exists():
        return tuple()
    data = json.loads(ROLE_OVERRIDE_PATH.read_text(encoding="utf-8"))
    return tuple(dict(item) for item in data.get("overrides", []))
