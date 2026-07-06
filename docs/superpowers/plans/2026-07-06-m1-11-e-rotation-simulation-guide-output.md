# M1.11E Rotation Simulation and Guide-Ready Priority Output Implementation Plan

> **For agentic workers:** Use TDD for state transitions, APL execution, candidate generation, and guide serialization. Commit after each checkpoint. Keep SimulationCraft/WoWAnalyzer as architecture references only; do not copy code, APLs, parsers, or class modules.

**Goal:** Generate one concise, role-aware, guide-ready rotation per selected build by executing structured APL candidates through the local combat engine.

**Architecture:** Add a rotation simulation layer between APL generation and guide rendering. The layer consumes selected build nodes, `coa_mechanics.jsonl`, generated APL data, role objectives, and encounter config, then emits `coa-rotation-guide-v1`.

---

## Checkpoint 1: Rotation Guide Schema and Data Model

Files:

- Create `docs/data/rotation-guide-schema.md`
- Create `coa_meta/rotation_guides.py`
- Create `tests/test_rotation_guides.py`
- Update `docs/data/meta-report-schema.md`

### Step 1: Add failing schema/model tests

Assertions:

- `RotationGuide.to_dict()` emits `schema_version: "coa-rotation-guide-v1"`.
- Empty optional sections serialize as empty lists, not `None`.
- `opener`, `core_loop`, `priority_rules`, `cooldown_rules`, `proc_rules`, `defensive_rules`, `healing_rules`, and `support_rules` preserve ability IDs and display names.
- `simulation_summary` includes role, encounter, duration, objective score, reliability, action count, unsupported mechanic counts, and warnings.
- Invalid reliability values raise a clear error.

Run:

```bash
PYTHONPATH=. pytest tests/test_rotation_guides.py
```

Expected: RED.

### Step 2: Implement guide dataclasses

Suggested types:

```text
RotationGuide
RotationGuideRule
RotationSimulationSummary
ActionUsageSummary
RotationReliability
```

Rule fields:

```text
rule_id
section
text
ability_name
spell_id
entry_id
icon
db_url
condition
priority
```

### Step 3: Document schema

`docs/data/rotation-guide-schema.md` should specify:

- Schema fields.
- Section semantics.
- Reliability meanings.
- Source labels: `theorycraft`, `simulated`, `empirical`, `blended`.
- Compatibility with current `rotation_loop`.

### Step 4: Verify and commit

Run:

```bash
PYTHONPATH=. pytest tests/test_rotation_guides.py
git diff --check
```

Commit:

```bash
git add coa_meta/rotation_guides.py tests/test_rotation_guides.py docs/data/rotation-guide-schema.md docs/data/meta-report-schema.md
git commit -m "Add rotation guide schema model"
```

---

## Checkpoint 2: Action Catalog from Mechanics

Files:

- Create `coa_meta/action_catalog.py`
- Extend `tests/test_action_catalog.py`
- Modify `coa_meta/mechanics.py` only if schema helpers are missing.

### Step 1: Add failing catalog tests

Fixture should include:

- A builder action.
- A spender action.
- A DoT/HoT action.
- A cooldown aura action.
- A passive talent that should not be directly cast.

Assertions:

- Catalog includes selected active abilities and excludes passives from executable action lists.
- Costs, generated resources, cooldown, GCD, duration, period, tags, and source confidence map into executable metadata.
- Missing mechanics emit warnings and conservative defaults.
- Role-specific action classification returns `damage`, `heal`, `mitigation`, `support`, `utility`, or `unknown`.

### Step 2: Implement catalog builder

Public API:

```text
build_action_catalog(selected_nodes, mechanics_repo, role, encounter) -> ActionCatalog
```

The catalog should expose:

```text
actions_by_key
actions_by_spell_id
warnings
coverage_summary
```

Do not invent coefficients. For M1.11E, use normalized proxy values from node score/features and parsed mechanics fields.

### Step 3: Verify and commit

Run:

```bash
PYTHONPATH=. pytest tests/test_action_catalog.py tests/test_mechanics.py
git diff --check
```

Commit:

```bash
git add coa_meta/action_catalog.py coa_meta/mechanics.py tests/test_action_catalog.py tests/test_mechanics.py
git commit -m "Build executable action catalogs from mechanics"
```

---

## Checkpoint 3: Stateful APL Simulation Loop

Files:

- Create `coa_meta/rotation_simulation.py`
- Extend `coa_meta/apl_interpreter.py`
- Extend `coa_meta/combat/state.py` or add wrappers as needed.
- Create `tests/test_rotation_simulation.py`
- Extend `tests/test_apl_interpreter.py`

### Step 1: Add failing simulation tests

Test scenarios:

1. Builder/spender loop:
   - Builder generates resource.
   - Spender fires only above threshold.
   - Simulation alternates enough to avoid overcapping.
