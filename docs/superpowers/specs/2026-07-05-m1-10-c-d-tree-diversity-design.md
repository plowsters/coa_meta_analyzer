# M1.10C/D Talent Tree Renderer and Build Diversity Design

Date: 2026-07-05

Status: ready for implementation planning

## Goal

M1.10C and M1.10D complete the next guide-site slice after M1.10A/B. The output should let a player open a spec guide, see the recommended build in a CoA-style tree, understand when talents become available while leveling, and compare two or three strong builds that play differently instead of only seeing the highest projected index rows.

M1.10C covers the static talent tree renderer.

M1.10D covers build diversity, playstyle labeling, and core rotation loop extraction.

These should be implemented together because the same selected nodes, APL actions, levels, costs, prerequisites, and tags determine both the tree state and the explanation for why a build is recommended.

## Research Summary

### Local Data Shape

The current Vol'Jin Alpha normalized artifact is suitable for a lightweight static tree renderer:

- `coa_scraper/dist/coa_entries.jsonl` has 3612 normalized entries.
- Tree placement spans rows `0..9` and columns `0..10`.
- Node ranks are mostly single-rank: 3313 records have `max_rank=1`, 280 have `max_rank=2`, and 19 have `max_rank=3`.
- Node shape data is available: 2834 `SpendCircle`, 773 `SpendSquare`, and 5 `SpendHex` records.
- Prerequisite and connection data exists: 124 records include `required_ids`, and 3404 include `connected_node_ids`.
- Effective level confidence is mixed: 329 high, 42 medium, and 3241 low in the current artifact. The tree must show level-aware advice but remain clear that many level gates are inferred or source-limited.
- Largest spec tabs have about 43-46 nodes, so a single spec tree can be rendered as static HTML/SVG without a heavy app framework.

The current implementation already has the right extension points:

- `coa_meta.guide_models.GuideNode` carries player-facing node identity, cost, tooltip, asset, and DB link fields, but does not yet carry row, column, rank, gate, prerequisite, or connection state.
- `coa_meta.builds.BuildRules` is the canonical legality engine for level, AE/TE budget, tab AE/TE gates, required nodes, free closure, and rank validation.
- `coa_meta.reporting.MetaReportRunner._run_scope` currently sorts scored candidates by projected index and slices the top N. This is the right insertion point for M1.10D diverse build selection.
- `coa_meta.apl.GeneratedAPL` and `APLAction` already separate actions, categories, conditions, evidence, and confidence. This is enough to derive a player-facing core loop without claiming final simulated rotation accuracy.

### Guide Reference Patterns

The target should borrow information architecture, not visual identity:

- Icy Veins presents class/spec pages with guide navigation, overview, talents, rotation, gear, stats, and update metadata.
- Wowhead emphasizes overview-first pages, quick cheat-sheet style sections, spell links, stat guidance, rotation, talents, consumables, and gearing.
- Archon emphasizes data context, content filters, jump links, stats, recommended talent builds, alternate builds, and log-backed metadata.
- Method uses compact guide navigation and player-facing playstyle explanations, including role-specific descriptions such as healer ramp windows and dungeon cadence.

Those patterns support the user's requested direction: individual spec pages should feel like guide pages, while CoA Meta Analyzer metrics should be hidden behind explanatory tooltips.

### Browser and Frontend Constraints

GitHub Pages favors static files. C/D should not introduce a runtime backend, build-time network dependency, or large client framework.

CSS Grid is appropriate for row/column talent placement because the normalized artifact already provides discrete row and column coordinates. SVG is appropriate for connectors because straight `<line>` elements can connect node centers, and `<path>` can support later curved or stepped connectors if needed. The tree should be readable without JavaScript; JavaScript should only improve build switching, level snapshots, and tooltips.

### Rotation Research

SimulationCraft's action list model is still the right conceptual anchor for this project: actions are priority lists evaluated from top to bottom, named sub-lists can group behavior, and sequence blocks can model explicit ordered bursts. M1.10D should not build a full simulator. It should translate the generated priority list into player language:

- What do I keep up?
- What do I press to set up?
- What is my repeating loop?
- When do I spend?
- What cooldown window matters?
- What changes for tank, healer, or support roles?

## Product Requirements

### M1.10C Player Outcome

On each spec guide page, the Talents section should show:

- A CoA-style tree for each recommended build.
- Node icons, rank badges, AE/TE cost chips, and shape styling based on `node_type`.
- Selected, free, available, gated, and illegal states.
- Lines between connected nodes.
- Tooltips on hover/focus, using the M1.10B tooltip catalog and AscensionDB hotlinks.
- A level selector for meaningful levels, at minimum 10, 20, 30, 40, 50, and 60, plus the exact report level when it differs.
- AE/TE budget totals and tab gate feedback for the selected level.
- A "leveling path" ordering that tells players when to take selected abilities and talents when source confidence allows it.
- A no-JS fallback that renders the level-60 selected build.

