# M1.8 Source, Level, and DB Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source-category, level-provenance, and AscensionDB enrichment artifacts so lower-level CoA meta reports can distinguish exact data from approximations.

**Architecture:** Keep the builder payload authoritative for legality and add AscensionDB as a separate enrichment source. Fetch `?spell=<id>&power` and `?item=<id>&power` into cached JSONL artifacts, join those artifacts into optional enriched normalized entries, and update validation/report eligibility to consume explicit availability confidence. Keep default package tests and report runs network-free.

**Tech Stack:** Node.js ESM scripts and `node:test` for scraper/enrichment work; Python 3.11 dataclasses and `pytest` for `coa_meta` report eligibility; no new runtime dependencies.

---

## File Structure

- Create `coa_scraper/scripts/lib/ascensiondb.mjs`: parse AscensionDB `&power` payloads, strip tooltip HTML, extract linked IDs and level text, fetch/cache DB responses.
- Create `coa_scraper/scripts/enrich-ascensiondb.mjs`: CLI that reads normalized entries and writes DB enrichment artifacts.
- Create `coa_scraper/scripts/lib/source-level.mjs`: source-category and availability derivation shared by export, join, and reports.
- Create `coa_scraper/scripts/apply-db-enrichment.mjs`: join normalized entries with DB spell tooltip artifacts and write enriched entries.
- Modify `coa_scraper/scripts/export-coa-normalized.mjs`: emit builder-only `source_category`, `source_confidence`, and `availability`.
- Modify `coa_scraper/scripts/validate-normalized.mjs`: validate optional M1.8 fields and enrichment artifacts when present.
- Modify `coa_scraper/scripts/run-normalization-pipeline.mjs`: keep current no-network pipeline and add clear messaging for DB enrichment follow-up.
- Modify `coa_scraper/scripts/write-artifact-manifest.mjs`: checksum new M1.8 scripts and artifacts.
- Modify `coa_scraper/scrape-coa-network.mjs`: add CLI options for headless/noninteractive capture.
- Modify `coa_scraper/package.json`: add `enrich-db`, `apply-db-enrichment`, and `pipeline:m1.8` scripts.
- Modify `coa_meta/domain.py`: expose optional `availability` and `source_category` from raw normalized entries.
- Modify `coa_meta/repository.py`: populate those optional fields without breaking old fixtures.
- Modify `coa_meta/reporting.py`: use `availability.effective_required_level` when confidence is usable and emit granular lower-level warnings.
- Create or modify Node tests in `coa_scraper/tests/pipeline-scripts.test.mjs`.
- Modify Python tests in `tests/test_report_eligibility.py`.
- Modify docs in `docs/data/normalized-schema.md`, `docs/MODULES.md`, and `docs/README.md`.

## Task 1: AscensionDB Parser Tests

**Files:**
- Modify: `coa_scraper/tests/pipeline-scripts.test.mjs`
- Create: `coa_scraper/scripts/lib/ascensiondb.mjs`

- [ ] **Step 1: Add parser imports to the test file**

At the top of `coa_scraper/tests/pipeline-scripts.test.mjs`, add:

```js
import {
  extractLinkedIds,
  parsePowerPayload,
  stripTooltipHtml
} from "../scripts/lib/ascensiondb.mjs";
```

- [ ] **Step 2: Add fixture strings to the test file**

Add these constants after `writeValidationFixture`:

```js
const SPELL_POWER_FIXTURE = `$WowheadPower.registerSpell(92117, 0, {
    "name_enus": "Dream Flowers",
    "icon": "inv_legion_faction_dreamweavers",
    "tooltip_enus": "<table><tr><td><span class=\\"q\\"><span style=\\"color: #66DDFF;\\">Level 10 Passive</span><br />Your damaging critical strikes spawn a <a href=\\"?spell=561005\\">Dream Flower</a>.</span></td></tr></table><!--?92117:1:1:80-->",
    "spells_enus": [],
    "buff_enus": "",
    "buffspells_enus": []
});`;

const EMPTY_SPELL_POWER_FIXTURE = `$WowheadPower.registerSpell(804137, 0, {});`;

const ITEM_POWER_FIXTURE = `$WowheadPower.registerItem(23887, 0, {
    "name_enus": "Schematic: Rocket Boots Xtreme",
    "quality": 3,
    "icon": "inv_boots_09",
    "tooltip_enus": "<table><tr><td><b class=\\"q3\\">Schematic: Rocket Boots Xtreme</b><br />Requires Level 58<br /><span class=\\"q2\\">Use: <a href=\\"?spell=30556\\">Teaches you how to make Rocket Boots Xtreme.</a></span><br /><span class=\\"q3\\"><a href=\\"?item=23824\\">Rocket Boots Xtreme</a></span></td></tr></table>"
});`;
```

- [ ] **Step 3: Add tests for spell, empty spell, and item payload parsing**

Add these tests:

```js
test("AscensionDB parser reads spell power payloads", () => {
  const parsed = parsePowerPayload(SPELL_POWER_FIXTURE, {
    kind: "spell",
    id: 92117,
    url: "https://db.ascension.gg/?spell=92117&power"
  });

  assert.equal(parsed.kind, "spell");
  assert.equal(parsed.id, 92117);
  assert.equal(parsed.status, "matched");
  assert.equal(parsed.name, "Dream Flowers");
  assert.equal(parsed.icon, "inv_legion_faction_dreamweavers");
  assert.equal(parsed.tooltip_level, 10);
  assert.deepEqual(parsed.linked_spell_ids, [561005]);
  assert.deepEqual(parsed.linked_item_ids, []);
  assert.match(parsed.tooltip_text, /Level 10 Passive/);
  assert.equal(parsed.provenance.url, "https://db.ascension.gg/?spell=92117&power");
});

test("AscensionDB parser classifies empty spell registrations", () => {
  const parsed = parsePowerPayload(EMPTY_SPELL_POWER_FIXTURE, {
    kind: "spell",
    id: 804137,
    url: "https://db.ascension.gg/?spell=804137&power"
  });

  assert.equal(parsed.kind, "spell");
  assert.equal(parsed.id, 804137);
  assert.equal(parsed.status, "empty_registration");
  assert.equal(parsed.name, null);
  assert.equal(parsed.tooltip_html, "");
  assert.deepEqual(parsed.linked_spell_ids, []);
});

test("AscensionDB parser reads item power payloads", () => {
  const parsed = parsePowerPayload(ITEM_POWER_FIXTURE, {
    kind: "item",
    id: 23887,
    url: "https://db.ascension.gg/?item=23887&power"
  });

  assert.equal(parsed.kind, "item");
  assert.equal(parsed.id, 23887);
  assert.equal(parsed.status, "matched");
  assert.equal(parsed.name, "Schematic: Rocket Boots Xtreme");
  assert.equal(parsed.required_level, 58);
  assert.deepEqual(parsed.linked_spell_ids, [30556]);
  assert.deepEqual(parsed.linked_item_ids, [23824]);
});
```

