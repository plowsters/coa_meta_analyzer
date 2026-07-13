# M1.14B Client Attribution and CoA Advancement Graph Design

Sub-milestone of [M1.14 Client DBC Data Foundation](2026-07-06-m1-14-client-dbc-data-foundation-design.md).
Depends on [M1.14A Client Extraction Core](2026-07-10-m1-14-a-client-extraction-core-design.md).

> This spec supersedes the M1.14B scope sketched in the umbrella (archive-family + ID-range +
> skill-line attribution against the Builder oracle). A pre-implementation discovery pass against the
> real 44 GB client on 2026-07-13 disproved that plan's core premise and found a far better source.
> The findings and the resulting redesign are below.

## Purpose

M1.14B answers "which records are Conquest of Azeroth, and what class/spec/node do they belong to?"
from client-native evidence, and fills the `coa_attribution` block that M1.14A left as `unknown`.

The discovery pass showed the answer is not a heuristic at all: the client ships
`DBFilesClient/CharacterAdvancement.dbc`, the authoritative, current, and complete DBC form of the
CoA advancement graph. M1.14B extracts it (plus its companion tables), uses it as the primary
attribution and ownership source, proves it against the CoA Builder oracle across all 21 CoA classes,
and emits a new `coa-client-advancement-v1` artifact carrying the full node graph and legality
fields. Per the agreed scope, M1.14B **extracts and proves**; it does not yet rewire the legality or
tree pipeline to consume the client graph — that staged supersession of Decision 1 is M1.15's job,
now substantially de-risked.

## Discovery findings (measured against the real client, 2026-07-13)

These are empirical results from `coa_client_extract` + StormLib against the live install, validated
against the 3,611-spell Builder oracle (`coa_scraper/dist/coa_entries.jsonl`).

1. **Archive-family attribution is dead.** The `patch-C*` family contains only art (`Character/` and
   `Creature/` models and textures) — **zero DBC files**. The entire DBC tier is unified tables
   supplied by a few archives shared across all Ascension game modes: `patch-M` (`SkillLine`,
   `SkillLineAbility`, `Talent`, `ChrClasses`, `CharacterAdvancement`, GameTables),
   `patch-S` (spell side tables — cast times, durations, ranges, icons, categories, rune cost), and
   `patch-T` (`Spell.dbc` alone, 230,929 rows). One `Spell.dbc` holds stock, CoA, Reborn, and
   classless rows together, so `effective_archive` proves where a table came from but says nothing
   about which mode owns an individual row. Decision 18's primary signal cannot work.

2. **The weaker client-native signals top out around two-thirds.** `SkillLine.dbc` IDs 475–495 are
   exactly the Builder's 21 CoA class names, and lower skill-line bands are CoA spec names (Venomancer
   → Stalking/Rot/Fortitude). Joining `SkillLineAbility` to those lines gives 64.4% recall against the
   oracle; the loose `CharacterAdvancementData.json` `Class` field gives 39.2%; their union 65.7%;
   rank-chain closure adds nothing. The residual ~1,240 Builder spells are ~86% talents.

3. **`CharacterAdvancement.dbc` closes the gap completely and is current.** An exhaustive search of
   every DBC table and Content JSON for the residual IDs found one table that contains **all** of
   them. Measured:
   - **100.00% recall** — every one of the 3,611 Builder spell IDs appears in its spell column as a
     non-Reborn class row.
   - **Current** — its row for spell `805775` reads *Adrenal Venom*. The loose
     `CharacterAdvancementData.json` (a stale 2026-02-08 export of this same table) and
     db.ascension.gg both still say the old *Fang Venom: Lifeblood*.
   - **Full graph + legality** — it carries class-type and tab-type foreign keys, ability/talent
     essence cost, required level, tab-investment gates, node column/sizing, and a wide block of
     connection/prerequisite adjacency slots (the fixed-width DBC form of `ConnectedNodes` /
     `RequiredIDs`). A full-spec check found exact membership parity with the Builder: DBC class
     Venomancer = 201 spells, Builder Venomancer = 201, overlap 201, zero missing.

   Its companion tables are `CharacterAdvancementClassTypes` (46 rows; IDs 14–35 are the 21 custom CoA
   classes incl. `ConquestOfAzeroth`, 36–46 are Reborn), `CharacterAdvancementTabTypes` (94 rows),
   `CharacterAdvancementCategories` (29 rows), and `CharacterAdvancementEssence` (5,440 rows).

