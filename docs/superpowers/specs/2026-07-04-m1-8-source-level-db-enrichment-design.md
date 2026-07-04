# M1.8 Source, Level, and AscensionDB Enrichment Design

## Purpose

M1.8 improves Phase 1 data fidelity without changing the Phase 1 promise. The meta report remains a theorycraft projection from builder data, but lower-level eligibility and source-aware reports should stop treating missing data as if it were exact.

The main change is to add a separate enrichment pipeline that joins Ascension CoA builder nodes with AscensionDB spell and item data, then records source category, level provenance, and enrichment confidence.

## Current Context

The repository currently has a clean Phase 1 release path:

- `coa_scraper/` captures and normalizes the Ascension CoA builder payload.
- `coa_meta/` loads normalized entries, validates legal builds, scores theorycraft profiles, generates APLs, and emits meta reports.
- `python -m coa_meta meta ...` is the documented release command.

The M1.6/M1.7 design explicitly left trainer/source/level fidelity to M1.8. Current lower-level reports filter known `required_level` values and warn with `shared_class_level_gating_incomplete`.

## Research Findings

### Builder Payload

The current `coa_scraper/dist` artifacts are internally healthy under M1.7 validation:

- 21 classes.
- 3,612 normalized node records.
- 96 class metadata tabs.
- 5 metadata tabs with no node records.
- 0 missing class records.
- 0 missing tab records.
- 0 unknown essence-kind records.

Level distribution in the current normalized entries:

- `required_level = 0`: 3,283 records.
- `required_level > 0`: 329 records.
- Positive levels present: 1, 10, 15, 20, 30, 40, 50.

All current shared `Class` pool records have `required_level = 0`. This is why lower-level reports are approximate even when spec-tree rows have known level gates.

There are 42 records where builder `requiredLevel` is `0` but tooltip text contains text such as `Level 10 Passive`. These are high-value validation candidates.

### AscensionDB

`db.ascension.gg` is useful, but not a drop-in replacement for the builder payload.

Useful URLs:

- `https://db.ascension.gg/?spell=<spell_id>`
- `https://db.ascension.gg/?spell=<spell_id>&power`
- `https://db.ascension.gg/?item=<item_id>`
- `https://db.ascension.gg/?item=<item_id>&power`
- `https://db.ascension.gg/?data=item-scaling`

The `&power` endpoints return compact JavaScript registration payloads:

```js
$WowheadPower.registerSpell(92117, 0, {
    "name_enus": "Dream Flowers",
    "icon": "inv_legion_faction_dreamweavers",
    "tooltip_enus": "...",
    "spells_enus": [],
    "buff_enus": "",
    "buffspells_enus": []
});
```

For item records:

```js
$WowheadPower.registerItem(23887, 0, {
    "name_enus": "Schematic: Rocket Boots Xtreme",
    "quality": 3,
    "icon": "inv_boots_09",
    "tooltip_enus": "..."
});
```

When a spell ID is known only as an empty registration, the response can be:

```js
$WowheadPower.registerSpell(804137, 0, {});
```

That means DB acquisition must preserve coverage and confidence. Empty registration is not a fatal error; it is an explicit `empty_registration` enrichment status.

Full spell pages sometimes include richer detail tables: school, cost, range, cast time, cooldown, GCD, effects, and affected spells. However, some pages are permission-restricted while still embedding tooltip payloads. M1.8 should use `&power` as the stable primary DB acquisition path and full pages as optional detail enrichment when available.

DB data is especially valuable for:

- tooltip normalization independent of builder UI rendering;
- spell tooltip level text;
- buff tooltip payloads;
- item and equipment tooltip payloads;
- use/equip spell references;
- required item levels and required character levels;
- armor/weapon slot and armor class text;
- item-scaling payloads.

DB data is not authoritative for:

- CoA class and tab ownership in the active builder slug;
- graph coordinates;
- prerequisites;
- AE/TE costs;
- tab gate values;
- reportable spec list;
- current build slug/version provenance.

## Source Authority Model

M1.8 uses a layered authority model.

### Builder Payload Is Authoritative For Legality

The Ascension CoA builder Next Flight payload remains the source of truth for:

- builder id, slug, name, max level;
- class roster and tab metadata;
- node ownership by class and tab;
- `entry_id`, `spell_id`, `spell_ids`;
- AE/TE costs;
- required tab AE/TE gates;
- required node IDs;
- connected node IDs;
- coordinates and node shape;
- rank count;
- passive and starting-node flags.

### AscensionDB Is Authoritative For Enrichment

AscensionDB is the preferred source for:

- canonical spell and item tooltip payloads;
- spell and item display names and icons;
- spell detail tables when public;
- item tooltip equipment text;
- item required level and item level;
- use/equip spell links;
- buff tooltip payloads;
- item-scaling tables.

AscensionDB enrichment must not overwrite builder legality fields unless a future milestone explicitly validates that DB exposes the same active CoA builder version.

### Tooltip Parsing Is Inferential

Any field extracted from tooltip text is inferred. This includes level text such as `Level 10 Passive`, item slot text, use/equip effects, and linked spell references parsed out of HTML.

The pipeline must store the raw tooltip HTML and the parsed result, with confidence.

## Normalized Schema Additions

M1.8 should keep `coa-normalized-v1` as the package-facing schema version and add optional fields. This avoids breaking the Phase 1 report path while making new data available to M1.8-aware consumers.

Add these top-level fields to normalized node records:

```json
{
  "source_category": "spec_tree",
  "source_confidence": "high",
  "availability": {
    "builder_required_level": 0,
    "tooltip_required_level": 10,
    "db_tooltip_required_level": 10,
    "effective_required_level": 10,
    "level_source": "db_tooltip",
    "level_confidence": "medium",
    "notes": ["builder_required_level_zero_but_tooltip_has_level"]
  },
  "db_enrichment": {
    "spell_id": 92117,
    "status": "matched",
    "name": "Dream Flowers",
    "name_match": true,
    "icon": "inv_legion_faction_dreamweavers",
    "tooltip_html": "...",
    "tooltip_text": "...",
    "buff_tooltip_html": "",
    "linked_spell_ids": [561005],
    "detail_status": "not_fetched",
    "provenance": {
      "url": "https://db.ascension.gg/?spell=92117&power",
      "fetched_at": "2026-07-04T00:00:00Z"
    }
  }
}
```

Source category enum:

- `spec_tree`: normal non-shared class/spec tree node.
- `class_pool`: shared `Class` pool node.
- `trainer`: trainer-learned ability, when verified by a source outside the builder.
- `misc_system`: system, hidden, quest, item, or metadata record not selected directly from a build tree.
- `metadata_only`: class metadata tab with no node rows.
- `unknown`: insufficient evidence.

Confidence enum:

- `high`: source field is direct from the authoritative source for that field.
- `medium`: field is parsed from canonical tooltip text or corroborated by two imperfect sources.
- `low`: field is inferred from naming, tab heuristics, or a conflicting source.

DB status enum:

- `matched`: DB returned non-empty data and key identity checks passed.
- `matched_name_differs`: DB returned data, but names differ enough to require review.
- `empty_registration`: DB returned an empty registration object.
- `not_found`: no DB record could be fetched.
- `fetch_failed`: network or response error.
- `not_applicable`: no spell ID or item ID exists for this record.

## New Artifacts

M1.8 should add DB enrichment as separate artifacts first, then join them into normalized output.

Recommended files:

- `coa_scraper/dist/coa_db_spell_tooltips.jsonl`
- `coa_scraper/dist/coa_db_spell_details.jsonl`
- `coa_scraper/dist/coa_db_item_tooltips.jsonl`
- `coa_scraper/reports/coa_db_enrichment_summary.json`
- `coa_scraper/reports/coa_source_level_report.txt`
- `coa_scraper/reports/coa_metadata_tab_report.json`
- `coa_scraper/reports/coa_cross_source_conflicts.json`

The existing `coa_entries.jsonl` should remain the primary optimizer input. M1.8 can add source and enrichment fields to it once the separate artifacts and reports are passing.

## Acquisition Design

### DB Fetcher

Add a focused DB fetch module under `coa_scraper/scripts/lib/ascensiondb.mjs`.

Responsibilities:

- Build `&power` URLs for spell and item IDs.
- Fetch with bounded concurrency.
- Cache successful and failed responses on disk.
- Parse `$WowheadPower.registerSpell(...)` and `$WowheadPower.registerItem(...)`.
- Classify empty registrations separately from fetch failures.
- Extract tooltip text safely from tooltip HTML.
- Extract linked spell and item IDs from tooltip anchors.
- Extract tooltip level text using conservative regexes.

The parser should use structured extraction from the registration payload rather than page scraping. The JS payload is JSON-like enough to parse by isolating the object argument and using `JSON.parse`.

### Full Page Detail Fetcher

Full detail pages are optional in M1.8.

Use full pages for public spell detail tables only after tooltip acquisition works. Store `detail_status` separately so permission-restricted pages do not cause M1.8 failures.

The first public detail fields to parse are:

- school;
- cost;
- range;
- cast time;
- cooldown;
- GCD;
- effects;
- affected spell IDs.

### Scraper Capture Cleanup

The current browser capture script opens Chromium headed and waits for manual tab clicking plus Enter. M1.8 should not depend on a user being present.

Refactor `scrape-coa-network.mjs` to support:

- `--headless`;
- `--interactive`;
- `--url`;
- `--out-dir`;
- `--snapshot-dir`;
- `--har`;
- `--wait-ms`;
- `--finalize-on-load`.

Default behavior should remain compatible with current manual capture, but CI and unattended runs should use:

```bash
npm run capture -- --headless --finalize-on-load
```

The current builder payload is embedded in the initial Next Flight HTML. M1.8 should first prove that a noninteractive headless capture can regenerate the same builder payload. If future data requires UI interaction, add automated class/tab click coverage with Playwright locators in a separate task.

## Validation Design

Add validation reports for:

- metadata tabs with no node rows;
- tabs whose ID/name appears under unexpected classes;
- `required_level = 0` with tooltip `Level N` text;
- builder level and DB tooltip level conflicts;
- DB empty registration rate;
- DB name mismatch rate;
- class pool records with unknown or zero-only level data;
- enrichment fetch coverage by class, tab, and source category.

Validation should fail only on contract violations and impossible states. Data gaps should be warnings with counts and examples.

M1.8 should not fail because DB has empty registrations or name differences. It should fail if the enrichment artifact is malformed, missing provenance, or internally inconsistent.

## Report Runner Integration

M1.8 should update lower-level report behavior only after normalized entries expose `availability.effective_required_level` and `availability.level_confidence`.

Eligibility policy:

- Use `effective_required_level` when `level_confidence` is `high` or `medium`.
- Fall back to `required_level` when M1.8 fields are absent.
- Emit granular warnings such as:
  - `class_pool_level_gating_incomplete`;
  - `trainer_source_unverified`;
  - `db_level_conflicts_present`;
  - `metadata_tabs_without_nodes_present`.

The current `shared_class_level_gating_incomplete` warning can remain as a compatibility alias until reports include the new warnings.

## Testing Strategy

Use fixture-driven tests with small local DB payload samples. Tests should not require network.

Test layers:

- parser tests for spell `&power` payloads;
- parser tests for item `&power` payloads;
- parser tests for empty registrations;
- extraction tests for tooltip text, level text, linked spell IDs, and linked item IDs;
- normalizer tests for source category and availability fields;
- validator tests for metadata tabs, DB conflicts, and class-pool level warnings;
- report eligibility tests for `effective_required_level`;
- one optional network smoke command documented but not required in normal tests.

## Out of Scope

M1.8 does not:

- build a simulator;
- claim raw DPS;
- replace builder legality fields with DB data;
- require DB enrichment for default level 60 reports;
- scrape private authenticated DB data;
- fully model gear/stat scaling;
- ingest combat logs;
- implement trainer availability from an in-game source unless a public source is discovered during implementation.

## Recommended Approach

Implement M1.8 in this order:

1. Add DB power-payload parser and fixture tests.
2. Add bounded DB enrichment artifact writer with cache and provenance.
3. Add source/level validation reports from current builder artifacts plus DB enrichment.
4. Add additive normalized fields.
5. Update report eligibility to consume `effective_required_level` conservatively.
6. Refactor browser capture for unattended headless runs.

This keeps the risky web-acquisition changes isolated from the optimizer and preserves the current Phase 1 release path while adding better data for lower-level reports.
