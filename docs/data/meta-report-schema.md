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
- `role`: player-facing primary guide role; one of `melee_dps`, `caster_dps`, `ranged_dps`, `tank`, `healer`, or `support`
- `primary_role`: same value as `role`, retained under a clearer guide-facing name
- `secondary_roles`: optional extra guide roles for hybrid specs
- `roles`: filter roles for the spec, including primary and secondary roles
- `engine_role`: broad role used for existing scoring/APL/stat/gear compatibility; one of `dps`, `tank`, or `healer_support`
- `role_provenance`: `coa-role-resolution-v1` payload describing role source, confidence, evidence, engine-role bridge, and role scores
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
- `primary_index`
- `primary_index_label`
- `objective_id`
- `objective_breakdown`
- `alternate_objective_scores`
- `confidence_label`
- `selected_nodes`
- `score_breakdown`
- `generated_apl`
- `simulation_result`
- `rotation_summary`
- `stat_priority`: legacy list-style stat priority retained for compatibility
- `stat_priority_report`: `coa-stat-priority-v2` grouped guide stat payload
- `gear_recommendation`: legacy broad weapon/armor recommendation retained for compatibility
- `gear_recommendation_report`: `coa-gear-recommendation-v2` best-vs-available guide gear payload
- `explanation`
- `provenance`
- `playstyle_fingerprint`
- `selection_reason`
- `rotation_loop`
- `warnings`

`projected_dps_index` is a theorycraft index. It is not raw DPS, simulated DPS, observed DPS, or empirical DPS.

`primary_index` is the guide-facing score for the spec's primary role. During M1.11B it reuses the same underlying theorycraft score as `projected_dps_index`, but it is labeled by role:

- Damage specs: `Projected Damage Index`
- Healer specs: `Projected Healing Index`
- Tank specs: `Projected Survival/Threat Index`
- Support specs: `Projected Support Index`

`objective_id` is one of `damage`, `healing`, `survival_threat`, or `support`. `objective_breakdown` groups score components by source key. `alternate_objective_scores` contains secondary-role payloads for hybrid specs.

`rotation_summary` remains for backwards compatibility. New guide rendering should prefer `rotation_loop` when present.

`playstyle_fingerprint` has schema version `coa-build-playstyle-v1` and summarizes selected node tags, active abilities, resources, schools, APL categories, and role cues for build comparison.

`selection_reason` has schema version `coa-build-selection-v1` and explains why the build was selected for the guide, including performance band, reliability label, diversity label, and comparison to the first selected build.

`rotation_loop` has schema version `coa-rotation-loop-v1` and provides player-facing objective, opener, core loop, cooldown, role-specific, resource, maintenance, and reliability notes derived from the generated APL.

## Role Resolution

`role_provenance` has schema version `coa-role-resolution-v1`:

- `role`: player-facing role used by guide filters and section wording
- `primary_role`: primary guide role
- `secondary_roles`: additional guide roles for hybrid specs
- `roles`: all guide-filter roles for this spec
- `engine_role`: broad role routed into existing scoring and APL profile loaders
- `source`: `authoritative`, `curated`, `inferred`, or `configured`
- `confidence`: `high`, `medium`, or `low`
- `evidence`: short source strings or score summaries
- `scores`: role scores when inference was used

The compatibility bridge is:

- `melee_dps`, `caster_dps`, and `ranged_dps` -> `dps`
- `tank` -> `tank`
- `healer` and `support` -> `healer_support`

## Stat Priority Report

`stat_priority_report` has schema version `coa-stat-priority-v2`:

- `role`: player-facing guide role
- `engine_role`: broad compatibility role
- `disclaimer`: one section-level player warning, currently used to state that stat priorities are early theorycraft until simulations or combat logs are available
- `source`: currently `heuristic`
- `confidence`: heuristic confidence label
- `groups`: grouped stat entries, usually `primary`, `secondary`, and `situational`
- `warnings`: section-level warnings such as `stat_priority_not_simulated`

Each group contains:

- `group_id`
- `label`
- `entries`: legacy `StatPriority` objects with `stat`, `weight`, `confidence`, and `reason`

The legacy `stat_priority` field remains readable for one schema generation. New guide rendering should prefer `stat_priority_report`.

## Gear Recommendation Report

`gear_recommendation_report` has schema version `coa-gear-recommendation-v2`:

- `role`: player-facing guide role
- `engine_role`: broad compatibility role
- `best_weapon_types`
- `best_armor_types`
- `available_weapon_types`
- `available_armor_types`
- `item_scores`: ranked item payloads when item data exists
- `source`: `defaults`, `item_data`, or `mixed`
- `confidence`: heuristic confidence label
- `warnings`: section-level warnings such as `item_data_missing` and `gear_targets_from_role_defaults`

The legacy `gear_recommendation` field remains readable for one schema generation. New guide rendering should prefer `gear_recommendation_report`.

## M1.10 Guide Extensions

The M1.10 guide-site renderer keeps JSON canonical and avoids relying on HTML-only state.

Implemented additions:

- `role` expands from Phase 1's broad roles to `melee_dps`, `caster_dps`, `ranged_dps`, `tank`, `healer`, and `support`, with role provenance.
- `primary_role`, `secondary_roles`, and `roles` support hybrid guide filtering while keeping one primary scoring path.
- Build results include role-specific objective index payloads while retaining `projected_dps_index` for compatibility.
- Build results include a playstyle fingerprint, diversity-selection reason, performance-band metadata, and player-facing rotation loop.
- Spec results should include guide navigation metadata, player-facing labels, and tooltip definitions for analyzer-only metrics.
- Selected nodes should include enough tooltip/link/icon data for static guide rendering, or the renderer should join against normalized entries by `entry_id`.
- Talent tree payloads should be explicit about level gates, AE/TE gates, prerequisite failures, and selected rank state.
- Stat and gear sections expose source warnings once per section rather than repeating them for every entry.
