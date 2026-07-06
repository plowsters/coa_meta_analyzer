from __future__ import annotations

from pathlib import Path

from coa_meta.builds import BuildConfig, BuildRules
from coa_meta.domain import SelectedRank
from coa_meta.domain import TalentNode
from coa_meta.leveling_path import (
    LEVELING_PATH_SCHEMA_VERSION,
    LevelingPathStep,
    automatic_passive_steps,
    build_leveling_path,
    essence_awards_for_levels,
    essence_kind_for_level,
)
from coa_meta.repository import TalentRepository

FIXTURES = Path(__file__).parent / "fixtures"


def test_level_10_through_60_alternates_ae_then_te():
    awards = essence_awards_for_levels(10, 60)

    assert LEVELING_PATH_SCHEMA_VERSION == "coa-leveling-path-v1"
    assert awards[0].level == 10
    assert awards[0].essence_kind == "ability"
    assert awards[1].level == 11
    assert awards[1].essence_kind == "talent"
    assert essence_kind_for_level(60) == "ability"
    assert sum(1 for award in awards if award.essence_kind == "ability") == 26
    assert sum(1 for award in awards if award.essence_kind == "talent") == 25


def _node(
    entry_id: int,
    name: str,
    *,
    level: int,
    ae: int = 0,
    te: int = 0,
    passive: bool = True,
    tab_name: str = "Damage",
    required_ids: tuple[int, ...] = tuple(),
    required_tab_ae: int = 0,
    required_tab_te: int = 0,
    tags: tuple[str, ...] = ("damage",),
) -> TalentNode:
    return TalentNode(
        entry_id=entry_id,
        spell_id=entry_id + 1000,
        name=name,
        class_id=1,
        class_name="Testclass",
        tab_id=10 if tab_name == "Class" else 11,
        tab_name=tab_name,
        entry_type="Talent",
        essence_kind="talent" if te else "ability",
        ae_cost=ae,
        te_cost=te,
        required_tab_ae=required_tab_ae,
        required_tab_te=required_tab_te,
        required_level=level,
        max_rank=1,
        row=0,
        col=10,
        node_type="SpendCircle",
        is_passive=passive,
        is_starting_node=False,
        required_ids=required_ids,
        connected_node_ids=tuple(),
        tags=tags,
        damage_schools=tuple(),
        resources=tuple(),
        description_text="Level passive.",
        availability={"effective_required_level": level, "level_confidence": "high"},
    )


def test_automatic_passives_unlock_without_spending_essence():
    passive = _node(401, "Level 20 Passive", level=20)

    steps = automatic_passive_steps((passive,), selected_ids={401}, level=20, already_unlocked=set())

    assert steps == (
        LevelingPathStep(
            level=20,
            event_type="automatic_passive",
            node_id=401,
            spell_id=1401,
            name="Level 20 Passive",
            essence_kind="free",
            reason="Unlocks automatically at level 20.",
            ae_spent=0,
            te_spent=0,
            warnings=tuple(),
        ),
    )


def test_leveling_path_reconstructs_selected_fixture_build():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    selected_ids = (101, 201, 202)
    selected_ranks = tuple(SelectedRank(node_id=node_id, rank=1) for node_id in selected_ids)
    config = BuildConfig(class_name="Testclass", level=60, max_ae=26, max_te=25)
    rules = BuildRules(repo, config)
    target_state = rules.validate(list(selected_ranks)).state
    assert target_state is not None

    path = build_leveling_path(
        repository=repo,
        state=target_state,
        class_name="Testclass",
        spec_name="Damage",
        build_id="fixture",
        config=config,
        role="caster_dps",
    )

    chosen_ids = [step.node_id for step in path.steps if step.event_type in {"choose_ability", "choose_talent"}]
    assert 101 in chosen_ids
    assert 201 in chosen_ids
    assert 202 in chosen_ids
    assert path.warnings == tuple()


def test_leveling_path_records_deferred_awards_without_off_build_filler():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    config = BuildConfig(class_name="Testclass", level=60, max_ae=26, max_te=25)
    target_state = BuildRules(repo, config).validate([SelectedRank(201, 1), SelectedRank(202, 1)]).state
    assert target_state is not None

    path = build_leveling_path(
        repository=repo,
        state=target_state,
        class_name="Testclass",
        spec_name="Damage",
        build_id="talent-only",
        config=config,
        role="caster_dps",
    )

    deferred = [step for step in path.steps if step.event_type == "deferred"]
    chosen_ids = {step.node_id for step in path.steps if step.event_type in {"choose_ability", "choose_talent"}}
    assert deferred
    assert "leveling_path_deferred_essence" in deferred[0].warnings
    assert 101 not in chosen_ids
