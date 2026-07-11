# Client Spell Schema

Records use schema version `coa-client-spell-v1`, produced by `coa_client_extract` (M1.14A) from the
CoA client's MPQ→DBC spell family. Attribution is deferred to M1.14B (`coa_attribution.status`
is `unknown` until then); reconciliation into `coa-mechanics-v1` is M1.14C.

## Required Fields
- `schema_version`: always `coa-client-spell-v1`
- `spell_id`: DBC spell id
- `name`: localized spell name from `Spell.dbc`
- `mechanics`: object with `school_mask`, `power_type`, `cast_time_ms`, `duration_ms`,
  `range_min_yd`, `range_max_yd`, `category`, `spell_icon_id` (any may be null when the source row is
  absent)
- `provenance`: `base_archive`, `patch_chain`, `effective_archive`, `source_dbcs`,
  `schema_match_confidence` (`high`|`low`), `extraction_date`
- `coa_attribution`: `status` (`unknown` in M1.14A), plus raw signals (`archive_family`, `id_range`)

## Consumer Rules
- `schema_match_confidence: "low"` means DBC drift was detected for a contributing table; downstream
  consumers must not treat those mechanical fields as high-confidence.
- Fields may be null; consumers tolerate partial records.
