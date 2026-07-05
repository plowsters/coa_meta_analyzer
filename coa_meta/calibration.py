from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CalibrationRecord:
    spell_id: int
    correction_type: str
    suggested_multiplier: float | None = None
    observed_value: float | None = None
    simulated_value: float | None = None
    confidence: str = "low"
    status: str = "proposed"
    notes: tuple[str, ...] = tuple()

    def to_dict(self) -> dict[str, Any]:
        return {
            "spell_id": self.spell_id,
            "correction_type": self.correction_type,
            "suggested_multiplier": self.suggested_multiplier,
            "observed_value": self.observed_value,
            "simulated_value": self.simulated_value,
            "confidence": self.confidence,
            "status": self.status,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class CalibrationReport:
    schema_version: str
    confidence: str
    sample_size: int
    variance: float
    records: tuple[CalibrationRecord, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "variance": self.variance,
            "records": [record.to_dict() for record in self.records],
            "warnings": list(self.warnings),
        }


def compare_spell_breakdowns(
    *,
    simulated_breakdown: tuple[dict[str, Any], ...],
    observed_breakdown: tuple[dict[str, Any], ...],
    sample_size: int,
    variance: float,
) -> CalibrationReport:
    confidence = confidence_from_sample(sample_size=sample_size, variance=variance)
    simulated = {_spell_id(row): float(row.get("average_damage", 0.0) or 0.0) for row in simulated_breakdown}
    observed = {_spell_id(row): float(row.get("average_damage", 0.0) or 0.0) for row in observed_breakdown}
    records: list[CalibrationRecord] = []
    warnings: list[str] = []

    for spell_id, observed_value in sorted(observed.items()):
        simulated_value = simulated.get(spell_id)
        if simulated_value is None:
            warnings.append(f"observed_spell_missing_in_simulation:{spell_id}")
            continue
        if simulated_value <= 0:
            warnings.append(f"simulated_spell_has_zero_damage:{spell_id}")
            continue
        records.append(
            CalibrationRecord(
                spell_id=spell_id,
                correction_type="coefficient_correction",
                suggested_multiplier=round(observed_value / simulated_value, 3),
                observed_value=observed_value,
                simulated_value=simulated_value,
                confidence=confidence,
                status="proposed",
                notes=("Derived from average spell damage comparison.",),
            )
        )

    for spell_id in sorted(set(simulated) - set(observed)):
        warnings.append(f"simulated_spell_missing_in_observed_data:{spell_id}")

    return CalibrationReport(
        schema_version="coa-calibration-report-v1",
        confidence=confidence,
        sample_size=sample_size,
        variance=variance,
        records=tuple(records),
        warnings=tuple(warnings),
    )


def confidence_from_sample(*, sample_size: int, variance: float) -> str:
    if sample_size < 10 or variance > 0.5:
        return "low"
    if sample_size >= 25 and variance <= 0.1:
        return "high"
    return "medium"


def placeholder_calibration_records(spell_id: int) -> tuple[CalibrationRecord, ...]:
    correction_types = (
        "coefficient_correction",
        "proc_rate_correction",
        "tick_interval_correction",
        "uptime_correction",
    )
    return tuple(
        CalibrationRecord(
            spell_id=spell_id,
            correction_type=correction_type,
            confidence="low",
            status="pending",
            notes=("Awaiting combat log or addon calibration data.",),
        )
        for correction_type in correction_types
    )


def _spell_id(row: dict[str, Any]) -> int:
    return int(row["spell_id"])
