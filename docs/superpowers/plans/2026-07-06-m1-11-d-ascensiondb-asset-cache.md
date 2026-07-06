# M1.11D AscensionDB Asset and Canonical Data Cache Implementation Plan

> **For agentic workers:** Use TDD for parser/cache behavior. Commit after each checkpoint. Do not run public network fetches in unit tests; use fixtures and injected fetch functions. Public AscensionDB fetches are allowed only for the smoke checkpoint.

**Goal:** Extend the scraper pipeline so CoA guide reports use local AscensionDB spell/item/effect/icon artifacts with cache-aware refreshes and no page-load network dependency.

**Architecture:** Add a cache layer under `coa_scraper/scripts/lib/`, then replace one-off spell/item enrichment scripts with a unified cache-aware enrichment command. Keep existing file names as compatibility outputs until downstream code migrates to v2 records.

---

## Checkpoint 1: Cache Manifest Schema and Fixture Fetcher

Files:

- Create `docs/data/ascensiondb-cache-schema.md`
- Create `coa_scraper/scripts/lib/ascensiondb-cache.mjs`
- Create `coa_scraper/tests/ascensiondb-cache.test.mjs`
- Create `coa_scraper/tests/fixtures/ascensiondb/spell-123-power.js`

### Step 1: Add failing cache tests

Assertions:

- `cacheKeyForUrl(url)` is stable and filesystem-safe.
- A fresh manifest row returns `fresh_cache` without calling fetch.
- A stale manifest row with `etag` sends `If-None-Match`.
- A stale manifest row with `last_modified` sends `If-Modified-Since`.
- A `304` result reuses the existing body path and updates `validated_at`.
- A `200` result writes body metadata with `content_sha256`, `byte_length`, and `fetched_at`.
- Fetch errors become `fetch_failed` rows and do not crash the whole batch unless `--strict` is later added.

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: RED.

### Step 2: Implement the cache module

Export:

```text
ASCENSIONDB_CACHE_SCHEMA_VERSION
cacheKeyForUrl(url)
loadCacheManifest(path)
writeCacheManifest(path, rows)
fetchCachedResource(options)
isFresh(row, staleDays, now)
```

`fetchCachedResource()` should accept injected `fetchText`, `readBody`, and `writeBody` functions so tests avoid network and disk-heavy setup.

### Step 3: Document the manifest schema

Document:

- Manifest row fields.
- Status enum.
- Refresh behavior.
- Hashing rules.
- Respectful public defaults.

### Step 4: Verify and commit

Run:

```bash
npm --prefix coa_scraper run unit-test
git diff --check
```

Commit:

```bash
git add docs/data/ascensiondb-cache-schema.md coa_scraper/scripts/lib/ascensiondb-cache.mjs coa_scraper/tests/ascensiondb-cache.test.mjs coa_scraper/tests/fixtures/ascensiondb
git commit -m "Add AscensionDB cache manifest support"
```

---

## Checkpoint 2: v2 Spell/Item Parser Records

Files:

- Modify `coa_scraper/scripts/lib/ascensiondb.mjs`
- Create or extend `coa_scraper/tests/ascensiondb-parser.test.mjs`
- Add parser fixtures for spell, linked spell, and item payloads.

### Step 1: Add failing parser tests

Assertions:

- `parseAscensionDbPayload()` keeps existing spell fields: `id`, `name`, `icon`, `tooltip_html`, `buff_html`, `linked_spell_ids`, `linked_item_ids`.
- It also emits v2 fields when data exists: `tooltip_text`, `required_level`, `cooldown_ms`, `gcd_ms`, `cast_time_ms`, `range_yards`, `duration_ms`, `period_ms`, `power_costs`, and `mechanic_tags`.
- Item payloads emit `quality`, `inventory_type`, `item_class`, `item_subclass`, `weapon_type`, `armor_type`, `stats`, and `effects` when parsable.
- Unknown payload fields are ignored but retained in parser warnings when useful.
- Malformed registration payloads return a structured empty row with `parse_failed`, not an unhandled exception.

### Step 2: Implement parser helpers conservatively

Add small helpers:

```text
htmlToText(html)
parseRequiredLevel(text)
parseCooldownMs(text)
parseCastTimeMs(text)
parseRangeYards(text)
parseDurationMs(text)
parsePowerCosts(text)
parseItemClass(text)
parseStats(text)
```

