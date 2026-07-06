# M1.11E Rotation Simulation and Guide-Ready Priority Output Design

Date: 2026-07-06

Status: ready for implementation planning

## Goal

M1.11E replaces category-based rotation summaries with guide-ready priority output backed by executable APL simulation.

Each selected build should receive one concise player-facing rotation guide that explains an opener, core loop, cooldown usage, proc/status rules, and role-specific defensive/healing/support priorities. The guide should use only the subset of the kit that the simulated priority system actually uses.

## Current State

The repo has the right skeleton, but it is not yet a real rotation optimizer:

- `coa_meta.apl` generates structured `coa-apl-v1` priority actions from profile rules.
- `coa_meta.apl_interpreter` can choose one available action from a priority list against a static runtime state.
- `coa_meta.combat.engine` can execute simple actions with damage/healing, resources, cooldowns, GCD, and periodic effects.
- `coa_meta.rotation_loops` turns APL categories into readable sections, but it does not simulate action sequences or identify a true repeatable loop.
- `coa_meta.reporting` selects diverse builds and includes `rotation_loop`, but the loop is still derived from labels like maintenance/cooldown/builder/spender.
- `coa_meta.mechanics` has fields for richer action metadata, but scraper-generated mechanics rows are still sparse.

M1.11E should connect these parts into a deterministic simulation loop before adding more guide prose.

## Research Findings

### SimulationCraft Pattern

SimulationCraft describes itself as a multi-player event-driven simulator for World of Warcraft combat. Its APL documentation models rotations as priority lists: periodically scan from the highest-priority action downward, skip actions whose cooldowns or conditions are not available, and execute the first available action. It also supports named sub-action lists (`call_action_list`, `run_action_list`) for readability and behavior changes.

Design implication:

- CoA Meta Analyzer should keep structured APL as canonical data.
- The simulator should execute priority rules repeatedly over time, not emit one static category summary.
- M1.11E should borrow the priority-list architecture, not copy SimC code or class modules.

### License Boundary

SimulationCraft is GPL-3.0, and WoWAnalyzer is AGPL-3.0. They are useful architecture references, but source-code reuse would require a deliberate license decision. M1.11E should remain clean-room and deterministic.

Design implication:

- Use public concepts: priority lists, event loops, log/analyzer separation, guide-facing summaries.
- Do not copy action modules, expression parsers, generated APLs, or analyzer implementations.
- Keep source references in docs, not code comments that imply derivation.

### Guide Site Pattern

Retail guide sites usually present rotations as player tasks:

- opener
- core priority or core loop
- cooldown timing
- DoT/buff maintenance
- proc handling
- AoE adjustments
- defensive/healing/support rules

They do not list every available ability. The player-facing output should be a compact priority guide generated from the simulated high-performing APL candidate.

## Scope

In scope:

- Executable APL simulation loop for the existing structured APL model.
- Combat state extension for auras, stacks, proc flags, charges, target count, and role objective events.
- Mechanics-to-action catalog builder using `coa_mechanics.jsonl`.
- Controlled rotation candidate generation from selected build actions.
- Role-aware objective scoring for damage, healing, tanking, support, and ranged/caster/melee DPS.
- Reliability and coverage metrics based on supported mechanics, unsupported conditions, variance, and action utilization.
- `rotation_guide` report schema and guide HTML rendering.

Out of scope:

- Importing or embedding SimulationCraft.
- Full coefficient-accurate live DPS simulation.
- User-uploaded SimC-style profile execution. That belongs to P2/Vercel backend planning.
- Empirical log calibration. That belongs to M1.11G/P2.
- Per-spec handcrafted perfect rotations for all 70 specs in the first pass.

## Core Architecture

### Simulation State

Add a state model that can represent:

```text
time_ms
duration_ms
gcd_ready_at_ms
target_count
resources
cooldowns
charges
buffs
debuffs
active_dots
active_hots
proc_flags
actor_health_pct
target_health_pct
threat
support_windows
event_log
warnings
```

This should extend or wrap the existing `coa_meta.combat.state` types rather than replacing them.

### APL Execution

APL execution should run this loop:

1. Evaluate priority actions against current state.
2. Select the first usable action.
3. Apply its cost, cooldown, GCD, aura changes, damage/healing/shield/threat/support effects, and event log row.
4. Advance time to the next event or GCD boundary.
5. Tick periodic effects.
6. Repeat until encounter duration ends.

Unsupported conditions should not be silently ignored. They should mark the candidate lower reliability and either:

- treat the condition as false when that is safer, or
- use a documented fallback if the condition is an advisory generated by the current profiles.

### Candidate Generation

M1.11E should not attempt an enormous random search. Use controlled candidate generation:

- Start from the generated APL.
- Keep illegal/unselected actions out.
- Generate candidates by reordering actions inside compatible groups, changing resource thresholds, including/excluding optional cooldowns, and changing opener order.
- Keep hard safety rules fixed: required maintenance, survival rules for tanks, emergency healing rules for healers, and support buff alignment rules.
- Use beam search or bounded top-N pruning by quick objective score.

Candidate dimensions:

```text
opener_order
core_priority_order
cooldown_policy
resource_thresholds
maintenance_thresholds
aoe_thresholds
defensive_thresholds
support_alignment_policy
```

### Role Objectives

Reuse M1.11B role-specific objective indexes as the scoring target:

- `melee_dps`, `ranged_dps`, `caster_dps`: throughput, uptime, resource efficiency, cooldown alignment, target-count fit.
- `tank`: damage reduction uptime, active mitigation timing, emergency coverage, threat generation, self-healing, damage contribution.
- `healer`: healing throughput proxy, mana efficiency, HoT/shield uptime, emergency response coverage, damage contribution when safe.
- `support`: buff/debuff uptime, alignment with burst windows, utility coverage, damage/healing contribution.

The score must remain labeled as theorycraft/simulated under stated assumptions until calibrated by logs.

### Guide Output

Schema target: `coa-rotation-guide-v1`

Fields:

```text
schema_version
source
role
encounter
build_id
simulation_summary
opener
core_loop
priority_rules
cooldown_rules
proc_rules
defensive_rules
healing_rules
support_rules
aoe_adjustments
movement_notes
ability_sequence
action_usage
reliability
warnings
```

Player-facing rules should use WoW guide language:

- "Keep X active."
- "Use Y before Z when both are ready."
- "Spend at high resource to avoid overcapping."
- "Use defensive cooldowns before heavy incoming damage."

Avoid engine language on the guide page unless it is in a metric tooltip or provenance section.

## Reliability Model

Reliability should be more sensitive than the current confidence label:

- `high`: most selected core actions have parsed cooldown/cost/duration data, conditions are supported, and candidate rankings are stable across minor assumption changes.
- `medium`: enough mechanics exist to form a plausible guide, but some coefficients/procs/effects are inferred.
- `low`: major core actions are missing mechanics, unsupported conditions dominate, or candidate rankings swing heavily.

Reliability inputs:

```text
mechanics_coverage_pct
unsupported_condition_count
unsupported_effect_count
action_usage_concentration
candidate_score_variance
role_objective_coverage
warnings
```

## Integration Points

Report generation:

- Build legal candidates.
- Score with role objective.
- Generate APL.
- Build action catalog from selected build mechanics.
- Generate and simulate rotation candidates.
- Pick the best reliable rotation candidate.
- Emit `rotation_guide`.
- Use `rotation_guide` for build diversity fingerprints when possible.

Guide rendering:

- Replace `rotation_loop` as the primary section when `rotation_guide` exists.
- Keep `rotation_loop` as a compatibility fallback.
- Show warnings only when present.
- Hotlink ability names and icons through local AscensionDB records.

CLI:

- `python -m coa_meta meta --simulate-rotations` should be an explicit flag at first.
- Once stable, M1.11E can make rotation simulation the default guide path while still allowing `--no-simulate-rotations` for fast reports.

## Risks

- Sparse mechanics data can create misleading "optimal" sequences. Reliability labels and guide warnings must make this visible.
- Role objectives can overweight the wrong proxy until logs exist. M1.11G must add calibration overrides and live-meta sanity checks.
- Candidate search can become slow if it expands too broadly. The first implementation should cap actions, candidates, and duration.
- APL condition support can creep into a large expression-language project. M1.11E should support the current generated condition set first and document unsupported expressions.

## References

- SimulationCraft README: <https://github.com/simulationcraft/simc/blob/thewarwithin/README.md>
- SimulationCraft action lists: <https://github.com/simulationcraft/simc/wiki/ActionLists>
- SimulationCraft GPL-3.0 license: <https://github.com/simulationcraft/simc/blob/thewarwithin/LICENSE>
- WoWAnalyzer repository and AGPL-3.0 license marker: <https://github.com/WoWAnalyzer/WoWAnalyzer>
- Local reference notes: `docs/RETAIL_TOOLING_REFERENCES.md`
