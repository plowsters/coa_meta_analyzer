# M1.10C/D Talent Tree Renderer and Build Diversity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Commit after each completed task.

**Goal:** Add CoA-style static talent trees to spec guide pages and change default guide recommendations from raw top-N builds to strong, reliable, distinct playstyles from the top theorycraft band.

**Architecture:** Keep `BuildRules` as the source of truth for legality. Extend the existing M1.10A/B guide model with tree nodes, tree snapshots, build playstyle metadata, and core rotation loops. Add separate modules for guide tree construction, build diversity, and rotation loop extraction. Keep static HTML/CSS/JS GitHub Pages-compatible and network-free.

**Tech Stack:** Python 3.14 stdlib, dataclasses, existing `coa_meta` package, JSON/JSONL artifacts, pytest, static HTML/CSS/JavaScript, no frontend build step.

---

## File Structure

Create:

- `coa_meta/guide_tree.py`: tree dataclasses, snapshot builder, edge builder, level path builder.
- `coa_meta/build_diversity.py`: playstyle fingerprints, distance scoring, reliability scoring, diverse candidate selection.
- `coa_meta/rotation_loops.py`: core loop extraction from generated APLs and selected nodes.
- `tests/test_guide_tree.py`
- `tests/test_build_diversity.py`
- `tests/test_rotation_loops.py`

Modify:

- `coa_meta/guide_models.py`: add tree, snapshot, edge, fingerprint, selection reason, and rotation loop dataclasses or fields.
- `coa_meta/guide_builder.py`: attach trees and enhanced build cards to guide specs.
- `coa_meta/guide_rendering.py`: render tree UI, playstyle build cards, and core loop sections.
- `coa_meta/reporting.py`: select diverse builds before creating `BuildReport`, populate new report fields, keep old fields compatible.
- `coa_meta/search.py`: if needed, expose enough candidate pool metadata without changing legality behavior.
- `docs/data/meta-report-schema.md`: document new optional report fields.
- `docs/README.md`: update guide output description after implementation.
- Existing guide/report tests to match the new tree and diverse build output.

Do not modify:

- Scraper normalization.
- AscensionDB enrichment behavior.
- The underlying scoring profile format unless a test proves a missing field is required.
- CLI argument names unless a backwards-compatible option is needed.

---

## Task 1: Guide Tree Data Model

**Files:**

- Modify: `coa_meta/guide_models.py`
- Create: `tests/test_guide_tree.py`
- Create: `coa_meta/guide_tree.py` as a stub if needed for imports

- [ ] **Step 1: Add failing model tests**

Create `tests/test_guide_tree.py` with model serialization expectations:

```python
from __future__ import annotations

from coa_meta.guide_models import (
    GuideNodeGate,
    GuideTree,
    GuideTreeEdge,
    GuideTreeSnapshot,
)


def test_guide_tree_serializes_snapshots_and_edges():
    tree = GuideTree(
        tree_id="testclass-damage-1",
        class_name="Testclass",
        spec_name="Damage",
        build_rank=1,
        build_label="Direct damage loop",
        level=60,
        max_ae=26,
        max_te=25,
        ae_spent=3,
        te_spent=2,
        rows=10,
        cols=11,
        nodes=tuple(),
        edges=(GuideTreeEdge(source_id=201, target_id=202, kind="connection", state="selected"),),
        snapshots=(
            GuideTreeSnapshot(
                level=60,
                max_ae=26,
                max_te=25,
                ae_spent=3,
                te_spent=2,
                selected_node_ids=(201, 202),
                free_node_ids=tuple(),
                available_node_ids=(203,),
                gated_nodes=(
                    GuideNodeGate(
                        node_id=204,
                        state="gated_required_node",
                        reasons=("Requires Damage Talent",),
                        issue_codes=("required_node_missing",),
                    ),
                ),
            ),
        ),
        warnings=tuple(),
    )

    payload = tree.to_dict()

    assert payload["schema_version"] == "coa-guide-tree-v1"
    assert payload["edges"][0]["source_id"] == 201
    assert payload["snapshots"][0]["gated_nodes"][0]["state"] == "gated_required_node"
```

- [ ] **Step 2: Extend `GuideNode`**

Add fields with defaults to avoid breaking current call sites while the tree builder is implemented:

