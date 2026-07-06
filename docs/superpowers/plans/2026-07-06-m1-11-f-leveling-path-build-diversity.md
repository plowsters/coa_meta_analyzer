# M1.11F Exact Leveling Path and Build Diversity Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate exact legal level-by-level build paths and select recommended builds by distinct playstyle clusters.

**Architecture:** Add a focused leveling-path module that reconstructs a selected build from level 10 to 60 using existing `BuildRules`. Extend build diversity with rotation signatures rather than replacing current fingerprints. Thread the new leveling payload through guide models/rendering per build.

**Tech Stack:** Python dataclasses, existing `coa_meta` repository/build/search/scoring modules, pytest, static guide renderer.

---

## File Structure

- Create `coa_meta/leveling_path.py`: essence schedule, path dataclasses, greedy legal path builder, marginal-value ranking.
- Create `tests/test_leveling_path.py`: unit coverage for essence awards, passives, legal reconstruction, deferred steps, and value ordering.
- Modify `coa_meta/guide_models.py`: add `leveling_path` to `GuideBuildCard`.
- Modify `coa_meta/guide_builder.py`: attach build-specific leveling path payloads.
- Modify `coa_meta/guide_rendering.py`: render exact path for selected build instead of sorted node list.
- Modify `coa_meta/build_diversity.py`: add rotation signature dataclasses and distance logic.
- Modify `tests/test_build_diversity.py`: verify clustering separates distinct loops and collapses near duplicates.
- Modify `coa_meta/reporting.py`: pass rotation guide data into diversity candidates when available.
- Update `docs/data/meta-report-schema.md`: document `leveling_path`.

## Task 1: Essence Award Schedule and Schema

**Files:**

- Create: `coa_meta/leveling_path.py`
- Create: `tests/test_leveling_path.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_leveling_path.py`:

```python
from coa_meta.leveling_path import (
    LEVELING_PATH_SCHEMA_VERSION,
    essence_awards_for_levels,
    essence_kind_for_level,
)


def test_level_10_through_60_alternates_ae_then_te():
    awards = essence_awards_for_levels(10, 60)

    assert LEVELING_PATH_SCHEMA_VERSION == "coa-leveling-path-v1"
    assert awards[0].level == 10
    assert awards[0].essence_kind == "ability"
    assert awards[1].level == 11
    assert awards[1].essence_kind == "talent"
    assert essence_kind_for_level(60) == "ability"
    assert sum(1 for award in awards if award.essence_kind == "ability") == 26
    assert sum(1 for award in awards if award.essence_kind == "talent") == 25
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. pytest tests/test_leveling_path.py::test_level_10_through_60_alternates_ae_then_te -q
```

Expected: fails with `ModuleNotFoundError: No module named 'coa_meta.leveling_path'`.

- [ ] **Step 3: Add minimal schedule implementation**

Create `coa_meta/leveling_path.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

LEVELING_PATH_SCHEMA_VERSION = "coa-leveling-path-v1"


@dataclass(frozen=True)
class EssenceAward:
    level: int
    essence_kind: str
    amount: int = 1

    def to_dict(self) -> dict[str, int | str]:
        return {"level": self.level, "essence_kind": self.essence_kind, "amount": self.amount}


def essence_kind_for_level(level: int) -> str:
    if level < 10 or level > 60:
        raise ValueError("CoA leveling essence awards are defined for levels 10 through 60")
    return "ability" if level % 2 == 0 else "talent"


def essence_awards_for_levels(start_level: int = 10, max_level: int = 60) -> tuple[EssenceAward, ...]:
    if start_level < 10 or max_level > 60 or start_level > max_level:
        raise ValueError("Expected a level range within 10..60")
    return tuple(EssenceAward(level=level, essence_kind=essence_kind_for_level(level)) for level in range(start_level, max_level + 1))
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=. pytest tests/test_leveling_path.py::test_level_10_through_60_alternates_ae_then_te -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/leveling_path.py tests/test_leveling_path.py
git commit -m "Add CoA essence award schedule"
```

## Task 2: Leveling Path Dataclasses and Passive Unlocks

**Files:**

