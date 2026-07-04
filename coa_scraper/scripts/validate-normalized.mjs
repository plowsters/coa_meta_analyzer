#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { loadJson, loadJsonl, writeJson } from "./lib/artifacts.mjs";

const NORMALIZED_SCHEMA_VERSION = "coa-normalized-v1";

function isNumberArray(value) {
  return Array.isArray(value) && value.every(v => typeof v === "number" && Number.isFinite(v));
}

export function validateNormalizedArtifacts({
  distDir = "dist",
  reportsDir = "reports",
  allowUnknownEssenceKind = false
} = {}) {
  const entriesPath = path.join(distDir, "coa_entries.jsonl");
  const classesPath = path.join(distDir, "coa_classes.json");
  const essenceCapsPath = path.join(distDir, "coa_essence_caps.json");
  const normalizationReportPath = path.join(reportsDir, "coa_normalization_report.txt");
  const shapeReportPath = path.join(reportsDir, "coa_payload_shape_report.txt");

  const entries = loadJsonl(entriesPath);
  const classes = loadJson(classesPath);
  loadJson(essenceCapsPath);

  const failures = [];
  const warnings = [];

  const fail = message => failures.push(message);

  if (!entries.length) fail("coa_entries.jsonl contains no records");
  if (!Array.isArray(classes) || !classes.length) fail("coa_classes.json contains no class records");

  const classNames = new Set(Array.isArray(classes) ? classes.map(c => c.class_name).filter(Boolean) : []);
  const entryClassNames = new Set(entries.map(e => e.class_name).filter(Boolean));

  if (Array.isArray(classes)) {
    for (const cls of classes) {
      if (cls.schema_version !== NORMALIZED_SCHEMA_VERSION) fail(`class ${cls.class_name || cls.class_id} missing schema_version`);
      if (!cls.class_name) fail(`class ${cls.class_id} missing class_name`);
      if (typeof cls.class_id !== "number") fail(`class ${cls.class_name} has non-number class_id`);
      if (!Array.isArray(cls.tabs)) fail(`class ${cls.class_name} tabs is not an array`);
      if (cls.class_name && !entryClassNames.has(cls.class_name)) fail(`class ${cls.class_name} has no normalized entries`);
    }
  }

  let missingClassRecords = 0;
  let missingTabRecords = 0;
  let unknownEssenceKindRecords = 0;
  let m18SourceRecords = 0;
  let m18AvailabilityRecords = 0;

  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    const label = `${e.class_name || "UNKNOWN_CLASS"}:${e.tab_name || "UNKNOWN_TAB"}:${e.name || "UNKNOWN_NAME"}:${e.entry_id || i}`;

    if (e.schema_version !== NORMALIZED_SCHEMA_VERSION) fail(`${label} missing schema_version`);
    if (!e.class_name) missingClassRecords++;
    if (!e.tab_name) missingTabRecords++;
    if (!["ability", "talent", "unknown"].includes(e.essence_kind)) fail(`${label} invalid essence_kind ${e.essence_kind}`);
    if (e.essence_kind === "unknown") unknownEssenceKindRecords++;
    if (!e.name) fail(`${label} missing name`);
    if (typeof e.class_id !== "number") fail(`${label} class_id is not numeric`);
    if (typeof e.tab_id !== "number") fail(`${label} tab_id is not numeric`);
    if (typeof e.ae_cost !== "number") fail(`${label} ae_cost is not numeric`);
    if (typeof e.te_cost !== "number") fail(`${label} te_cost is not numeric`);
    if (typeof e.required_tab_ae !== "number") fail(`${label} required_tab_ae is not numeric`);
    if (typeof e.required_tab_te !== "number") fail(`${label} required_tab_te is not numeric`);
    if (!isNumberArray(e.required_ids)) fail(`${label} required_ids must be numeric array`);
    if (!isNumberArray(e.connected_node_ids)) fail(`${label} connected_node_ids must be numeric array`);
    if (!Array.isArray(e.tags)) fail(`${label} tags must be array`);
    if (!Array.isArray(e.damage_schools)) fail(`${label} damage_schools must be array`);
    if (!Array.isArray(e.resources)) fail(`${label} resources must be array`);
    if (!e.field_sources || typeof e.field_sources !== "object") fail(`${label} missing field_sources object`);
    if (!e.inferred || typeof e.inferred !== "object") fail(`${label} missing inferred object`);
    if (!e.raw || typeof e.raw !== "object") fail(`${label} missing raw object`);
    if (e.source_category !== undefined) {
      m18SourceRecords++;
      if (!["spec_tree", "class_pool", "trainer", "misc_system", "metadata_only", "unknown"].includes(e.source_category)) {
        fail(`${label} invalid source_category ${e.source_category}`);
      }
    }
    if (e.availability !== undefined) {
      m18AvailabilityRecords++;
      if (typeof e.availability !== "object" || e.availability === null) {
        fail(`${label} availability must be object`);
      } else {
        if (typeof e.availability.effective_required_level !== "number") {
          fail(`${label} availability.effective_required_level is not numeric`);
        }
        if (!["high", "medium", "low"].includes(e.availability.level_confidence)) {
          fail(`${label} invalid availability.level_confidence ${e.availability.level_confidence}`);
        }
      }
    }
  }

  if (missingClassRecords > 0) fail(`missing class records: ${missingClassRecords}`);
  if (missingTabRecords > 0) fail(`missing tab records: ${missingTabRecords}`);
  if (unknownEssenceKindRecords > 0 && !allowUnknownEssenceKind) {
    fail(`unknown essence-kind records: ${unknownEssenceKindRecords}`);
  }

  try {
    loadJson(path.join(reportsDir, "coa_payload_shape.json"));
  } catch (err) {
    warnings.push(err.message);
  }

  for (const requiredReport of [normalizationReportPath, shapeReportPath]) {
    if (!fs.existsSync(requiredReport)) {
      fail(`required report does not exist: ${requiredReport}`);
    }
  }

  const summary = {
    schema_version: "coa-validation-summary-v1",
    status: failures.length ? "fail" : "pass",
    class_count: Array.isArray(classes) ? classes.length : 0,
    record_count: entries.length,
    class_names: [...classNames].sort(),
    missing_class_records: missingClassRecords,
    missing_tab_records: missingTabRecords,
    unknown_essence_kind_records: unknownEssenceKindRecords,
    m1_8_source_records: m18SourceRecords,
    m1_8_availability_records: m18AvailabilityRecords,
    failures,
    warnings
  };

  writeJson(path.join(reportsDir, "coa_validation_summary.json"), summary);

  if (failures.length) {
    const err = new Error(`Normalized artifact validation failed with ${failures.length} failure(s)`);
    err.summary = summary;
    throw err;
  }

  return summary;
}

function isCliEntryPoint() {
  return process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]);
}

if (isCliEntryPoint()) {
  const distDir = process.argv[2] || "dist";
  const reportsDir = process.argv[3] || "reports";
  const allowUnknownEssenceKind = process.argv.includes("--allow-unknown-essence-kind");

  try {
    const summary = validateNormalizedArtifacts({ distDir, reportsDir, allowUnknownEssenceKind });
    console.log(JSON.stringify(summary, null, 2));
  } catch (err) {
    if (err.summary) {
      console.log(JSON.stringify(err.summary, null, 2));
    } else {
      console.error(err.message);
    }
    process.exit(1);
  }
}