### M1.10D Player Outcome

In Recommended Builds and Rotation, the guide should show:

- Two or three recommended builds chosen for strong output, reliable loop quality, and distinct playstyle.
- A concise label for each build, such as "poison DoT loop", "pet setup window", "burst cooldown cycle", "defensive sustain", "aura support", or "direct-damage spender".
- A plain-language reason why the build was selected.
- A performance band note, such as "within the top theorycraft band" rather than exposing raw algorithm thresholds.
- A core loop for the selected build, not only action categories.
- Role-specific rotation language:
  - `melee_dps`: uptime, builders, spenders, cooldown windows, cleave/AoE notes.
  - `caster_dps`: casts, DoTs, procs, spenders, cooldown windows, movement caveats.
  - `tank`: mitigation cadence, resource stability, defensive cooldowns, threat/DPS filler.
  - `healer`: maintenance healing, ramp or burst healing, emergency buttons, damage weave where supported.
  - `support`: aura/buff uptime, debuff coverage, group cooldown timing, filler loop.
- Reliability notes that separate "clear repeatable loop" from "early inferred loop".

## Data Model Design

### Guide Tree Records

Extend `GuideNode` rather than creating a parallel node record that loses tooltip and asset integration.

Add fields:

```text
row: int
col: int
node_type: str
max_rank: int
rank: int
selected: bool
free: bool
required_ids: tuple[int, ...]
connected_node_ids: tuple[int, ...]
required_tab_ae: int
required_tab_te: int
availability_confidence: str
source_level: int | None
tooltip_required_level: int | None
tree_state: str
gate_reasons: tuple[str, ...]
```

Add tree-level records:

```text
GuideTree
  tree_id: str
  class_name: str
  spec_name: str
  build_rank: int
  build_label: str
  level: int
  max_ae: int
  max_te: int
  ae_spent: int
  te_spent: int
  rows: int
  cols: int
  nodes: tuple[GuideNode, ...]
  edges: tuple[GuideTreeEdge, ...]
  snapshots: tuple[GuideTreeSnapshot, ...]
  warnings: tuple[str, ...]

GuideTreeEdge
  source_id: int
  target_id: int
  kind: "connection" | "requirement"
  state: "selected" | "available" | "gated" | "inactive"

GuideTreeSnapshot
  level: int
  max_ae: int
  max_te: int
  ae_spent: int
  te_spent: int
  selected_node_ids: tuple[int, ...]
  free_node_ids: tuple[int, ...]
  available_node_ids: tuple[int, ...]
  gated_nodes: tuple[GuideNodeGate, ...]
```

`GuideTreeSnapshot` should be precomputed in Python. Client JavaScript can switch snapshots by toggling data attributes; it should not reimplement `BuildRules`.

### Node States

Use stable state names for CSS and tests:

- `selected`: chosen by the displayed build at the displayed level.
- `free`: zero-cost closure selected by rules.
- `available`: legal to add under the displayed level and budgets.
- `gated_level`: blocked by required level.
- `gated_tab_ae`: blocked by ability essence invested in the tab.
- `gated_tab_te`: blocked by talent essence invested in the tab.
- `gated_required_node`: blocked by a missing prerequisite node.
- `over_budget`: part of the final build but not legal at the displayed level or budget.
- `inactive`: valid node in the tree but neither selected nor immediately available.

If multiple gates apply, `tree_state` should hold the most player-actionable state and `gate_reasons` should carry every reason.

### Build Diversity Records

Add a playstyle payload to `BuildReport`:

```text
playstyle_fingerprint:
  schema_version: "coa-build-playstyle-v1"
  label: str
  primary_tags: list[str]
  active_ability_names: list[str]
  passive_ratio: float
  active_count: int
  cooldown_count: int
  dot_count: int
  summon_count: int
  heal_count: int
  defensive_count: int
  support_count: int
  melee_score: float
  ranged_score: float
  caster_score: float
  schools: dict[str, int]
  resources: dict[str, int]
  apl_categories: dict[str, int]
  selected_node_ids: list[int]

selection_reason:
  schema_version: "coa-build-selection-v1"
  performance_band: str
  reliability_label: "high" | "medium" | "low"
  diversity_label: str
  reason: str
  compared_to_rank_1: str | None

rotation_loop:
  schema_version: "coa-rotation-loop-v1"
  objective: str
  opener: list[str]
  core_loop: list[str]
  cooldowns: list[str]
  defensive_or_support: list[str]
  resource_rule: str | None
  maintenance_rule: str | None
  reliability_label: "high" | "medium" | "low"
  warnings: list[str]
```

Keep the current `rotation_summary` field during migration so existing tests and consumers do not break. The HTML guide should prefer `rotation_loop` when present.