Conclusion: the client is authoritative for CoA membership, ownership, and the graph — the exact role
Decision 1 gives the Builder — and it is more current than the Builder-adjacent web sources.
Decision 18's *principle* (client authoritative, Builder = cross-validation oracle) is vindicated;
only its *mechanism* (archive family) was wrong.

> The provisional column indices found by correlation (spell col 5; class-type FK ~col 32; AE cost
> col 17; TE cost col 15; required level col 28; tab column col 30; TE-investment gate col 39;
> connection/prereq adjacency ~cols 48–97) are **starting points, not contract**. The implementation
> finalizes the column map by decoding the schema with the loose JSON export's field names as the key,
> and records the resolved layout in `dbc_layouts.py` with drift detection like every other table.

## Non-Goals (staged, not dropped)

- **Rewiring the legality engine / tree renderer to consume the client graph, retiring the Builder
  scrape, and superseding Decision 1.** M1.14B proves parity and emits the artifact; the pipeline flip
  is M1.15 (talent-tree correctness), which already owns tree/level-path work. See Decision 21 below.
- **Reconciliation into `coa-mechanics-v1` and db mechanical sunset** — still M1.14C.
- **GameTable / `coa-wow-constants-v1`** — still M1.14D.
- **Full pixel-position layout parity** — cosmetic; positions did not resolve cleanly against the
  stale JSON and layout is M1.15's concern. M1.14B extracts whatever position/column fields decode
  cleanly and flags the rest.
- **Server-side computed numbers** (coefficients, scripted procs, scaling) — not in client DBC at all;
  scoped to the M1.14F spike and Phase 2, and unaffected by this discovery.

## Architecture

M1.14B is additive to M1.14A and reuses all of its machinery (`ArchiveBackend`, the header-driven
`wdbc` reader with drift detection, `manifest`, provenance). No new native surface.

### Data flow

```
Ascension client (…/ascension-live/Data/)
        │
        ▼
coa_client_extract  (M1.14A machinery, unchanged)
  ├─ archive_plan / ArchiveBackend ─ effective patch-chain bytes + provenance
  ├─ wdbc + dbc_layouts ─ NOW ALSO: CharacterAdvancement + *Types + Essence layouts
  ├─ advancement.py (NEW) ─ join CA graph → class/tab/type/costs/gates/connections/essence
  ├─ attribution.py (NEW) ─ per-record CoA status + confidence + signals
  ├─ content_json ─ loose CharacterAdvancementData.json kept as QA drift signal only
  └─ artifacts ─ writes coa-client-advancement-v1 + fills coa_attribution on coa-client-spell-v1
        │
        ▼
coa-client-advancement-v1.jsonl   (full CoA node graph + legality, client-native, provenanced)
coa-client-spell-v1.jsonl         (M1.14A artifact; coa_attribution now filled)
coa-client-content-v1.jsonl       (M1.14A; CharacterAdvancementData records flagged supersede/QA)
reports/client_extract/coa_builder_parity_report.json  (NEW: 21-class validation)
```

### New modules

```
coa_client_extract/
├── advancement.py     # CharacterAdvancement graph reader + companion-table resolvers
├── attribution.py     # CoA attribution model (primary: CA registry; corroborating: skill-line, id-range)
└── (dbc_layouts.py)   # + CharacterAdvancement, CharacterAdvancementClassTypes/TabTypes/
                       #   Categories/Essence layouts, finalized against the JSON schema key
```

Attribution and the advancement reader live in their own modules so each has one purpose and is unit
testable against synthetic fixtures through the fake backend, exactly like M1.14A's readers.

## Attribution model

`attribution.py` assigns, per record, a `coa_attribution` block:

```json
{
  "status": "coa",
  "confidence": "high",
  "class": "Venomancer",
  "spec": "Rot",
  "signals": [
    { "kind": "advancement_registry", "class_type_id": 33, "tab_type_id": 41, "node_id": 12841 },
    { "kind": "skill_line", "skill_line_id": 103, "name": "Rot" }
  ],
  "archive_family": "other",
  "id_range": "high"
}
```

