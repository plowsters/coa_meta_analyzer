from __future__ import annotations

import re
from typing import Any

from .mechanics import MechanicEffect, MechanicProvenance, MechanicRecord, ProcRule

SCHOOLS = ("arcane", "fire", "frost", "holy", "nature", "physical", "shadow", "fel")


def infer_mechanic_from_tooltip(
    *,
    spell_id: int,
    name: str,
    tooltip_text: str,
    source_node_ids: tuple[int, ...] = tuple(),
    tags: tuple[str, ...] = tuple(),
    damage_schools: tuple[str, ...] = tuple(),
    resources: tuple[str, ...] = tuple(),
    overrides: dict[str, Any] | None = None,
) -> MechanicRecord:
    text = tooltip_text or ""
    school = _infer_school(text, damage_schools)
    duration_ms = _infer_duration_ms(text)
    tick_interval_ms = _infer_tick_interval_ms(text)
    costs = _infer_costs(text, resources)
    cooldown_ms = _infer_cooldown_ms(text)
    charges = _infer_charges(text)
    max_targets = _infer_max_targets(text)
    proc = _infer_proc(text)
    effect = _infer_effect(text, school, duration_ms, tick_interval_ms, tags)
    kind = _infer_kind(text, tags, effect)
    provenance = [
        MechanicProvenance(
            source="tooltip_parser",
            source_id=f"spell:{spell_id}",
            parser="mechanics_inference",
            confidence="medium",
        )
    ]
    confidence = "medium" if effect is not None or costs or cooldown_ms is not None or proc is not None else "low"

    if overrides:
        kind = str(overrides.get("kind", kind))
        cooldown_ms = _override_int(overrides, "cooldown_ms", cooldown_ms)
        charges = _override_int(overrides, "charges", charges)
        max_targets = _override_int(overrides, "max_targets", max_targets)
        confidence = str(overrides.get("confidence", confidence))
        note = overrides.get("provenance_note")
        provenance.append(
            MechanicProvenance(
                source="override",
                source_id=f"spell:{spell_id}",
                parser="mechanics_inference",
                confidence=confidence,
                notes=(str(note),) if note else tuple(),
            )
        )

    return MechanicRecord(
        schema_version="coa-mechanics-v1",
        spell_id=spell_id,
        name=name,
        kind=kind,
        source_node_ids=source_node_ids,
        source_urls=tuple(),
        school=school,
        power_type=next(iter(resources), ""),
        cooldown_ms=cooldown_ms,
        charges=charges,
        duration_ms=duration_ms,
        tick_interval_ms=tick_interval_ms,
        costs=costs,
        max_targets=max_targets,
        effects=(effect,) if effect is not None else tuple(),
        proc=proc,
        provenance=tuple(provenance),
        confidence=confidence,
        raw={"tooltip_text": text, "tags": list(tags)},
    )


def _infer_effect(
    text: str,
    school: str,
    duration_ms: int | None,
    tick_interval_ms: int | None,
    tags: tuple[str, ...],
) -> MechanicEffect | None:
    heal_amount = _infer_heal_amount(text)
    if heal_amount is not None or "heal" in tags:
        return MechanicEffect(
            effect_type="heal",
            school=school,
            target="ally",
            amount=heal_amount,
            duration_ms=duration_ms,
            tick_interval_ms=tick_interval_ms,
            tags=_effect_tags(tags, duration_ms, tick_interval_ms),
        )
    damage_amount = _infer_damage_amount(text)
    if damage_amount is not None or "dot" in tags or re.search(r"\bdamage\b", text, re.I):
        return MechanicEffect(
            effect_type="damage",
            school=school,
            target="enemy",
            amount=damage_amount,
            duration_ms=duration_ms,
            tick_interval_ms=tick_interval_ms,
            tags=_effect_tags(tags, duration_ms, tick_interval_ms),
        )
    if re.search(r"\bincreases?|buff|aura\b", text, re.I):
        return MechanicEffect(
            effect_type="aura_apply",
            target="self",
            duration_ms=duration_ms,
            tags=_effect_tags(tags, duration_ms, tick_interval_ms),
        )
    return None


