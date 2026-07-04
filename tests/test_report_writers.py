from __future__ import annotations

import json
from pathlib import Path

from coa_meta.report_assets import AssetResolver
from coa_meta.reporting import MetaReportRunner, MetaRunConfig, render_html_report, render_markdown_report, write_report_outputs

FIXTURES = Path(__file__).parent / "fixtures"


def _report():
    return MetaReportRunner(
        MetaRunConfig(
            entries_path=FIXTURES / "meta_report_fixture.jsonl",
            classes_path=FIXTURES / "meta_classes.json",
            class_names=("Testclass",),
            top=1,
            beam_width=2,
            branch_width=2,
            require_budget_fraction=0.0,
        )
    ).run()


def test_writes_json_markdown_and_html_outputs(tmp_path):
    report = _report()

    written = write_report_outputs(report, tmp_path, formats=("json", "md", "html"))

    assert {path.name for path in written} == {"meta-report.json", "meta-report.md", "meta-report.html"}
    data = json.loads((tmp_path / "meta-report.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == "coa-meta-report-v1"
    assert "Projected DPS Index" in (tmp_path / "meta-report.md").read_text(encoding="utf-8")
    assert "<html" in (tmp_path / "meta-report.html").read_text(encoding="utf-8")


def test_markdown_and_html_include_warnings_and_theorycraft_label():
    report = _report()

    markdown = render_markdown_report(report)
    html = render_html_report(report)

    assert "theorycraft" in markdown.lower()
    assert "metadata_tab_has_no_nodes:Testclass:Empty" in markdown
    assert "Observed DPS" not in markdown
    assert "Projected DPS Index" in html


def test_asset_resolver_returns_none_for_missing_assets(tmp_path):
    resolver = AssetResolver(tmp_path)

    assert resolver.class_tree_image("Testclass") is None
    assert resolver.node_icon("Interface\\Icons\\Missing") is None