- [ ] **Step 4: Add utility extraction tests**

Add:

```js
test("tooltip utilities strip HTML and extract linked ids", () => {
  const html = `<span>Requires Level 20</span><a href="?spell=100">Spell</a><a href="?item=200">Item</a>`;

  assert.equal(stripTooltipHtml(html), "Requires Level 20 Spell Item");
  assert.deepEqual(extractLinkedIds(html, "spell"), [100]);
  assert.deepEqual(extractLinkedIds(html, "item"), [200]);
});
```

- [ ] **Step 5: Run the focused Node test and verify it fails**

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: fail with an import or missing export error for `ascensiondb.mjs`.

## Task 2: AscensionDB Parser Implementation

**Files:**
- Create: `coa_scraper/scripts/lib/ascensiondb.mjs`
- Test: `coa_scraper/tests/pipeline-scripts.test.mjs`

- [ ] **Step 1: Implement parser utilities**

Create `coa_scraper/scripts/lib/ascensiondb.mjs`:

```js
import fs from "node:fs";
import path from "node:path";

const DB_HOST = "https://db.ascension.gg";

export function powerUrl(kind, id) {
  if (kind !== "spell" && kind !== "item") {
    throw new Error(`Unsupported AscensionDB kind: ${kind}`);
  }
  return `${DB_HOST}/?${kind}=${id}&power`;
}

export function stripTooltipHtml(html) {
  return String(html || "")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
}

export function extractLinkedIds(html, kind) {
  const rx = new RegExp(`href=["']\\?${kind}=(\\d+)["']`, "g");
  const ids = [];
  for (const match of String(html || "").matchAll(rx)) {
    const id = Number(match[1]);
    if (Number.isFinite(id) && !ids.includes(id)) ids.push(id);
  }
  return ids;
}

export function extractTooltipLevel(text) {
  const match = String(text || "").match(/\bLevel\s+(\d+)\b/i);
  return match ? Number(match[1]) : null;
}

function parseRegisterCall(payload, expectedKind, expectedId) {
  const kindName = expectedKind === "spell" ? "registerSpell" : "registerItem";
  const rx = new RegExp(`\\$WowheadPower\\.${kindName}\\((\\d+),\\s*(\\d+),\\s*([\\s\\S]*)\\);\\s*$`);
  const match = String(payload || "").trim().match(rx);
  if (!match) {
    return null;
  }
  const id = Number(match[1]);
  if (id !== Number(expectedId)) {
    throw new Error(`AscensionDB payload id ${id} did not match requested id ${expectedId}`);
  }
  return JSON.parse(match[3]);
}

export function parsePowerPayload(payload, { kind, id, url, fetchedAt = new Date().toISOString() }) {
  const data = parseRegisterCall(payload, kind, id);
  if (data === null) {
    return {
      kind,
      id,
      status: "not_found",
      name: null,
      icon: null,
      tooltip_html: "",
      tooltip_text: "",
      tooltip_level: null,
      required_level: null,
      linked_spell_ids: [],
      linked_item_ids: [],
      raw: String(payload || ""),
      provenance: { url, fetched_at: fetchedAt }
    };
  }

  if (Object.keys(data).length === 0) {
    return {
      kind,
      id,
      status: "empty_registration",
      name: null,
      icon: null,
      tooltip_html: "",
      tooltip_text: "",
      tooltip_level: null,
      required_level: null,
      linked_spell_ids: [],
      linked_item_ids: [],
      raw: data,
      provenance: { url, fetched_at: fetchedAt }
    };
  }

  const tooltipHtml = data.tooltip_enus || "";
  const tooltipText = stripTooltipHtml(tooltipHtml);
  const tooltipLevel = extractTooltipLevel(tooltipText);
  const requiredLevelMatch = tooltipText.match(/\bRequires Level\s+(\d+)\b/i);
  return {
    kind,
    id,
    status: "matched",
    name: data.name_enus || null,
    icon: data.icon || null,
    quality: data.quality ?? null,
    tooltip_html: tooltipHtml,
    tooltip_text: tooltipText,
    tooltip_level: tooltipLevel,
    required_level: requiredLevelMatch ? Number(requiredLevelMatch[1]) : tooltipLevel,
    linked_spell_ids: extractLinkedIds(tooltipHtml, "spell"),
    linked_item_ids: extractLinkedIds(tooltipHtml, "item"),
    buff_tooltip_html: data.buff_enus || "",
    raw: data,
    provenance: { url, fetched_at: fetchedAt }
  };
}

export function readJsonl(filePath) {
  if (!fs.existsSync(filePath)) return [];
  const text = fs.readFileSync(filePath, "utf8").trim();
  if (!text) return [];
  return text.split("\n").filter(Boolean).map(line => JSON.parse(line));
}

