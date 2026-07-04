from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APL_PROFILE_SCHEMA_VERSION = "coa-apl-profile-v1"
PROFILE_DIR = Path(__file__).parent / "data" / "apl_profiles"

SUPPORTED_MATCH_OPERATORS = {
    "tags_any",
    "tags_all",
    "schools_any",
    "resources_any",
    "name_contains_any",
    "description_matches_any",
    "entry_type_in",
    "essence_kind_in",
    "active_only",
    "passive_only",
    "selected_rank_at_least",
}
SUPPORTED_CATEGORIES = {
    "precombat",
    "maintenance",
    "cooldown",
    "builder",
    "spender",
    "execute",
    "aoe",
    "filler",
    "utility",
}
SUPPORTED_CONFIDENCE = {"high", "medium", "low"}
FUTURE_INPUTS = {"combat_log_metrics", "saved_variables_snapshot", "sim_state"}


class APLProfileLoadError(ValueError):
    pass


@dataclass(frozen=True)
class APLResource:
    name: str
    aliases: tuple[str, ...]
    default_pool: int | None = None


@dataclass(frozen=True)
class APLRuleProfile:
    id: str
    category: str
    match: dict[str, Any]
    condition_template: str
    priority: float
    confidence: str
    note: str


@dataclass(frozen=True)
class APLBranchProfile:
    encounter: str
    include_categories: tuple[str, ...]


@dataclass(frozen=True)
class APLProfile:
    schema_version: str
    profile_id: str
    class_name: str
    spec_key: str
    role: str
    supported_encounters: tuple[str, ...]
    resources: tuple[APLResource, ...]
    thresholds: dict[str, Any]
    condition_templates: dict[str, str]
    rules: tuple[APLRuleProfile, ...]
    branches: tuple[APLBranchProfile, ...]
    assumptions: tuple[str, ...]
    future_inputs: tuple[str, ...]
    confidence: dict[str, Any]


def load_builtin_apl_profile(profile_id: str) -> APLProfile:
    path = PROFILE_DIR / f"{profile_id}.json"
    if not path.exists():
        raise APLProfileLoadError(f"Unknown APL profile {profile_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_apl_profile_data(data, source=str(path))


def load_apl_profile_by_role(class_name: str, spec_key: str, role: str) -> tuple[APLProfile, list[str]]:
    specific_id = f"{class_name.lower().replace(' ', '_')}_{spec_key}"
    warnings: list[str] = []
    try:
        return load_builtin_apl_profile(specific_id), warnings
    except APLProfileLoadError:
        warnings.append("specific_apl_profile_missing")

    generic_id = {
        "dps": "generic_dps",
        "tank": "generic_tank",
        "healer_support": "generic_healer_support",
    }.get(role)
    if not generic_id:
        raise APLProfileLoadError(f"Unsupported role {role}")
    return load_builtin_apl_profile(generic_id), warnings


def validate_apl_profile_data(data: dict[str, Any], source: str = "<memory>") -> APLProfile:
    profile = copy.deepcopy(data)
    required = {
        "schema_version",
        "profile_id",
        "class_name",
        "spec_key",
        "role",
        "supported_encounters",
        "resources",
        "thresholds",
        "condition_templates",
        "rules",
        "branches",
        "assumptions",
    }
    missing = sorted(required - set(profile))
    if missing:
        raise APLProfileLoadError(f"{source} missing required fields: {', '.join(missing)}")
    if profile.get("schema_version") != APL_PROFILE_SCHEMA_VERSION:
        raise APLProfileLoadError(f"{source} invalid schema_version {profile.get('schema_version')!r}")

    required_inputs = set(profile.get("required_inputs", []))
    future_required = sorted(required_inputs & FUTURE_INPUTS)
    if future_required:
        raise APLProfileLoadError(f"{source} marks future input as required: {', '.join(future_required)}")

    condition_templates = {
        str(key): str(value) for key, value in dict(profile.get("condition_templates", {})).items()
    }
    rules = tuple(_validate_rule(item, condition_templates, source) for item in profile.get("rules", []))
    branches = tuple(_validate_branch(item, source) for item in profile.get("branches", []))
    supported = tuple(str(item) for item in profile.get("supported_encounters", []))
    branch_encounters = {branch.encounter for branch in branches}
    for encounter in branch_encounters:
        if encounter not in supported:
            raise APLProfileLoadError(f"{source} unsupported encounter in branch {encounter!r}")

    resources = tuple(
        APLResource(
            name=str(item.get("name", "")),
            aliases=tuple(str(alias) for alias in item.get("aliases", [])),
            default_pool=item.get("default_pool"),
        )
        for item in profile.get("resources", [])
    )
    return APLProfile(
        schema_version=APL_PROFILE_SCHEMA_VERSION,
        profile_id=str(profile["profile_id"]),
        class_name=str(profile["class_name"]),
        spec_key=str(profile["spec_key"]),
        role=str(profile["role"]),
        supported_encounters=supported,
        resources=resources,
        thresholds=dict(profile.get("thresholds", {})),
        condition_templates=condition_templates,
        rules=rules,
        branches=branches,
        assumptions=tuple(str(item) for item in profile.get("assumptions", [])),
        future_inputs=tuple(str(item) for item in profile.get("future_inputs", [])),
        confidence=dict(profile.get("confidence", {})),
    )


def _validate_rule(item: dict[str, Any], templates: dict[str, str], source: str) -> APLRuleProfile:
    rule_id = str(item.get("id", ""))
    category = str(item.get("category", ""))
    if category not in SUPPORTED_CATEGORIES:
        raise APLProfileLoadError(f"{source} rule {rule_id} has invalid category {category!r}")
    match = dict(item.get("match", {}))
    for operator in match:
        if operator not in SUPPORTED_MATCH_OPERATORS:
            raise APLProfileLoadError(f"{source} rule {rule_id} has unsupported match operator {operator!r}")
    template = str(item.get("condition_template", ""))
    if template and template not in templates:
        raise APLProfileLoadError(f"{source} rule {rule_id} references unknown condition template {template!r}")
    confidence = str(item.get("confidence", "medium"))
    if confidence not in SUPPORTED_CONFIDENCE:
        raise APLProfileLoadError(f"{source} rule {rule_id} has invalid confidence {confidence!r}")
    try:
        priority = float(item.get("priority", 100))
    except (TypeError, ValueError) as exc:
        raise APLProfileLoadError(f"{source} rule {rule_id} priority is not numeric") from exc
    return APLRuleProfile(
        id=rule_id,
        category=category,
        match=match,
        condition_template=template,
        priority=priority,
        confidence=confidence,
        note=str(item.get("note", "")),
    )


def _validate_branch(item: dict[str, Any], source: str) -> APLBranchProfile:
    encounter = str(item.get("encounter", ""))
    categories = tuple(str(category) for category in item.get("include_categories", []))
    for category in categories:
        if category not in SUPPORTED_CATEGORIES:
            raise APLProfileLoadError(f"{source} branch {encounter} has unknown branch category {category!r}")
    return APLBranchProfile(encounter=encounter, include_categories=categories)
