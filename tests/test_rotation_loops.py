from __future__ import annotations

from coa_meta.apl import APLAction, APLDocument
from coa_meta.rotation_loops import build_rotation_loop


def test_build_rotation_loop_translates_priority_actions_to_player_steps():
    apl = APLDocument(
        schema_version="coa-apl-v1",
        source="theorycraft",
        profile_id="test",
        class_name="Testclass",
        spec_key="Damage",
        role="melee_dps",
        encounter="single_target",
        actions=(
            APLAction("keep_dot", "Venom Bite", 201, 2001, "maintenance", "if missing", 1, "high", tuple(), tuple()),
            APLAction("burst", "Shadow Frenzy", 202, 2002, "cooldown", "on cooldown", 2, "high", tuple(), tuple()),
            APLAction("builder", "Quick Strike", 203, 2003, "builder", "if resource low", 3, "medium", tuple(), tuple()),
            APLAction("spender", "Deadly Finish", 204, 2004, "spender", "if resource high", 4, "medium", tuple(), tuple()),
        ),
        assumptions=tuple(),
        warnings=tuple(),
        provenance={},
    )

    loop = build_rotation_loop(apl=apl, selected_nodes=tuple(), role="melee_dps", encounter="single_target")

    assert loop.reliability_label in {"high", "medium"}
    assert any("Venom Bite" in step for step in loop.core_loop)
    assert loop.resource_rule


def test_healer_loop_uses_healing_language():
    apl = APLDocument(
        schema_version="coa-apl-v1",
        source="theorycraft",
        profile_id="test",
        class_name="Testclass",
        spec_key="Mending",
        role="healer",
        encounter="single_target",
        actions=(
            APLAction("heal", "Renewing Light", 301, 3001, "heal", "when allies injured", 1, "high", tuple(), tuple()),
        ),
        assumptions=tuple(),
        warnings=tuple(),
        provenance={},
    )

    loop = build_rotation_loop(apl=apl, selected_nodes=tuple(), role="healer", encounter="single_target")

    assert "healing" in loop.objective.lower() or "keep allies alive" in loop.objective.lower()
    assert loop.defensive_or_support