- Modify: `coa_meta/leveling_path.py`
- Modify: `tests/test_leveling_path.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
from coa_meta.domain import TalentNode
from coa_meta.leveling_path import automatic_passive_steps, LevelingPathStep


def _node(entry_id: int, name: str, *, level: int, ae: int = 0, te: int = 0, passive: bool = True) -> TalentNode:
    return TalentNode(
        entry_id=entry_id,
        spell_id=entry_id + 1000,
        name=name,
        class_id=1,
        class_name="Testclass",
        tab_id=11,
        tab_name="Damage",
        entry_type="Talent",
        essence_kind="talent" if te else "ability",
        ae_cost=ae,
        te_cost=te,
        required_tab_ae=0,
        required_tab_te=0,
        required_level=level,
        max_rank=1,
        row=0,
        col=10,
        node_type="SpendCircle",
        is_passive=passive,
        is_starting_node=False,
        required_ids=tuple(),
        connected_node_ids=tuple(),
        tags=("damage",),
        damage_schools=tuple(),
        resources=tuple(),
        description_text="Level passive.",
        availability={"effective_required_level": level, "level_confidence": "high"},
    )


def test_automatic_passives_unlock_without_spending_essence():
    passive = _node(401, "Level 20 Passive", level=20)

    steps = automatic_passive_steps((passive,), selected_ids={401}, level=20, already_unlocked=set())

    assert steps == (
        LevelingPathStep(
            level=20,
            event_type="automatic_passive",
            node_id=401,
            spell_id=1401,
            name="Level 20 Passive",
            essence_kind="free",
            reason="Unlocks automatically at level 20.",
            ae_spent=0,
            te_spent=0,
            warnings=tuple(),
        ),
    )
```

- [ ] **Step 2: Run failing test**

Run:

```bash
PYTHONPATH=. pytest tests/test_leveling_path.py::test_automatic_passives_unlock_without_spending_essence -q
```

Expected: fails because `LevelingPathStep` and `automatic_passive_steps` are missing.

- [ ] **Step 3: Add dataclasses and passive helper**

Append to `coa_meta/leveling_path.py`:

```python
from typing import Iterable

from .domain import TalentNode


@dataclass(frozen=True)
class LevelingPathStep:
    level: int
    event_type: str
    node_id: int | None
    spell_id: int | None
    name: str
    essence_kind: str
    reason: str
    ae_spent: int
    te_spent: int
    warnings: tuple[str, ...] = tuple()

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "event_type": self.event_type,
            "node_id": self.node_id,
            "spell_id": self.spell_id,
            "name": self.name,
            "essence_kind": self.essence_kind,
            "reason": self.reason,
            "ae_spent": self.ae_spent,
            "te_spent": self.te_spent,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class LevelingPath:
    schema_version: str
    class_name: str
    spec_name: str
    build_id: str
    max_level: int
    steps: tuple[LevelingPathStep, ...]
    warnings: tuple[str, ...] = tuple()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "class_name": self.class_name,
            "spec_name": self.spec_name,
            "build_id": self.build_id,
            "max_level": self.max_level,
            "steps": [step.to_dict() for step in self.steps],
            "warnings": list(self.warnings),
        }


def effective_level(node: TalentNode) -> int:
    availability = node.availability or node.raw.get("availability") or {}
    if availability.get("level_confidence") in {"high", "medium"} and type(availability.get("effective_required_level")) is int:
        return int(availability["effective_required_level"])
    return int(node.required_level)


def automatic_passive_steps(
    nodes: Iterable[TalentNode],
    *,
    selected_ids: set[int],
    level: int,
    already_unlocked: set[int],
) -> tuple[LevelingPathStep, ...]:
    steps: list[LevelingPathStep] = []
    for node in sorted(nodes, key=lambda item: (effective_level(item), item.row, item.col, item.name)):
        if node.entry_id not in selected_ids or node.entry_id in already_unlocked:
            continue
        if node.ae_cost or node.te_cost:
            continue
        if effective_level(node) != level:
            continue
        already_unlocked.add(node.entry_id)
        steps.append(
            LevelingPathStep(
                level=level,
                event_type="automatic_passive",
                node_id=node.entry_id,
                spell_id=node.spell_id,
                name=node.name,
                essence_kind="free",
                reason=f"Unlocks automatically at level {level}.",
                ae_spent=0,
                te_spent=0,
            )
        )
    return tuple(steps)
```

- [ ] **Step 4: Verify**

Run:

```bash
PYTHONPATH=. pytest tests/test_leveling_path.py -q
```