Rules:

- Prefer explicit structured fields from the DB payload if present.
- Fall back to tooltip text parsing only when the pattern is stable.
- Emit warnings for inferred fields.
- Do not guess coefficients or proc rates in M1.11D.

### Step 3: Verify and commit

Run:

```bash
npm --prefix coa_scraper run unit-test
git diff --check
```

Commit:

```bash
git add coa_scraper/scripts/lib/ascensiondb.mjs coa_scraper/tests coa_scraper/tests/fixtures/ascensiondb
git commit -m "Parse richer AscensionDB spell and item records"
```

---

## Checkpoint 3: Unified Cache-Aware Enrichment Command

Files:

- Create `coa_scraper/scripts/enrich-ascensiondb-assets.mjs`
- Modify `coa_scraper/package.json`
- Modify root `package.json` if a root-level convenience script is useful.
- Extend `coa_scraper/scripts/write-artifact-manifest.mjs`

### Step 1: Add command tests around pure functions

Create exported pure helpers in the script or a small lib module:

```text
buildSeedResources(entries)
discoverLinkedResources(spellRows, itemRows, options)
summarizeCacheRun(results)
normalizeCliOptions(argv)
```

Test:

- Seed resources include unique spell IDs from entries.
- Linked resources are bounded by configured depth.
- Summary reports `fetched`, `fresh_cache`, `not_modified`, `fetch_failed`, `parse_failed`, and `asset_missing`.
- CLI defaults use `concurrency=4`, `stale_days=7`, `linked_spell_depth=1`, `linked_item_depth=1`.

### Step 2: Implement command stages and logs

Log these stages:

```text
[ascensiondb-assets] Stage 1: load entries and cache manifest
[ascensiondb-assets] Stage 2: fetch/reuse spell payloads
[ascensiondb-assets] Stage 3: discover linked spell/item records
[ascensiondb-assets] Stage 4: fetch/reuse linked records
[ascensiondb-assets] Stage 5: resolve icon assets
[ascensiondb-assets] Stage 6: write artifacts and summaries
```

Outputs:

```text
dist/coa_db_spell_records.jsonl
dist/coa_db_item_records.jsonl
dist/coa_db_effect_records.jsonl
dist/coa_db_asset_records.jsonl
dist/coa_db_spell_tooltips.jsonl        # compatibility
dist/coa_db_item_tooltips.jsonl         # compatibility
reports/coa_ascensiondb_cache_manifest.json
reports/coa_ascensiondb_cache_summary.json
```

### Step 3: Preserve M1.8/M1.9 script behavior

Update scripts:

```json
"enrich-assets": "node scripts/enrich-ascensiondb-assets.mjs ...",
"enrich-db": "node scripts/enrich-ascensiondb-assets.mjs --compat-spells-only ...",
"enrich-items": "node scripts/enrich-ascensiondb-assets.mjs --compat-items-only ..."
```

If compatibility wrappers are too awkward, keep old scripts but route their fetch path through `ascensiondb-cache.mjs`.

### Step 4: Verify and commit

Run:

```bash
npm --prefix coa_scraper run unit-test
npm --prefix coa_scraper run validate
git diff --check
```

Commit:

```bash
git add coa_scraper/scripts coa_scraper/package.json package.json
git commit -m "Add cache-aware AscensionDB asset enrichment command"
```

---

## Checkpoint 4: Icon Asset Resolver

Files:

- Create `coa_scraper/scripts/lib/icon-assets.mjs`
- Extend `coa_scraper/tests/icon-assets.test.mjs`
- Modify `enrich-ascensiondb-assets.mjs`

### Step 1: Add failing resolver tests

Assertions:

- Existing fresh asset manifest rows are reused.
- Successful asset fetch writes `asset_path`, `content_type`, `byte_length`, `content_sha256`, and status `fetched`.
- Failed URL templates are cached as `asset_missing` and not retried while fresh.
- Resolver probes only the configured URL templates and stops after first success.
- `--skip-assets` writes DB records without failing.

### Step 2: Implement resolver

Recommended API:

```text
resolveIconAsset({ iconToken, manifest, assetRoot, fetchBinary, templates, now })
```

Constraints:

- Lowercase and sanitize icon tokens.
- Default asset path: `dist/assets/icons/<icon-token>.<ext>`.
- Keep URL templates centralized.
- Use low concurrency for binary assets.
- Do not include external image URLs in generated guide HTML.