def _infer_kind(text: str, tags: tuple[str, ...], effect: MechanicEffect | None) -> str:
    if "dot" in tags or effect and effect.tick_interval_ms and effect.effect_type == "damage":
        return "debuff"
    if "cooldown" in tags:
        return "cooldown"
    if effect and effect.effect_type in {"damage", "heal"}:
        return "ability"
    if effect and effect.effect_type == "aura_apply":
        return "buff"
    return "ability"


def _infer_costs(text: str, resources: tuple[str, ...]) -> dict[str, float]:
    costs: dict[str, float] = {}
    for match in re.finditer(r"\bCosts?\s+(\d+(?:\.\d+)?)\s+([A-Za-z][A-Za-z ]+?)(?:\.|,|$)", text, re.I):
        resource = _normalize_resource(match.group(2), resources)
        costs[resource] = float(match.group(1))
    return costs


def _normalize_resource(raw: str, resources: tuple[str, ...]) -> str:
    compact = raw.strip()
    for resource in resources:
        if compact.casefold() == resource.casefold():
            return resource
    return compact[:1].upper() + compact[1:]


def _infer_damage_amount(text: str) -> float | None:
    match = re.search(r"\bDeals?\s+(\d+(?:\.\d+)?)\s+(?:[A-Za-z]+\s+)?damage\b", text, re.I)
    return float(match.group(1)) if match else None


def _infer_heal_amount(text: str) -> float | None:
    match = re.search(r"\bHeals?(?:\s+\w+)*\s+for\s+(\d+(?:\.\d+)?)\b", text, re.I)
    return float(match.group(1)) if match else None


def _infer_school(text: str, damage_schools: tuple[str, ...]) -> str:
    if damage_schools:
        return damage_schools[0]
    match = re.search(r"\b(" + "|".join(SCHOOLS) + r")\b", text, re.I)
    return match.group(1).lower() if match else ""


def _infer_duration_ms(text: str) -> int | None:
    match = re.search(r"\b(?:for|over|lasts?)\s+(\d+(?:\.\d+)?)\s*(sec|second|seconds|s)\b", text, re.I)
    return round(float(match.group(1)) * 1000) if match else None


def _infer_tick_interval_ms(text: str) -> int | None:
    match = re.search(r"\bevery\s+(\d+(?:\.\d+)?)\s*(sec|second|seconds|s)\b", text, re.I)
    return round(float(match.group(1)) * 1000) if match else None


def _infer_cooldown_ms(text: str) -> int | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(sec|second|seconds|s)\s+cooldown\b", text, re.I)
    return round(float(match.group(1)) * 1000) if match else None


def _infer_charges(text: str) -> int | None:
    match = re.search(r"\b(\d+)\s+charges?\b", text, re.I)
    return int(match.group(1)) if match else None


def _infer_max_targets(text: str) -> int | None:
    match = re.search(r"\bup to\s+(\d+)\s+(?:enemies|targets|allies)\b", text, re.I)
    return int(match.group(1)) if match else None


def _infer_proc(text: str) -> ProcRule | None:
    chance_match = re.search(r"\b(\d+(?:\.\d+)?)%\s+chance\b", text, re.I)
    icd_match = re.search(r"\bonce every\s+(\d+(?:\.\d+)?)\s*(sec|second|seconds|s)\b", text, re.I)
    if not chance_match and not icd_match:
        return None
    return ProcRule(
        chance=float(chance_match.group(1)) / 100 if chance_match else None,
        internal_cooldown_ms=round(float(icd_match.group(1)) * 1000) if icd_match else None,
        trigger_conditions=("tooltip_inferred",),
    )


def _effect_tags(tags: tuple[str, ...], duration_ms: int | None, tick_interval_ms: int | None) -> tuple[str, ...]:
    out = list(tags)
    if duration_ms is not None and tick_interval_ms is not None and "dot" not in out:
        out.append("dot")
    return tuple(out)


def _override_int(overrides: dict[str, Any], key: str, current: int | None) -> int | None:
    if key not in overrides:
        return current
    value = overrides[key]
    return int(value) if value is not None else None