```python
row: int | None = None
col: int | None = None
node_type: str = "SpendCircle"
max_rank: int = 1
rank: int = 0
selected: bool = False
free: bool = False
required_ids: tuple[int, ...] = tuple()
connected_node_ids: tuple[int, ...] = tuple()
required_tab_ae: int = 0
required_tab_te: int = 0
availability_confidence: str = "unknown"
source_level: int | None = None
tooltip_required_level: int | None = None
tree_state: str = "inactive"
gate_reasons: tuple[str, ...] = tuple()
```

Update `GuideNode.to_dict()` so tuple fields serialize as lists.

- [ ] **Step 3: Add tree dataclasses**

In `coa_meta/guide_models.py`, add:

- `GuideNodeGate`
- `GuideTreeEdge`
- `GuideTreeSnapshot`
- `GuideTree`

Each class should have a deterministic `to_dict()` method and `schema_version` at the top-level object where applicable.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_guide_tree.py -q
```

Expected: pass.

- [ ] **Step 5: Run guide model callers**

Run:

```bash
python -m pytest tests/test_guide_builder.py tests/test_guide_rendering.py -q
```

Expected: pass after preserving defaults.

- [ ] **Step 6: Commit**

```bash
git add coa_meta/guide_models.py tests/test_guide_tree.py
git commit -m "feat: add guide tree data model"
```

---

## Task 2: Build Guide Trees From Canonical Legality Rules

**Files:**

- Create/modify: `coa_meta/guide_tree.py`
- Modify: `coa_meta/guide_builder.py`
- Modify: `tests/test_guide_tree.py`
- Modify: `tests/test_guide_builder.py`

- [ ] **Step 1: Add tree builder tests**

Extend `tests/test_guide_tree.py`:

```python
from pathlib import Path

from coa_meta.builds import BuildConfig
from coa_meta.guide_builder import build_guide_site
from coa_meta.guide_tree import build_guide_tree, default_tree_levels
from coa_meta.reporting import MetaReportRunner, MetaRunConfig
from coa_meta.repository import TalentRepository

FIXTURES = Path(__file__).parent / "fixtures"


def test_default_tree_levels_include_report_level_and_key_breakpoints():
    assert default_tree_levels(13) == (10, 13, 20, 30, 40, 50, 60)


def test_build_guide_tree_uses_coordinates_edges_and_snapshots():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    nodes = tuple(repo.nodes_for_class("Testclass"))
    selected_ids = (201, 202)

    tree = build_guide_tree(
        repository=repo,
        class_name="Testclass",
        spec_name="Damage",
        build_rank=1,
        build_label="Direct damage loop",
        selected_node_ids=selected_ids,
        config=BuildConfig(class_name="Testclass", level=60, max_ae=26, max_te=25),
        spec_nodes=nodes,
    )

    assert tree.rows >= 1
    assert tree.cols >= 1
    assert any(edge.source_id == 201 for edge in tree.edges)
    assert any(snapshot.level == 60 for snapshot in tree.snapshots)
    assert {node.entry_id for node in tree.nodes if node.selected} >= set(selected_ids)
```

- [ ] **Step 2: Implement `default_tree_levels`**

Return sorted unique levels from `(10, 20, 30, 40, 50, 60, report_level)`, excluding values below 1.

- [ ] **Step 3: Implement `build_guide_tree`**

Signature:

```python
def build_guide_tree(
    *,
    repository: TalentRepository,
    class_name: str,
    spec_name: str,
    build_rank: int,
    build_label: str,
    selected_node_ids: tuple[int, ...],
    config: BuildConfig,
    spec_nodes: tuple[TalentNode, ...],
    levels: tuple[int, ...] | None = None,
) -> GuideTree:
    ...