export function writeJsonl(filePath, rows) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, rows.map(row => JSON.stringify(row)).join("\n") + "\n");
}
```

- [ ] **Step 2: Run parser tests**

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: all Node unit tests pass.

- [ ] **Step 3: Commit parser work**

Run:

```bash
git add coa_scraper/scripts/lib/ascensiondb.mjs coa_scraper/tests/pipeline-scripts.test.mjs
git commit -m "feat: add AscensionDB power parser"
```

## Task 3: DB Enrichment Fetcher and CLI Tests

**Files:**
- Modify: `coa_scraper/tests/pipeline-scripts.test.mjs`
- Modify: `coa_scraper/scripts/lib/ascensiondb.mjs`
- Create: `coa_scraper/scripts/enrich-ascensiondb.mjs`

- [ ] **Step 1: Add new imports**

Extend the `ascensiondb.mjs` import in `coa_scraper/tests/pipeline-scripts.test.mjs`:

```js
import {
  buildEnrichmentRows,
  extractLinkedIds,
  parsePowerPayload,
  stripTooltipHtml
} from "../scripts/lib/ascensiondb.mjs";
```

- [ ] **Step 2: Add a test for enrichment row building**

Add:

```js
test("DB enrichment rows use fetch results and classify name differences", async () => {
  const entries = [
    validNode({ entry_id: 1, spell_id: 92117, name: "Dream Flowers" }),
    validNode({ entry_id: 2, spell_id: 804137, name: "Headhunter's Spear" })
  ];
  const responses = new Map([
    [92117, SPELL_POWER_FIXTURE],
    [804137, EMPTY_SPELL_POWER_FIXTURE]
  ]);
  const fetchPower = async ({ id }) => responses.get(id);

  const rows = await buildEnrichmentRows({
    entries,
    kind: "spell",
    fetchPower,
    fetchedAt: "2026-07-04T00:00:00.000Z"
  });

  assert.equal(rows.length, 2);
  assert.equal(rows[0].status, "matched");
  assert.equal(rows[0].name_match, true);
  assert.equal(rows[1].status, "empty_registration");
  assert.equal(rows[1].name_match, false);
});
```

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: fail because `buildEnrichmentRows` is not exported.

## Task 4: DB Enrichment Fetcher and CLI Implementation

**Files:**
- Modify: `coa_scraper/scripts/lib/ascensiondb.mjs`
- Create: `coa_scraper/scripts/enrich-ascensiondb.mjs`
- Modify: `coa_scraper/package.json`

- [ ] **Step 1: Add enrichment helper functions**

Append to `coa_scraper/scripts/lib/ascensiondb.mjs`:

```js
export function normalizeName(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

export function uniqueSpellIds(entries) {
  return [...new Set(entries.map(entry => Number(entry.spell_id)).filter(Number.isFinite))].sort((a, b) => a - b);
}

export async function buildEnrichmentRows({ entries, kind, fetchPower, fetchedAt = new Date().toISOString() }) {
  const ids = kind === "spell"
    ? uniqueSpellIds(entries)
    : [...new Set(entries.map(entry => Number(entry.item_id)).filter(Number.isFinite))].sort((a, b) => a - b);
  const byId = new Map(entries.map(entry => [Number(kind === "spell" ? entry.spell_id : entry.item_id), entry]));
  const rows = [];

  for (const id of ids) {
    const url = powerUrl(kind, id);
    let parsed;
    try {
      const payload = await fetchPower({ kind, id, url });
      parsed = parsePowerPayload(payload, { kind, id, url, fetchedAt });
    } catch (error) {
      parsed = {
        kind,
        id,
        status: "fetch_failed",
        name: null,
        icon: null,
        tooltip_html: "",
        tooltip_text: "",
        tooltip_level: null,
        required_level: null,
        linked_spell_ids: [],
        linked_item_ids: [],
        raw: String(error.message || error),
        provenance: { url, fetched_at: fetchedAt }
      };
    }

    const entry = byId.get(id);
    const nameMatch = Boolean(parsed.name && entry && normalizeName(parsed.name) === normalizeName(entry.name));
    rows.push({
      ...parsed,
      entry_id: entry?.entry_id ?? null,
      builder_name: entry?.name ?? null,
      name_match: nameMatch
    });
  }

  return rows;
}

export async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.text();
}
```

- [ ] **Step 2: Create the CLI script**

Create `coa_scraper/scripts/enrich-ascensiondb.mjs`:

```js
#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

import {
  buildEnrichmentRows,
  fetchText,
  readJsonl,
  writeJsonl
} from "./lib/ascensiondb.mjs";
import { writeJson } from "./lib/artifacts.mjs";

const entriesPath = process.argv[2] || "dist/coa_entries.jsonl";
const distDir = process.argv[3] || "dist";
const reportsDir = process.argv[4] || "reports";

const entries = readJsonl(entriesPath);
const fetchedAt = new Date().toISOString();
const rows = await buildEnrichmentRows({
  entries,
  kind: "spell",
  fetchedAt,
  fetchPower: ({ url }) => fetchText(url)
});

const outPath = path.join(distDir, "coa_db_spell_tooltips.jsonl");
writeJsonl(outPath, rows);

const counts = rows.reduce((acc, row) => {
  acc[row.status] = (acc[row.status] || 0) + 1;
  return acc;
}, {});

const summary = {
  schema_version: "coa-db-enrichment-summary-v1",
  fetched_at: fetchedAt,
  entries_path: entriesPath,
  spell_count: rows.length,
  status_counts: counts,
  name_mismatch_count: rows.filter(row => row.status === "matched" && !row.name_match).length,
  tooltip_level_count: rows.filter(row => row.tooltip_level !== null).length,
  output: outPath
};

fs.mkdirSync(reportsDir, { recursive: true });
writeJson(path.join(reportsDir, "coa_db_enrichment_summary.json"), summary);

