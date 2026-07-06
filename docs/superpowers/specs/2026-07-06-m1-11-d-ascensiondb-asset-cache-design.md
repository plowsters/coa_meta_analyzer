# M1.11D AscensionDB Asset and Canonical Data Cache Design

Date: 2026-07-06

Status: ready for implementation planning

## Goal

M1.11D makes AscensionDB enrichment complete enough for guide-site use without adding live network dependencies to the generated report.

The scraper should fetch canonical spell, item, effect, weapon, armor, tooltip, and icon/image records from `db.ascension.gg`; cache them with conservative refresh behavior; and emit stable local artifacts consumed by the Python guide generator.

## Current State

The repo already has useful but incomplete AscensionDB plumbing:

- `coa_scraper/scripts/lib/ascensiondb.mjs` builds `?spell=<id>&power` and `?item=<id>&power` URLs, extracts `$WowheadPower.registerSpell` and `$WowheadPower.registerItem` payloads, and parses names, icon tokens, HTML tooltip text, buff HTML, and linked spell/item IDs.
- `coa_scraper/scripts/enrich-ascensiondb.mjs` fetches spell payloads for normalized entries and writes `dist/coa_db_spell_tooltips.jsonl`.
- `coa_scraper/scripts/enrich-linked-items.mjs` follows linked item IDs and writes `dist/coa_db_item_tooltips.jsonl`.
- `coa_scraper/scripts/build-mechanics-artifacts.mjs` produces `dist/coa_mechanics.jsonl` and `dist/coa_items.jsonl`, but most mechanic fields remain heuristic because the parsed DB payloads are shallow.
- Guide HTML currently links to AscensionDB and can use icon tokens, but it does not guarantee local icon files, stable asset manifests, effect records, or cache-aware refreshes.

## Research Findings

### HTTP Cache Validation

HTTP has first-class conditional request validators. RFC 9110 defines `Last-Modified` as a timestamp validator and recommends sending it when it can reduce unnecessary transfers; it also defines `ETag` as an opaque representation validator. MDN documents the practical cache-refresh flow: send cached validators as `If-None-Match` or `If-Modified-Since`, use `304 Not Modified` to keep the cached body, and only replace local content on a new `200 OK` response.

Design implication:

- Use HTTP validators when AscensionDB returns them.
- Keep SHA-256 content hashes and parsed-record hashes even when validators are absent or unreliable.
- Do not refetch fresh cache entries by default.

### AscensionDB Power Payloads

The `?power` pages expose a JavaScript registration payload rather than clean JSON. The existing parser already handles this shape well enough to extract canonical tooltips, icon tokens, and link references. M1.11D should extend that parser instead of replacing it with a browser scrape.

Design implication:

- The primary canonical source remains the lightweight power payload.
- Browser automation is not part of the normal asset refresh path.
- Any HTML parsing should be isolated in tested parser functions with saved fixtures.

### Icon and Image Assets

AscensionDB spell/item records expose icon tokens, not necessarily final image URLs. The least brittle implementation is a small resolver that maps icon tokens to known local cache entries and probes a short ordered list of AscensionDB/Wow-compatible icon URL templates only when an icon is missing.

Design implication:

- Store icon token, resolved source URL, local path, content type, dimensions when available, and hash.
- Cap resolver probes to a tiny fixed set of URL templates.
- Never probe arbitrary paths or repeated failed icons in normal runs.

## Scope

In scope:

- Cache-aware fetcher for AscensionDB power pages and icon/image assets.
- Conditional GET support with `ETag` and `Last-Modified`.
- Local manifest with URL, resource kind, source ID, parser version, fetch metadata, content hash, parsed hash, and asset path.
- Stable JSONL artifacts for spell records, item records, linked effect spell records, mechanics rows, item rows, and asset records.
- Conservative CLI defaults for concurrency, timeout, stale age, and refetch limits.
- Better stage logging for scraper enrichment.
- Backward-compatible outputs so current M1.8/M1.9 commands keep working.

Out of scope:

- Full browser rendering of AscensionDB pages.
- Runtime report calls to AscensionDB.
- Large-scale crawling outside IDs discovered from builder records and linked tooltip IDs.
- Empirical stat or rotation calibration. That belongs to M1.11G/P2.

## Artifact Model

### Cache Manifest

Schema target: `coa-ascensiondb-cache-manifest-v1`

One manifest row per fetched or cached URL:

```text
cache_key
url
resource_kind
source_kind
source_id
parser_version
status
http_status
etag
last_modified
cache_control
fetched_at
validated_at
expires_at
content_sha256
parsed_sha256
body_path
asset_path
content_type
byte_length
warnings
errors
```

Statuses:

- `fetched`: new body downloaded and parsed.
- `not_modified`: server returned `304`; cached body was reused.
- `fresh_cache`: local entry was younger than `--stale-days`; no network call.
- `parse_failed`: body fetched but parser failed.
- `fetch_failed`: request failed after retry policy.
- `asset_missing`: icon/image URL could not be resolved.
- `skipped`: excluded by CLI filters or limits.