```

Implementation requirements:

- Build a `BuildRules` instance for each snapshot level.
- Convert selected IDs to `SelectedRank(node_id, 1)` initially. If rank data is available from `BuildReport` later, preserve it.
- Validate the selected build for the report level.
- Compute `ae_spent`, `te_spent`, free IDs, valid/invalid issue codes, and gate reasons from `BuildValidationResult`.
- For each node:
  - Copy `row`, `col`, `node_type`, `max_rank`, costs, `required_ids`, `connected_node_ids`, `required_tab_ae`, `required_tab_te`, and availability confidence from `TalentNode`.
  - Set `selected`, `free`, `rank`, `tree_state`, and `gate_reasons`.
  - Preserve tooltip and asset fields already built by M1.10B by accepting an optional `guide_nodes_by_id` mapping if needed.
- Build edges from `connected_node_ids` and `required_ids`.
- Ignore edges whose target/source node is outside the rendered spec tree, but record a warning.

- [ ] **Step 4: Add availability classification helper**

In `coa_meta/guide_tree.py`:

```python
def classify_node_state(
    *,
    node: TalentNode,
    selected_ids: set[int],
    free_ids: set[int],
    available_ids: set[int],
    issues_by_node: dict[int, tuple[ValidationIssue, ...]],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    ...
```

Return `(state, human_reasons, issue_codes)`.

- [ ] **Step 5: Attach trees to guide specs**

Update `GuideBuildCard` with optional `tree: GuideTree | None`.

Update `build_guide_site()` so each build card receives a tree built from the report's selected node IDs and the spec's guide nodes.

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m pytest tests/test_guide_tree.py tests/test_guide_builder.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add coa_meta/guide_tree.py coa_meta/guide_builder.py coa_meta/guide_models.py tests/test_guide_tree.py tests/test_guide_builder.py
git commit -m "feat: build guide talent trees"
```

---

## Task 3: Render CoA-Style Static Talent Trees

**Files:**

- Modify: `coa_meta/guide_rendering.py`
- Modify: `tests/test_guide_rendering.py`

- [ ] **Step 1: Add rendering tests**

Extend `tests/test_guide_rendering.py`:

```python
def test_render_spec_html_includes_static_talent_tree():
    site = _site()
    spec = next(item for item in site.specs if item.spec_name == "Damage")

    html = render_spec_html(site, spec)

    assert 'class="talent-tree"' in html
    assert 'class="tree-links"' in html
    assert 'data-tree-level-selector' in html
    assert 'data-tree-node-id="201"' in html
    assert "AE" in html
    assert "TE" in html


def test_static_tree_javascript_has_no_network_calls():
    assert "fetch(" not in GUIDE_JS
    assert "XMLHttpRequest" not in GUIDE_JS
    assert "getBoundingClientRect" in GUIDE_JS
```

- [ ] **Step 2: Replace Talents placeholder**

In `render_spec_html()`, replace the M1.10C placeholder with a call to `_render_talent_tree_section(spec)`.

Render:

- Build selector if more than one build exists.
- Level selector using tree snapshots.
- Budget summary.
- Leveling path panel.
- One `.talent-tree` per build, with non-selected trees hidden.

- [ ] **Step 3: Render nodes**

For each tree node:

- Use `button` so hover/focus tooltips work with keyboard.
- Add `data-tooltip-id`.
- Add `data-tree-node-id`.
- Add `data-state`.
- Add `data-rank` and `data-max-rank`.
- Use CSS custom properties for grid placement:

```html
style="--node-col: 4; --node-row: 2"
```

CSS maps these to `grid-column` and `grid-row`.

- [ ] **Step 4: Render edges**

Render a blank SVG with serialized edge data:

```html
<svg class="tree-links" data-tree-edges='[...]' aria-hidden="true"></svg>
```

JavaScript draws lines from node geometry after layout.

- [ ] **Step 5: Add CSS states**

Update `GUIDE_CSS`:

- `.talent-tree`
- `.tree-links`
- `.tree-node`
- `.shape-circle`, `.shape-square`, `.shape-hex`
- `.is-selected`, `.is-free`, `.is-available`, `.is-gated`, `.is-over-budget`
- `.tree-toolbar`
- `.leveling-path`

The tree should use a horizontal scroll container on small screens instead of compressing below readable size.

- [ ] **Step 6: Add JS behavior**

Update `GUIDE_JS`:

- On DOMContentLoaded, initialize every `.guide-tree-panel`.
- Bind build and level selectors.
- Toggle active tree.
- Apply snapshot state classes to nodes.
- Update budget summary.
- Draw SVG lines using `getBoundingClientRect`.
- Recalculate on `resize`.

Keep JS self-contained and no-network.

- [ ] **Step 7: Run rendering tests**

Run:

```bash
python -m pytest tests/test_guide_rendering.py -q
```

Expected: pass.

- [ ] **Step 8: Full guide smoke test**

Run:

```bash
python -m pytest tests/test_guide_builder.py tests/test_guide_rendering.py tests/test_report_writers.py -q
```

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add coa_meta/guide_rendering.py tests/test_guide_rendering.py
git commit -m "feat: render static talent trees"
```

---

## Task 4: Playstyle Fingerprints, Distance, and Reliability

**Files:**

- Create: `coa_meta/build_diversity.py`
- Create: `tests/test_build_diversity.py`
- Modify: `coa_meta/guide_models.py` if report payload dataclasses live there

- [ ] **Step 1: Add tests**

Create `tests/test_build_diversity.py`:

```python
from __future__ import annotations

from pathlib import Path

from coa_meta.apl import APLAction, GeneratedAPL
from coa_meta.build_diversity import (
    build_playstyle_fingerprint,
    fingerprint_distance,
    reliability_label,
    reliability_score,
)
from coa_meta.repository import TalentRepository

FIXTURES = Path(__file__).parent / "fixtures"


def test_fingerprint_uses_selected_tags_and_apl_actions():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    nodes = [repo.node_by_id(201), repo.node_by_id(202)]
    apl = GeneratedAPL(
        profile_id="test",
        class_name="Testclass",
        spec_name="Damage",
        encounter="single_target",
        role="melee_dps",
        actions=(
            APLAction(
                action_key="damage_talent",
                name="Damage Talent",
                node_id=201,
                spell_id=2001,
                category="builder",
                condition="use when available",
                priority=1,
                confidence="high",
                notes=("selected ability",),
                evidence=tuple(),
            ),
        ),
        warnings=tuple(),
    )

    fp = build_playstyle_fingerprint(nodes=nodes, apl=apl, role="melee_dps")

    assert fp.active_count >= 1
    assert fp.apl_categories["builder"] == 1
    assert fp.label


def test_fingerprint_distance_separates_different_playstyles():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    node_a = repo.node_by_id(201)
    node_b = repo.node_by_id(203)

    fp_a = build_playstyle_fingerprint(nodes=[node_a], apl=None, role="melee_dps")
    fp_b = build_playstyle_fingerprint(nodes=[node_b], apl=None, role="healer")

    assert fingerprint_distance(fp_a, fp_b) > 0.20


def test_reliability_penalizes_missing_active_apl_actions():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    nodes = [repo.node_by_id(201)]

    score = reliability_score(nodes=nodes, apl=None, role="melee_dps", warnings=tuple())

    assert score < 0.85
    assert reliability_label(score) in {"medium", "low"}
```

- [ ] **Step 2: Implement dataclasses**

In `coa_meta/build_diversity.py`, add:

- `PlaystyleFingerprint`
- `SelectionReason`
- `BuildDiversityCandidate`

Each should expose `to_dict()`.

- [ ] **Step 3: Implement fingerprint extraction**

Function:

```python
def build_playstyle_fingerprint(
    *,
    nodes: Sequence[TalentNode],
    apl: GeneratedAPL | None,
    role: str,
) -> PlaystyleFingerprint:
    ...
```

Rules:

- Count tags, resources, schools, active/passive, cooldown, DoT, summon, heal, defensive, support, builder, spender, melee, ranged, caster.
- Pull APL categories from `apl.actions`.
- Use selected active ability names as high-signal features.
- Generate deterministic label from strongest evidence.

- [ ] **Step 4: Implement distance**

Function:

```python
def fingerprint_distance(left: PlaystyleFingerprint, right: PlaystyleFingerprint) -> float:
    ...
```

Use weighted Jaccard plus bounded numeric deltas as documented in the design.

- [ ] **Step 5: Implement reliability**

Functions:

```python
def reliability_score(
    *,
    nodes: Sequence[TalentNode],
    apl: GeneratedAPL | None,
    role: str,
    warnings: Sequence[str],
) -> float:
    ...

def reliability_label(score: float) -> str:
    ...
```

Start at 1.0, apply design penalties, clamp to `0.0..1.0`.

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_build_diversity.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add coa_meta/build_diversity.py tests/test_build_diversity.py
git commit -m "feat: model build playstyle diversity"
```

---

## Task 5: Core Rotation Loop Extraction

**Files:**

- Create: `coa_meta/rotation_loops.py`
- Create: `tests/test_rotation_loops.py`
- Modify: `coa_meta/guide_models.py` or reporting dataclasses as needed

- [ ] **Step 1: Add tests**

Create `tests/test_rotation_loops.py`:

```python
from __future__ import annotations

from coa_meta.apl import APLAction, GeneratedAPL
from coa_meta.rotation_loops import build_rotation_loop


def test_build_rotation_loop_translates_priority_actions_to_player_steps():
    apl = GeneratedAPL(
        profile_id="test",
        class_name="Testclass",
        spec_name="Damage",
        encounter="single_target",
        role="melee_dps",
        actions=(
            APLAction("keep_dot", "Venom Bite", 201, 2001, "maintenance", "if missing", 1, "high", tuple(), tuple()),
            APLAction("burst", "Shadow Frenzy", 202, 2002, "cooldown", "on cooldown", 2, "high", tuple(), tuple()),
            APLAction("builder", "Quick Strike", 203, 2003, "builder", "if resource low", 3, "medium", tuple(), tuple()),
            APLAction("spender", "Deadly Finish", 204, 2004, "spender", "if resource high", 4, "medium", tuple(), tuple()),
        ),
        warnings=tuple(),
    )

    loop = build_rotation_loop(apl=apl, selected_nodes=tuple(), role="melee_dps", encounter="single_target")

    assert loop.reliability_label in {"high", "medium"}
    assert any("Venom Bite" in step for step in loop.core_loop)
    assert loop.resource_rule


def test_healer_loop_uses_healing_language():
    apl = GeneratedAPL(
        profile_id="test",
        class_name="Testclass",
        spec_name="Mending",
        encounter="single_target",
        role="healer",
        actions=(
            APLAction("heal", "Renewing Light", 301, 3001, "heal", "when allies injured", 1, "high", tuple(), tuple()),
        ),
        warnings=tuple(),
    )

    loop = build_rotation_loop(apl=apl, selected_nodes=tuple(), role="healer", encounter="single_target")

    assert "healing" in loop.objective.lower() or "keep allies alive" in loop.objective.lower()
    assert loop.defensive_or_support
```

- [ ] **Step 2: Implement `RotationLoop` dataclass**

Fields:

- `schema_version`
- `objective`
- `opener`
- `core_loop`
- `cooldowns`
- `defensive_or_support`
- `resource_rule`
- `maintenance_rule`
- `reliability_label`
- `warnings`

- [ ] **Step 3: Implement `build_rotation_loop`**

Signature:

```python
def build_rotation_loop(
    *,
    apl: GeneratedAPL,
    selected_nodes: Sequence[TalentNode],
    role: str,
    encounter: str,
) -> RotationLoop:
    ...
```

Implementation:

- Group APL actions by category.
- Generate role objective.
- Add setup/maintenance actions first.
- Add builder/spender loop when both exist.
- Add cooldown actions as window notes.
- Add healer/tank/support actions to `defensive_or_support`.
- If no core loop can be found, fall back to highest-priority active actions and add `inferred_loop_low_confidence`.
- Use player-facing labels, not internal category headings.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_rotation_loops.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/rotation_loops.py tests/test_rotation_loops.py
git commit -m "feat: extract player-facing rotation loops"
```

---

## Task 6: Integrate Diverse Build Selection Into Report Runner

**Files:**

- Modify: `coa_meta/reporting.py`
- Modify: `coa_meta/build_diversity.py`
- Modify: `tests/test_meta_report_runner.py`
- Modify: `docs/data/meta-report-schema.md`

- [ ] **Step 1: Add report tests**

Extend `tests/test_meta_report_runner.py`:

```python
def test_meta_report_top_builds_include_playstyle_and_rotation_loop(tmp_path):
    report = MetaReportRunner(
        MetaRunConfig(
            entries_path=FIXTURES / "meta_report_fixture.jsonl",
            classes_path=FIXTURES / "meta_classes.json",
            class_names=("Testclass",),
            top=2,
            beam_width=4,
            branch_width=3,
            require_budget_fraction=0.0,
        )
    ).run()

    spec = report.spec_results[0]

    assert spec.top_builds
    assert spec.top_builds[0].playstyle_fingerprint["schema_version"] == "coa-build-playstyle-v1"
    assert spec.top_builds[0].selection_reason["schema_version"] == "coa-build-selection-v1"
    assert spec.top_builds[0].rotation_loop["schema_version"] == "coa-rotation-loop-v1"
```

Add a second test with synthetic candidates if fixture diversity is too small:

```python
def test_diverse_selector_prefers_different_reliable_builds():
    ...
```

- [ ] **Step 2: Implement performance band helper**

In `coa_meta/build_diversity.py`:

```python
def performance_band_floor(projected_indexes: Sequence[float], *, minimum_relative_floor: float = 0.90) -> tuple[float, tuple[str, ...]]:
    ...
```

Follow the design:

- Include best.
- Use MAD when at least six candidates exist.
- Relative floor no lower than `best * 0.90`.
- Return warnings when the band must widen.

- [ ] **Step 3: Implement selector**

In `coa_meta/build_diversity.py`:

```python
def select_diverse_builds(
    candidates: Sequence[BuildDiversityCandidate],
    *,
    top: int,
    minimum_distance: float = 0.22,
) -> tuple[BuildDiversityCandidate, ...]:
    ...
```

Rules:

- Pick best medium/high reliability candidate first.
- Fill remaining slots by maximizing normalized score, reliability, and minimum distance to selected builds.
- If no candidate clears the distance floor, select fewer or mark as a minor variation through `SelectionReason`.

- [ ] **Step 4: Modify `_run_scope` candidate handling**

In `MetaReportRunner._run_scope`:

1. Search with a larger display pool:

```python
candidate_limit = max(scope.top * 5, 12)
```

Use existing `beam_width` and branch behavior. Do not loosen legality.

2. Score all valid candidates.

3. For each candidate, generate APL before final slicing.

4. Build `PlaystyleFingerprint`, reliability score, reliability label, and `RotationLoop`.

5. Wrap each in `BuildDiversityCandidate`.

6. Call `select_diverse_builds`.

7. Create `BuildReport` rows from selected candidates and assign display ranks in selected order.

- [ ] **Step 5: Extend `BuildReport`**

Add fields with dict defaults:

- `playstyle_fingerprint: dict[str, Any]`
- `selection_reason: dict[str, Any]`
- `rotation_loop: dict[str, Any]`

Update `to_dict()`.

Keep `rotation_summary` unchanged for compatibility.

- [ ] **Step 6: Update schema docs**

In `docs/data/meta-report-schema.md`, document:

- `playstyle_fingerprint`
- `selection_reason`
- `rotation_loop`
- Backwards-compatible status of `rotation_summary`

- [ ] **Step 7: Run tests**

Run:

```bash
python -m pytest tests/test_build_diversity.py tests/test_rotation_loops.py tests/test_meta_report_runner.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add coa_meta/reporting.py coa_meta/build_diversity.py docs/data/meta-report-schema.md tests/test_meta_report_runner.py
git commit -m "feat: select diverse reliable builds"
```

---

## Task 7: Render Diverse Builds and Core Loops in Guide Pages

**Files:**

- Modify: `coa_meta/guide_builder.py`
- Modify: `coa_meta/guide_rendering.py`
- Modify: `tests/test_guide_builder.py`
- Modify: `tests/test_guide_rendering.py`
- Modify: `docs/README.md`

- [ ] **Step 1: Add guide tests**

Extend `tests/test_guide_builder.py`:

```python
def test_guide_build_cards_include_playstyle_metadata():
    site = _site()
    build = site.specs[0].builds[0]

    assert build.playstyle_label
    assert build.selection_reason
    assert build.rotation_loop
```

Extend `tests/test_guide_rendering.py`:

```python
def test_spec_html_renders_build_playstyle_and_core_loop():
    site = _site()
    spec = next(item for item in site.specs if item.spec_name == "Damage")

    html = render_spec_html(site, spec)

    assert "Recommended Builds" in html
    assert "Core Loop" in html
    assert "Early theorycraft picks" not in html
```

- [ ] **Step 2: Extend `GuideBuildCard`**

Add:

- `playstyle_label: str`
- `selection_reason: str`
- `performance_band: str`
- `reliability_label: str`
- `rotation_loop: dict[str, Any]`
- `tree: GuideTree | None`

Update `to_dict()`.

- [ ] **Step 3: Map report fields into guide cards**

In `guide_builder.py`, populate the new card fields from `BuildReport.to_dict()` output or dataclass fields.

Fallbacks:

- `playstyle_label`: existing card label.
- `selection_reason`: "Strongest current theorycraft result for this spec."
- `performance_band`: "top theorycraft band"
- `reliability_label`: confidence label mapped to high/medium/low where needed.
- `rotation_loop`: derive from existing `rotation_summary` only if M1.10D report fields are absent.

- [ ] **Step 4: Update Recommended Builds rendering**

Render each card with:

- Playstyle label as the primary title.
- Reliability badge.
- "Why this build" sentence.
- "View tree" link.
- Compact metric tooltip for projected index.
- Warning badge only when warnings exist.

- [ ] **Step 5: Update Rotation rendering**

Prefer `rotation_loop`.

Sections:

- Core Loop
- Opener and Setup, only when non-empty.
- Cooldowns, only when non-empty.
- Defensive, Healing, or Support Priorities, only when non-empty.
- Reliability Note

Fallback to current `rotation_summary` if needed.

- [ ] **Step 6: Update docs**

In `docs/README.md`, update M1.10 static guide description to include:

- Static talent trees.
- Level snapshots.
- Diverse recommended builds.
- Core rotation loops.

- [ ] **Step 7: Run guide tests**

Run:

```bash
python -m pytest tests/test_guide_builder.py tests/test_guide_rendering.py tests/test_report_writers.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add coa_meta/guide_builder.py coa_meta/guide_models.py coa_meta/guide_rendering.py docs/README.md tests/test_guide_builder.py tests/test_guide_rendering.py
git commit -m "feat: show diverse builds in guide pages"
```

---

## Task 8: End-to-End Verification and Docs Cleanup

**Files:**

- Modify as needed: `docs/ROADMAP.md`
- Modify as needed: `docs/superpowers/specs/2026-07-05-m1-10-guide-site-report-ux-design.md`

- [ ] **Step 1: Run focused unit suite**

Run:

```bash
python -m pytest tests/test_guide_tree.py tests/test_build_diversity.py tests/test_rotation_loops.py tests/test_guide_builder.py tests/test_guide_rendering.py tests/test_meta_report_runner.py tests/test_report_writers.py -q
```

Expected: pass.

- [ ] **Step 2: Run full package suite**

Run:

```bash
python -m pytest -q
```

Expected: pass.

- [ ] **Step 3: Generate a smoke report**

Run:

```bash
python -m coa_meta meta \
  --entries coa_scraper/dist/coa_entries.jsonl \
  --classes coa_scraper/dist/coa_classes.json \
  --db-tooltips coa_scraper/dist/coa_db_spell_tooltips.jsonl \
  --out reports/meta-m1-10-cd-smoke \
  --format json --format html \
  --class Venomancer \
  --top 3
```

Expected:

- `reports/meta-m1-10-cd-smoke/index.html`
- `reports/meta-m1-10-cd-smoke/specs/*.html`
- JSON top builds include `playstyle_fingerprint`, `selection_reason`, and `rotation_loop`.
- Spec HTML includes `.talent-tree`, level selector, and "Core Loop".

- [ ] **Step 4: Inspect smoke output without committing generated reports**

Run:

```bash
rg -n "talent-tree|Core Loop|coa-build-playstyle-v1|coa-rotation-loop-v1" reports/meta-m1-10-cd-smoke
```

Expected: all markers present.

Do not stage generated `reports/` files unless the user explicitly asks for committed sample output.

- [ ] **Step 5: Update roadmap status**

After implementation passes, update:

- `docs/ROADMAP.md`: M1.10C/D complete, M1.10E/F still planned.
- `docs/superpowers/specs/2026-07-05-m1-10-guide-site-report-ux-design.md`: implementation status and links.

- [ ] **Step 6: Final commit**

```bash
git add docs/ROADMAP.md docs/superpowers/specs/2026-07-05-m1-10-guide-site-report-ux-design.md
git commit -m "docs: mark m1.10 tree diversity progress"
```

---

## Manual QA Checklist

- [ ] Tree nodes do not overlap at desktop widths.
- [ ] Tree remains readable on mobile by horizontal scrolling, not by crushing icons.
- [ ] Tooltips work on hover and keyboard focus.
- [ ] AscensionDB links still point to `https://db.ascension.gg/?spell=<id>`.
- [ ] Warnings section remains hidden when empty.
- [ ] Build cards explain why each build is recommended in player-facing language.
- [ ] Top recommended builds are not all identical unless the candidate pool truly lacks diversity.
- [ ] Rotation section describes a core loop rather than only "Maintenance", "Cooldowns", and "Builder/Spender" buckets.
- [ ] JSON remains backwards-compatible for existing consumers that read `rotation_summary`.

## Rollback Plan

If tree rendering causes layout failures late in implementation, keep the data model and report fields but gate the visual tree behind a simple list renderer. Do not revert build diversity unless report tests prove the selector is invalid.

If diversity selection reduces report coverage for sparse specs, fall back to raw score ordering for that spec and emit a `diversity_selection_insufficient_candidates` warning.