console.log(JSON.stringify(summary, null, 2));
```

- [ ] **Step 3: Add package scripts**

In `coa_scraper/package.json`, add:

```json
"enrich-db": "node scripts/enrich-ascensiondb.mjs dist/coa_entries.jsonl dist reports",
"pipeline:m1.8": "npm run pipeline && npm run enrich-db"
```

Keep the existing `pipeline` script unchanged.

- [ ] **Step 4: Run unit tests**

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: all Node unit tests pass.

- [ ] **Step 5: Run optional network smoke**

Run only when network access is available:

```bash
npm --prefix coa_scraper run enrich-db
```

Expected: writes `coa_scraper/dist/coa_db_spell_tooltips.jsonl` and `coa_scraper/reports/coa_db_enrichment_summary.json`.

- [ ] **Step 6: Commit DB enrichment CLI**

Run:

```bash
git add coa_scraper/scripts/lib/ascensiondb.mjs coa_scraper/scripts/enrich-ascensiondb.mjs coa_scraper/package.json coa_scraper/tests/pipeline-scripts.test.mjs
git commit -m "feat: add AscensionDB enrichment artifact writer"
```

## Task 5: Source and Availability Derivation Tests

**Files:**
- Modify: `coa_scraper/tests/pipeline-scripts.test.mjs`
- Create: `coa_scraper/scripts/lib/source-level.mjs`

- [ ] **Step 1: Add imports**

Add:

```js
import {
  classifySourceCategory,
  deriveAvailability,
  summarizeMetadataTabs
} from "../scripts/lib/source-level.mjs";
```

- [ ] **Step 2: Add source category tests**

Add:

```js
test("source category distinguishes spec tree, class pool, and unknown nodes", () => {
  assert.equal(classifySourceCategory(validNode({ tab_name: "Stalking" })), "spec_tree");
  assert.equal(classifySourceCategory(validNode({ tab_name: "Class" })), "class_pool");
  assert.equal(classifySourceCategory(validNode({ tab_name: "" })), "unknown");
});
```

- [ ] **Step 3: Add availability derivation tests**

Add:

```js
test("availability uses builder level when explicit", () => {
  const availability = deriveAvailability({
    builderRequiredLevel: 40,
    builderTooltipText: "Level 40 Passive",
    dbTooltipLevel: null
  });

  assert.equal(availability.effective_required_level, 40);
  assert.equal(availability.level_source, "builder_required_level");
  assert.equal(availability.level_confidence, "high");
});

test("availability upgrades zero builder level when tooltip has level text", () => {
  const availability = deriveAvailability({
    builderRequiredLevel: 0,
    builderTooltipText: "Level 10 Passive",
    dbTooltipLevel: 10
  });

  assert.equal(availability.effective_required_level, 10);
  assert.equal(availability.level_source, "db_tooltip");
  assert.equal(availability.level_confidence, "medium");
  assert(availability.notes.includes("builder_required_level_zero_but_tooltip_has_level"));
});
```

- [ ] **Step 4: Add metadata tab summary test**

Add:

```js
test("metadata summary reports tabs without node rows", () => {
  const classes = [
    validClass({
      tabs: [
        { tab_id: 77, tab_name: "Stalking", sort_order: 2, nominal_essence_kind: "talent" },
        { tab_id: 1, tab_name: "None", sort_order: 0, nominal_essence_kind: "talent" }
      ]
    })
  ];
  const rows = summarizeMetadataTabs(classes, [validNode({ tab_id: 77, tab_name: "Stalking" })]);

  assert.deepEqual(rows.tabs_without_nodes.map(row => row.tab_name), ["None"]);
});
```

- [ ] **Step 5: Run tests and verify failure**

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: fail because `source-level.mjs` does not exist.

## Task 6: Source and Availability Derivation Implementation

**Files:**
- Create: `coa_scraper/scripts/lib/source-level.mjs`
- Modify: `coa_scraper/scripts/export-coa-normalized.mjs`

- [ ] **Step 1: Create `source-level.mjs`**

Create `coa_scraper/scripts/lib/source-level.mjs`:

```js
export function extractLevelText(text) {
  const match = String(text || "").match(/\bLevel\s+(\d+)\b/i);
  return match ? Number(match[1]) : null;
}

export function classifySourceCategory(node) {
  if (!node || !node.tab_name) return "unknown";
  if (node.tab_name === "Class") return "class_pool";
  if (node.tab_name === "None") return "metadata_only";
  return "spec_tree";
}

export function sourceConfidenceFor(category) {
  if (category === "spec_tree" || category === "class_pool") return "high";
  if (category === "metadata_only") return "medium";
  return "low";
}

export function deriveAvailability({ builderRequiredLevel, builderTooltipText, dbTooltipLevel = null }) {
  const builderLevel = Number(builderRequiredLevel || 0);
  const tooltipLevel = extractLevelText(builderTooltipText);
  const notes = [];

  if (builderLevel > 0) {
    if (dbTooltipLevel !== null && dbTooltipLevel !== builderLevel) notes.push("db_tooltip_level_conflicts_with_builder_required_level");
    return {
      builder_required_level: builderLevel,
      tooltip_required_level: tooltipLevel,
      db_tooltip_required_level: dbTooltipLevel,
      effective_required_level: builderLevel,
      level_source: "builder_required_level",
      level_confidence: "high",
      notes
    };
  }

  if (dbTooltipLevel !== null) {
    notes.push("builder_required_level_zero_but_tooltip_has_level");
    return {
      builder_required_level: builderLevel,
      tooltip_required_level: tooltipLevel,
      db_tooltip_required_level: dbTooltipLevel,
      effective_required_level: dbTooltipLevel,
      level_source: "db_tooltip",
      level_confidence: "medium",
      notes
    };
  }

  if (tooltipLevel !== null) {
    notes.push("builder_required_level_zero_but_tooltip_has_level");
    return {
      builder_required_level: builderLevel,
      tooltip_required_level: tooltipLevel,
      db_tooltip_required_level: null,
      effective_required_level: tooltipLevel,
      level_source: "builder_tooltip",
      level_confidence: "medium",
      notes
    };
  }

  return {
    builder_required_level: builderLevel,
    tooltip_required_level: null,
    db_tooltip_required_level: null,
    effective_required_level: builderLevel,
    level_source: builderLevel === 0 ? "builder_required_level_zero_or_unknown" : "builder_required_level",
    level_confidence: builderLevel === 0 ? "low" : "high",
    notes: builderLevel === 0 ? ["required_level_zero_means_available_or_unknown"] : []
  };
}

