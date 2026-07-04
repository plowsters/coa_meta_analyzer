#!/usr/bin/env node
import { spawnSync } from "node:child_process";

const steps = [
  ["extract payload", ["node", "scripts/extract-coa-builder-payload.mjs", "data/snapshots/final-page-content.html", "reports"]],
  ["inspect payload shape", ["node", "scripts/inspect-coa-payload-shape.mjs", "reports/coa_builder_payload.json", "reports/coa_payload_shape_report.txt", "reports/coa_payload_shape.json"]],
  ["summarize payload", ["node", "scripts/summarize-coa-payload.mjs", "reports/coa_builder_payload.json", "reports/coa_payload_report.txt"]],
  ["normalize payload", ["node", "scripts/export-coa-normalized.mjs", "reports/coa_builder_payload.json", "dist"]],
  ["build class profile input", ["node", "scripts/build-class-profile-input.mjs", "dist/coa_entries.jsonl", "dist/coa_classes.json", "dist/coa_class_profile_input.json"]],
  ["validate normalized artifacts", ["node", "scripts/validate-normalized.mjs", "dist", "reports"]],
  ["write source level report", ["node", "scripts/write-source-level-report.mjs", "dist/coa_entries.jsonl", "dist/coa_classes.json", "reports"]],
  ["write artifact manifest", ["node", "scripts/write-artifact-manifest.mjs", "reports", "dist", "reports/coa_artifact_manifest.json"]]
];

for (const [label, cmd] of steps) {
  console.log(`\n=== ${label} ===`);
  const result = spawnSync(cmd[0], cmd.slice(1), {
    stdio: "inherit",
    shell: false
  });
  if (result.status !== 0) {
    console.error(`Step failed: ${label}`);
    process.exit(result.status || 1);
  }
}

console.log("\nPipeline completed successfully.");
