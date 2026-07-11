# Client Content Schema

Records use schema version `coa-client-content-v1`, produced by `coa_client_extract` (M1.14A) from the
loose `Data/Content/*.json` tier.

## Required Fields
- `schema_version`: always `coa-client-content-v1`
- `content_kind`: `spell_rank` | `spell_stat_suggestion` | `spell_role_suggestion` |
  `item_variation` | `character_advancement`
- `spell_id` and/or `item_id`: whichever the source entry keys on
- `values`: the remaining source fields verbatim
- `provenance`: `source_file`, `file_sha256`, `extraction_date`
- `coa_attribution`: `status` (`unknown` in M1.14A); `character_advancement` carries an `investigate`
  note pending attribution.