export function summarizeMetadataTabs(classes, entries) {
  const nodeTabs = new Set(entries.map(entry => `${entry.class_name}\t${entry.tab_id}\t${entry.tab_name}`));
  const tabs = [];
  for (const cls of classes || []) {
    for (const tab of cls.tabs || []) {
      const key = `${cls.class_name}\t${tab.tab_id}\t${tab.tab_name}`;
      tabs.push({
        class_name: cls.class_name,
        tab_id: tab.tab_id,
        tab_name: tab.tab_name,
        sort_order: tab.sort_order,
        nominal_essence_kind: tab.nominal_essence_kind,
        has_nodes: nodeTabs.has(key)
      });
    }
  }
  return {
    schema_version: "coa-metadata-tab-report-v1",
    tab_count: tabs.length,
    tabs_without_nodes: tabs.filter(tab => !tab.has_nodes),
    tabs
  };
}
```

- [ ] **Step 2: Wire builder-only fields into `export-coa-normalized.mjs`**

At the top of `coa_scraper/scripts/export-coa-normalized.mjs`, add:

```js
import {
  classifySourceCategory,
  deriveAvailability,
  sourceConfidenceFor
} from "./lib/source-level.mjs";
```

Before constructing `rec`, add:

```js
    const sourceCategory = classifySourceCategory({
      tab_name: ownerTab?.tabName ?? null
    });
    const builderAvailability = deriveAvailability({
      builderRequiredLevel: discoverNumeric(entry, ["requiredLevel", "required_level", "level"]),
      builderTooltipText: description
    });
```

Inside `rec`, after `raw: entry`, add:

```js
      source_category: sourceCategory,
      source_confidence: sourceConfidenceFor(sourceCategory),
      availability: builderAvailability,
```

Keep the existing `required_level` top-level field unchanged.

- [ ] **Step 3: Run tests**

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: all Node unit tests pass.

- [ ] **Step 4: Regenerate current local artifacts**

Run:

```bash
npm --prefix coa_scraper run pipeline
```

Expected: pipeline passes and normalized entries now include builder-only M1.8 source/availability fields.

- [ ] **Step 5: Commit source-level fields**

Run:

```bash
git add coa_scraper/scripts/lib/source-level.mjs coa_scraper/scripts/export-coa-normalized.mjs coa_scraper/tests/pipeline-scripts.test.mjs coa_scraper/dist coa_scraper/reports
git commit -m "feat: add source and availability metadata"
```

## Task 7: Apply DB Enrichment to Normalized Entries

**Files:**
- Create: `coa_scraper/scripts/apply-db-enrichment.mjs`
- Modify: `coa_scraper/package.json`
- Modify: `coa_scraper/tests/pipeline-scripts.test.mjs`

- [ ] **Step 1: Add a test helper for join behavior**

In `coa_scraper/tests/pipeline-scripts.test.mjs`, add:

```js
function enrichedSpellRow(overrides = {}) {
  return {
    kind: "spell",
    id: 92117,
    entry_id: 123,
    builder_name: "Test Node",
    status: "matched",
    name: "Test Node",
    name_match: true,
    icon: "inv_test",
    tooltip_html: "<span>Level 10 Passive</span>",
    tooltip_text: "Level 10 Passive",
    tooltip_level: 10,
    required_level: 10,
    linked_spell_ids: [],
    linked_item_ids: [],
    provenance: {
      url: "https://db.ascension.gg/?spell=92117&power",
      fetched_at: "2026-07-04T00:00:00Z"
    },
    ...overrides
  };
}
```

- [ ] **Step 2: Add a test for enriched entry output**

Add:

```js
test("DB enrichment can be joined into normalized entries", async () => {
  const { applyDbEnrichmentToEntries } = await import("../scripts/apply-db-enrichment.mjs");
  const rows = applyDbEnrichmentToEntries(
    [validNode({ spell_id: 92117, required_level: 0, description_text: "Level 10 Passive" })],
    [enrichedSpellRow()]
  );

  assert.equal(rows[0].db_enrichment.status, "matched");
  assert.equal(rows[0].availability.effective_required_level, 10);
  assert.equal(rows[0].availability.level_source, "db_tooltip");
});
```

- [ ] **Step 3: Create `apply-db-enrichment.mjs`**

Create `coa_scraper/scripts/apply-db-enrichment.mjs`:

```js
#!/usr/bin/env node
import { fileURLToPath } from "node:url";
import path from "node:path";

import { readJsonl, writeJsonl } from "./lib/ascensiondb.mjs";
import { deriveAvailability } from "./lib/source-level.mjs";

export function applyDbEnrichmentToEntries(entries, spellRows) {
  const bySpellId = new Map(spellRows.map(row => [Number(row.id), row]));
  return entries.map(entry => {
    const db = bySpellId.get(Number(entry.spell_id)) || null;
    if (!db) return entry;
    const availability = deriveAvailability({
      builderRequiredLevel: entry.required_level,
      builderTooltipText: entry.description_text,
      dbTooltipLevel: db.tooltip_level
    });
    return {
      ...entry,
      availability,
      db_enrichment: {
        spell_id: db.id,
        status: db.status,
        name: db.name,
        name_match: db.name_match,
        icon: db.icon,
        tooltip_html: db.tooltip_html,
        tooltip_text: db.tooltip_text,
        buff_tooltip_html: db.buff_tooltip_html || "",
        linked_spell_ids: db.linked_spell_ids || [],
        linked_item_ids: db.linked_item_ids || [],
        detail_status: "not_fetched",
        provenance: db.provenance
      }
    };
  });
}

function isCliEntryPoint() {
  return process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]);
}

