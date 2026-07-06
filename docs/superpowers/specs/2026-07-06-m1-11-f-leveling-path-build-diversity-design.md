# M1.11F Exact Leveling Path and Build Diversity Correctness Design

## Purpose

M1.11F makes recommended builds usable as leveling and build-choice guidance instead of only endgame snapshots. It has two linked goals:

- Generate an exact level-by-level order for every selected build from level 10 through 60.
- Choose two or three recommended builds by meaningfully different playstyle, not by near-duplicate score rank.

This milestone stays in Phase 1. It uses builder legality, normalized node metadata, role objectives, APL output, and M1.11E rotation guides. It does not require combat logs, empirical DPS/HPS, or a full Phase 3 simulator.

## Current State

The guide site currently renders talent trees using the M1.11C builder-layout model. The "Leveling Path" section is still a weak ordered list of selected nodes sorted by level and grid position. That does not reflect how CoA players earn essence or how prerequisites and tab gates should affect choices.

Build diversity has an initial `coa_meta/build_diversity.py` implementation. It computes a playstyle fingerprint and selects builds from a top performance band, but it does not yet use simulated rotation signatures, level-path feasibility, or stronger clustering rules. As a result, similar DoT loop builds can still appear as separate recommendations.

## Player Rules

Leveling path generation follows the user-supplied CoA rules:

- Level 10 grants one Ability Essence.
- Levels alternate essence awards through level 60.
- Even levels from 10 through 60 grant Ability Essence.
- Odd levels from 11 through 59 grant Talent Essence.
- This yields 26 Ability Essence and 25 Talent Essence at level 60.
- Level passives unlock automatically at their required level and do not spend essence.
- Paid choices must obey prerequisites, tab essence gates, class/spec eligibility, required level, and total essence budgets.

## Research Notes

SimulationCraft is useful as an architecture reference because it treats rotations and stat weights as event-driven simulation output rather than closed-form formulas; its README describes an event-driven combat simulator and highlights why simple calculators become inaccurate for proc-heavy mechanics. The project is GPL-3.0 licensed, so M1.11F should not reuse code or class modules from it.

WoWAnalyzer is useful as a separation-of-concerns reference: ingest events, compute metrics, and produce suggestions. Its repository describes a tool for analyzing raid performance and is AGPL-3.0 licensed. M1.11F should borrow the concept of metrics feeding guidance, not implementation code.

M1.11F does not need live logs. It should consume the local clean-room APL/rotation guide outputs created in M1.11E.

Sources:

- SimulationCraft README/license: <https://github.com/simulationcraft/simc>
- WoWAnalyzer README/license: <https://github.com/WoWAnalyzer/WoWAnalyzer>

## Scope

M1.11F includes:

- `coa-leveling-path-v1` schema and dataclasses.
- Essence award schedule from level 10 to 60.
- Legal path reconstruction for a selected endgame build.
- Automatic passive unlock events.
- Marginal-value ordering so the most useful legal target nodes are chosen early.
- Warnings when a selected build cannot be reconstructed exactly.
- Guide model and renderer changes so build selection updates leveling order.
- Rotation-aware build clustering so the top builds differ by core loop/playstyle.

M1.11F does not include:

- Empirical log calibration.
- Full item ranking.
- Account-specific pathing from a partially leveled character.
- Mobile-responsive tree reflow.
- Copying external SimC or WoWAnalyzer implementation code.

## Leveling Path Model

Add `coa_meta/leveling_path.py`.

Primary dataclasses:

- `EssenceAward`: level, essence kind, amount.
- `LevelingPathStep`: level, event type, node id, spell id, name, essence kind spent, reason, current AE/TE totals, legality warnings.
- `LevelingPath`: schema version, class/spec/build id, max level, final AE/TE spent, steps, warnings.

Event types:

- `choose_ability`: paid Ability Essence node selected at an AE level.
- `choose_talent`: paid Talent Essence node selected at a TE level.
- `automatic_passive`: level passive unlocked without essence.
- `deferred`: an essence was awarded but no target or gate-unlocking node was legal.

Level passives should be identified conservatively:

- `ae_cost == 0`
- `te_cost == 0`
- not a starting class bootstrap node unless it has a meaningful required level
- effective required level from availability metadata when confidence is high or medium, otherwise `required_level`
- selected/free in the final build or relevant to the class/spec panel

## Path Algorithm

Inputs:

- `TalentRepository`
- selected `BuildState`
- selected node objects
- `BuildConfig`
- role
- optional generated APL
- optional rotation guide

Algorithm:

1. Build the target node set from the final selected build.
2. Add target dependencies from `required_ids` so the path can explain prerequisite picks.
3. Iterate levels 10 through 60.
4. At each level, append newly available automatic passives.
5. Award AE on even levels and TE on odd levels.
6. Build a candidate pool for the awarded essence kind:
   - target nodes not yet selected
   - dependency nodes needed by target nodes
   - gate-unlocking selected nodes that make more target nodes legal
7. Validate each candidate against `BuildRules` at the current level and current partial state.
8. Pick the candidate with the highest marginal value.
9. If no candidate is legal, append a `deferred` step and carry the unspent essence forward.
10. After level 60, validate that the reconstructed path matches the target build.

The generator must not invent off-build filler picks unless explicitly requested later. If the target build cannot spend an essence legally at a given level, it should record a deferred step rather than silently choosing unrelated nodes.

## Marginal Value

M1.11F should rank legal choices using a deterministic proxy, not random search:

- Direct target node: high base value.
- APL or rotation-guide action used in the core loop: large bonus.
- Cooldown/maintenance/role tool used in rotation guide: medium bonus.
- Node tags matching the guide role: medium bonus.
- Required prerequisite for a high-value target: unlocker bonus.
- Passive-only throughput/survival/support tag: small bonus.
- Node required later because of tab gates: urgency bonus.

Tie-breakers:

1. lower required level
2. lower tab gate requirement
3. builder-layout row/column if available
4. node name
5. entry id

This gives stable paths and avoids churn in generated reports.

## Build Diversity Model

M1.11F should extend, not replace, `coa_meta/build_diversity.py`.

The current fingerprint should gain a second-level `RotationPlaystyleSignature`:

- core loop action keys
- opener action keys
- maintenance action keys
- cooldown action keys
- role-tool action keys
- resource loop kind: builder/spender, cooldown-driven, maintenance-loop, support-cycle, defensive-cycle, unknown
- burst cadence: none, short, medium, long
- uptime mechanics: DoT, HoT, aura, mitigation, pet/summon
- range profile: melee, ranged, caster, hybrid

Build clustering should then:

1. Generate a larger raw candidate pool.
2. Score and generate APL/rotation guide for each candidate when available.
3. Compute playstyle fingerprints and rotation signatures.
4. Build clusters using deterministic distance thresholds.
5. Select one representative per close cluster.
6. Pick representatives from a performance band.
7. Prefer builds with medium/high reliability and a consistent simulated rotation.
8. Label any unavoidable similar build as a minor variation instead of pretending it is a distinct build.

Recommended default thresholds:

- performance floor: current MAD/relative floor logic from `performance_band_floor`
- build fingerprint distance floor: `0.22`
- rotation signature distance floor: `0.28`
- representative reliability floor: medium when at least one medium/high option exists

## Guide Integration

Each `GuideBuildCard` should carry a build-specific leveling path payload. The renderer should display the exact path for the currently selected build, not a shared spec-level order.

The section should show:

- level
- essence awarded
- chosen ability/talent/passive
- short reason
- warnings only when present

Example language:

- "Level 10, Ability Essence: Take Shared Strike first because it starts the core resource loop."
- "Level 11, Talent Essence: Take Damage Talent because it unlocks the spec's DoT loop."
- "Level 20: Passive unlocks automatically."

## Failure Modes

M1.11F should warn, not hide problems:

- `leveling_path_target_unreachable`
- `leveling_path_deferred_essence`
- `leveling_path_missing_prerequisite`
- `leveling_path_budget_mismatch`
- `leveling_path_reconstruction_mismatch`
- `diversity_selection_insufficient_clusters`
- `rotation_signature_missing`

Warnings should appear in build/report JSON. The visual guide should only show a warning panel for the leveling path if the path itself has warnings.

## Acceptance Criteria

- Level 10 through 60 produces 26 AE awards and 25 TE awards.
- Passives unlock automatically and do not spend essence.
- The final path reconstructs the selected endgame build when source data allows it.
- Each selected build has its own leveling path.
- Switching builds updates leveling order, rotation guide, tree state, stats, gear, warnings, and playstyle metadata.
- Duplicate poison DoT loop variants collapse to one recommendation.
- A stealth/burst build can appear alongside a DoT loop build if both are competitive and reliable.
- Sparse candidate pools degrade gracefully with warnings.

## Risks

- Some builder data may not expose enough level-gate confidence for every class-wide node. Mitigation: use availability confidence and explicit warnings.
- Greedy marginal value can pick a locally good but globally awkward order. Mitigation: keep deterministic backtracking for one-step gate dead ends and validate final reconstruction.
- Overly strict clustering can hide viable variants. Mitigation: if fewer than requested builds remain, widen performance band and label minor variations.