## M1.10C Architecture

### Python Layer

Create `coa_meta/guide_tree.py`.

Responsibilities:

- Convert a `GuideBuildCard` and spec nodes into a `GuideTree`.
- Use `BuildRules` to validate the full build and each level snapshot.
- Compute free closure and available/gated states from canonical legality rules.
- Build edges from `connected_node_ids` and `required_ids`.
- Preserve tooltip IDs and asset records from M1.10B.
- Emit warnings when row/column, node type, or edge references are missing.

Do not duplicate legality rules in the renderer. If a tree state needs legality knowledge, it should call `BuildRules`.

### Rendering Layer

Modify `coa_meta/guide_rendering.py`.

HTML structure:

```html
<section id="talents" class="guide-section">
  <div class="tree-toolbar">
    <select data-tree-build-selector>...</select>
    <select data-tree-level-selector>...</select>
    <span data-tree-budget-summary>AE 26/26 - TE 25/25</span>
  </div>
  <div class="talent-tree" data-tree-id="venomancer-stalking-1" style="--tree-cols: 11; --tree-rows: 10">
    <svg class="tree-links" aria-hidden="true">...</svg>
    <button class="tree-node is-selected shape-circle" style="grid-column: 4; grid-row: 2" ...>...</button>
  </div>
</section>
```

CSS:

- Use CSS Grid for node placement.
- Use an absolutely positioned SVG layer for connectors.
- Use fel/void state colors:
  - selected: fel green glow.
  - free: softer green/teal tint.
  - available: purple rim.
  - gated: desaturated violet with lock/chip.
  - over budget: amber warning rim.
- Preserve mobile readability by letting the tree scroll horizontally inside a bounded section rather than squeezing nodes until tooltips and icons become unusable.

JavaScript:

- Toggle visible build and level snapshot.
- Update node classes, rank badges, budget text, and gate chips from precomputed JSON embedded in the page.
- Draw or update SVG lines by reading node center positions with `getBoundingClientRect`.
- Recalculate connectors on resize.
- Make no network requests.

### Leveling Path

The tree should include a simple "take order" panel:

1. Sort selected nodes by effective required level.
2. Break ties by row, column, essence kind, then name.
3. Mark low-confidence levels with a compact warning chip.
4. If the source level is unknown or low-confidence, say "available once prerequisites and essence gates are met" instead of inventing exact level advice.

This avoids overclaiming while still organizing build advice around what players can choose first.

## M1.10D Architecture

### Candidate Pool

`MetaReportRunner._run_scope` should request more candidates than it displays. It already does this by searching up to a multiple of `scope.top`; D should formalize the behavior:

- Generate at least `max(scope.top * 5, 12)` raw candidates when feasible.
- Score all valid candidates with `TheoryScorer`.
- Build APL and loop/fingerprint data for the eligible pool, not only the displayed rows.
- Apply diversity selection to choose the display set.

### Performance Band

The band should keep the recommendation competitive without pretending the top decimal place is meaningful.

Use a robust threshold:

- Always include the highest projected candidate.
- If there are at least six scored candidates, compute the median absolute deviation of projected indexes and set the floor to `best - max(1.5 * MAD, best * 0.05)`.
- Also enforce a relative floor of `best * 0.90` so diversity does not select a much weaker build only because it looks different.
- If fewer than `scope.top` candidates survive, widen to `best * 0.88` and record a `wide_performance_band` warning.

The HTML should not expose the exact math by default. It can say "within the top theorycraft band" and put details in a metric tooltip.

### Reliability Score

Reliability is not complexity. A complex build can be reliable if its loop is clear; a simple build can be unreliable if it has no explicit active abilities or depends on weak tag inference.

Start with 1.0 and apply penalties:

- `-0.20` when the generated APL has no selected active ability as an action.
- `-0.15` when the loop lacks a role-appropriate core action. For example, no mitigation/healing/support action for non-DPS roles.
- `-0.10` when more than half of APL actions are low-confidence.
- `-0.10` when the build has no explicit spender or no explicit cooldown where the selected tags strongly imply one.
- `-0.10` when warnings include missing role, missing level, or missing tooltip source issues that affect selected nodes.

Clamp to `0..1` and label:

- `high`: `>= 0.75`
- `medium`: `>= 0.50`
- `low`: below `0.50`

Low reliability does not automatically disqualify a candidate, but the selector should prefer medium/high reliability for the guide's top two or three builds.

### Fingerprint and Distance

Create `coa_meta/build_diversity.py`.

Fingerprint inputs:

- Selected node tags and normalized tags.
- Active/passive ratio.
- APL action categories and confidence.
- Named active ability highlights.
- Damage schools and resources.
- Counts for DoT, cooldown, summon, heal, defensive, support, builder, spender, melee, ranged, caster.
- Role and encounter.

Distance:

- Use weighted Jaccard distance for categorical sets.
- Add bounded numeric deltas for count fields.
- Weight high-signal player-facing differences higher than generic tags:
  - `0.30` active ability overlap.
  - `0.25` primary tag overlap.
  - `0.15` APL category overlap.
  - `0.10` school/resource overlap.
  - `0.10` active/passive and cooldown/dot/summon deltas.
  - `0.10` role-specific deltas.

Selection:

1. Pick the highest-scoring candidate with at least medium reliability. If none exist, pick the best candidate and warn.
2. For each remaining slot, choose the candidate in the performance band that maximizes:
   - projected index normalized against best candidate.
   - reliability.
   - minimum distance from already selected builds.
3. Require a minimum distance of `0.22` when possible.
4. If no candidate clears the distance floor, keep fewer builds or label the later build as a "minor variation" rather than pretending it is distinct.

### Playstyle Labels

Generate labels from strongest fingerprint features:

- `poison`/`venom` + `dot`: "poison DoT loop"
- `summon`/`pet`: "pet setup window"
- `cooldown` + `burst`: "burst cooldown cycle"
- `defensive`/`tank`: "defensive sustain"
- `heal` + `hot`/`atonement-like` tags: "healing ramp"
- `support`/`aura`/`buff`: "support uptime"
- `builder` + `spender`: "builder-spender loop"
- `ranged` + `proc`: "ranged proc loop"
- fallback: `<primary tag> build`

Labels must be deterministic and backed by selected node evidence. If a label comes from weak inference, add a low-confidence note.

### Core Loop Extraction

Create `coa_meta/rotation_loops.py`.

Inputs:

- `GeneratedAPL`
- selected `TalentNode` list
- role
- encounter
- scoring confidence/warnings

Output:

- `opener`: first-use setup and cooldowns.
- `core_loop`: repeatable priority cadence in three to six player-facing steps.
- `cooldowns`: major cooldowns and timing notes.
- `defensive_or_support`: role-specific mitigation, healing, or group support priorities.
- `resource_rule`: builder/spender or overcap prevention rule.
- `maintenance_rule`: DoT, buff, debuff, or aura upkeep rule.
- `reliability_label` and warnings.

The loop extractor should preserve the APL's priority semantics but avoid exposing internal category names. For example:

- "Keep Poisoned Blades active on your main target."
- "Build with quick melee strikes until your spender is ready."
- "Spend before you overcap, or during your cooldown window."
- "Use your main summon before the damage window if the build includes pet setup."

Avoid claiming exact DPS, HPS, or mitigation order until Phase 2 logs and Phase 3 simulation can validate timings.

## Schema and Documentation Impact

Update during implementation:

- `docs/data/meta-report-schema.md`: add `playstyle_fingerprint`, `selection_reason`, `rotation_loop`, and guide tree payload notes.
- `docs/README.md`: document that the guide site now includes tree snapshots and diverse recommended builds.
- `docs/ROADMAP.md`: mark M1.10C/D complete after implementation and keep E/F as follow-ups.
- `docs/superpowers/specs/2026-07-05-m1-10-guide-site-report-ux-design.md`: link this detailed C/D design.

## Risks and Mitigations

- **Risk: source level confidence is low for most records.** Mitigation: show exact levels only when confidence is high/medium, otherwise phrase guidance around prerequisites and essence gates.
- **Risk: tree legality diverges from optimizer legality.** Mitigation: compute snapshots through `BuildRules`, not JavaScript reimplementation.
- **Risk: SVG connectors drift on resize.** Mitigation: recompute from DOM geometry on load and resize; preserve no-JS tree even if connectors fail.
- **Risk: diverse selection picks a weaker build for novelty.** Mitigation: enforce performance band and reliability floor, and label minor variations honestly.
- **Risk: rotation loops overstate confidence.** Mitigation: emit reliability labels and warnings; keep the raw APL available in data notes.

## References

- Icy Veins Outlaw Rogue guide: `https://www.icy-veins.com/wow/outlaw-rogue-pve-dps-guide`
- Wowhead Demonology Warlock guide: `https://www.wowhead.com/guide/classes/warlock/demonology/overview-pve-dps`
- Archon Brewmaster Monk Mythic+ build: `https://www.archon.gg/wow/builds/brewmaster/monk/mythic-plus/overview/10/all-dungeons/this-week`
- Method Discipline Priest guide: `https://www.method.gg/guides/discipline-priest`
- SimulationCraft ActionLists: `https://github.com/simulationcraft/simc/wiki/ActionLists`
- MDN CSS Grid layout: `https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout`
- MDN SVG basic shapes: `https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorials/SVG_from_scratch/Basic_shapes`
- MDN `getBoundingClientRect`: `https://developer.mozilla.org/en-US/docs/Web/API/Element/getBoundingClientRect`