### Step 3: Verify and commit

Run:

```bash
npm --prefix coa_scraper run unit-test
git diff --check
```

Commit:

```bash
git add coa_scraper/scripts/lib/icon-assets.mjs coa_scraper/scripts/enrich-ascensiondb-assets.mjs coa_scraper/tests
git commit -m "Cache AscensionDB icon assets locally"
```

---

## Checkpoint 5: Mechanics and Guide Integration

Files:

- Modify `coa_scraper/scripts/build-mechanics-artifacts.mjs`
- Modify `coa_meta/guide_assets.py`
- Modify `coa_meta/guide_builder.py`
- Modify `coa_meta/guide_rendering.py`
- Extend tests:
  - `tests/test_guide_assets.py`
  - `tests/test_guide_builder.py`
  - `tests/test_guide_rendering.py`
  - scraper mechanics tests if present

### Step 1: Add failing Python tests

Assertions:

- Guide asset resolution prefers local `icon_asset_path`.
- Spell/talent tooltips render safe DB table tags as tables.
- Script/event attributes are stripped.
- Missing icons use a local fallback and add one provenance warning.
- Guide pages never call AscensionDB at runtime.

### Step 2: Feed richer records into mechanics artifacts

Update mechanics generation to use v2 fields:

- Costs/generates/spends.
- Cooldown/GCD/cast time.
- Duration/periodic flags.
- Linked effect spell refs.
- Item effect refs.
- Source confidence and parser warnings.

Keep fields unknown instead of guessing when parser confidence is low.

### Step 3: Update report artifact manifest

Ensure `reports/coa_artifact_manifest.json` includes:

- `coa_db_spell_records.jsonl`
- `coa_db_item_records.jsonl`
- `coa_db_effect_records.jsonl`
- `coa_db_asset_records.jsonl`
- `coa_ascensiondb_cache_manifest.json`
- `coa_ascensiondb_cache_summary.json`
- local icon asset count and hash rollup

### Step 4: Verify and commit

Run:

```bash
PYTHONPATH=. pytest tests/test_guide_assets.py tests/test_guide_builder.py tests/test_guide_rendering.py
npm --prefix coa_scraper run unit-test
git diff --check
```

Commit:

```bash
git add coa_meta tests coa_scraper/scripts
git commit -m "Use cached AscensionDB assets in guides"
```

---

## Checkpoint 6: Real Artifact Smoke

This checkpoint is the only one that should contact `db.ascension.gg`.

### Step 1: Run a bounded smoke

Use a small limit first:

```bash
npm --prefix coa_scraper run enrich-assets -- \
  --entries dist/coa_entries.enriched.jsonl \
  --out dist \
  --reports reports \
  --asset-root dist/assets \
  --manifest reports/coa_ascensiondb_cache_manifest.json \
  --limit 25 \
  --concurrency 2
```

Expected:

- Command logs every stage.
- Summary contains a mix of fetched/cached statuses.
- No unhandled parser exceptions.
- Asset failures are warnings, not crashes.

### Step 2: Run full pipeline only if bounded smoke is clean

```bash
npm --prefix coa_scraper run pipeline:m1.9
python -m coa_meta meta \
  --entries coa_scraper/dist/coa_entries.enriched.jsonl \
  --classes coa_scraper/dist/coa_classes.json \
  --out reports/meta \
  --format json --format md --format html
```

### Step 3: Commit source only

Do not commit generated `dist/`, `reports/`, screenshots, or cache bodies unless the repository has an explicit fixture/artifact policy for that file.

Commit any final source/doc fixes:

```bash
git add docs coa_scraper/scripts coa_scraper/tests coa_meta tests package.json coa_scraper/package.json
git commit -m "Complete AscensionDB asset cache planning integration"
```

---

## Acceptance Checklist

- [ ] Cache manifest schema documented.
- [ ] Unit tests cover fresh cache, stale conditional request, `304`, `200`, and fetch failure.
- [ ] Rich spell and item records are emitted while compatibility outputs still work.
- [ ] Icon assets are cached locally and referenced by guide HTML.
- [ ] Tooltip tables render as tables and unsafe markup is stripped.
- [ ] Pipeline logs state every major stage and completion counts.
- [ ] Full report generation remains network-free after artifacts are produced.