if (isCliEntryPoint()) {
  const entriesPath = process.argv[2] || "dist/coa_entries.jsonl";
  const spellRowsPath = process.argv[3] || "dist/coa_db_spell_tooltips.jsonl";
  const outPath = process.argv[4] || "dist/coa_entries.enriched.jsonl";
  const entries = readJsonl(entriesPath);
  const spellRows = readJsonl(spellRowsPath);
  writeJsonl(outPath, applyDbEnrichmentToEntries(entries, spellRows));
  console.log(`Wrote ${outPath}`);
}
```

- [ ] **Step 4: Add package script**

In `coa_scraper/package.json`, add:

```json
"apply-db-enrichment": "node scripts/apply-db-enrichment.mjs dist/coa_entries.jsonl dist/coa_db_spell_tooltips.jsonl dist/coa_entries.enriched.jsonl"
```

Update `pipeline:m1.8` to:

```json
"pipeline:m1.8": "npm run pipeline && npm run enrich-db && npm run apply-db-enrichment"
```

- [ ] **Step 5: Run tests**

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: all Node unit tests pass.

- [ ] **Step 6: Commit DB join script**

Run:

```bash
git add coa_scraper/scripts/apply-db-enrichment.mjs coa_scraper/package.json coa_scraper/tests/pipeline-scripts.test.mjs
git commit -m "feat: join DB enrichment into entries"
```

## Task 8: Validator and Reports for M1.8 Data Quality

**Files:**
- Modify: `coa_scraper/scripts/validate-normalized.mjs`
- Modify: `coa_scraper/scripts/run-normalization-pipeline.mjs`
- Modify: `coa_scraper/scripts/write-artifact-manifest.mjs`
- Create: `coa_scraper/scripts/write-source-level-report.mjs`
- Modify: `coa_scraper/package.json`
- Modify: `coa_scraper/tests/pipeline-scripts.test.mjs`

- [ ] **Step 1: Add validator tests for optional M1.8 fields**

In `coa_scraper/tests/pipeline-scripts.test.mjs`, add:

```js
test("validator accepts optional M1.8 source and availability fields", () => {
  const dir = tempProject();
  const { dist, reports } = writeValidationFixture(dir, {
    source_category: "spec_tree",
    source_confidence: "high",
    availability: {
      builder_required_level: 0,
      tooltip_required_level: 10,
      db_tooltip_required_level: null,
      effective_required_level: 10,
      level_source: "builder_tooltip",
      level_confidence: "medium",
      notes: ["builder_required_level_zero_but_tooltip_has_level"]
    }
  });

  const summary = validateNormalizedArtifacts({ distDir: dist, reportsDir: reports });

  assert.equal(summary.status, "pass");
  assert.equal(summary.m1_8_source_records, 1);
});
```

- [ ] **Step 2: Update validator implementation**

In `coa_scraper/scripts/validate-normalized.mjs`, initialize:

```js
let m18SourceRecords = 0;
let m18AvailabilityRecords = 0;
```

Inside the entry loop, add:

```js
    if (e.source_category !== undefined) {
      m18SourceRecords++;
      if (!["spec_tree", "class_pool", "trainer", "misc_system", "metadata_only", "unknown"].includes(e.source_category)) {
        fail(`${label} invalid source_category ${e.source_category}`);
      }
    }
    if (e.availability !== undefined) {
      m18AvailabilityRecords++;
      if (typeof e.availability !== "object" || e.availability === null) fail(`${label} availability must be object`);
      else {
        if (typeof e.availability.effective_required_level !== "number") {
          fail(`${label} availability.effective_required_level is not numeric`);
        }
        if (!["high", "medium", "low"].includes(e.availability.level_confidence)) {
          fail(`${label} invalid availability.level_confidence ${e.availability.level_confidence}`);
        }
      }
    }
```

In the summary object, add:

```js
    m1_8_source_records: m18SourceRecords,
    m1_8_availability_records: m18AvailabilityRecords,
```

- [ ] **Step 3: Create source-level report CLI**

Create `coa_scraper/scripts/write-source-level-report.mjs`:

```js
#!/usr/bin/env node
import path from "node:path";

import { loadJson, writeJson } from "./lib/artifacts.mjs";
import { readJsonl } from "./lib/ascensiondb.mjs";
import { summarizeMetadataTabs } from "./lib/source-level.mjs";

const entriesPath = process.argv[2] || "dist/coa_entries.jsonl";
const classesPath = process.argv[3] || "dist/coa_classes.json";
const reportsDir = process.argv[4] || "reports";

const entries = readJsonl(entriesPath);
const classes = loadJson(classesPath);
const metadata = summarizeMetadataTabs(classes, entries);
const levelMismatches = entries.filter(entry =>
  Number(entry.required_level || 0) === 0 &&
  entry.availability?.tooltip_required_level !== null &&
  entry.availability?.tooltip_required_level !== undefined
);
const classPoolUnknown = entries.filter(entry =>
  entry.source_category === "class_pool" &&
  entry.availability?.level_confidence === "low"
);

const report = {
  schema_version: "coa-source-level-report-v1",
  record_count: entries.length,
  metadata_tab_count: metadata.tab_count,
  metadata_tabs_without_nodes: metadata.tabs_without_nodes,
  required_level_zero_with_tooltip_level_count: levelMismatches.length,
  required_level_zero_with_tooltip_level_samples: levelMismatches.slice(0, 25).map(entry => ({
    class_name: entry.class_name,
    tab_name: entry.tab_name,
    entry_id: entry.entry_id,
    spell_id: entry.spell_id,
    name: entry.name,
    tooltip_required_level: entry.availability.tooltip_required_level
  })),
  class_pool_unknown_level_count: classPoolUnknown.length,
  class_pool_unknown_level_samples: classPoolUnknown.slice(0, 25).map(entry => ({
    class_name: entry.class_name,
    entry_id: entry.entry_id,
    spell_id: entry.spell_id,
    name: entry.name
  }))
};

writeJson(path.join(reportsDir, "coa_metadata_tab_report.json"), metadata);
writeJson(path.join(reportsDir, "coa_source_level_report.json"), report);
console.log(JSON.stringify(report, null, 2));
```

- [ ] **Step 4: Add report script and pipeline step**

In `coa_scraper/package.json`, add:

```json
"source-level-report": "node scripts/write-source-level-report.mjs dist/coa_entries.jsonl dist/coa_classes.json reports"
```

In `coa_scraper/scripts/run-normalization-pipeline.mjs`, add this step after `validate normalized artifacts` and before `write artifact manifest`:

```js
  ["write source level report", ["node", "scripts/write-source-level-report.mjs", "dist/coa_entries.jsonl", "dist/coa_classes.json", "reports"]],
```

In `coa_scraper/scripts/write-artifact-manifest.mjs`, add these script paths to `scriptPaths`:

```js
  "scripts/lib/ascensiondb.mjs",
  "scripts/lib/source-level.mjs",
  "scripts/enrich-ascensiondb.mjs",
  "scripts/apply-db-enrichment.mjs",
  "scripts/write-source-level-report.mjs",