- **Primary signal — `advancement_registry`.** Membership in `CharacterAdvancement.dbc` with a
  class-type FK in the CoA band (IDs 14–35) yields `status: "coa"`, `confidence: "high"`, and the
  resolved class/spec. Reborn class-type rows (36–46) yield `status: "reborn"`; stock class types
  (2–11) plus `None`/`General`/`Hero` yield `status: "non_coa"`.
- **Corroborating signals** — skill-line membership and ID range are recorded when present, but do not
  override the registry. They raise confidence and, for the small set of client records *not* in the
  advancement graph, provide a lower-confidence fallback classification (`confidence: "medium"|"low"`)
  rather than a hard drop.
- **`archive_family` is retained as raw provenance only** (it is now known to be uninformative for
  attribution) so the artifact history stays honest about what was and wasn't used.
- **The Builder is never an input.** It is the oracle used to *measure* this model (below). Absence
  from the Builder is never negative evidence — client-only CoA nodes the Builder never exposed are
  retained with their registry-derived attribution.

Multi-membership is preserved: `class`/`spec` become arrays when a node legitimately belongs to more
than one class/spec context, so attribution is not lossily flattened.

## Artifacts and schemas

New schema doc `docs/data/client-advancement-schema.md`; update `client-spell-schema.md` (attribution
now filled) and `client-content-schema.md` (CharacterAdvancementData supersede/QA note).

### `coa-client-advancement-v1` (one record per CoA advancement node)

```json
{
  "schema_version": "coa-client-advancement-v1",
  "node_id": 12841,
  "spell_id": 805775,
  "name": "Adrenal Venom",
  "class": "Venomancer",
  "spec": "Rot",
  "entry_type": "Ability",
  "essence_kind": "ability",
  "legality": {
    "ae_cost": 1, "te_cost": 0,
    "required_level": 0,
    "required_tab_ae": 0, "required_tab_te": 0,
    "required_ids": [],
    "connected_node_ids": [6096, 7235],
    "column": 3, "row": 5,
    "max_rank": 1
  },
  "provenance": {
    "source_dbcs": { "CharacterAdvancement": "patch-M.MPQ", "CharacterAdvancementClassTypes": "patch-M.MPQ" },
    "effective_archive": "patch-M.MPQ",
    "schema_match_confidence": "high",
    "supersedes": { "source_file": "CharacterAdvancementData.json", "field_drift": ["name"] },
    "extraction_date": "2026-07-13"
  },
  "coa_attribution": { "status": "coa", "confidence": "high", "signals": [ … ] }
}
```

The `legality` field names line up with the Builder's normalized record
(`ae_cost`/`te_cost`/`required_level`/`required_tab_ae`/`required_tab_te`/`required_ids`/
`connected_node_ids`/`row`/`column`/`max_rank`) so M1.15's pipeline flip is a direct field map, the
same way M1.14A's `mechanics` fields were pre-aligned to `coa-mechanics-v1`.

### `coa-client-spell-v1` (M1.14A artifact — attribution now filled)

M1.14B joins each spell record to the advancement registry by `spell_id` and replaces
`coa_attribution.status: "unknown"` with the computed block. Spells absent from the graph keep a
corroborating-signal classification with lower confidence.

## Builder-parity validation

The deliverable that earns "the client can replace the Builder" is a report, not a claim:
`coa_builder_parity_report.json`, computed over all 21 CoA classes. For each class it records, and in
aggregate:

- **Membership**: spells in the client graph vs the Builder, overlap, client-only, Builder-only.
- **Ownership agreement**: class/spec agreement rate for the overlap.
- **Legality agreement**: match rate for AE cost, TE cost, required level, tab-investment gates, and
  connection/prerequisite sets, with every disagreement enumerated (client value, Builder value).
- **Currency**: the `805775` acid test, plus a small changelog spot-check sample
  (from `ascension.gg/en/changelog`) confirmed present in the client graph.

