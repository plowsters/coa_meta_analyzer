# Role Map Schema

Schema version: `coa-spec-role-map-v1`

The role map records source-backed CoA class/spec roles. It is the preferred input for M1.11B role resolution before legacy role overrides or metadata inference.

## Top-Level Object

- `schema_version`: always `coa-spec-role-map-v1`
- `source_note`: short human-readable provenance note for the data batch
- `specs`: list of spec role records

## Spec Role Record

- `class_name`: normalized source class name.
- `source_spec_name`: spec/tab name used by builder/API artifacts.
- `display_spec_name`: player-facing spec name used in reports.
- `primary_role`: default guide/scoring role; one of `melee_dps`, `caster_dps`, `ranged_dps`, `tank`, `healer`, or `support`.
- `secondary_roles`: optional additional roles used for guide filtering and future alternate guide variants.
- `engine_role`: broad compatibility role; one of `dps`, `tank`, or `healer_support`.
- `complexity`: official complexity label when known. It is metadata only and must not affect scoring in M1.11B.
- `source`: provenance type, currently `authoritative_video`, `authoritative_builder`, `curated`, or `inferred`.
- `confidence`: `high`, `medium`, or `low`.
- `evidence`: non-empty list of short evidence strings.
- `source_urls`: list of URLs that support the record when available.
- `notes`: optional migration or ambiguity note.

## Hybrid Roles

Hybrid specs use one `primary_role` plus zero or more `secondary_roles`.

Example:

```json
{
  "class_name": "Guardian",
  "source_spec_name": "Inspiration",
  "display_spec_name": "Inspiration",
  "primary_role": "melee_dps",
  "secondary_roles": ["support"],
  "engine_role": "dps",
  "complexity": "Normal",
  "source": "authoritative_video",
  "confidence": "high",
  "evidence": ["launch_video: Guardian Inspiration melee DPS/Support"],
  "source_urls": []
}
```

Guide filters should include the spec under both primary and secondary roles. Default scoring and build selection should use the primary role until separate role-specific guide variants exist.
