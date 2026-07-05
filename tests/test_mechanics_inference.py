from __future__ import annotations

from coa_meta.mechanics_inference import infer_mechanic_from_tooltip


def test_infers_direct_damage_cost_cooldown_charges_and_target_cap():
    record = infer_mechanic_from_tooltip(
        spell_id=3001,
        name="Venom Burst",
        tooltip_text="Costs 35 Energy. Deals 120 Nature damage to up to 5 enemies within 8 yards. 6 sec cooldown. 2 charges.",
        source_node_ids=(501,),
        tags=("spender",),
        resources=("Energy",),
    )

    assert record.kind == "ability"
    assert record.costs == {"Energy": 35.0}
    assert record.cooldown_ms == 6000
    assert record.charges == 2
    assert record.max_targets == 5
    assert record.effects[0].effect_type == "damage"
    assert record.effects[0].school == "nature"
    assert record.effects[0].amount == 120


def test_infers_dot_duration_and_tick_interval():
    record = infer_mechanic_from_tooltip(
        spell_id=3002,
        name="Lingering Toxin",
        tooltip_text="Deals 24 Nature damage every 2 sec for 12 sec.",
        tags=("dot",),
    )

    assert record.kind == "debuff"
    assert record.duration_ms == 12000
    assert record.tick_interval_ms == 2000
    assert record.effects[0].duration_ms == 12000
    assert record.effects[0].tick_interval_ms == 2000
    assert "dot" in record.effects[0].tags


def test_infers_healing_and_proc_rules():
    record = infer_mechanic_from_tooltip(
        spell_id=3003,
        name="Restorative Spores",
        tooltip_text=(
            "Heals an ally for 180 Nature health. Your healing spells have a 20% chance "
            "to trigger Restorative Spores. This effect cannot occur more than once every 10 sec."
        ),
        tags=("heal",),
    )

    assert record.effects[0].effect_type == "heal"
    assert record.effects[0].amount == 180
    assert record.proc is not None
    assert record.proc.chance == 0.2
    assert record.proc.internal_cooldown_ms == 10000


def test_override_can_raise_confidence_and_replace_fields():
    record = infer_mechanic_from_tooltip(
        spell_id=3004,
        name="Known Cooldown",
        tooltip_text="Increases your Nature damage for 15 sec.",
        overrides={
            "kind": "cooldown",
            "cooldown_ms": 90000,
            "confidence": "high",
            "provenance_note": "verified by manual override",
        },
    )

    assert record.kind == "cooldown"
    assert record.cooldown_ms == 90000
    assert record.confidence == "high"
    assert "verified by manual override" in record.provenance[-1].notes