The report is the evidence M1.15 consumes to decide the Decision 1 flip. Disagreements are expected
where the loose JSON was stale; the report attributes each to client-current-vs-stale drift vs a
genuine gap, so M1.15 does not have to rediscover them.

## Decision impacts

- **Amend Decision 18.** Replace the archive-family attribution mechanism with the
  `CharacterAdvancement.dbc` registry as the primary CoA signal (archive family demoted to raw
  provenance; skill-line and ID range corroborating). The principle — client authoritative, Builder =
  cross-validation oracle — is unchanged and now fully realized.
- **New Decision 21 (staged Decision 1 supersession).** Record that the CoA client advancement graph
  is a candidate *canonical* source for the talent graph and legality, superseding Decision 1's
  "Builder is the Phase 1 source of truth," **gated** on the M1.14B parity report passing across all
  21 classes. Until M1.15 performs the pipeline flip, the Builder remains the operative graph
  authority and the client artifact is validated-but-not-yet-consumed. This keeps the foundational
  decision honest about being staged rather than silently reversed.

## Error handling

- Reuses M1.14A's `DbcDriftError` / drift-warning path for the new tables: a `CharacterAdvancement`
  header disagreeing with the finalized layout records `schema_match_confidence: "low"` on affected
  records and surfaces in the manifest, rather than misreading.
- A CoA class-type FK that resolves outside the known 14–35 band is flagged (possible new CoA class or
  layout drift), not silently bucketed.
- Fail-closed and effective-chain rules from M1.14A/Decision 20 are unchanged: read the effective
  patch-chain copy of `CharacterAdvancement.dbc` (not `patch-M` directly), and write nothing without
  StormLib.

## Testing strategy

Same three tiers as M1.14A; all committed fixtures synthetic/self-authored (redistribution boundary).

1. **Default unit tests** (no client, no StormLib):
   - `advancement`: synthetic `CharacterAdvancement` + companion WDBC fixtures → assert graph join,
     class/tab resolution, cost/gate/connection decoding, essence-lane derivation, and drift handling.
   - `attribution`: synthetic registry rows → assert CoA/Reborn/non-CoA status, confidence tiers,
     corroborating-signal fallback for graph-absent spells, and multi-membership arrays.
   - `artifacts`: `coa-client-advancement-v1` schema validation; `coa-client-spell-v1` attribution
     now filled; `supersedes` provenance present.
   - parity: a synthetic mini-oracle vs a synthetic graph → assert the parity report's membership/
     ownership/legality math and disagreement enumeration.
2. **Native integration test** (`@pytest.mark.stormlib`, miniature MPQs): a base archive with a tiny
   `CharacterAdvancement.dbc` overridden by a patch; assert effective-chain resolution and provenance.
3. **Local-client acceptance test** (`@pytest.mark.client`, real install): extract the real graph,
   assert 100% Builder membership recall, Venomancer 201/201 parity, `805775` → current *Adrenal
   Venom* with `status: "coa"`/`class: "Venomancer"`, and emit the parity report.

Testing standards follow M1.14E: assertions check intended behavior (attribution correctness,
parity math), never incidental output.

## Exit Criteria

- `CharacterAdvancement.dbc` and its companion tables are extracted through the M1.14A backend with
  finalized, drift-checked layouts, from the effective patch chain.
- `coa-client-advancement-v1` regenerates with the full CoA node graph (spell, class, spec, type,
  essence, AE/TE cost, level, tab gates, connections) and provenance.
- `coa_attribution` on `coa-client-spell-v1` is filled: spell `805775` is `status: "coa"`,
  `class: "Venomancer"`, `confidence: "high"` from the registry, with current mechanical data.
- The Builder-parity report is produced over all 21 CoA classes: it reproduces the measured 100%
  membership recall (all 3,611 Builder spells present in the client graph), reports class/spec
  ownership agreement, and enumerates every legality disagreement with client-vs-stale attribution.
- The loose `CharacterAdvancementData.json` is retained only as a QA drift signal; nothing downstream
  reads its values.
- Decision 18 is amended (registry replaces archive family); Decision 21 records the staged Decision 1
  supersession gated on the parity report.
- Default `pytest` stays green through the fake backend; no legality/tree pipeline is rewired (that is
  M1.15).