```

Add these artifact paths to `artifactPaths`:

```js
  "reports/coa_source_level_report.json",
  "reports/coa_metadata_tab_report.json",
  "reports/coa_db_enrichment_summary.json",
  "dist/coa_db_spell_tooltips.jsonl",
  "dist/coa_entries.enriched.jsonl",
```

- [ ] **Step 5: Run tests and pipeline**

Run:

```bash
npm --prefix coa_scraper run unit-test
npm --prefix coa_scraper run pipeline
```

Expected: tests pass; pipeline writes `coa_source_level_report.json` and `coa_metadata_tab_report.json`.

- [ ] **Step 6: Commit validation and reports**

Run:

```bash
git add coa_scraper/scripts/validate-normalized.mjs coa_scraper/scripts/write-source-level-report.mjs coa_scraper/scripts/run-normalization-pipeline.mjs coa_scraper/scripts/write-artifact-manifest.mjs coa_scraper/package.json coa_scraper/tests/pipeline-scripts.test.mjs coa_scraper/dist coa_scraper/reports
git commit -m "feat: report source and level data quality"
```

## Task 9: Report Eligibility Uses Effective Required Level

**Files:**
- Modify: `coa_meta/domain.py`
- Modify: `coa_meta/repository.py`
- Modify: `coa_meta/reporting.py`
- Modify: `tests/test_report_eligibility.py`

- [ ] **Step 1: Add Python eligibility test**

In `tests/test_report_eligibility.py`, add:

```python
def test_level_filtering_uses_medium_confidence_effective_required_level():
    repo = TalentRepository.from_entries(META_NODES)
    node = repo.node_by_id(102)
    node.raw["availability"] = {
        "effective_required_level": 50,
        "level_confidence": "medium",
        "level_source": "db_tooltip",
        "notes": []
    }
    policy = EligibilityPolicy()
    scope = BuildScope(
        class_name="Testclass",
        spec_id=11,
        spec_name="Damage",
        level=15,
        encounter_profile_id="baseline_single_target",
        search_profile_id="default",
        scoring_profile_id="auto",
        apl_profile_id="auto",
        top=3,
    )

    eligible = policy.eligible_node_ids(repo, scope)

    assert 102 not in eligible
```

- [ ] **Step 2: Run focused Python test and verify failure**

Run:

```bash
python -m pytest tests/test_report_eligibility.py::test_level_filtering_uses_medium_confidence_effective_required_level -q
```

Expected: fail because `EligibilityPolicy` still only reads `node.required_level`.

- [ ] **Step 3: Add optional domain fields**

In `coa_meta/domain.py`, add fields to `TalentNode` after `description_text`:

```python
    source_category: str = ""
    availability: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)
```

- [ ] **Step 4: Populate fields in repository**

In `coa_meta/repository.py`, add to `TalentNode(...)`:

```python
        source_category=raw.get("source_category") or "",
        availability=dict(raw.get("availability") or {}),
```

- [ ] **Step 5: Add level helper in reporting**

In `coa_meta/reporting.py`, add near `slugify_key`:

```python
def effective_required_level(node: TalentNode) -> int:
    availability = node.availability or {}
    confidence = availability.get("level_confidence")
    level = availability.get("effective_required_level")
    if confidence in {"high", "medium"} and isinstance(level, int):
        return level
    return node.required_level
```

Change `eligible_node_ids` to:

```python
            if effective_required_level(node) > scope.level:
                continue
```

- [ ] **Step 6: Update scope warnings**

Change `scope_warnings` to:

```python
        class_pool_nodes = [
            node for node in repository.nodes_for_class(scope.class_name)
            if node.tab_name == "Class"
        ]
        if scope.level < 60 and any(not node.availability for node in class_pool_nodes):
            warnings.append("class_pool_level_gating_incomplete")
            warnings.append("shared_class_level_gating_incomplete")
```

Keep the old warning as compatibility for existing tests.

- [ ] **Step 7: Run Python tests**

Run:

```bash
python -m pytest tests/test_report_eligibility.py -q
```

Expected: all report eligibility tests pass.

- [ ] **Step 8: Commit Python eligibility changes**

Run:

```bash
git add coa_meta/domain.py coa_meta/repository.py coa_meta/reporting.py tests/test_report_eligibility.py
git commit -m "feat: use source-aware level eligibility"
```

## Task 10: Noninteractive Builder Capture Cleanup

**Files:**
- Modify: `coa_scraper/scrape-coa-network.mjs`
- Modify: `coa_scraper/package.json`

- [ ] **Step 1: Add CLI option parsing**

At the top of `coa_scraper/scrape-coa-network.mjs`, replace constants with:

```js
const args = new Set(process.argv.slice(2));
const valueAfter = (name, fallback) => {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
};

const URL = valueAfter("--url", "https://ascension.gg/en/v2/coa-builder/voljin-alpha");
const OUT = valueAfter("--out-dir", "data/raw");
const SNAP = valueAfter("--snapshot-dir", "data/snapshots");
const HAR = valueAfter("--har", "data/coa.har");
const WAIT_MS = Number(valueAfter("--wait-ms", "8000"));
const HEADLESS = args.has("--headless");
const INTERACTIVE = args.has("--interactive") || !args.has("--finalize-on-load");
```

- [ ] **Step 2: Wire headless launch**

Change launch config to:

```js
const browser = await chromium.launch({
  headless: HEADLESS,
  executablePath: "/usr/bin/chromium"
});
```

Change the initial wait to:

```js
await page.waitForTimeout(WAIT_MS);
```

- [ ] **Step 3: Extract finalization into a function**

Before the current `process.stdin.resume()` block, add:

```js
async function finalizeCapture() {
  await page.waitForTimeout(2000);

  await fs.writeFile(
    path.join(SNAP, "final-page-content.html"),
    await page.content(),
    "utf8"
  );

  const finalRuntimeDump = await page.evaluate(() => {
    const dumpStorage = store => {
      const out = {};
      for (let i = 0; i < store.length; i++) {
        const key = store.key(i);
        out[key] = store.getItem(key);
      }
      return out;
    };

    return {
      href: location.href,
      title: document.title,
      nextData: globalThis.__NEXT_DATA__ ?? null,
      nextFlight: globalThis.__next_f ?? null,
      localStorage: dumpStorage(localStorage),
      sessionStorage: dumpStorage(sessionStorage)
    };
  });

  await fs.writeFile(
    path.join(SNAP, "final-runtime-dump.json"),
    JSON.stringify(finalRuntimeDump, null, 2),
    "utf8"
  );

  await context.close();
  await browser.close();

  console.log("Saved HAR:", HAR);
  console.log("Saved snapshots:", SNAP);
}
```

Replace the stdin block with:

```js
if (!INTERACTIVE) {
  await finalizeCapture();
  process.exit(0);
}

