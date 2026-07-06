from __future__ import annotations

from pathlib import Path

from coa_meta.repository import TalentRepository
from coa_meta.reporting import BuildScope
from coa_meta.roles import (
    GUIDE_ROLES,
    RoleResolution,
    engine_role_for_guide_role,
    load_spec_role_records,
    resolve_spec_role_record,
    resolve_spec_role,
    roles_for_filter,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_engine_role_bridge_preserves_existing_profile_roles():
    assert GUIDE_ROLES == ("melee_dps", "caster_dps", "ranged_dps", "tank", "healer", "support")
    assert engine_role_for_guide_role("melee_dps") == "dps"
    assert engine_role_for_guide_role("caster_dps") == "dps"
    assert engine_role_for_guide_role("ranged_dps") == "dps"
    assert engine_role_for_guide_role("tank") == "tank"
    assert engine_role_for_guide_role("healer") == "healer_support"
    assert engine_role_for_guide_role("support") == "healer_support"


def test_role_resolution_serializes_provenance():
    resolution = RoleResolution(
        role="caster_dps",
        engine_role="dps",
        source="inferred",
        confidence="medium",
        evidence=("spell_text:3",),
        scores={"caster_dps": 8.0, "melee_dps": 2.0},
    )

    payload = resolution.to_dict()

    assert payload["schema_version"] == "coa-role-resolution-v1"
    assert payload["role"] == "caster_dps"
    assert payload["engine_role"] == "dps"
    assert payload["evidence"] == ["spell_text:3"]


def test_curated_override_wins_for_fixture_support_spec():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    scope = BuildScope(
        class_name="Testclass",
        spec_id=12,
        spec_name="Support",
        level=60,
        encounter_profile_id="baseline_single_target",
        search_profile_id="default",
        scoring_profile_id="auto",
        apl_profile_id="auto",
        top=1,
    )

    resolution = resolve_spec_role(repo, scope)

    assert resolution.role == "healer"
    assert resolution.engine_role == "healer_support"
    assert resolution.source == "curated"


def test_curated_reaper_overrides_keep_harvest_and_soul_as_dps():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")

    harvest = resolve_spec_role(
        repo,
        BuildScope(
            class_name="Reaper",
            spec_id=30,
            spec_name="Harvest",
            level=60,
            encounter_profile_id="baseline_single_target",
            search_profile_id="default",
            scoring_profile_id="auto",
            apl_profile_id="auto",
            top=1,
        ),
    )
    soul = resolve_spec_role(
        repo,
        BuildScope(
            class_name="Reaper",
            spec_id=30,
            spec_name="Soul",
            level=60,
            encounter_profile_id="baseline_single_target",
            search_profile_id="default",
            scoring_profile_id="auto",
            apl_profile_id="auto",
            top=1,
        ),
    )

    assert harvest.role == "melee_dps"
    assert soul.role == "melee_dps"


def test_official_spec_role_map_loads_launch_video_seed():
    records = load_spec_role_records()

    assert len(records) == 70
    assert all(record.class_name for record in records)
    assert all(record.source_spec_name for record in records)
    assert all(record.display_spec_name for record in records)
    assert all(record.primary_role in GUIDE_ROLES for record in records)
    assert all(set(record.secondary_roles).issubset(GUIDE_ROLES) for record in records)
    assert all(record.engine_role in {"dps", "tank", "healer_support"} for record in records)
    assert all(record.source in {"authoritative_video", "authoritative_builder", "curated", "inferred"} for record in records)
    assert all(record.confidence in {"high", "medium", "low"} for record in records)
    assert all(record.evidence for record in records)


def test_official_spec_role_map_preserves_hybrid_roles():
    inspiration = resolve_spec_role_record("Guardian", "Inspiration")
    farstrider = resolve_spec_role_record("Ranger", "Farstrider")
    wind = resolve_spec_role_record("Stormbringer", "Wind")
    accursed = resolve_spec_role_record("Bloodmage", "Accursed")

    assert inspiration is not None
    assert inspiration.primary_role == "melee_dps"
    assert inspiration.secondary_roles == ("support",)
    assert roles_for_filter(inspiration) == ("melee_dps", "support")

    assert farstrider is not None
    assert farstrider.primary_role == "ranged_dps"
    assert farstrider.secondary_roles == ("support",)

    assert wind is not None
    assert wind.primary_role == "caster_dps"
    assert wind.secondary_roles == ("support",)

    assert accursed is not None
    assert accursed.primary_role == "melee_dps"
    assert accursed.secondary_roles == ("caster_dps",)


def test_official_spec_role_map_uses_source_and_display_spec_names():
    arcane = resolve_spec_role_record("Runemaster", "Arcane")
    runic = resolve_spec_role_record("Runemaster", "Runic")
    venom = resolve_spec_role_record("Venomancer", "Venom")
    life = resolve_spec_role_record("Primalist", "Life")
    primal = resolve_spec_role_record("Primalist", "Primal")
    houndmaster = resolve_spec_role_record("Witch Hunter", "Houndmaster")
    crusader = resolve_spec_role_record("Templar", "Crusader")

    assert arcane is not None and arcane.display_spec_name == "Glyphic"
    assert runic is not None and runic.display_spec_name == "Engravement"
    assert venom is not None and venom.display_spec_name == "Rot"
    assert life is not None and life.display_spec_name == "Grovekeeper"
    assert primal is not None and primal.display_spec_name == "Wildwalker"
    assert houndmaster is not None and houndmaster.display_spec_name == "Darkness"
    assert crusader is not None
    assert crusader.primary_role == "melee_dps"
    assert crusader.confidence == "high"
