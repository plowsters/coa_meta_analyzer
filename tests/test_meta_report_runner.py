from __future__ import annotations

from pathlib import Path

from coa_meta.reporting import MetaReportRunner, MetaRunConfig

FIXTURES = Path(__file__).parent / "fixtures"


def test_meta_report_runner_generates_spec_results_from_fixture():
    config = MetaRunConfig(
        entries_path=FIXTURES / "meta_report_fixture.jsonl",
        classes_path=FIXTURES / "meta_classes.json",
        class_names=("Testclass",),
        top=2,
        beam_width=4,
        branch_width=4,
        require_budget_fraction=0.0,
    )

    report = MetaReportRunner(config).run()
    data = report.to_dict()

    assert data["schema_version"] == "coa-meta-report-v1"
    assert data["run_config"]["top"] == 2
    assert [row["spec_name"] for row in data["spec_results"]] == ["Damage", "Support"]
    assert data["spec_results"][0]["top_builds"]
    assert data["spec_results"][0]["top_builds"][0]["projected_dps_index"] > 0
    assert data["spec_results"][0]["top_builds"][0]["generated_apl"]["schema_version"] == "coa-apl-v1"


def test_meta_report_runner_preserves_metadata_warnings():
    config = MetaRunConfig(
        entries_path=FIXTURES / "meta_report_fixture.jsonl",
        classes_path=FIXTURES / "meta_classes.json",
        class_names=("Testclass",),
        top=1,
        beam_width=2,
        branch_width=2,
        require_budget_fraction=0.0,
    )

    report = MetaReportRunner(config).run()

    assert any("metadata_tab_has_no_nodes:Testclass:Empty" in warning for warning in report.warnings)
