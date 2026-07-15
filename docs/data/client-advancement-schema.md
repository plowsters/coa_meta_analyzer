# Client Advancement Schema

Records use schema version `coa-client-advancement-v1`, produced by `coa_client_extract` (M1.14B)
from `DBFilesClient/CharacterAdvancement.dbc` (plus its companion class-type/tab-type/spell tables).
One record is emitted **per advancement node** — the row in `CharacterAdvancement.dbc` — not per
spell. `coa-client-advancement-v1` is the candidate canonical talent graph; it is validated against
the CoA Builder oracle (`coa-builder-parity-v3`, see [client-content-schema.md](client-content-schema.md)
sibling docs and [DECISIONS.md](../DECISIONS.md) Decisions 21/22) but not yet consumed by the legality
or tree pipeline — that staged supersession is M1.15's job.

## `CharacterAdvancement.dbc` is a unified all-class registry, not CoA-only

The real client's `CharacterAdvancement.dbc` holds 12,037 rows spanning every game mode, resolved by
`class_type` (`kind`, see [client-class-types-schema.md](client-class-types-schema.md)) into: **4,383
`stock`**, **3,614 `coa_class`**, **2,591 `meta`**, **1,325 `reborn`**, and **124 `None`/`unknown`**
(class_type 1, unresolved). M1.14B owns only the CoA subgraph: `regenerate` validates
(`validate_semantics`), emits `coa-client-advancement-v1` records, and Builder-parity-checks
(`build_parity_report`) **only** the `class_kind == "coa_class"` nodes — the stock/meta/reborn/`None`
rows are real rows in the same table but out of M1.14B scope, deferred to later milestones. This is a
scoping decision, not a data gap: the table itself is not partitioned by mode at the file level (no
separate stock/CoA table), only by the `class_type` FK per row.

`attribute()`, by contrast, still runs over the **full, unscoped** node set (not just `coa_class`), so
that a spell participating in more than one mode — e.g. a spell that is both a CoA node and a stock
node — has its cross-system multi-mode participation captured in `coa_attribution`/`memberships[]`
rather than silently dropped by the CoA scoping that `regenerate`'s validate/emit/parity steps apply.

## Node identity is not spell identity

`node_id` (col 0 of `CharacterAdvancement.dbc`, unique across all 12,037 rows) is the canonical
identity of a record — the advancement-row id. `spell_id` (col 5) is **many-to-one** with nodes:
the same spell can be realized as more than one node. The canonical example is Builder spell
`503748`, which is one spell realized as two distinct Witch Doctor advancement nodes — a
Brewing-tab `Talent` node and a Class-tab `Ability` node — which is exactly why the Builder oracle
holds 3,612 records over only 3,611 unique spell IDs. Consumers that key on `spell_id` alone will
silently collapse these into one entry; key on `node_id` for ownership/graph identity, and use the
spell's aggregated `memberships[]` (on `coa-client-spell-v1`, filled by M1.14B) when the question is
"which advancement contexts does this spell participate in."

## Required Fields

- `schema_version`: always `coa-client-advancement-v1`
- `node_id`: the advancement-row id (`CharacterAdvancement` col 0) — canonical node identity
- `spell_id`: the spell realized by this node (`CharacterAdvancement` col 5); `0` when the node has
  no spell
