# M1.12–M1.20 Public-Release and Systems-Correctness Roadmap Design

## Purpose

This document delineates the Phase 1 continuation milestones (M1.12 through M1.20) that take
CoA Meta Analyzer from its current M1.11 first-pass state to a public GitHub Pages resource whose
numbers are defensible because they model the actual in-game systems that drive player power in
World of Warcraft.

It captures preliminary findings, the strategic decisions made during brainstorming, the full
milestone decomposition, and cross-cutting principles. Two of these milestones — M1.12 and M1.14 —
have their own detailed design specs and implementation plans. The rest are delineated here at
scope/dependency granularity and will get their own specs when they are next in line.

## Motivating Problems

Three problems drive this roadmap.

1. **The canonical enrichment source (db.ascension.gg) is stale.** Spell IDs can be shared between
   the CoA Builder and db.ascension.gg while the DB title/description reflect an older version of
   the spell. Example: spell `805775` renders as *Adrenal Venom* (current) in the CoA Builder and
   the live client, but db.ascension.gg still returns *Fang Venom: Lifeblood* (outdated). The DB is
   easy to consume but cannot be trusted as canonical.

2. **The calculators do not model WoW's power systems.** The current scoring/simulation is a
   keyword-and-constant heuristic: damage amounts are hardcoded constants
   (`simulation.py::_estimated_amount`), stats never feed damage or resource regen, GCD is a fixed
   1500 ms, energy regen and haste interactions are absent, and build labels are produced by keyword
   matching (`build_diversity.py::_label_from_features`, which is why nearly every build is a
   "DoT/Poison loop"). A tool that presents authoritative-looking numbers from a mechanically hollow
   model is worse than no tool, because it looks trustworthy while being wrong.

3. **The tool is about to become a public resource** and still has visible correctness/UX gaps:
   two-letter ability abbreviations instead of icons, a role filter that works by deselection, a
   leveling path that skips levels and repeats boilerplate, builds that leave essence unspent, and
   no handling of mutually exclusive (shared-node) talents.

## Strategic Decisions

These were resolved during brainstorming and constrain every milestone below.

1. **Milestone sequencing.** M1.12 is pure UI quick fixes (no engine/data changes). M1.13 is a
   fel/void site redesign sourced from Claude Design (assets supplied later in an uncommitted
   project-root folder). M1.14 is the client data foundation. Talent-tree correctness follows, then
   the analytical engine, then rotation/gear/selection, then public-resource hardening.

2. **Primary authoritative source: the WoW client.** As much mechanical and systems data as possible
   is extracted directly from the local Ascension CoA client (MPQ→DBC plus `Data/Content/*.json`).
   The existing CoA Builder pipeline is *not* replaced wholesale; it stays authoritative for the
   talent graph, legality, and node descriptions. The client is layered on additively as the
   authoritative source for mechanical fields and systems constants.

3. **CoA attribution must be client-native.** We must confidently attribute client data to CoA
   (versus Area-52 and Warcraft Reborn/Bronzebeard, which share the install) using signals derived
   from the client itself — primarily archive-family membership, plus ID range and
   specialization/skill-line markers. The CoA Builder payload is used only as a cross-validation
   oracle to measure the attribution heuristic's precision/recall. It is never a whitelist gate,
   because (a) that would silently make the Builder canonical over the client, (b) it would discard
   the richer client-only data the Builder never exposed, and (c) the Builder can drift or go
   offline at any time.

4. **Modeling depth: deterministic analytical model, not a full simulator yet.** Phase 1 builds a
   deterministic analytical player-power model (rating→% conversions at level, coefficient-based
   per-cast damage/heal, haste→GCD/resource-regen, crit/hit/expertise/armor, DoT/HoT). It feeds
   scoring and priority-based rotation output and is labeled as projection. The full event-driven
   Monte-Carlo simulator remains Phase 3. The modeling core is split: the *inputs* (mechanical
   fields, GameTable conversion primitives, base resource/regen constants) are delivered by the data
   foundation milestone (M1.14); the *engine* that consumes them is its own milestone (M1.16), with
   tree-correctness (M1.15) sitting cleanly between them.

