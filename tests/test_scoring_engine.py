from pathlib import Path

from coa_meta.builds import BuildConfig, BuildRules
from coa_meta.domain import SelectedRank
from coa_meta.profiles import load_builtin_profile
from coa_meta.repository import TalentRepository
from coa_meta.scoring import ScoreComponent, TheoryScorer


FIXTURE = Path(__file__).parent / "fixtures" / "legal_build_fixture.jsonl"


def build_state():
    repo = TalentRepository.from_entries(FIXTURE)
    rules = BuildRules(repo, BuildConfig(class_name="Testclass", level=60, max_ae=2, max_te=3))
    result = rules.validate([SelectedRank(101, 1), SelectedRank(102, 2)])
    assert result.valid
    return repo, result.state


def test_theory_scorer_outputs_projected_index_and_components():
    repo, state = build_state()
    profile = load_builtin_profile("generic_dps", encounter="single_target")
    scorer = TheoryScorer(profile)

    scored = scorer.score_build(state, repo)

    assert scored.source == "theorycraft"
    assert scored.projected_dps_index > 100
    assert scored.raw_score > 0
    assert scored.confidence in {"low", "medium", "high"}
    assert scored.uncertainty["low"] < scored.uncertainty["mid"] < scored.uncertainty["high"]
    assert any(component.kind == "tag" for component in scored.components)
    assert any(component.kind == "school" for component in scored.components)


def test_synergies_and_anti_synergies_are_explained():
    from dataclasses import replace

    repo, state = build_state()
    profile = load_builtin_profile("generic_dps", encounter="single_target")
    custom_profile = replace(
        profile,
        synergies=({"names": ["Builder Strike", "Poison Talent"], "weight": 10.0, "reason": "test synergy"},),
        anti_synergies=({"names": ["Builder Strike", "Poison Talent"], "weight": -2.0, "reason": "test anti"},),
    )
    scorer = TheoryScorer(custom_profile)

    scored = scorer.score_build(state, repo)

    assert any(component.kind == "synergy" and component.reason == "test synergy" for component in scored.components)
    assert any(component.kind == "anti_synergy" and component.reason == "test anti" for component in scored.components)


def test_role_objective_labels_and_hybrid_alternate_scores():
    from coa_meta.objectives import objective_for_role

    components = (
        ScoreComponent(kind="tag", key="heal", value=4.0, reason="tag:heal"),
        ScoreComponent(kind="school", key="nature", value=2.5, reason="school:nature"),
    )

    assert objective_for_role("melee_dps", 118.5, components).primary_index_label == "Projected Damage Index"
    assert objective_for_role("ranged_dps", 118.5, components).primary_index_label == "Projected Damage Index"
    assert objective_for_role("caster_dps", 118.5, components).primary_index_label == "Projected Damage Index"
    assert objective_for_role("healer", 118.5, components).primary_index_label == "Projected Healing Index"
    assert objective_for_role("tank", 118.5, components).primary_index_label == "Projected Survival/Threat Index"
    assert objective_for_role("support", 118.5, components).primary_index_label == "Projected Support Index"

    hybrid = objective_for_role("melee_dps", 118.5, components, secondary_roles=("support",))

    assert hybrid.primary_index == 118.5
    assert hybrid.objective_breakdown["tag:heal"] == 4.0
    assert hybrid.alternate_objective_scores["support"]["primary_index_label"] == "Projected Support Index"
