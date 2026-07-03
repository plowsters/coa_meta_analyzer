# CoA Scraper Pipeline

This module captures the official Ascension Conquest of Azeroth builder, extracts the builder payload, normalizes talent and ability entries, validates the normalized artifacts, and writes an artifact manifest.

## Capture

Run:

```bash
npm run capture
```

The capture script opens Chromium and saves HAR/raw responses/snapshots under `data/`. Manual interaction is currently expected: after the page loads, click through classes and tabs that need to be present in the final snapshot, then press Enter in the terminal.

## Regenerate Artifacts From Existing Snapshot

Run:

```bash
npm run pipeline
```

This command reads `data/snapshots/final-page-content.html` and writes:

- `reports/coa_builder_payload.json`
- `reports/coa_builder_summary.json`
- `reports/coa_payload_shape.json`
- `reports/coa_payload_shape_report.txt`
- `reports/coa_payload_report.txt`
- `reports/coa_normalization_report.txt`
- `reports/coa_counts_by_class_tab_kind.txt`
- `reports/coa_validation_summary.json`
- `reports/coa_artifact_manifest.json`
- `dist/coa_entries.jsonl`
- `dist/coa_entries.pretty.json`
- `dist/coa_classes.json`
- `dist/coa_essence_caps.json`
- `dist/coa_class_profile_input.json`

## Validate

Run:

```bash
npm run validate
```

Validation fails when required normalized fields are missing, class/tab ownership is missing, unknown essence kinds are present, or normalized records do not include schema metadata.

## Source of Truth

The optimizer consumes `dist/coa_entries.jsonl`, `dist/coa_classes.json`, and `dist/coa_essence_caps.json`. It should not parse HAR files, HTML snapshots, or Next Flight payloads directly.
