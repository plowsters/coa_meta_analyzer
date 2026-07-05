from __future__ import annotations

from coa_meta.guide_models import (
    GuideNodeGate,
    GuideTree,
    GuideTreeEdge,
    GuideTreeSnapshot,
)


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
