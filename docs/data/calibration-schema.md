# Calibration Schema

Calibration reports use schema version `coa-calibration-report-v1`.

## Purpose

Calibration records compare simulated outputs with log or addon-derived observations. They are additive corrections. Theory and simulation must still run when no calibration records exist.

## Report Fields

- `schema_version`
- `confidence`
- `sample_size`
- `variance`
- `records`
- `warnings`

## Record Fields

- `spell_id`
- `correction_type`
- `suggested_multiplier`
- `observed_value`
- `simulated_value`
- `confidence`
- `status`
- `notes`

Supported initial correction types:

- `coefficient_correction`
- `proc_rate_correction`
- `tick_interval_correction`
- `uptime_correction`

## Confidence

M1.9 confidence is based on sample size and variance only. Later phases can replace this with richer statistics while preserving the report schema.
