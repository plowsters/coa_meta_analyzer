from __future__ import annotations

import pytest

from coa_meta.rotation_guides import (
    ActionUsageSummary,
    RotationGuide,
    RotationGuideRule,
    RotationSimulationSummary,
)


def _rule(rule_id: str, section: str, name: str) -> RotationGuideRule:
    return RotationGuideRule(
        rule_id=rule_id,
        section=section,
        text=f"Use {name}.",
        ability_name=name,
        spell_id=1000,
        entry_id=2000,
        icon="ability_test",
        db_url="https://db.ascension.gg/?spell=1000",
        condition="when ready",
        priority=1,
    )


def test_rotation_guide_serializes_schema_sections_and_rules():
    summary = RotationSimulationSummary(
        source="simulated",
        role="melee_dps",
        encounter="single_target",
        duration_ms=90000,
        objective_score=123.4,
        reliability="medium",
        action_count=42,
        unsupported_condition_count=1,
        unsupported_effect_count=2,
        warnings=("unsupported_condition:buff.remains",),
    )
    guide = RotationGuide(
        source="simulated",
        role="melee_dps",
        encounter="single_target",
        build_id="test-build",
        simulation_summary=summary,
        opener=(_rule("open", "opener", "Fel Opener"),),
        core_loop=(_rule("core", "core_loop", "Fel Strike"),),
        priority_rules=(_rule("priority", "priority", "Venom Bite"),),
        cooldown_rules=(_rule("cooldown", "cooldowns", "Fel Frenzy"),),
        proc_rules=(_rule("proc", "procs", "Toxic Surge"),),
        defensive_rules=(_rule("defensive", "defensives", "Hardened Skin"),),
        healing_rules=(_rule("heal", "healing", "Renewing Spores"),),
        support_rules=(_rule("support", "support", "Fel Chant"),),
        ability_sequence=("Fel Opener", "Fel Strike", "Venom Bite"),
        action_usage=(ActionUsageSummary(action_key="fel_strike", ability_name="Fel Strike", count=12, first_used_ms=1500),),
        reliability="medium",
        warnings=("mechanics_inferred",),
    )

    payload = guide.to_dict()

    assert payload["schema_version"] == "coa-rotation-guide-v1"
    assert payload["source"] == "simulated"
    assert payload["build_id"] == "test-build"
    assert payload["simulation_summary"]["objective_score"] == 123.4
    assert payload["simulation_summary"]["unsupported_condition_count"] == 1
    assert payload["simulation_summary"]["unsupported_effect_count"] == 2
    assert payload["opener"][0]["ability_name"] == "Fel Opener"
    assert payload["core_loop"][0]["spell_id"] == 1000
    assert payload["cooldown_rules"][0]["db_url"] == "https://db.ascension.gg/?spell=1000"
    assert payload["proc_rules"][0]["entry_id"] == 2000
    assert payload["defensive_rules"][0]["text"] == "Use Hardened Skin."
    assert payload["healing_rules"][0]["ability_name"] == "Renewing Spores"
    assert payload["support_rules"][0]["ability_name"] == "Fel Chant"
    assert payload["ability_sequence"] == ["Fel Opener", "Fel Strike", "Venom Bite"]
    assert payload["action_usage"][0]["count"] == 12
    assert payload["warnings"] == ["mechanics_inferred"]


def test_empty_rotation_guide_sections_serialize_as_lists():
    guide = RotationGuide(
        source="theorycraft",
        role="healer",
        encounter="aoe",
        build_id="empty",
        simulation_summary=RotationSimulationSummary(
            source="theorycraft",
            role="healer",
            encounter="aoe",
            duration_ms=0,
            objective_score=0.0,
            reliability="low",
            action_count=0,
            unsupported_condition_count=0,
            unsupported_effect_count=0,
        ),
        reliability="low",
    )

    payload = guide.to_dict()

    for key in (
        "opener",
        "core_loop",
        "priority_rules",
        "cooldown_rules",
        "proc_rules",
        "defensive_rules",
        "healing_rules",
        "support_rules",
        "aoe_adjustments",
        "movement_notes",
        "ability_sequence",
        "action_usage",
        "warnings",
    ):
        assert payload[key] == []


def test_rotation_reliability_values_are_validated():
    with pytest.raises(ValueError, match="Invalid rotation reliability"):
        RotationSimulationSummary(
            source="simulated",
            role="tank",
            encounter="single_target",
            duration_ms=90000,
            objective_score=1.0,
            reliability="certain",
            action_count=1,
            unsupported_condition_count=0,
            unsupported_effect_count=0,
        )

    with pytest.raises(ValueError, match="Invalid rotation reliability"):
        RotationGuide(
            source="simulated",
            role="tank",
            encounter="single_target",
            build_id="bad",
            simulation_summary=RotationSimulationSummary(
                source="simulated",
                role="tank",
                encounter="single_target",
                duration_ms=90000,
                objective_score=1.0,
                reliability="medium",
                action_count=1,
                unsupported_condition_count=0,
                unsupported_effect_count=0,
            ),
            reliability="certain",
        )
