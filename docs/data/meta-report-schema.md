# Meta Report Schema

Schema version: `coa-meta-report-v1`

The meta report is the canonical Phase 1 theorycraft output. JSON is the source of truth. Markdown and HTML are renderings of the same model.

## Top-Level Object

- `schema_version`: always `coa-meta-report-v1`
- `generated_at`: UTC ISO timestamp
- `input_artifacts`: paths used for normalized entries and class metadata
- `run_config`: class/spec/level/encounter/search settings
- `assumptions`: report-level assumptions
- `warnings`: report-level warnings
- `class_summaries`: summaries derived from spec results
- `spec_results`: one row per class/spec/encounter profile

## Spec Result

- `class_name`
- `spec_id`
- `spec_name`
- `role`
- `level`
- `encounter_profile_id`
- `search_profile_id`
- `scoring_profile_id`
- `apl_profile_id`
- `summary`
- `top_builds`
- `warnings`

## Build Result

- `rank`
- `projected_dps_index`
- `confidence_label`
- `selected_nodes`
- `score_breakdown`
- `generated_apl`
- `simulation_result`
- `rotation_summary`
- `stat_priority`
- `gear_recommendation`
- `explanation`
- `provenance`
- `warnings`

`projected_dps_index` is a theorycraft index. It is not raw DPS, simulated DPS, observed DPS, or empirical DPS.

## M1.10 Planned Guide Extensions

The M1.10 guide-site renderer should keep JSON canonical and add structured fields before relying on HTML-only state.

Planned additions:

- `role` should expand from Phase 1's broad roles to `melee_dps`, `caster_dps`, `tank`, `healer`, and `support`, with role provenance.
- Build results should include a playstyle fingerprint, diversity-selection reason, performance-band metadata, and rotation reliability.
- Spec results should include guide navigation metadata, player-facing labels, and tooltip definitions for analyzer-only metrics.
- Selected nodes should include enough tooltip/link/icon data for static guide rendering, or the renderer should join against normalized entries by `entry_id`.
- Talent tree payloads should be explicit about level gates, AE/TE gates, prerequisite failures, and selected rank state.
- Stat and gear sections should expose source warnings once per section rather than repeating them for every entry.