5. **Client is the primary source; changelog and API are secondary.** The Ascension changelog
   (`ascension.gg/en/changelog/4`, a Next.js app of natural-language deltas) is a currency/
   verification signal, not a primary structured parser. The `data.project-ascension.com` / db
   `&power` API endpoints are probed as a convenience source but are not trusted for currency until
   verified.

## Client Findings (preliminary)

From inspecting `…/ascension-live/Data/`:

- **Archive-family partitioning is a strong CoA attribution signal.** `patch-C*` (C, CA…CZ, CZZ — a
  dozen-plus archives dated the day of inspection) map to **C**onquest of Azeroth; `Data/area-52/
  patch-D.MPQ` is Area-52, physically segregated; `patch-W*` (WA, WB, WC…) map to Warcraft
  Reborn/Bronzebeard. Base game is `common/expansion/lichking/patch(-2/-3)`.
- **The client ships two data tiers.** MPQ→DBC (`DBFilesClient/*.dbc` for spells, cast times,
  durations, ranges, icons, and GameTables) **and** `Data/Content/*.json` — structured
  Ascension-specific data including `SpellRankData.json`, `SpellToStatSuggestionData.json`,
  `SpellToRoleSuggestionData.json`, `SpellToSpellSuggestionData.json`,
  `EnchantmentToStatSuggestionData.json`, `ItemVariationData.json`, and
  `CharacterAdvancementData.json` (7.8 MB). Some of this (`SpellToStat/RoleSuggestion`, `SpellRank`)
  is directly relevant to stat-interaction and role modeling; `CharacterAdvancementData` may be the
  classless/Area-52 system and must be attributed before use.
- **MPQ load order matters.** Later patch archives override earlier ones, so extraction must read the
  *effective* (latest CoA) record, not a stale base copy.
- **Custom numbers and item stats are partly server-side.** Client DBC gives the mechanical skeleton
  (cast time, cost, cooldown, school, coefficients, base points, duration, range) but heavily
  scripted custom scaling and proc values, and item stats (3.3.5 `item_template`), are server-side.
  `Extensions.dll`/`MemoryBridge.log` suggest a memory bridge that could later read live-computed
  values — investigated as a spike in M1.14, not solved there.

Sources:

- Ascension changelog structure: <https://ascension.gg/en/changelog/4>
- Ascension DB / spell tooltip endpoints: <https://db.ascension.gg/>, `data.project-ascension.com/api/spells/{id}/tooltip.html`
- MPQ/DBC tooling: StormLib <http://www.zezula.net/en/mpq/download.html>, pyStormLib, pywowlib, dawidcxx/wow-file-tools, stoneharry/WoW-Spell-Editor

## Milestone Decomposition

| # | Milestone | Purpose | Depends on |
|---|-----------|---------|------------|
| **1.12** | Public-Release UI Quick Fixes | Ship a clean, correct-looking public site: icons everywhere, new disclaimer, GitHub header link, footer, select-to-include role filter, remove leveling-path boilerplate. No engine/data changes. | — |
| **1.13** | Fel/Void Site Redesign | Integrate the Claude Design fel/void redesign (assets supplied later, uncommitted). M1.12 wiring is inherited and restyled. | 1.12 |
| **1.14** | Client DBC Data Foundation | Extract authoritative mechanical spell data + WoW conversion primitives from the CoA client (MPQ→DBC and `Data/Content/*.json`); client-native CoA attribution; sunset stale db mechanical enrichment; audit the test suite; spike memory-bridge/API. | — |
| **1.15** | Talent-Tree Correctness | Full AE/TE essence spend to target level; granular 10–60 level slider; consistent level-gating across all sections; mutually exclusive shared-node choices; leveling path never skips a level. | 1.12 |
| **1.16** | Analytical Player-Power Model | The engine: rating→% at level, coefficient-based per-cast damage/heal, haste→GCD & resource regen, crit/hit/expertise/armor, DoT/HoT. Rewire scoring + rotation sim to consume real numbers. | 1.14, 1.15 |
| **1.17** | Rotation Quality | Derive true core loops (small optimal subset) from the model; build-archetype taxonomy beyond "DoT loop"; concise opener/priority/CD/role sections. | 1.16 |
| **1.18** | Gear/Stat Interaction & Breakpoints | Model-derived stat weights per level; haste/other breakpoints that flip build ranking; leveling stat scaling (Worldforged/level-scaled); item stat sourcing where AtlasLoot lacks Ascension gear. | 1.16 |
| **1.19** | Multi-Build Selection Re-tune | Revisit the "too strict" performance-band/diversity selection now that model-backed scores exist; select genuinely distinct viable playstyles. | 1.17, 1.18 |
| **1.20** | Public-Resource Hardening | GitHub Pages deploy pipeline, CI, regression snapshots, changelog-as-currency drift verification, contribution docs. | 1.12–1.19 |