Expected: all current leveling path tests pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/leveling_path.py tests/test_leveling_path.py
git commit -m "Model leveling path steps and passive unlocks"
```

## Task 3: Legal Target Build Reconstruction

**Files:**

- Modify: `coa_meta/leveling_path.py`
- Modify: `tests/test_leveling_path.py`

- [ ] **Step 1: Write failing fixture test**

Use `tests/fixtures/meta_report_fixture.jsonl` and existing repository/build rules:

```python
from pathlib import Path

from coa_meta.builds import BuildConfig, BuildRules
from coa_meta.domain import SelectedRank
from coa_meta.leveling_path import build_leveling_path
from coa_meta.repository import TalentRepository

FIXTURES = Path(__file__).parent / "fixtures"


def test_leveling_path_reconstructs_selected_fixture_build():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    selected_ids = (101, 201, 202)
    selected_ranks = tuple(SelectedRank(node_id=node_id, rank=1) for node_id in selected_ids)
    config = BuildConfig(class_name="Testclass", level=60, max_ae=26, max_te=25)
    rules = BuildRules(repo, config)
    target_state = rules.validate(selected_ranks).state
    assert target_state is not None

    path = build_leveling_path(
        repository=repo,
        state=target_state,
        class_name="Testclass",
        spec_name="Damage",
        build_id="fixture",
        config=config,
        role="caster_dps",
    )

    chosen_ids = [step.node_id for step in path.steps if step.event_type in {"choose_ability", "choose_talent"}]
    assert 101 in chosen_ids
    assert 201 in chosen_ids
    assert 202 in chosen_ids
    assert path.warnings == tuple()
```

- [ ] **Step 2: Run failing test**

Run:

```bash
PYTHONPATH=. pytest tests/test_leveling_path.py::test_leveling_path_reconstructs_selected_fixture_build -q
```

Expected: fails because `build_leveling_path` is missing.

- [ ] **Step 3: Implement legal path builder**

Add `build_leveling_path`, candidate validation, and value ranking to `coa_meta/leveling_path.py`. Reuse `BuildRules.validate` at each step:

```python
from .builds import BuildConfig, BuildRules
from .domain import BuildState, SelectedRank
from .repository import TalentRepository


def build_leveling_path(
    *,
    repository: TalentRepository,
    state: BuildState,
    class_name: str,
    spec_name: str,
    build_id: str,
    config: BuildConfig,
    role: str,
    apl=None,
    rotation_guide: dict | None = None,
) -> LevelingPath:
    target_ids = set(state.selected_ids)
    nodes = tuple(repository.node_by_id(node_id) for node_id in sorted(target_ids))
    selected: set[int] = set(state.free_node_ids)
    unlocked_passives: set[int] = set()
    paid_ranks: list[SelectedRank] = []
    steps: list[LevelingPathStep] = []
    warnings: list[str] = []
    ae_spent = 0
    te_spent = 0

    for award in essence_awards_for_levels(10, min(config.level, 60)):
        steps.extend(automatic_passive_steps(nodes, selected_ids=target_ids, level=award.level, already_unlocked=unlocked_passives))
        candidate = _best_legal_candidate(
            repository=repository,
            config=config,
            class_name=class_name,
            level=award.level,
            target_nodes=nodes,
            selected=selected,
            paid_ranks=paid_ranks,
            essence_kind=award.essence_kind,
            role=role,
            rotation_guide=rotation_guide or {},
        )
        if candidate is None:
            steps.append(
                LevelingPathStep(
                    level=award.level,
                    event_type="deferred",
                    node_id=None,
                    spell_id=None,
                    name="No legal target choice",
                    essence_kind=award.essence_kind,
                    reason=f"No selected {award.essence_kind} node is legal yet.",
                    ae_spent=ae_spent,
                    te_spent=te_spent,
                    warnings=("leveling_path_deferred_essence",),
                )
            )
            continue
        selected.add(candidate.entry_id)
        paid_ranks.append(SelectedRank(node_id=candidate.entry_id, rank=1))
        ae_spent += candidate.ae_cost
        te_spent += candidate.te_cost
        steps.append(
            LevelingPathStep(
                level=award.level,
                event_type="choose_ability" if award.essence_kind == "ability" else "choose_talent",
                node_id=candidate.entry_id,
                spell_id=candidate.spell_id,
                name=candidate.name,
                essence_kind=award.essence_kind,
                reason=_choice_reason(candidate, role, rotation_guide or {}),
                ae_spent=ae_spent,
                te_spent=te_spent,
            )
        )

    final_ids = {rank.node_id for rank in paid_ranks} | set(state.free_node_ids) | unlocked_passives
    missing = sorted(target_ids - final_ids)
    if missing:
        warnings.append("leveling_path_reconstruction_mismatch")
    return LevelingPath(
        schema_version=LEVELING_PATH_SCHEMA_VERSION,
        class_name=class_name,
        spec_name=spec_name,
        build_id=build_id,
        max_level=config.level,
        steps=tuple(steps),
        warnings=tuple(dict.fromkeys(warnings)),
    )
