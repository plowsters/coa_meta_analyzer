import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  artifactRecord,
  loadJson,
  loadJsonl,
  sha256File,
  writeJson
} from "../scripts/lib/artifacts.mjs";
import { validateNormalizedArtifacts } from "../scripts/validate-normalized.mjs";
import { writeArtifactManifest } from "../scripts/write-artifact-manifest.mjs";

function tempProject() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "coa-pipeline-test-"));
}

function writeJsonl(filePath, rows) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, rows.map(row => JSON.stringify(row)).join("\n") + "\n");
}

function validNode(overrides = {}) {
  return {
    schema_version: "coa-normalized-v1",
    build_id: 39,
    build_slug: "voljin-alpha",
    build_name: "Vol'Jin Alpha",
    class_id: 29,
    class_name: "Venomancer",
    tab_id: 77,
    tab_name: "Stalking",
    tab_sort_order: 2,
    entry_type: "Talent",
    essence_kind: "talent",
    essence_type: "talentEssence",
    entry_id: 123,
    spell_id: 456,
    spell_ids: [456],
    name: "Test Node",
    icon: "Interface\\Icons\\test",
    ae_cost: 0,
    te_cost: 1,
    required_tab_ae: 0,
    required_tab_te: 0,
    description_html: "Deals Nature damage.",
    description_text: "Deals Nature damage.",
    required_level: 0,
    max_rank: 1,
    row: 1,
    col: 2,
    node_type: "SpendCircle",
    flags: 0,
    group: 0,
    is_passive: false,
    is_starting_node: false,
    required_ids: [],
    connected_node_ids: [123],
    tags: ["dot"],
    damage_schools: ["nature"],
    resources: ["Energy"],
    field_sources: { name: "entry.name" },
    inferred: { tags: ["dot"], damage_schools: ["nature"], resources: ["Energy"] },
    raw: { id: 123 },
    ...overrides
  };
}

function validClass(overrides = {}) {
  return {
    schema_version: "coa-normalized-v1",
    class_id: 29,
    class_name: "Venomancer",
    tabs: [
      {
        tab_id: 77,
        tab_name: "Stalking",
        sort_order: 2,
        nominal_essence_kind: "talent"
      }
    ],
    essence_caps: {
      maxTalentEssence: 25,
      maxAbilityEssence: 26
    },
    ...overrides
  };
}

function writeValidationFixture(dir, nodeOverrides = {}) {
  const dist = path.join(dir, "dist");
  const reports = path.join(dir, "reports");
  fs.mkdirSync(dist, { recursive: true });
  fs.mkdirSync(reports, { recursive: true });
  writeJsonl(path.join(dist, "coa_entries.jsonl"), [validNode(nodeOverrides)]);
  writeJson(path.join(dist, "coa_classes.json"), [validClass()]);
  writeJson(path.join(dist, "coa_essence_caps.json"), {
    "29": { maxTalentEssence: 25, maxAbilityEssence: 26 }
  });
  writeJson(path.join(reports, "coa_payload_shape.json"), { builder: { id: 39 } });
  fs.writeFileSync(path.join(reports, "coa_normalization_report.txt"), "ok\n");
  fs.writeFileSync(path.join(reports, "coa_payload_shape_report.txt"), "ok\n");
  return { dist, reports };
}

test("artifact utilities hash, load, and describe files", () => {
  const dir = tempProject();
  const file = path.join(dir, "data.json");
  writeJson(file, { ok: true });
  fs.writeFileSync(path.join(dir, "rows.jsonl"), "");

  assert.equal(loadJson(file).ok, true);
  assert.match(sha256File(file), /^[a-f0-9]{64}$/);
  assert.deepEqual(loadJsonl(path.join(dir, "rows.jsonl")), []);

  fs.writeFileSync(path.join(dir, "rows.jsonl"), "{\"a\":1}\n");
  assert.deepEqual(loadJsonl(path.join(dir, "rows.jsonl")), [{ a: 1 }]);
  assert.equal(artifactRecord(file, dir).path, "data.json");
});

test("validator accepts complete normalized artifacts and writes summary", () => {
  const dir = tempProject();
  const { dist, reports } = writeValidationFixture(dir);

  const summary = validateNormalizedArtifacts({ distDir: dist, reportsDir: reports });

  assert.equal(summary.status, "pass");
  assert.equal(summary.record_count, 1);
  assert.equal(summary.missing_class_records, 0);
  assert.equal(summary.missing_tab_records, 0);
  assert.equal(summary.unknown_essence_kind_records, 0);
});

test("validator rejects records without schema metadata", () => {
  const dir = tempProject();
  const { dist, reports } = writeValidationFixture(dir, {
    schema_version: null,
    field_sources: null,
    inferred: null
  });

  assert.throws(
    () => validateNormalizedArtifacts({ distDir: dist, reportsDir: reports }),
    /Normalized artifact validation failed/
  );

  const summary = loadJson(path.join(reports, "coa_validation_summary.json"));
  assert.equal(summary.status, "fail");
  assert(summary.failures.some(failure => failure.includes("missing schema_version")));
});

test("manifest writer records builder, validation, artifact hashes, and missing optional files", () => {
  const dir = tempProject();
  const reports = path.join(dir, "reports");
  const dist = path.join(dir, "dist");
  fs.mkdirSync(reports, { recursive: true });
  fs.mkdirSync(dist, { recursive: true });

  writeJson(path.join(reports, "coa_builder_payload.json"), {
    id: 39,
    slug: "voljin-alpha",
    name: "Vol'Jin Alpha",
    max_level: 60
  });
  writeJson(path.join(reports, "coa_validation_summary.json"), {
    status: "pass",
    record_count: 1
  });
  fs.writeFileSync(path.join(dist, "coa_entries.jsonl"), "{}\n");

  const outPath = path.join(reports, "manifest.json");
  writeArtifactManifest({ rootDir: dir, reportsDir: reports, distDir: dist, outPath });

  const manifest = loadJson(outPath);
  assert.equal(manifest.schema_version, "coa-artifact-manifest-v1");
  assert.equal(manifest.builder.slug, "voljin-alpha");
  assert.equal(manifest.validation.status, "pass");
  assert(manifest.artifacts.some(artifact => artifact.path === "dist/coa_entries.jsonl" && artifact.sha256));
  assert(manifest.artifacts.some(artifact => artifact.missing === true));
});