### Per-milestone notes

- **M1.12** and **M1.14** have detailed specs:
  [M1.12 UI Quick Fixes](2026-07-06-m1-12-public-release-ui-quick-fixes-design.md),
  [M1.14 Client DBC Data Foundation](2026-07-06-m1-14-client-dbc-data-foundation-design.md).
- **M1.13** is externally sourced (Claude Design). This roadmap only reserves the number and requires
  that M1.12 be implemented as durable behavior/content so the redesign inherits wiring rather than
  throwaway styling.
- **M1.15** owns the correctness items deferred out of M1.12: builds must spend the full essence
  budget at the target level (fixing the observed TE 6/25 under-spend), the leveling path must show
  every level 10–60 with a concrete pick (no silent `deferred` skips), and mutually exclusive
  talents that share a physical node (e.g. Venomancer *Mamba Mentality* vs *Celerity*; Ancestry
  Barbarian choice passives) must be modeled as choose-one groups in the normalized schema,
  legality, and renderer.
- **M1.16** is the modeling engine. It consumes M1.14's `coa-client-spell-v1` and
  `coa-wow-constants-v1` artifacts and M1.15's corrected build/level state. It replaces hardcoded
  damage constants and static stat weights with formula-based projections.
- **M1.17–M1.19** progressively make rotations, gear/stat guidance, and build selection reflect the
  model instead of keyword heuristics.
- **M1.20** makes the project sustainable and publishable.

## Cross-Cutting Principles

- **Additive, not destructive.** The Builder graph pipeline and normalized artifacts remain. New
  client-sourced data is layered with provenance and confidence; existing consumers keep working.
- **Provenance and attribution on every record.** Every client-sourced field records its source
  archive/DBC/JSON, extraction date, client build, CoA-attribution confidence, and schema-match
  confidence (extends Decision 10).
- **Capture is isolated from analysis.** MPQ/DBC/JSON extraction lives in a dedicated capture module;
  the optimizer never reads client archives (extends Decision 3).
- **Tests must assert intended behavior, not incidental output.** The recent tooltip HTML-escaping
  regression (commit `84ad112`) is the canonical example of a test locking in wrong behavior. M1.14
  includes a test-suite integrity audit, and every modeling milestone tests formulas against known
  WotLK reference values.
- **Honest labeling.** All Phase 1 output stays labeled as theorycraft projection. Raw DPS is never
  claimed without empirical logs (Phase 2) or the Phase 3 simulator.
- **Redistribution boundary.** Extracting from the user's own client for derived data is in scope;
  redistributing client asset files (icons, art) via the public site is not — the site hotlinks or
  uses permissibly sourced assets.

## Non-Goals for This Phase

- Full event-driven Monte-Carlo simulation (Phase 3).
- Empirical log calibration and AscensionLogs ingestion (Phase 2).
- BiS gear optimization and full item ranking (a later, level-60-only effort; M1.18 handles
  stat-driven leveling behavior, not BiS search).
- Account-specific pathing from a partially leveled character.