```

Implement `_best_legal_candidate` by trying each unselected target node of the awarded essence kind with `BuildRules(... level=award.level).validate(tuple(paid_ranks + [SelectedRank(candidate.entry_id)]))`.

- [ ] **Step 4: Verify reconstruction**

Run:

```bash
PYTHONPATH=. pytest tests/test_leveling_path.py -q
```

Expected: leveling path tests pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/leveling_path.py tests/test_leveling_path.py
git commit -m "Reconstruct selected builds as leveling paths"
```

## Task 4: Guide Model and Renderer Integration

**Files:**

- Modify: `coa_meta/guide_models.py`
- Modify: `coa_meta/guide_builder.py`
- Modify: `coa_meta/guide_rendering.py`
- Modify: `tests/test_guide_builder.py`
- Modify: `tests/test_guide_rendering.py`

- [ ] **Step 1: Add failing guide tests**

Add to `tests/test_guide_builder.py`:

```python
def test_guide_build_cards_include_build_specific_leveling_path():
    site = build_guide_site(_report(), entries_path=FIXTURES / "meta_report_fixture.jsonl")
    build = site.specs[0].builds[0]

    assert build.leveling_path
    assert build.leveling_path["schema_version"] == "coa-leveling-path-v1"
    assert any(step["event_type"].startswith("choose_") for step in build.leveling_path["steps"])
```

Add to `tests/test_guide_rendering.py`:

```python
def test_spec_html_renders_exact_leveling_path_events():
    site = _site()
    spec = next(item for item in site.specs if item.spec_name == "Damage")

    html = render_spec_html(site, spec)

    assert "Leveling Path" in html
    assert "Ability Essence" in html or "Talent Essence" in html
    assert "No legal target choice" not in html
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
PYTHONPATH=. pytest tests/test_guide_builder.py::test_guide_build_cards_include_build_specific_leveling_path tests/test_guide_rendering.py::test_spec_html_renders_exact_leveling_path_events -q
```

Expected: tests fail because `GuideBuildCard.leveling_path` is missing or empty.

- [ ] **Step 3: Add model field**

Modify `GuideBuildCard` in `coa_meta/guide_models.py`:

```python
leveling_path: dict[str, Any] | None = None
```

and include:

```python
"leveling_path": dict(self.leveling_path or {}),
```

in `to_dict`.

- [ ] **Step 4: Build path in guide builder**

In `coa_meta/guide_builder.py`, import `build_leveling_path` and call it inside `_build_cards` after `node_ids` is available. Pass the repository, selected build state reconstructed from node ids, class/spec, and `BuildConfig`. If reconstruction fails, set `leveling_path={}` and append `leveling_path_unavailable` to the card warnings.

- [ ] **Step 5: Render exact path**

Replace `_render_leveling_path` in `coa_meta/guide_rendering.py` so it first checks `build.leveling_path`:

```python
def _render_leveling_path_for_build(build: GuideBuildCard) -> str:
    path = dict(build.leveling_path or {})
    steps = [dict(step) for step in path.get("steps", [])]
    if not steps:
        return ""
    items = []
    for step in steps:
        if step.get("event_type") == "deferred":
            continue
        essence = str(step.get("essence_kind", "")).replace("_", " ").title()
        items.append(
            f"<li><strong>Level {_e(step.get('level'))}</strong> "
            f"<span class=\"chip\">{_e(essence)}</span> "
            f"{_e(step.get('name'))}<br><span class=\"muted\">{_e(step.get('reason'))}</span></li>"
        )
    return f'<div class="leveling-path"><h3>Leveling Path</h3><ol>{"".join(items)}</ol></div>' if items else ""
```