### Spell Records

Schema target: `coa-db-spell-record-v2`

Fields:

```text
schema_version
spell_id
name
icon
icon_asset_path
tooltip_html
buff_html
tooltip_text
rank
required_level
power_costs
cooldown_ms
gcd_ms
cast_time_ms
range_yards
duration_ms
period_ms
school
mechanic_tags
effect_refs
linked_spell_ids
linked_item_ids
source
source_url
cache_key
parser_version
warnings
```

The v2 record can be a superset of the current `coa_db_spell_tooltips.jsonl`. Compatibility writers should keep the old file name until downstream code migrates.

### Item Records

Schema target: `coa-db-item-record-v1`

Fields:

```text
schema_version
item_id
name
icon
icon_asset_path
quality
inventory_type
item_class
item_subclass
weapon_type
armor_type
required_level
stats
effects
tooltip_html
tooltip_text
linked_spell_ids
source_url
cache_key
warnings
```

### Asset Records

Schema target: `coa-db-asset-record-v1`

Fields:

```text
schema_version
asset_id
asset_kind
icon_token
source_url
local_path
content_type
width
height
content_sha256
byte_length
fetched_at
status
warnings
```

## Pipeline Design

Add a single cache-aware enrichment command and keep the old commands as wrappers:

```bash
npm --prefix coa_scraper run enrich-assets -- \
  --entries dist/coa_entries.enriched.jsonl \
  --out dist \
  --reports reports \
  --asset-root dist/assets \
  --manifest reports/coa_ascensiondb_cache_manifest.json \
  --stale-days 7 \
  --concurrency 4
```

Pipeline stages:

1. Load normalized/enriched entries and existing manifest.
2. Build seed URL set from entry spell IDs.
3. Fetch or reuse spell power payloads.
4. Parse spell rows and discover linked spell/item IDs.
5. Fetch or reuse linked spell/item power payloads inside a bounded discovery depth.
6. Resolve icon tokens to local assets.
7. Write spell/item/effect/asset JSONL outputs.
8. Rebuild mechanics/item artifacts from richer parsed records.
9. Write manifest, summary, and artifact manifest.

Discovery limits:

- Only fetch spell IDs present in builder data or linked from those spells/items.
- Only fetch item IDs linked from spell/item tooltips unless a future class/equipment source seeds additional items.
- Default linked-spell depth: 1.
- Default linked-item depth: 1.
- Default concurrency: 4 for public AscensionDB requests.
- Default retry: one retry for transient network failures with jitter.

## Cache Refresh Policy

Default behavior:

- If a manifest row is younger than `--stale-days`, use `fresh_cache`.
- If stale and validators exist, issue conditional GET with `If-None-Match` and/or `If-Modified-Since`.
- If the response is `304`, keep body path and parsed record, update `validated_at`, and set `not_modified`.
- If the response is `200`, write a new body, parse it, update hashes, and mark `fetched`.
- If no validators exist, use stale age plus content hash comparison after a normal GET.

CLI controls:

```text
--stale-days <days>
--force
--limit <count>
--concurrency <count>
--timeout-ms <ms>
--linked-spell-depth <n>
--linked-item-depth <n>
--skip-assets
--asset-only
--id spell:12345
--id item:67890
```

## Report Integration

The guide generator should consume local assets only:

- Spell/talent icons use `icon_asset_path` when available.
- Tooltips use sanitized local `tooltip_html`.
- Item/ability links point to AscensionDB pages but do not fetch at page load.
- Missing assets show a local fallback and emit data provenance warnings.

Tooltip HTML must preserve safe tables. The sanitizer should allow table structure tags (`table`, `thead`, `tbody`, `tr`, `th`, `td`) and strip active content (`script`, event attributes, external image injection, inline JavaScript URLs).

## Validation

Automated validation should prove:

- Cache manifest rows are stable and deterministic for fixture fetches.
- Conditional requests send expected headers when validators exist.
- `304` reuses cached content without rewriting body files.
- Parser changes preserve existing `coa_db_spell_tooltips.jsonl` compatibility fields.
- Icon resolver does not refetch successful fresh assets.
- Tooltip sanitizer renders DB tables as tables and strips unsafe markup.
- Pipeline summary includes fetched, cached, not-modified, failed, and missing-asset counts.

## Risks

- AscensionDB may not emit validators consistently. SHA-256 hashes and stale-age policy are the fallback.
- Icon URL paths may change. The resolver should isolate URL templates and cache failures to avoid repeated probing.
- The power payload shape may change. Parser versioning and fixture tests should catch this.
- Rich effect parsing may be incomplete at first. The record schema should carry raw tooltip/effect references plus parser warnings rather than pretending confidence is high.

## References

- RFC 9110 HTTP Semantics: <https://www.rfc-editor.org/rfc/rfc9110.html>
- MDN HTTP conditional requests: <https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Conditional_requests>
- Existing parser: `coa_scraper/scripts/lib/ascensiondb.mjs`
- Existing spell enrichment command: `coa_scraper/scripts/enrich-ascensiondb.mjs`