2. DoT maintenance:
   - DoT is applied when missing.
   - DoT is refreshed near expiry, not every GCD.
3. Cooldown priority:
   - Cooldown action is used when ready and skipped while unavailable.
4. Healer emergency:
   - Emergency heal triggers below configured health threshold.
5. Tank mitigation:
   - Mitigation buff is kept up during damage windows.
6. Unsupported condition:
   - Candidate finishes with a warning and lower reliability input.

### Step 2: Implement simulation state

Add:

```text
RotationSimulationConfig
RotationSimulationState
RotationSimulationResult
RotationEvent
simulate_apl(apl, action_catalog, config)
```

Default config:

```text
duration_ms=90000
target_count=1
seed=1
max_events=10000
```

State should support:

- Resources and max resources.
- Cooldowns and charges.
- Buff/debuff stacks and expirations.
- GCD.
- Periodic ticks.
- Target health bands.
- Role event windows.

### Step 3: Expand condition support only for generated APLs

Support the current generated condition vocabulary first:

```text
if missing
on cooldown
if resource low
if resource high
when allies injured
before heavy damage
if active enemies >= n
if target health <= n
if buff/debuff missing/up/down/remains
```

Unsupported expressions should produce `unsupported_condition:<condition>` warnings.

### Step 4: Verify and commit

Run:

```bash
PYTHONPATH=. pytest tests/test_apl_interpreter.py tests/test_rotation_simulation.py tests/test_combat_engine.py
git diff --check
```

Commit:

```bash
git add coa_meta/rotation_simulation.py coa_meta/apl_interpreter.py coa_meta/combat tests
git commit -m "Execute APLs through rotation simulation"
```

---

## Checkpoint 4: Rotation Candidate Generator

Files:

- Create `coa_meta/rotation_candidates.py`
- Create `tests/test_rotation_candidates.py`

### Step 1: Add failing candidate tests

Assertions:

- Candidate generation starts with the generated APL unchanged.
- It only reorders actions inside compatible groups.
- It never drops mandatory survival/healing/support rules for tank/healer/support roles.
- It can change resource thresholds inside configured bounds.
- It caps total candidates deterministically.
- It returns stable IDs and fingerprints.

### Step 2: Implement bounded candidate generation

Public API:

```text
generate_rotation_candidates(apl, action_catalog, role, config) -> tuple[RotationCandidate, ...]
```

Config:

```text
max_candidates=48
max_actions=12
threshold_variants=(low, default, high)
include_opener_variants=True
include_cooldown_policy_variants=True
```

Use deterministic ordering. No random search in the first pass.

### Step 3: Add quick pre-score pruning

Before full simulation, reject candidates that:

- contain no executable core actions;
- are all cooldowns and no filler;
- have no role-relevant action for healer/tank/support;
- exceed `max_actions` after trimming.

### Step 4: Verify and commit

Run:

```bash
PYTHONPATH=. pytest tests/test_rotation_candidates.py
git diff --check
```

Commit:

```bash
git add coa_meta/rotation_candidates.py tests/test_rotation_candidates.py
git commit -m "Generate bounded rotation candidates"
```

---

## Checkpoint 5: Role Objective Scoring and Reliability

Files:

- Create `coa_meta/rotation_scoring.py`
- Create `tests/test_rotation_scoring.py`
- Reuse M1.11B objective helpers where practical.

### Step 1: Add failing scoring tests

Assertions:

- DPS roles prefer higher throughput, uptime, and resource efficiency.
- Tank role values mitigation uptime, emergency coverage, threat, self-healing, and damage contribution.
- Healer role values healing proxy, mana efficiency, emergency response, and safe damage contribution.
- Support role values buff/debuff uptime, burst alignment, utility, and contribution.
- Reliability changes between high/medium/low based on mechanics coverage, unsupported conditions, unsupported effects, and candidate variance.
- A candidate with higher raw damage but low reliability can lose to a slightly lower but stable candidate.

### Step 2: Implement role scoring

Public API:

```text
score_rotation_result(result, role_objective, action_catalog) -> RotationScore
select_best_rotation_candidate(results, role_objective) -> RotationSelection
```

Keep score units relative and labeled. Do not emit observed DPS/HPS.

### Step 3: Verify and commit

Run:

```bash
PYTHONPATH=. pytest tests/test_rotation_scoring.py tests/test_role_objectives.py
git diff --check
```

Commit:

```bash
git add coa_meta/rotation_scoring.py tests/test_rotation_scoring.py
git commit -m "Score simulated rotations by role objective"
```

---

## Checkpoint 6: Generate Player-Facing Rotation Guides

Files:

- Extend `coa_meta/rotation_guides.py`
- Create or extend `tests/test_rotation_guides.py`
- Modify `coa_meta/rotation_loops.py` only as a compatibility fallback.

### Step 1: Add failing guide-generation tests

Assertions:

- A simulated builder/spender candidate becomes a concise core loop.
- A DoT maintenance action becomes a maintenance priority rule, not a full-kit category.
- Cooldowns become a separate cooldown rule section.
- Tank/healer/support roles populate their role-specific sections.
- Output includes 4-12 primary ability rules unless sparse data forces fewer with a warning.
- Ability sequence is derived from event usage, not from raw APL order alone.

### Step 2: Implement guide extraction

Public API:

```text
build_rotation_guide(selection, apl, action_catalog, role, encounter) -> RotationGuide
```

Algorithm:

1. Use action usage and event order to identify repeated windows.
2. Pick the recurring core loop actions.
3. Pull opener from first-use ordering inside the first cooldown window.
4. Pull cooldown/proc/defensive/healing/support sections from rule metadata and event timing.
5. Drop unused or rarely used actions unless they are emergency/utility rules.
6. Emit warnings for sparse or unsupported mechanics.

### Step 3: Verify and commit

Run:

```bash
PYTHONPATH=. pytest tests/test_rotation_guides.py tests/test_rotation_simulation.py
git diff --check
```

Commit:

```bash
git add coa_meta/rotation_guides.py coa_meta/rotation_loops.py tests/test_rotation_guides.py
git commit -m "Build guide-ready rotations from simulation"
```

---

## Checkpoint 7: Report and Guide Rendering Integration

Files:

- Modify `coa_meta/reporting.py`
- Modify `coa_meta/guide_models.py`
- Modify `coa_meta/guide_builder.py`
- Modify `coa_meta/guide_rendering.py`
- Modify `coa_meta/cli.py`
- Extend tests:
  - `tests/test_meta_report_runner.py`
  - `tests/test_guide_builder.py`
  - `tests/test_guide_rendering.py`
  - `tests/test_cli.py`

### Step 1: Add failing integration tests

Assertions:

- `python -m coa_meta meta --simulate-rotations` emits `rotation_guide` for top builds.
- If rotation simulation fails or has no executable actions, the report falls back to `rotation_loop` and emits a warning.
- Guide pages prefer `rotation_guide`.
- Rotation sections use player-facing wording and include icons/links when assets exist.
- Warnings section remains hidden when no warnings exist.
- CLI logs the rotation-simulation stage and completion counts.

### Step 2: Wire pipeline

Reporting flow per candidate:

```text
score build
generate APL
build action catalog
generate rotation candidates
simulate candidates
score/select best rotation
build rotation guide
emit report build
```

Initial CLI behavior:

```text
--simulate-rotations
--rotation-duration-ms 90000
--rotation-candidates 48
--no-simulate-rotations
```

### Step 3: Update guide rendering

Use section order:

1. Quick priority
2. Opener
3. Core loop
4. Cooldowns
5. Procs/statuses
6. Role tools
7. AoE adjustments
8. Reliability/provenance

### Step 4: Verify and commit

Run:

```bash
PYTHONPATH=. pytest tests/test_meta_report_runner.py tests/test_guide_builder.py tests/test_guide_rendering.py tests/test_cli.py
git diff --check
```

Commit:

```bash
git add coa_meta tests docs/data/meta-report-schema.md
git commit -m "Wire simulated rotation guides into reports"
```

---

## Checkpoint 8: Real Report Smoke

### Step 1: Run focused reports

Use specs with different roles:

```bash
python -m coa_meta meta \
  --entries coa_scraper/dist/coa_entries.enriched.jsonl \
  --classes coa_scraper/dist/coa_classes.json \
  --out reports/meta \
  --format json --format md --format html \
  --simulate-rotations
```

Inspect generated JSON for:

- `rotation_guide.schema_version == "coa-rotation-guide-v1"`
- role-specific objective summary
- concise section sizes
- reliability warnings where mechanics are sparse

### Step 2: Run focused unit suite

```bash
PYTHONPATH=. pytest \
  tests/test_action_catalog.py \
  tests/test_rotation_simulation.py \
  tests/test_rotation_candidates.py \
  tests/test_rotation_scoring.py \
  tests/test_rotation_guides.py \
  tests/test_meta_report_runner.py \
  tests/test_guide_rendering.py
```

### Step 3: Commit source only

Do not commit generated `reports/` unless explicitly requested.

```bash
git add coa_meta tests docs/data docs/superpowers
git commit -m "Complete rotation simulation guide output"
```

---

## Acceptance Checklist

- [ ] APLs execute repeatedly over time instead of being summarized by category.
- [ ] Candidate search is deterministic and bounded.
- [ ] Role objective scoring changes rotation selection for tanks, healers, and support specs.
- [ ] Guide output uses 4-12 primary rotation rules where data supports it.
- [ ] Report JSON includes `rotation_guide` and preserves `rotation_loop` fallback.
- [ ] Sparse mechanics produce reliability warnings instead of confident claims.
- [ ] No SimC or WoWAnalyzer code is copied.