- `name`: the spell's *current* name, joined from the already-extracted `coa-client-spell-v1` record
  by `spell_id` (not read from the advancement table's own string block)
- `class`: `{ class_type_id, internal, display, kind }` — the node's owning class, resolved via the
  `class_type` FK (col 32) against `CharacterAdvancementClassTypes` (see
  [client-class-types-schema.md](client-class-types-schema.md) for `kind`/`display` semantics; the
  curated alpha→display rename and its provenance live there, joined by `class_type_id`, not
  duplicated per node)
- `tab`: `{ tab_type_id, name }` — resolved via the tab-type FK against `CharacterAdvancementTabTypes`
- `entry_type`: the node's kind (e.g. `Ability`, `Talent`, `TalentAbility`), decoded from a proven
  numeric→string map — withheld (empty string) if that column has not decoded to `high` confidence
- `essence_kind`: `"ability"` | `"talent"` | `""`, derived from `entry_type` (`Ability`/
  `TalentAbility` → `ability`, `Talent` → `talent`, otherwise empty)
- `legality`: a dict carrying **only** the legality fields that decoded to `field_confidence: high`
  for this node. Possible keys: `ae_cost`, `te_cost`, `required_level`, `required_tab_ae`,
  `required_tab_te`, `max_rank`, `row`, `col`, `connected_node_ids`, `required_ids`. A field absent
  from `legality` is honestly unresolved for that node (not zero, not padding) — the parity report's
  `readiness.legality[field]` and `readiness.layout` reflect this per field, per artifact-wide
  confidence.
  - `required_level` follows the `{0} ∪ [1, 60]` rule: `0` normalizes to "no level requirement"
    (available immediately), never to "unknown" or padding; any other value must fall in `[1, 60]`
    or the node is rejected before canonical emission (`DbcSemanticError`).
  - `connected_node_ids` / `required_ids` are nonempty only once adjacency has been proven to resolve
    in the `node_id` domain (no dangling references, no self-reference); values are de-duplicated and
    sorted, with zero/padding slots normalized away.
- `field_confidence`: index-keyed-by-field-name map (e.g. `{"ae_cost": "high", "row": "high"}`)
  recording which `legality` entries reached `high` confidence. Only `high` fields are eligible to
  feed the M1.15 Builder-supersession adapter; every other field keeps the Builder as its fallback,
  explicitly marked.
- `raw`: `{ "cols": { "<cell_index>": <value>, ... } }` — the full index-keyed audit map of every raw
  column value for this row, retained regardless of decode confidence, so a later mis-mapping is
  recoverable without re-extraction. Because JSON object keys are always strings, the integer cell
  indices are stringified on serialization.
- `provenance`: per-table provenance for this record's contributing tables — `client_build`,
  `source_dbcs` (map of contributing table name → effective archive that supplied it, e.g.
  `CharacterAdvancement`, `CharacterAdvancementClassTypes`, `CharacterAdvancementTabTypes`, `Spell`),
  `supersedes` (`{"source_file": "CharacterAdvancementData.json"}` — see
  [client-content-schema.md](client-content-schema.md)), and `extraction_date`
- `coa_attribution`: the participation block for this node's spell — `{ is_coa, modes, exclusive_mode,
  confidence }` — identical in shape to the block filled on `coa-client-spell-v1` (see
  [client-spell-schema.md](client-spell-schema.md)) and joined here for per-node convenience; the
  spell-level record is where the aggregated `memberships[]` lives, not here (a node has exactly one
  precise `(class, tab)` context by construction)
  - `archive_family` / `id_range`: **not present** on the advancement record — those M1.14A raw
    signals live only on the spell record's `coa_attribution` block

## Builder-Parity Report (`coa-builder-parity-v3`)

`build_parity_report` (`coa_client_extract/parity.py`) crosswalks the `coa_class`-scoped nodes above
against the Builder oracle by id (`node_id` ↔ `entry_id`). Ownership and identity are no longer exact
set/tuple equality; both generalize the Decision-22 four-way discrepancy classification (see
[DECISIONS.md](../DECISIONS.md) Decision 22 for the full reasoning):

- **Ownership adjudication.** The real client legitimately leads the Builder oracle: after CoA
  scoping, `ownership_recall == 1.0`/`unique_spell_recall == 1.0` (`builder_only_records == 0`), but
  the client has 2 CoA nodes the Builder capture lacks (`raw_ownership_precision == 0.9994`). A
  client-only node is classified via a curated adjudication file,
  [`reports/client_extract/client_only_adjudication.json`](../../reports/client_extract/client_only_adjudication.json)
  (schema `coa-client-only-adjudication-v1`), loaded by `regenerate` through the
  `--client-only-adjudication` CLI flag and reported as `client_only_classification`:
  `{verified_client_current, representation_difference, extraction_defect, unresolved}`, each a list
  of `{node_id, spell_id, class, reason}`. Only `verified_client_current` and
  `representation_difference` are accepted; `extraction_defect` and an unadjudicated (`unresolved`)
  node still block. `builder_refresh_recommended: true` flags whenever any client-only node exists (the
  Builder scrape should be refreshed). `ownership_ready` is:
  ```
  ownership_ready = builder_only_records == 0
                    AND hard_identity_mismatches == 0
                    AND every client_only record classified verified_client_current | representation_difference
                    AND taxonomy/count/non-empty guards
  ```
  Readiness comes from adjudication, never recall alone; the raw counts stay visible
  (`builder_coverage_recall`, `raw_ownership_precision` — kept, never hidden or redefined; the retained
  `ownership_recall`/`ownership_precision` are unchanged).
- **Identity canonicalization.** 708 of 3,612 matched nodes had a class-label mismatch that is pure
  formatting — client CamelCase vs Builder spaced (`WitchDoctor`/`Witch Doctor`,
  `WitchHunter`/`Witch Hunter`, `KnightOfXoroth`/`Knight of Xoroth`, `SunCleric`/`Sun Cleric`) — zero
  spell-ID divergence. The identity check canonicalizes the class label before comparing:
  `canonical_class_label(v) = "".join(unicodedata.normalize("NFKC", v).split()).casefold()`, version
  `class_label_normalization: "nfkc-casefold-remove-whitespace-v1"` (NFKC + whitespace-strip +
  casefold; no punctuation removal, no fuzzy matching). A raw mismatch that canonicalizes equal is a
  `representation_difference` (normalized + accepted, visible in `raw_identity_mismatches`,
  `representation_differences`, and `representation_difference_pairs` as `{"Client → Builder": count}`);
  a raw mismatch that still canonicalizes unequal — a real semantic class change or any spell-ID
  divergence — is a `hard_identity_mismatch` (`hard_identity_mismatches`, sampled in
  `hard_identity_mismatch_sample`) and blocks ownership. These fields **replace** the old
  `identity_mismatches`/`identity_mismatch_sample`. This canonicalization is comparison-only: the
  client artifact always ships its own native label on `class.internal`/`class.display` (e.g.
  `WitchDoctor`, per [client-class-types-schema.md](client-class-types-schema.md)); only the Builder's
  spaced form is normalized for parity comparison, never rewritten into the artifact. It is distinct
  from the 3 curated *semantic* aliases (Bloodmage/Felsworn/Templar — same doc).

## Consumer Rules

- Treat `node_id` as identity; never assume `spell_id` is unique.
- Only read a `legality` field a caller cares about if `field_confidence[field] == "high"`; an
  absent-from-`legality` field is not zero.
- `raw.cols` is an audit trail, not a stable contract — column indices are the current decode's
  resolution and may be re-mapped if a future decode pass corrects them (with `raw` used to verify the
  correction against the same source bytes).
- This artifact does not itself retire the Builder graph or legality pipeline. The node-level parity
  report (`coa-builder-parity-v3`) and the per-field Builder-supersession adapter are what M1.15
  consumes to do that, one field at a time (Decision 21).
