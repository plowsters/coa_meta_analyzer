# Rotation Guide Schema

Schema version: `coa-rotation-guide-v1`

Rotation guides are the M1.11E player-facing rotation payload. They are generated from structured APL data and, once later checkpoints are complete, from local rotation simulation results.

`rotation_loop` remains available as a compatibility fallback. New report and guide renderers should prefer `rotation_guide` when present.

## Source Labels

- `theorycraft`: deterministic heuristic or APL-derived guidance without simulation.
- `simulated`: local event/priority simulation under stated assumptions.
- `empirical`: observed combat-log or addon-derived data.
- `blended`: combined simulated and empirical data.

## Reliability

Reliability is one of:

- `high`: most core mechanics are parsed and candidate order is stable.
- `medium`: the guide is plausible but depends on some inferred mechanics.
- `low`: major mechanics, conditions, or role objective inputs are missing.

## Top-Level Fields

- `schema_version`: always `coa-rotation-guide-v1`
- `source`
- `role`
- `encounter`
- `build_id`
- `simulation_summary`
- `opener`
- `core_loop`
- `priority_rules`
- `cooldown_rules`
- `proc_rules`
- `defensive_rules`
- `healing_rules`
- `support_rules`
- `aoe_adjustments`
- `movement_notes`
- `ability_sequence`
- `action_usage`
- `reliability`
- `warnings`

All section fields serialize as arrays. Empty sections must serialize as `[]`, not `null`.

## Simulation Summary

`simulation_summary` records the source and quality of the guide:

- `source`
- `role`
- `encounter`
- `duration_ms`
- `objective_score`
- `reliability`
- `action_count`
- `unsupported_condition_count`
- `unsupported_effect_count`
- `warnings`

Scores are relative theorycraft/simulation indexes unless later labeled `empirical` or `blended`.

## Rule Object

Each rule object contains:

- `rule_id`
- `section`
- `text`
- `ability_name`
- `spell_id`
- `entry_id`
- `icon`
- `db_url`
- `condition`
- `priority`

Rules should use player-facing wording such as "Keep X active" or "Use Y before Z when both are ready." Engine internals belong in the provenance or metric tooltip sections, not the main guide.

## Action Usage

`action_usage` summarizes actions used by the selected simulated/derived rotation:

- `action_key`
- `ability_name`
- `count`
- `first_used_ms`
- `last_used_ms`
- `uptime_pct`

## Compatibility

Build results may contain both:

- `rotation_loop`: existing M1.10/M1.11 category-derived guide fallback.
- `rotation_guide`: M1.11E guide-ready priority payload.

Consumers should render `rotation_guide` first, then fall back to `rotation_loop`.