Call this with the selected build where the tree section is rendered.

- [ ] **Step 6: Verify guide tests**

Run:

```bash
PYTHONPATH=. pytest tests/test_leveling_path.py tests/test_guide_builder.py tests/test_guide_rendering.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git add coa_meta/leveling_path.py coa_meta/guide_models.py coa_meta/guide_builder.py coa_meta/guide_rendering.py tests
git commit -m "Render exact level-by-level build paths"
```

## Task 5: Rotation-Aware Build Diversity Signatures

**Files:**

- Modify: `coa_meta/build_diversity.py`
- Modify: `tests/test_build_diversity.py`

- [ ] **Step 1: Write failing diversity tests**

Add:

```python
from coa_meta.build_diversity import (
    RotationPlaystyleSignature,
    rotation_signature_distance,
)


def test_rotation_signature_separates_dot_loop_from_burst_loop():
    dot = RotationPlaystyleSignature(
        schema_version="coa-rotation-playstyle-v1",
        core_actions=("poison_bite", "venom_tick"),
        opener_actions=("poison_bite",),
        maintenance_actions=("venom_tick",),
        cooldown_actions=tuple(),
        role_tool_actions=tuple(),
        resource_loop="maintenance_loop",
        burst_cadence="none",
        uptime_mechanics=("dot",),
        range_profile="caster",
    )
    burst = RotationPlaystyleSignature(
        schema_version="coa-rotation-playstyle-v1",
        core_actions=("shadowstep", "ambush"),
        opener_actions=("stealth", "ambush"),
        maintenance_actions=tuple(),
        cooldown_actions=("shadow_dance",),
        role_tool_actions=tuple(),
        resource_loop="cooldown_driven",
        burst_cadence="medium",
        uptime_mechanics=tuple(),
        range_profile="melee",
    )

    assert rotation_signature_distance(dot, burst) >= 0.5
    assert rotation_signature_distance(dot, dot) == 0.0
```

- [ ] **Step 2: Run failing test**

Run:

```bash
PYTHONPATH=. pytest tests/test_build_diversity.py::test_rotation_signature_separates_dot_loop_from_burst_loop -q
```

Expected: fails because `RotationPlaystyleSignature` is missing.

- [ ] **Step 3: Add signature dataclass and distance**

Add to `coa_meta/build_diversity.py`:

```python
@dataclass(frozen=True)
class RotationPlaystyleSignature:
    schema_version: str
    core_actions: tuple[str, ...]
    opener_actions: tuple[str, ...]
    maintenance_actions: tuple[str, ...]
    cooldown_actions: tuple[str, ...]
    role_tool_actions: tuple[str, ...]
    resource_loop: str
    burst_cadence: str
    uptime_mechanics: tuple[str, ...]
    range_profile: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "core_actions": list(self.core_actions),
            "opener_actions": list(self.opener_actions),
            "maintenance_actions": list(self.maintenance_actions),
            "cooldown_actions": list(self.cooldown_actions),
            "role_tool_actions": list(self.role_tool_actions),
            "resource_loop": self.resource_loop,
            "burst_cadence": self.burst_cadence,
            "uptime_mechanics": list(self.uptime_mechanics),
            "range_profile": self.range_profile,
        }


def rotation_signature_distance(left: RotationPlaystyleSignature, right: RotationPlaystyleSignature) -> float:
    action_distance = (
        _jaccard_distance(set(left.core_actions), set(right.core_actions)) * 0.35
        + _jaccard_distance(set(left.opener_actions), set(right.opener_actions)) * 0.15
        + _jaccard_distance(set(left.maintenance_actions), set(right.maintenance_actions)) * 0.15
        + _jaccard_distance(set(left.cooldown_actions), set(right.cooldown_actions)) * 0.15
    )
    categorical = sum(
        1.0
        for a, b in (
            (left.resource_loop, right.resource_loop),
            (left.burst_cadence, right.burst_cadence),
            (left.range_profile, right.range_profile),
        )
        if a != b
    ) / 3
    uptime = _jaccard_distance(set(left.uptime_mechanics), set(right.uptime_mechanics))
    return round(min(1.0, action_distance + categorical * 0.15 + uptime * 0.05), 4)
```

- [ ] **Step 4: Verify**

Run:

```bash
PYTHONPATH=. pytest tests/test_build_diversity.py -q
```

Expected: build diversity tests pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/build_diversity.py tests/test_build_diversity.py
git commit -m "Add rotation-aware playstyle signatures"
```

## Task 6: Cluster Recommended Builds by Fingerprint and Rotation Signature

**Files:**

- Modify: `coa_meta/build_diversity.py`
- Modify: `coa_meta/reporting.py`
- Modify: `tests/test_build_diversity.py`
- Modify: `tests/test_meta_report_runner.py`

- [ ] **Step 1: Add failing clustering test**

Add a synthetic test with three candidates: two near-identical DoT loops and one burst loop. Assert only the strongest DoT loop and the burst loop are selected.

```python
def test_diverse_selection_collapses_near_duplicate_rotation_signatures():
    dot_a = _candidate("dot-a", score=100.0, label="dot", rotation_kind="dot")
    dot_b = _candidate("dot-b", score=99.0, label="dot", rotation_kind="dot")
    burst = _candidate("burst", score=96.0, label="burst", rotation_kind="burst")

    selected = select_diverse_builds((dot_a, dot_b, burst), top=3)

    assert [item.build_id for item in selected] == ["dot-a", "burst"]
```

Define `_candidate` in the test using existing `BuildDiversityCandidate` plus a `rotation_signature` field added in Step 3.

- [ ] **Step 2: Run failing test**

Run:

```bash
PYTHONPATH=. pytest tests/test_build_diversity.py::test_diverse_selection_collapses_near_duplicate_rotation_signatures -q
```

Expected: fails because candidates do not carry rotation signatures or clustering ignores them.

- [ ] **Step 3: Extend candidate model**

Modify `BuildDiversityCandidate`:

```python
rotation_signature: RotationPlaystyleSignature | None = None
```

Include `rotation_signature.to_dict()` in `to_dict` when present.

Modify `select_diverse_builds` so candidate distance is:

```python
fingerprint_part = fingerprint_distance(candidate.fingerprint, item.fingerprint)
rotation_part = rotation_signature_distance(candidate.rotation_signature, item.rotation_signature) if both signatures exist else fingerprint_part
combined_distance = fingerprint_part * 0.55 + rotation_part * 0.45
```

Use the combined distance for the diversity floor.

- [ ] **Step 4: Populate signature in reporting**

In `coa_meta/reporting.py`, derive rotation signatures from `rotation_guide` when M1.11E data exists. Use fallback empty signatures when it does not, and add `rotation_signature_missing` to candidate warnings.

- [ ] **Step 5: Verify**

Run:

```bash
PYTHONPATH=. pytest tests/test_build_diversity.py tests/test_meta_report_runner.py -q
```

Expected: tests pass and recommended builds remain stable.

- [ ] **Step 6: Commit**

```bash
git add coa_meta/build_diversity.py coa_meta/reporting.py tests/test_build_diversity.py tests/test_meta_report_runner.py
git commit -m "Cluster recommended builds by rotation playstyle"
```

## Task 7: Docs and Final Verification

**Files:**

- Modify: `docs/data/meta-report-schema.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Document new payloads**

Add `leveling_path` and `rotation_signature` to `docs/data/meta-report-schema.md`.

- [ ] **Step 2: Update roadmap status**

In `docs/ROADMAP.md`, mark M1.11F as implemented once all previous tasks are committed.

- [ ] **Step 3: Run focused suite**

Run:

```bash
PYTHONPATH=. pytest tests/test_leveling_path.py tests/test_build_diversity.py tests/test_meta_report_runner.py tests/test_guide_builder.py tests/test_guide_rendering.py -q
```

Expected: all pass.

- [ ] **Step 4: Run full suite**

Run:

```bash
PYTHONPATH=. pytest
```

Expected: all pass or known unrelated failures documented.

- [ ] **Step 5: Commit docs**

```bash
git add docs/data/meta-report-schema.md docs/ROADMAP.md docs/README.md
git commit -m "Document leveling path and build diversity outputs"
```

## Self-Review Checklist

- Every path event is legal under `BuildRules`.
- Essence awards match 26 AE and 25 TE at level 60.
- Passives do not spend essence.
- Guide rendering uses the selected build's path.
- Duplicate builds are filtered by both selected nodes and rotation behavior.
- No external GPL/AGPL code is copied.
