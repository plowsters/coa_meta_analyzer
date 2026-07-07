# M1.14 Client DBC Data Foundation Design

## Purpose

M1.14 establishes the local Ascension CoA game client as the authoritative source for mechanical
spell data and WoW systems constants. It extracts that data from the client's MPQ→DBC files and
`Data/Content/*.json` tier, attributes it to CoA using client-native heuristics, reconciles it with
the existing normalized Builder pipeline, and sunsets the stale db.ascension.gg mechanical
enrichment. It also delivers the "modeling inputs" (mechanical fields plus GameTable conversion
primitives and base resource/regen constants) that the M1.16 analytical player-power engine will
consume, and it hardens the test suite so later systems-correctness work stands on trustworthy tests.

M1.14 stays in Phase 1 and does not build the analytical engine, the simulator, or gear stat
modeling. It produces attributed, provenanced data artifacts and the tooling to regenerate them.

## Current State

- Mechanical enrichment (cast time, cost, cooldown, tooltip text) comes from db.ascension.gg via the
  M1.8/M1.11D scraper. This source is demonstrably stale (spell `805775` returns the outdated *Fang
  Venom: Lifeblood* rather than the current *Adrenal Venom*).
- The CoA Builder payload is authoritative for the talent graph, legality, tab ownership, AE/TE
  costs, prerequisites, and node descriptions (Decision 1, Decision 15).
- No client data is currently ingested. The local install
  (`…/ascension-live/Data/`) contains classic 3.3.5a MPQ archives and a `Data/Content/*.json` tier.

## Client Layout Findings

- **Archive-family partitioning attributes content to a game.** `patch-C*` (C, CA…CZ, CZZ) map to
  Conquest of Azeroth; `Data/area-52/patch-D.MPQ` is Area-52, physically segregated; `patch-W*`
  (WA, WB, WC…) map to Warcraft Reborn/Bronzebeard; base game is `common/expansion/lichking/patch`.
- **MPQ load order overrides.** Later patch archives override earlier ones; extraction must read the
  effective (latest CoA) record.
- **Two data tiers.** DBC files under `DBFilesClient/` inside the MPQs, and structured JSON under
  `Data/Content/` (`SpellRankData.json`, `SpellToStatSuggestionData.json`,
  `SpellToRoleSuggestionData.json`, `SpellToSpellSuggestionData.json`,
  `EnchantmentToStatSuggestionData.json`, `ItemVariationData.json`, `CharacterAdvancementData.json`).
- **Ascension likely extends DBC schemas** (extra columns); layout cannot be assumed to match stock
  3.3.5a and must be validated from the DBC header.
- **Custom numbers and item stats are partly server-side** and not fully present in client DBC.
  `Extensions.dll`/`MemoryBridge.log` indicate a memory bridge that could later read live-computed
  values.

## Scope

M1.14 includes:

- **A. MPQ extraction tooling** with correct patch-chain/load-order resolution (StormLib).
- **B. Client-native CoA attribution** with per-record confidence and provenance.
- **C. DBC parsing** with header-driven layout and schema-drift detection.
- **D. `Data/Content/*.json` ingestion** for the JSON tier, attributed like the DBC tier.
- **E. New artifacts and reconciliation** with the Builder pipeline; sunset of stale db mechanical
  enrichment.
- **F. WoW conversion primitives** (GameTables and documented constants) for the modeling engine.
- **G. Test-suite integrity audit** and modeling-test standards.
- **H. Investigation spike** into the memory bridge and the Ascension API.

M1.14 does not include:

- The analytical player-power engine (M1.16).
- Item stat ingestion/ranking (M1.18) beyond icon/type/display captured incidentally.
- Extraction of server-side custom scaling/proc numbers (scouted by the spike; not solved).
- Any visual/report changes beyond consuming richer mechanical fields where already rendered.

## Design

### A. MPQ extraction tooling

Use **StormLib** (via a thin Python wrapper/ctypes binding) because it correctly resolves the MPQ
patch chain, listfiles, and encryption. `mpyq` is a pure-Python fallback but handles patch overrides
poorly and is not the primary path. Extraction lives in a new capture module
(`coa_client_extract/`) that is isolated from the optimizer (extends Decision 3: the optimizer never
reads client archives). The module:

- Enumerates the CoA archive set and base archives in correct load order.
- Resolves each needed `DBFilesClient/*.dbc` and `Data/Content/*.json` to its effective (highest
  priority) version.
- Records, per extracted file, the source archive, extraction timestamp, and client build.

Client build is read from the client version where available and recorded on every artifact.

### B. Client-native CoA attribution

Attribution answers "is this record CoA?" from client-derived signals, producing a confidence and
provenance per record. Signals, in priority order:

1. **Archive-family membership** — the record's effective source archive is in the `patch-C*` family
   (CoA) versus `area-52/` (Area-52) or `patch-W*` (Reborn). Primary signal.
2. **ID range** — CoA custom content uses high ID ranges distinct from stock 3.3.5a and from the
   other games' ranges; the observed ranges are learned during implementation and recorded.
3. **Specialization/skill-line markers** — CoA specialization spells (e.g. the "Conquest of Azeroth
   Specialization - <Class> (<Spec>)" records) and their skill-line/family associations tag related
   content.

The **CoA Builder payload is a cross-validation oracle only**: the ~3,612 Builder spell IDs are a
labeled positive set used to measure the attribution heuristic's precision and recall and to tune
thresholds. It is never used to filter ingestion, so client-only records the Builder never exposed
are retained (with their attribution confidence). Records attributed to CoA below a confidence
threshold are ingested but flagged, not dropped.

Acid test: spell `805775` is attributed to CoA by client-native signals, its client mechanical data
matches the current *Adrenal Venom*, and the Builder cross-check confirms the heuristic caught it.
Additionally, a spot-check confirms that CoA-attributed spells *not* present in the Builder are
genuinely CoA.

### C. DBC parsing with drift detection

A generic `WDBC` reader parses the header (magic, record count, field count, record size, string
block size) and reads fixed-width records plus the string block. Per-DBC field layouts are declared
as specs. Because Ascension may extend schemas, the reader validates the header's field count and
record size against the expected 3.3.5a layout and emits a **schema-drift warning** (mirroring the
existing pipeline's drift checks) rather than misreading silently. DBCs parsed include at least:
`Spell`, `SpellCastTimes`, `SpellDuration`, `SpellRange`, `SpellRadius`, `SpellIcon`,
`SpellDescriptionVariables`, `SpellCategory`, and `SpellRuneCost`, plus item display DBCs
(`Item`, `ItemDisplayInfo`) for icon/type/display.

### D. Content JSON ingestion

Ingest the `Data/Content/*.json` tier through the same attribution and provenance pipeline. Priority
files are those relevant to systems correctness: `SpellRankData` (rank scaling),
`SpellToStatSuggestionData` and `SpellToRoleSuggestionData` (stat-interaction and role signals), and
`ItemVariationData`. `CharacterAdvancementData` is investigated for whether it is CoA or the
classless/Area-52 system before any use. Each ingested record carries its source file and attribution
confidence.

### E. Artifacts and reconciliation

New artifacts (JSONL/JSON with schema versions and per-field provenance):

- `coa-client-spell-v1` — one record per CoA-attributed spell: cast time, cost, cooldown, GCD
  category, school, effect base points/coefficients, proc data, icon, duration, range, plus
  attribution confidence and schema-match confidence.
- `coa-wow-constants-v1` — see F.
- Optional `coa-client-content-v1` — normalized records from the attributed Content JSON tier.

Reconciliation joins client records to normalized Builder entries by spell ID. **Builder stays
authoritative for the talent graph and node descriptions** (per the primary-source decision); the
**client becomes authoritative for mechanical fields**; db.ascension.gg mechanical enrichment is
demoted to fallback-only for spells the client does not cover. Disagreements are recorded with both
values and their sources rather than silently overwritten. The default report path remains
network-free after artifacts are generated.

Changelog currency spot-check: a small sample of recently changed spells from
`ascension.gg/en/changelog/4` is verified to be reflected in the extracted client data, confirming
the client is current. This uses the changelog as a verification signal, not a parser.

### F. WoW conversion primitives (modeling inputs)

Extract and normalize the GameTables and base constants into `coa-wow-constants-v1`:

- `gtCombatRatings` and the crit tables (`gtChanceToMeleeCrit(Base)`, `gtChanceToSpellCrit(Base)`) —
  rating→% conversions at level.
- Regen tables (`gtRegenMPPerSpt`, `gtOCTRegenMP/HP`) and base HP/MP by class/level
  (`gtOCTBaseHP/MPByClass`, `ChrClasses`).
- Documented game constants not in DBC: base energy (100) and regen (10/sec), focus behavior, GCD
  rules and the WotLK GCD floor, and haste's effect on GCD and resource regen.

Every constant records its source (DBC/GameTable name or "documented WotLK ruleset") and flags where
Ascension may deviate, so the M1.16 engine can treat them as inputs with stated assumptions.

### G. Test-suite integrity audit

Review every existing test for assertions that lock in incidental or wrong behavior rather than
intended behavior. The canonical example is commit `84ad112` ("Fix tooltips rendering raw AscensionDB
HTML as literal text"), where a test asserted the escaped-HTML output and thereby ossified a
rendering bug. Deliverables:

- A test-audit findings report enumerating suspect tests (especially golden/snapshot assertions) and
  their disposition.
- A rendering-correctness test that would have caught the tooltip HTML-escaping regression (tooltips
  render as HTML tables, not escaped text).
- Testing standards for the modeling milestones: formulas checked against known WotLK reference
  values (e.g. rating conversions at levels 60/80, known coefficient results), monotonicity property
  tests (more haste → not fewer casts), and provenance/schema-drift/attribution tests for extraction.

### H. Investigation spike (memory bridge + API)

A time-boxed spike, producing a viable/not-viable/defer recommendation with evidence, for two avenues
that could later supply the server-side custom numbers M1.14 cannot:

- **Memory bridge** — whether `Extensions.dll`/`MemoryBridge` exposes live-computed spell/stat values
  in a readable form and whether reading them is technically and ethically appropriate for this tool.
- **Ascension API** — whether `data.project-ascension.com/api/spells/{id}/tooltip.html` and the db
  `&power` endpoints are current (unlike the stale db HTML) and worth using as a convenience source.

The spike does not implement either integration; it scopes their value for a later milestone.

## Module Layout

- `coa_client_extract/` — MPQ/DBC/JSON capture, attribution, drift detection, artifact writers.
  Depends on StormLib. Isolated from `coa_meta`.
- `coa_meta` repository layer — loads the new `coa-client-spell-v1` and `coa-wow-constants-v1`
  artifacts with provenance, alongside existing normalized artifacts.
- `docs/data/` — schema docs for the new artifacts.
- `docs/DECISIONS.md` — record the client-authoritative-mechanical-source and client-native
  attribution decisions.

## Risks and Boundaries

- **Schema drift:** Ascension DBC extensions could break naive parsing; mitigated by header-driven
  layout and drift warnings.
- **Attribution error:** archive-family membership is strong but not proven complete; mitigated by
  Builder cross-validation and confidence flags rather than hard drops.
- **Server-side gaps:** custom scaling/proc numbers and item stats are not fully in client DBC; scoped
  to the spike and to M1.18, and documented as a known limitation.
- **Redistribution:** extracting from the user's own client is in scope; the public site must not
  redistribute client asset files — it hotlinks or uses permissibly sourced assets.

## Exit Criteria

- `coa-client-spell-v1` regenerates from a fresh MPQ read via the capture module.
- Spell `805775` is CoA-attributed by client-native signals and carries current mechanical data
  matching the live client, not the stale db *Fang Venom: Lifeblood*.
- CoA is separated from Area-52 and Reborn using client-derived signals, with attribution confidence
  measured against the Builder oracle and reported.
- `coa-wow-constants-v1` is produced with sourced conversion tables and documented constants.
- Schema-drift detection warns on DBC layout deviations rather than misreading.
- The test-suite integrity audit is complete, its findings addressed, and the new
  regression/correctness/modeling-standard tests are in place.
- db.ascension.gg mechanical enrichment is demoted to fallback-only; the Builder graph is unchanged.
- The memory-bridge/API spike has produced a documented recommendation.
