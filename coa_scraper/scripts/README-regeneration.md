# Regenerating client-derived artifacts

This repo does **not** commit the real client-derived outputs — the CoA spell projection, the
canonical mechanics artifact, and their manifests. Per the redistribution boundary (see
[docs/DECISIONS.md](../../docs/DECISIONS.md) and the M1.14C design spec's
"Redistribution boundary and ignore rules" section), only **synthetic** fixtures, schemas, tests, and
this regeneration doc are tracked. The real artifacts are excluded by file-specific `.gitignore`
rules (see the repo root `.gitignore`) — never a blanket directory ignore, so curated files like
`reports/client_extract/coa_ca_decode_report.json` and
`reports/client_extract/client_only_adjudication.json` stay tracked.

**What a fresh clone can and cannot reproduce:**

- A fresh clone **can** reproduce the Node test suite (`npm test` in `coa_scraper/`) and the Python
  test suite (`python -m pytest`, default tier) — both run against synthetic/in-memory fixtures, no
  client and no StormLib required.
- A fresh clone **can** reproduce a **fallback** (degraded) `coa_mechanics.fallback.jsonl` — it needs
  only the Builder-scraped entries and the AscensionDB tooltip cache, both of which are already
  committed under `coa_scraper/dist/`.
- A fresh clone **cannot** reproduce the **canonical** `coa_mechanics.jsonl`, nor the
  `coa_client_spell_coa.jsonl` projection it depends on, without **your own** licensed CoA client
  install (MPQ archives) and a StormLib binding to read them. There is no way around this: the
  canonical build fails closed (`MechanicsBuildError`) if the projection is missing and
  `--allow-fallback-mechanics` was not passed, and fails closed even *with* that flag if a projection
  is present but invalid.

## Step 1 — Regenerate the client extract + CoA spell projection

Requires a local CoA client install and [StormLib](http://www.zezula.net/en/mpq/stormlib.html) (MIT).
Run from the repo root:

```bash
python -m coa_client_extract regenerate \
  --client-root "$HOME/Games/ascension-wow/drive_c/Program Files/Ascension Launcher/resources/ascension-live/Data" \
  --out reports/client_extract \
  --builder-entries coa_scraper/dist/coa_entries.jsonl
```

- `--client-root` points at the client's `Data` directory (containing the base + patch MPQ archives).
- `--out` is where every `coa-client-*` artifact is written, including
  `reports/client_extract/coa_client_spell.jsonl` (the full spell extract) and, as of M1.14C,
  `reports/client_extract/coa_client_spell_coa.jsonl` + its
  `coa_client_spell_projection.manifest.json` (the CoA-attributed projection —
  `coa_attribution.is_coa == true` rows only — that the mechanics build below consumes; see
  [docs/data/client-spell-schema.md](../../docs/data/client-spell-schema.md)).
- `--builder-entries` (optional) additionally produces `coa_builder_parity_report.json`, cross-checking
  the client's advancement graph against the Builder scrape. Omit it to run the extraction alone.
- Without StormLib available, the command fails closed and writes nothing — never a partial or
  degraded client extract.

See [coa_client_extract/README.md](../../coa_client_extract/README.md) for the full command reference
and test tiers (`-m stormlib`, `-m client`).

## Step 2 — Build the mechanics artifact

Run from `coa_scraper/`:

```bash
# Canonical build — REQUIRES Step 1's real projection + manifest to already exist.
npm run build-mechanics

# Fallback (degraded) build — no client/projection required, but the output is NOT canonical
# and is never written to the canonical coa_mechanics.jsonl filename.
npm run build-mechanics:fallback
```

- `npm run build-mechanics` invokes
  `node scripts/build-mechanics-artifacts.mjs --builder-entries dist/coa_entries.jsonl --db-spells dist/coa_db_spell_tooltips.jsonl --projection ../reports/client_extract/coa_client_spell_coa.jsonl --projection-manifest ../reports/client_extract/coa_client_spell_projection.manifest.json --out dist`.
  It requires Step 1's projection (`coa_client_spell_coa.jsonl`) and its manifest to be present and
  valid (sha256/byte-length/schema/coverage all checked before a single row is reconciled — see
  [docs/data/mechanics-schema.md](../../docs/data/mechanics-schema.md)). On success it writes
  `dist/coa_mechanics.jsonl` and `dist/coa_mechanics.manifest.json` with `"canonical": true`.
- `npm run build-mechanics:fallback` passes `--allow-fallback-mechanics`. If the projection is
  **entirely absent**, it writes a **degraded** build to the separate filenames
  `dist/coa_mechanics.fallback.jsonl` / `dist/coa_mechanics.fallback.manifest.json` (`"canonical": false`,
  `"client_source": "absent"`) — it never writes to the canonical `coa_mechanics.jsonl` name, so a
  fallback run can't silently shadow (or be mistaken for) a canonical one. If the projection **is**
  present but invalid (bad schema, checksum mismatch, per-table DBC drift on a populated field, an
  unknown school-mask bit or power-type enum, a non-`is_coa` row, or a Builder/projection coverage
  gap), the build still fails — even with `--allow-fallback-mechanics`. Only a fully-**absent**
  projection is eligible to degrade.
- The full local pipeline (`npm run pipeline:m1.9` / `pipeline:m1.9:fallback` in
  `coa_scraper/package.json`) chains scraping, enrichment, item generation, and the corresponding
  mechanics build variant, then refreshes `reports/coa_artifact_manifest.json`.

## Redistribution policy gate (forward note — mandatory before M1.16 / public release)

M1.14C does **not** decide, and does not broaden, the redistribution boundary. It records a hard
entry condition for later work: **before M1.16 consumes these artifacts, and before any canonical
public release**, one explicit policy decision must cover **all** client-derived outputs
*consistently* — at minimum `coa_client_spell_coa.jsonl`, `coa_mechanics.jsonl`, and any public-site
output that embeds facts derived from those two. This mirrors the M1.15 adjacency-domain entry
condition and must not be dropped or forgotten during later decomposition of M1.16 work. Until that
decision is made, the default remains: real client-derived artifacts are regenerated locally by each
user from their own client, are never committed, and are never republished.
