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
  - `patch_chain` / `effective_archive` are StormLib's own reported chain of archives that
    supplied the winning bytes (winner last), not the attach order.
  - `source_dbcs` maps each contributing table (`Spell`, `SpellCastTimes`, `SpellDuration`,
    `SpellRange`) to the archive that supplied it.
- `coa_attribution`: `status` (`unknown` in M1.14A), plus raw signals:
  - `archive_family`: family of the archive that supplied `Spell.dbc` — `coa` (patch-C*),
    `base` (stock WotLK archives), `reborn` (patch-W*, normally excluded), or `other`.
    Empirically (real client, 2026-07) the current authoritative `Spell.dbc` — carrying
    spell `805775` = *Adrenal Venom* — is supplied by `patch-T.MPQ`, so `archive_family` is
    `other`, **not** `coa`. Decision 18's patch-C*-only CoA heuristic is therefore
    incomplete; reconciling the `patch-T` family into CoA attribution is M1.14B's job.
  - `id_range`: coarse magnitude band of `spell_id` — `high` when `spell_id >= 100000`
    (custom high-range content), else `base`. A raw signal; M1.14B owns id-range policy.

## Mechanics scope (M1.14A)
M1.14A extracts the reduced spell family: `Spell` plus the three index tables it references
(`SpellCastTimes`, `SpellDuration`, `SpellRange`). The umbrella spec's fuller mechanical set
— spell cooldowns/category cooldowns, rune cost, and the `SpellEffect` `effects[]` join — is
**deferred to a later M1.14 sub-milestone**. Those tables are load-bearing for the M1.16
power model, not for M1.14A extraction, and are tracked as follow-up rather than dropped.

## Consumer Rules
- `schema_match_confidence: "low"` means DBC drift was detected for a contributing table; downstream
  consumers must not treat those mechanical fields as high-confidence.
- Fields may be null; consumers tolerate partial records.
