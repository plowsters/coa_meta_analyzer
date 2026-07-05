from __future__ import annotations

from pathlib import Path

from coa_meta.builds import BuildConfig
from coa_meta.guide_models import (
    GuideNodeGate,
    GuideTree,
    GuideTreeEdge,
    GuideTreeSnapshot,
)
from coa_meta.guide_tree import build_guide_tree, default_tree_levels
from coa_meta.repository import TalentRepository


FIXTURES = Path(__file__).parent / "fixtures"


def test_guide_tree_serializes_snapshots_and_edges():
    tree = GuideTree(
        tree_id="testclass-damage-1",
        class_name="Testclass",
        spec_name="Damage",
        build_rank=1,
        build_label="Direct damage loop",
        level=60,
        max_ae=26,
        max_te=25,
        ae_spent=3,
        te_spent=2,
        rows=10,
        cols=11,
        nodes=tuple(),
        edges=(GuideTreeEdge(source_id=201, target_id=202, kind="connection", state="selected"),),
        snapshots=(
            GuideTreeSnapshot(
                level=60,
                max_ae=26,
                max_te=25,
                ae_spent=3,
                te_spent=2,
                selected_node_ids=(201, 202),
                free_node_ids=tuple(),
                available_node_ids=(203,),
                gated_nodes=(
                    GuideNodeGate(
                        node_id=204,
                        state="gated_required_node",
                        reasons=("Requires Damage Talent",),
                        issue_codes=("required_node_missing",),
                    ),
                ),
            ),
        ),
        warnings=tuple(),
    )

    payload = tree.to_dict()

    assert payload["schema_version"] == "coa-guide-tree-v1"
    assert payload["edges"][0]["source_id"] == 201
    assert payload["snapshots"][0]["gated_nodes"][0]["state"] == "gated_required_node"


def test_default_tree_levels_include_report_level_and_key_breakpoints():
    assert default_tree_levels(13) == (10, 13, 20, 30, 40, 50, 60)


def test_build_guide_tree_uses_coordinates_edges_and_snapshots():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    nodes = tuple(
        node for node in repo.nodes_for_class("Testclass")
        if node.tab_name in {"Class", "Damage"}
    )

    tree = build_guide_tree(
        repository=repo,
        class_name="Testclass",
        spec_name="Damage",
        build_rank=1,
        build_label="Direct damage loop",
        selected_node_ids=(201, 202),
        config=BuildConfig(class_name="Testclass", level=60, max_ae=26, max_te=25),
        spec_nodes=nodes,
    )

    assert tree.rows >= 3
    assert tree.cols >= 2
    assert any(edge.source_id == 201 and edge.target_id == 202 for edge in tree.edges)
    assert any(snapshot.level == 60 for snapshot in tree.snapshots)
    assert {node.entry_id for node in tree.nodes if node.selected} >= {201, 202}
