# Client Archive Plan Schema

The archive plan (`coa-client-archive-plan-v1`) records how `coa_client_extract` (M1.14A) partitions
and orders the client's MPQ archives. CoA Codex owns this policy; StormLib only applies patches.

## Fields
- `schema_version`: always `coa-client-archive-plan-v1`
- `client_root`: absolute path to the client `Data/` directory
- `ordering_rule`: `coa-archive-order-v1`
- `base_archives`: ordered base archive filenames (`common`, `common-2`, `expansion`, `lichking`)
- `patch_archives`: ordered patch filenames (numeric patches, then the `patch-C*` CoA family)
- `excluded`: `{area52: [...], reborn: [...]}` — archives deliberately not loaded

The ordering is validated against a known-overridden file before it is treated as canonical.
