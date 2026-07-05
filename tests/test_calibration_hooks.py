from __future__ import annotations

from coa_meta.calibration import (
    compare_spell_breakdowns,
    confidence_from_sample,
    placeholder_calibration_records,
)


def test_compare_spell_breakdowns_proposes_coefficient_corrections_and_warnings():
    report = compare_spell_breakdowns(
        simulated_breakdown=(
            {"spell_id": 1001, "average_damage": 100.0},
            {"spell_id": 1002, "average_damage": 50.0},
        ),
        observed_breakdown=(
            {"spell_id": 1001, "average_damage": 150.0},
            {"spell_id": 1003, "average_damage": 25.0},
        ),
        sample_size=12,
        variance=0.2,
    )

    assert report.schema_version == "coa-calibration-report-v1"
    assert report.confidence == "medium"
    assert report.records[0].correction_type == "coefficient_correction"
    assert report.records[0].suggested_multiplier == 1.5
    assert "observed_spell_missing_in_simulation:1003" in report.warnings


def test_confidence_from_sample_uses_sample_size_and_variance():
    assert confidence_from_sample(sample_size=2, variance=0.1) == "low"
    assert confidence_from_sample(sample_size=12, variance=0.3) == "medium"
    assert confidence_from_sample(sample_size=30, variance=0.05) == "high"


def test_placeholder_calibration_records_are_additive_and_pending():
    records = placeholder_calibration_records(spell_id=1001)
    types = {record.correction_type for record in records}

    assert {"coefficient_correction", "proc_rate_correction", "tick_interval_correction", "uptime_correction"} <= types
    assert all(record.status == "pending" for record in records)