console.log("Initial capture complete.");
console.log("Now manually click class tabs and essence/talent panels in the browser.");
console.log("When finished, press Enter here.");

process.stdin.resume();
process.stdin.once("data", async () => {
  await finalizeCapture();
  process.exit(0);
});
```

- [ ] **Step 4: Add package scripts**

In `coa_scraper/package.json`, add:

```json
"capture:headless": "node scrape-coa-network.mjs --headless --finalize-on-load"
```

- [ ] **Step 5: Run non-network syntax check**

Run:

```bash
node --check coa_scraper/scrape-coa-network.mjs
```

Expected: no syntax errors.

- [ ] **Step 6: Optional headless capture smoke**

Run only when network and Chromium are available:

```bash
npm --prefix coa_scraper run capture:headless
npm --prefix coa_scraper run pipeline
```

Expected: capture completes without manual input and pipeline can extract the builder payload.

- [ ] **Step 7: Commit capture cleanup**

Run:

```bash
git add coa_scraper/scrape-coa-network.mjs coa_scraper/package.json
git commit -m "feat: support unattended builder capture"
```

## Task 11: Documentation Updates

**Files:**
- Modify: `docs/data/normalized-schema.md`
- Modify: `docs/MODULES.md`
- Modify: `docs/README.md`
- Modify: `docs/DECISIONS.md`

- [ ] **Step 1: Update normalized schema docs**

In `docs/data/normalized-schema.md`, add a section:

```markdown
## M1.8 Source and Level Fields

M1.8 keeps `coa-normalized-v1` and adds optional source-aware fields:

- `source_category`: `spec_tree`, `class_pool`, `trainer`, `misc_system`, `metadata_only`, or `unknown`.
- `source_confidence`: `high`, `medium`, or `low`.
- `availability`: builder, tooltip, DB tooltip, effective level, confidence, source, and notes.
- `db_enrichment`: optional AscensionDB spell tooltip join data.

Consumers must continue to support records without these fields. When present, `availability.effective_required_level` may be used for lower-level eligibility only if `availability.level_confidence` is `high` or `medium`.
```

- [ ] **Step 2: Update module docs**

In `docs/MODULES.md`, under Normalization Module outputs, add:

```markdown
- `coa_db_spell_tooltips.jsonl`
- `coa_db_enrichment_summary.json`
- `coa_source_level_report.json`
- `coa_metadata_tab_report.json`
```

Under Normalization Module responsibilities, add:

```markdown
- Join builder records with optional AscensionDB tooltip enrichment while preserving builder legality as the source of truth.
```

- [ ] **Step 3: Update README command docs**

In `docs/README.md`, add:

````markdown
## Optional M1.8 DB Enrichment

The default Phase 1 report path remains network-free after artifacts exist. To refresh source and level enrichment from AscensionDB, run:

```bash
cd coa_scraper
npm run pipeline:m1.8
```

This writes DB tooltip artifacts and an enriched entries file. AscensionDB enrichment is used for provenance and lower-level confidence; it does not replace builder legality fields.
````

- [ ] **Step 4: Add architecture decision**

Append to `docs/DECISIONS.md`:

```markdown
## Decision 15: AscensionDB Enriches But Does Not Replace Builder Legality

Status: accepted.

M1.8 treats the CoA builder payload as authoritative for class/tab ownership, graph structure, prerequisites, AE/TE costs, and tab gates. AscensionDB is the preferred source for spell and item tooltip enrichment, buff/effect text, equipment text, linked spell/item IDs, and tooltip-level evidence.

Reasoning:

- The builder payload carries active builder graph data that DB pages do not expose as a coherent build graph.
- AscensionDB exposes richer spell and item tooltip payloads through `&power` endpoints.
- DB records can be missing, empty, permission-restricted, or named differently from builder nodes, so enrichment needs confidence and coverage rather than blind overwrites.
```

- [ ] **Step 5: Commit docs**

Run:

```bash
git add docs/data/normalized-schema.md docs/MODULES.md docs/README.md docs/DECISIONS.md
git commit -m "docs: document M1.8 enrichment model"
```

## Task 12: M1.8 Verification Gate

**Files:**
- No source edits unless a verification command exposes a defect in changed files.

- [ ] **Step 1: Run Node tests**

Run:

```bash
npm --prefix coa_scraper run unit-test
```

Expected: all Node unit tests pass.

- [ ] **Step 2: Run scraper validation**

Run:

```bash
npm --prefix coa_scraper run validate
```

Expected: validation summary status is `pass`.

- [ ] **Step 3: Run Python tests**

Run:

```bash
python -m pytest -q
```

Expected: all Python tests pass.

- [ ] **Step 4: Run full no-network pipeline**

Run:

```bash
npm --prefix coa_scraper run pipeline
```

Expected: pipeline completes from existing snapshots and writes source-level reports.

- [ ] **Step 5: Run optional network enrichment**

Run only with network approval:

```bash
npm --prefix coa_scraper run pipeline:m1.8
```

Expected: DB enrichment artifacts are written. Empty registrations and name mismatches may appear in the summary as warnings/counts, not failures.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short
```

Expected: no uncommitted changes after the final commit.

- [ ] **Step 7: Final milestone commit if needed**

If any intentional M1.8 files remain uncommitted, commit them:

```bash
git add coa_scraper coa_meta tests docs
git commit -m "chore: complete M1.8 source enrichment"
```
