from __future__ import annotations

from pathlib import Path

from coa_meta.builds import BuildConfig, BuildRules
from coa_meta.domain import SelectedRank
from coa_meta.repository import TalentRepository

FIXTURE = Path(__file__).parent / "fixtures" / "legal_build_fixture.jsonl"


def test_build_rules_restrict_paid_nodes_to_allowed_scope():
    repo = TalentRepository.from_entries(FIXTURE)
    rules = BuildRules(
        repo,
        BuildConfig(
            class_name="Testclass",
            level=60,
            max_ae=2,
            max_te=3,
            allowed_node_ids=(100, 101, 102),
        ),
    )

    assert sorted(rules.nodes) == [100, 101, 102]
    result = rules.validate([SelectedRank(103, 1)])

    assert result.valid is False
    assert "node_not_in_scope" in result.issue_codes()


def test_build_rules_allow_valid_selection_inside_scope():
    repo = TalentRepository.from_entries(FIXTURE)
    rules = BuildRules(
        repo,
        BuildConfig(
            class_name="Testclass",
            level=60,
            max_ae=2,
            max_te=3,
            allowed_node_ids=(100, 101, 102),
        ),
    )

    result = rules.validate([SelectedRank(101, 1), SelectedRank(102, 1)])

    assert result.valid is True
    assert result.state is not None
    assert result.state.ae_spent == 1
    assert result.state.te_spent == 1
