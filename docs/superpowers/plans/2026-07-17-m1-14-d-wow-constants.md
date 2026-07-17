# M1.14D WoW Conversion Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the client-authoritative WoW GameTable conversion primitives plus documented, verification-labelled WotLK rules into a single versioned `coa-wow-constants-v1` snapshot (with a binding manifest), and ship a thin, non-computing `coa_meta` reader — the modeling-inputs layer for M1.16.

**Architecture:** Reuse the M1.14A extraction core (`ArchiveBackend`, patch-chain resolution, WDBC header parse, atomic-write + manifest-last helpers). Add a float ordinal/explicit-id DBC reader, a declarative GameTable axis policy, a deep reconnaissance pass that freezes real-client facts before canonical extraction is trusted, a strict canonical extractor that emits one JSON snapshot + hashed manifest, and a `WowConstantsRepository` that verifies the manifest, validates structure, and looks up raw values (with provenance) without computing any formula.

**Tech Stack:** Python 3.11 (stdlib only — `struct`, `json`, `hashlib`, `math`, `dataclasses`); pytest with the existing `stormlib`/`client` markers; the M1.14A `coa_client_extract` module and `coa_meta` repository layer.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-17-m1-14-d-wow-constants-design.md`. Every task's requirements implicitly include these.

- **Artifact schema:** `coa-wow-constants-v1`; manifest schema `coa-wow-constants-manifest-v1`. The `coa_meta` reader hard-rejects any other `schema_version`.
- **No formulas.** No executable analytical engine. The reader returns raw looked-up values + provenance and may *name* a reference formula; it never evaluates one (no rating→%, GCD, crit, or regen math, no derived multiplier).
- **Native namespace only.** Class-indexed reader methods take a keyword-only `wow_class_id` in the stock `ChrClasses` namespace. The reader never accepts a CoA class-type id, never guesses a namespace, and never maps between namespaces. Composite class-context readiness is M1.16's.
- **`class_context_resolution`** ∈ `{unproven, actor_wow_class_id, versioned_bridge}` — manifest field; default `unproven`. Any published bridge is a complete, hashed mapping with a cardinality policy — never a Boolean.
- **Axis meaning is proven, not assumed.** Established from the pinned reference indexing contract and validated against physical form, explicit/implicit keys, coverage, holes/padding, duplicate ids, and sampled anchors — never from record count alone. Class axis width is never derived from `len(ChrClasses)`.
- **Reference contract:** `level_stride = 100`; combat-rating index `rating_id * 100 + (level - 1)`; class scalar index `(wow_class_id - 1) * 32 + rating_id + 1` (`rating_storage_stride = 32`, `+1` offset); supported rating IDs `0–24`; rating→% reference formula (identified, not computed) `class_scalar / combat_rating`.
- **Stock ChrClasses columns (3.3.5a, pinned):** `ClassID` at cell **0**, `powerType` at cell **2**, first localized (enUS) name at cell **5**. Class ids are sparse `1–9`, `11` (hole at `10`).
- **Manifest binds every authored input** with a version *and* a SHA-256: rules, rating enum, power-type enum, axis policy, reference anchors, and (when the class axis is not `exact`) the class-axis adjudication — plus the artifact hash + byte length and each source-DBC hash.
- **Rules are verification-labelled** (`authority`, `ascension_verification`, `applies_to`) and live in tracked declarative JSON; every rule ships `ascension_verification: unverified` until M1.14G/logs confirm.
- **Fail closed.** StormLib is an extraction-time dependency only; the `wow-constants` command writes nothing and exits non-zero when StormLib is unavailable. Canonical emission parses **strict** (drift → raise before any write). A missing proven-required table, or a non-`exact` class axis without a tracked adjudication, fails closed.
- **Real-client tests gate on structure/sanity, not stock equality.** Structural/layout mismatch, impossible coordinates, duplicates, non-finite values, and unmapped IDs fail; a valid value differing from stock is a recorded `reference_comparison` deviation, not a failure.
- **Redistribution boundary.** The snapshot + manifest + recon report are client-derived → git-ignored; committed fixtures are synthetic; authored inputs (rules, enums, axis policy, anchors) and the class-axis adjudication are tracked. `coa_wow_constants.json` joins the M1.14C mandatory forward policy gate.

---

## File Structure

**Create:**
- `coa_client_extract/data/gt_axis_policy_v1.json` — declarative GameTable axis/physical/index/domain policy.
- `coa_client_extract/data/rating_enum_v1.json` — pinned `CombatRating` id→name map.
- `coa_client_extract/data/power_type_enum_v1.json` — power-type id→name map (same values as M1.14C).
- `coa_client_extract/data/wow_rules_v1.json` — authored verification-labelled rules.
- `coa_client_extract/data/wotlk_reference_anchors_v1.json` — raw, table-tagged coordinate anchor set.
- `coa_client_extract/wow_constants.py` — authored-input loading, axis mapping, class axis, recon, reference comparison, snapshot assembly, extract orchestrator.
- `coa_meta/wow_constants.py` — `WowConstantsRepository` (manifest-verifying load/validate/lookup; no computation).
- `docs/data/wow-constants-schema.md` — schema doc.
- `reports/client_extract/wow_class_axis_adjudication.json` — tracked machine-readable class-axis adjudication (created at the Task 7 checkpoint only if the real client's axis is not `exact`).
- Tests: `tests/test_wow_constants_gametable.py`, `tests/test_wow_constants_authored.py`, `tests/test_wow_constants_axis.py`, `tests/test_wow_constants_class_axis.py`, `tests/test_wow_constants_recon.py`, `tests/test_wow_constants_snapshot.py`, `tests/test_wow_constants_write.py`, `tests/test_wow_constants_cli.py`, `tests/test_wow_constants_repository.py`, `tests/test_wow_constants_oracles.py`, `tests/test_wow_constants_acceptance.py`, `tests/test_wow_constants_stormlib.py`.

**Modify:**
- `coa_client_extract/wdbc.py` — add `GameTable` + `parse_gametable`.
- `coa_client_extract/dbc_layouts.py` — add `CHR_CLASSES` named layout + `GameTableLayout` + `load_axis_policy`.
- `coa_client_extract/artifacts.py` — add `write_wow_constants`.
- `coa_client_extract/cli.py` — add the `wow-constants` subcommand (`--recon-only` in Task 6; canonical in Task 10).
- `pyproject.toml` — add `coa_client_extract` package-data for `data/*.json`.
- `.gitignore` — add the client-derived output ignore rules.
- `docs/DECISIONS.md` — register `coa_wow_constants.json` under the M1.14C forward policy gate.

---

## Task 1: Float ordinal / explicit-id GameTable reader

**Files:**
- Modify: `coa_client_extract/wdbc.py`
- Test: `tests/test_wow_constants_gametable.py`

**Interfaces:**
- Consumes: `_HEADER`/`_MAGIC`/`_CELL` and `DbcDriftError` in `wdbc.py`.
- Produces: `GameTable(physical_form: str, field_count: int, record_size: int, record_count: int, rows: list[dict], drift: bool)` where each row is `{"ordinal": int, "value": float, "id": int | None}`; `parse_gametable(data, *, physical_form, expected_field_count, expected_record_size, value_cell=0, id_cell=None, strict=False) -> GameTable`; and `classify_physical_form(field_count: int, record_size: int) -> str` returning `"implicit_row"` when `field_count == 1 and record_size == 4`, else `"explicit_id"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wow_constants_gametable.py
import struct
import pytest
from coa_client_extract.errors import DbcDriftError
from coa_client_extract.wdbc import parse_gametable, classify_physical_form


def _gt(records: bytes, field_count: int, record_size: int) -> bytes:
    count = len(records) // record_size
    return struct.pack("<4sIIII", b"WDBC", count, field_count, record_size, 0) + records


def test_classify_physical_form():
    assert classify_physical_form(1, 4) == "implicit_row"
    assert classify_physical_form(2, 8) == "explicit_id"


def test_implicit_row_reads_floats_in_order():
    data = _gt(struct.pack("<fff", 1.5, 2.5, 3.5), field_count=1, record_size=4)
    table = parse_gametable(data, physical_form="implicit_row",
                            expected_field_count=1, expected_record_size=4)
    assert table.record_count == 3 and table.drift is False
    assert [(r["ordinal"], r["value"], r["id"]) for r in table.rows] == [
        (0, 1.5, None), (1, 2.5, None), (2, 3.5, None)]


def test_explicit_id_reads_id_and_float():
    body = struct.pack("<If", 7, 4.25) + struct.pack("<If", 9, 8.75)
    data = _gt(body, field_count=2, record_size=8)
    table = parse_gametable(data, physical_form="explicit_id", expected_field_count=2,
                            expected_record_size=8, value_cell=1, id_cell=0)
    assert [(r["ordinal"], r["id"], r["value"]) for r in table.rows] == [(0, 7, 4.25), (1, 9, 8.75)]


def test_drift_flags_non_strict_and_raises_strict():
    data = _gt(struct.pack("<ff", 1.0, 2.0), field_count=2, record_size=8)
    assert parse_gametable(data, physical_form="implicit_row",
                           expected_field_count=1, expected_record_size=4).drift is True
    with pytest.raises(DbcDriftError):
        parse_gametable(data, physical_form="implicit_row",
                        expected_field_count=1, expected_record_size=4, strict=True)


def test_record_size_not_multiple_of_cell_raises():
    data = struct.pack("<4sIIII", b"WDBC", 0, 1, 6, 0)
    with pytest.raises(DbcDriftError):
        parse_gametable(data, physical_form="implicit_row",
                        expected_field_count=1, expected_record_size=4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_gametable.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_gametable'`.

- [ ] **Step 3: Add `GameTable`, `parse_gametable`, `classify_physical_form` to `wdbc.py`**

```python
# coa_client_extract/wdbc.py  (append)
@dataclass(frozen=True)
class GameTable:
    physical_form: str          # "implicit_row" | "explicit_id"
    field_count: int
    record_size: int
    record_count: int
    rows: list[dict]            # {"ordinal": int, "value": float, "id": int | None}
    drift: bool


def classify_physical_form(field_count: int, record_size: int) -> str:
    return "implicit_row" if field_count == 1 and record_size == _CELL else "explicit_id"


def parse_gametable(data: bytes, *, physical_form: str, expected_field_count: int,
                    expected_record_size: int, value_cell: int = 0,
                    id_cell: int | None = None, strict: bool = False) -> GameTable:
    """Decode a GameTable DBC preserving row ordinal and reading the value cell as a 32-bit float.
    Never decodes the value as an integer (contrast parse_positional)."""
    if physical_form not in ("implicit_row", "explicit_id"):
        raise ValueError(f"unknown physical_form {physical_form!r}")
    if len(data) < _HEADER.size:
        raise DbcDriftError("file smaller than DBC header")
    magic, record_count, field_count, record_size, _string_size = _HEADER.unpack_from(data, 0)
    if magic != _MAGIC:
        raise DbcDriftError(f"bad magic {magic!r}, expected WDBC")
    if record_size % _CELL != 0:
        raise DbcDriftError(f"record_size {record_size} not a multiple of {_CELL}")
    drift = field_count != expected_field_count or record_size != expected_record_size
    if drift and strict:
        raise DbcDriftError(f"field_count {field_count} / record_size {record_size} != expected "
                            f"{expected_field_count} / {expected_record_size}")
    records_start = _HEADER.size
    end = records_start + record_count * record_size
    if len(data) < end:
        raise DbcDriftError(f"truncated ({len(data)} bytes, expected >= {end})")
    cells = record_size // _CELL
    if value_cell >= cells or (id_cell is not None and id_cell >= cells):
        raise DbcDriftError(f"value/id cell index out of record bounds ({cells} cells)")
    rows: list[dict] = []
    for i in range(record_count):
        base = records_start + i * record_size
        (value,) = struct.unpack_from("<f", data, base + value_cell * _CELL)
        ident = None
        if id_cell is not None:
            (ident,) = struct.unpack_from("<I", data, base + id_cell * _CELL)
        rows.append({"ordinal": i, "value": value, "id": ident})
    return GameTable(physical_form, field_count, record_size, record_count, rows, drift)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wow_constants_gametable.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/wdbc.py tests/test_wow_constants_gametable.py
git commit -m "M1.14D Task 1: float ordinal/explicit-id GameTable reader (parse_gametable)"
```

---

## Task 2: Authored data files + hashing loader

**Files:**
- Create: `coa_client_extract/data/gt_axis_policy_v1.json`, `rating_enum_v1.json`, `power_type_enum_v1.json`, `wow_rules_v1.json`, `wotlk_reference_anchors_v1.json`
- Create: `coa_client_extract/wow_constants.py`
- Modify: `pyproject.toml`
- Test: `tests/test_wow_constants_authored.py`

**Interfaces:**
- Produces: `AuthoredInput(name: str, payload: dict, version: str, sha256: str)`; `load_authored_input(name, *, root=None) -> AuthoredInput` (reads `data/<name>_v1.json`, hashes exact bytes, requires string `version`); `AUTHORED_INPUTS = ("wow_rules", "rating_enum", "power_type_enum", "gt_axis_policy", "wotlk_reference_anchors")`.

- [ ] **Step 1: Create the five authored data files**

`coa_client_extract/data/rating_enum_v1.json`:

```json
{
  "version": "cr-3.3.5a-v1",
  "storage_stride": 32,
  "supported": {
    "0": "weapon_skill", "1": "defense_skill", "2": "dodge", "3": "parry", "4": "block",
    "5": "hit_melee", "6": "hit_ranged", "7": "hit_spell", "8": "crit_melee", "9": "crit_ranged",
    "10": "crit_spell", "11": "hit_taken_melee", "12": "hit_taken_ranged", "13": "hit_taken_spell",
    "14": "crit_taken_melee", "15": "crit_taken_ranged", "16": "crit_taken_spell",
    "17": "haste_melee", "18": "haste_ranged", "19": "haste_spell", "20": "weapon_skill_mainhand",
    "21": "weapon_skill_offhand", "22": "weapon_skill_ranged", "23": "expertise",
    "24": "armor_penetration"
  }
}
```

`coa_client_extract/data/power_type_enum_v1.json`:

```json
{
  "version": "m1.14c-power-v1",
  "map": {"-2": "health", "0": "mana", "1": "rage", "2": "focus", "3": "energy",
          "4": "happiness", "5": "runes", "6": "runic_power"}
}
```

`coa_client_extract/data/gt_axis_policy_v1.json` (each table declares its physical form + header + cells so explicit-id clients are handled without code changes; recon confirms/corrects and the Task 7 freeze commits the truth):

```json
{
  "version": "gt-layout-v1",
  "level_stride": 100,
  "rating_stride": 32,
  "class_axis": {"namespace": "chr_classes", "reference_expected_ids": [1,2,3,4,5,6,7,8,9,11],
                 "reference_holes": [10]},
  "defaults": {"physical_form": "implicit_row", "key_source": "ordinal",
               "expected_field_count": 1, "expected_record_size": 4, "value_cell": 0, "id_cell": null},
  "tables": {
    "combat_ratings": {"source_dbc": "gtCombatRatings", "index_kind": "rating_by_level",
      "axes": ["rating_id", "level"], "class_indexed": false,
      "supported": {"rating_id": {"min": 0, "max": 24}, "level": {"min": 1, "max": 100}}},
    "class_combat_rating_scalar": {"source_dbc": "gtOCTClassCombatRatingScalar",
      "index_kind": "class_rating_scalar", "index_offset": 1,
      "axes": ["wow_class_id", "rating_id"], "class_indexed": true,
      "supported": {"rating_id": {"min": 0, "max": 24}}},
    "melee_crit_per_agi": {"source_dbc": "gtChanceToMeleeCrit", "index_kind": "class_by_level",
      "axes": ["wow_class_id", "level"], "class_indexed": true,
      "supported": {"level": {"min": 1, "max": 100}}},
    "melee_crit_base": {"source_dbc": "gtChanceToMeleeCritBase", "index_kind": "class_only",
      "axes": ["wow_class_id"], "class_indexed": true, "supported": {}},
    "spell_crit_per_int": {"source_dbc": "gtChanceToSpellCrit", "index_kind": "class_by_level",
      "axes": ["wow_class_id", "level"], "class_indexed": true,
      "supported": {"level": {"min": 1, "max": 100}}},
    "spell_crit_base": {"source_dbc": "gtChanceToSpellCritBase", "index_kind": "class_only",
      "axes": ["wow_class_id"], "class_indexed": true, "supported": {}},
    "mana_regen_per_spirit": {"source_dbc": "gtRegenMPPerSpt", "index_kind": "class_by_level",
      "axes": ["wow_class_id", "level"], "class_indexed": true,
      "supported": {"level": {"min": 1, "max": 100}}}
  },
  "recon_gated": {
    "base_mana_by_class": {"source_dbc": "gtOCTBaseMPByClass", "index_kind": "class_by_level",
      "axes": ["wow_class_id", "level"], "class_indexed": true,
      "supported": {"level": {"min": 1, "max": 100}}, "semantics": "unproven"},
    "base_hp_by_class": {"source_dbc": "gtOCTBaseHPByClass", "index_kind": "class_by_level",
      "axes": ["wow_class_id", "level"], "class_indexed": true,
      "supported": {"level": {"min": 1, "max": 100}}, "semantics": "unproven"},
    "oct_regen_mp": {"source_dbc": "gtOCTRegenMP", "index_kind": "class_by_level",
      "axes": ["wow_class_id", "level"], "class_indexed": true,
      "supported": {"level": {"min": 1, "max": 100}}, "semantics": "unproven"}
  }
}
```

`coa_client_extract/data/wow_rules_v1.json`:

```json
{
  "version": "wow-rules-v1",
  "rules": {
    "base_energy": {"value": 100, "unit": "energy", "authority": "wotlk_reference",
      "ascension_verification": "unverified", "applies_to": ["energy_users"],
      "source_ref": "WotLK 3.3.5a base energy pool", "notes": "before aura/talent modifiers"},
    "energy_regen_per_sec": {"value": 10, "unit": "energy_per_sec", "authority": "wotlk_reference",
      "ascension_verification": "unverified", "applies_to": ["energy_users"],
      "source_ref": "WotLK 3.3.5a energy regen", "notes": "flat; not affected by haste in the stock path"},
    "rage_bounds": {"value": {"min": 0, "max": 100}, "unit": "rage_display",
      "authority": "wotlk_reference", "ascension_verification": "unverified",
      "applies_to": ["rage_users"], "source_ref": "WotLK 3.3.5a rage",
      "notes": "display units (internal x10); event-generated, decays out of combat"},
    "runic_power_bounds": {"value": {"min": 0, "max": 100}, "unit": "runic_power_display",
      "authority": "wotlk_reference", "ascension_verification": "unverified",
      "applies_to": ["runic_power_users"], "source_ref": "WotLK 3.3.5a runic power",
      "notes": "display units; event-generated, decays out of combat"},
    "gcd_floor_ms": {"value": 1000, "unit": "ms", "authority": "wotlk_reference",
      "ascension_verification": "unverified", "applies_to": ["all_spells"],
      "source_ref": "WotLK 3.3.5a GCD haste floor", "notes": "haste reduces spell GCD to this floor"},
    "standard_spell_gcd_base_ms": {"value": 1500, "unit": "ms", "authority": "wotlk_reference",
      "ascension_verification": "unverified", "applies_to": ["most_spells"],
      "source_ref": "WotLK 3.3.5a standard GCD",
      "notes": "standard default only; real base is per-spell StartRecoveryTime (M1.14E), not a ceiling"}
  }
}
```

`coa_client_extract/data/wotlk_reference_anchors_v1.json` (RAW, table-tagged coordinate anchors — `gtCombatRatings` is class-independent, so its raw divisor at a level equals the published "rating per 1%" for the base case; verified/extended at the Task 7 freeze):

```json
{
  "version": "wotlk-335a-anchors-v1",
  "anchors": [
    {"table": "combat_ratings", "rating_id": 10, "level": 60, "expected": 14.0, "tolerance": 1.0,
     "source_ref": "WotLK 3.3.5a: ~14 crit rating = 1% at level 60 (base divisor)"},
    {"table": "combat_ratings", "rating_id": 10, "level": 80, "expected": 45.90574, "tolerance": 1.0,
     "source_ref": "WotLK 3.3.5a: 45.90574 crit rating = 1% at level 80 (base divisor)"}
  ]
}
```

- [ ] **Step 2: Add `coa_client_extract` package-data to `pyproject.toml`**

Under `[tool.setuptools.package-data]`, add:

```toml
coa_client_extract = ["data/*.json"]
```

- [ ] **Step 3: Write the failing test**

```python
# tests/test_wow_constants_authored.py
import hashlib
import json
import pytest
from coa_client_extract.wow_constants import AUTHORED_INPUTS, load_authored_input


def test_all_authored_inputs_load_with_version_and_hash():
    for name in AUTHORED_INPUTS:
        ai = load_authored_input(name)
        assert ai.name == name and ai.version and len(ai.sha256) == 64
        assert isinstance(ai.payload, dict)


def test_hash_is_over_exact_on_disk_bytes(tmp_path):
    src = tmp_path / "wow_rules_v1.json"
    src.write_text(json.dumps({"version": "x", "rules": {}}))
    ai = load_authored_input("wow_rules", root=tmp_path)
    assert ai.sha256 == hashlib.sha256(src.read_bytes()).hexdigest()
    assert ai.version == "x"


def test_missing_version_key_raises(tmp_path):
    (tmp_path / "wow_rules_v1.json").write_text(json.dumps({"rules": {}}))
    with pytest.raises(ValueError):
        load_authored_input("wow_rules", root=tmp_path)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_authored.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'coa_client_extract.wow_constants'`.

- [ ] **Step 5: Create `wow_constants.py` with the loader**

```python
# coa_client_extract/wow_constants.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

AUTHORED_INPUTS = ("wow_rules", "rating_enum", "power_type_enum",
                   "gt_axis_policy", "wotlk_reference_anchors")
_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class AuthoredInput:
    name: str
    payload: dict
    version: str
    sha256: str


def load_authored_input(name: str, *, root: Path | None = None) -> AuthoredInput:
    path = (root or _DATA_DIR) / f"{name}_v1.json"
    raw = path.read_bytes()
    payload = json.loads(raw)
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{path.name}: missing string 'version'")
    return AuthoredInput(name=name, payload=payload, version=version,
                         sha256=hashlib.sha256(raw).hexdigest())
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_wow_constants_authored.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add coa_client_extract/data/ coa_client_extract/wow_constants.py \
        tests/test_wow_constants_authored.py pyproject.toml
git commit -m "M1.14D Task 2: authored data files (raw table-tagged anchors) + hashing loader"
```

---

## Task 3: GameTableLayout (physical form + cells) + axis mapping + ChrClasses

**Files:**
- Modify: `coa_client_extract/dbc_layouts.py`
- Modify: `coa_client_extract/wow_constants.py`
- Test: `tests/test_wow_constants_axis.py`

**Interfaces:**
- Produces: `GameTableLayout(key, source_dbc, physical_form, key_source, expected_field_count, expected_record_size, value_cell, id_cell, index_kind, axes, class_indexed, supported, index_offset=0, semantics="proven")`; `CHR_CLASSES` `DbcLayout` (id@0, power_type@2, name@5); `load_axis_policy(payload) -> (dict[str, GameTableLayout], int, int)` = `(layouts, level_stride, rating_stride)`; `map_table_entries(layout, table, *, class_roster, level_stride, rating_stride) -> (entries, counts)` where each entry is `{axis: int, ..., "value": float}` and `counts = {"source_records","emitted_entries","padding_records"}`. Raises `ValueError` on duplicate explicit ids.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wow_constants_axis.py
import struct
import pytest
from coa_client_extract.wow_constants import load_authored_input, load_axis_policy, map_table_entries
from coa_client_extract.wdbc import parse_gametable


def _implicit(values):
    return struct.pack("<4sIIII", b"WDBC", len(values), 1, 4, 0) + b"".join(
        struct.pack("<f", v) for v in values)


def _explicit(pairs):  # list of (id, value)
    body = b"".join(struct.pack("<If", i, v) for i, v in pairs)
    return struct.pack("<4sIIII", b"WDBC", len(pairs), 2, 8, 0) + body


def _policy():
    return load_axis_policy(load_authored_input("gt_axis_policy").payload)


def test_rating_by_level_drops_padding():
    layouts, ls, rs = _policy()
    table = parse_gametable(_implicit([float(i) for i in range(32 * 100)]),
                            physical_form="implicit_row", expected_field_count=1, expected_record_size=4)
    entries, counts = map_table_entries(layouts["combat_ratings"], table, class_roster=[],
                                        level_stride=ls, rating_stride=rs)
    assert counts == {"source_records": 3200, "emitted_entries": 2500, "padding_records": 700}
    assert next(e for e in entries if e["rating_id"] == 6 and e["level"] == 60)["value"] == 659.0


def test_class_rating_scalar_plus_one_offset_and_sparse_roster():
    layouts, ls, rs = _policy()
    table = parse_gametable(_implicit([float(i) for i in range(12 * 32)]),
                            physical_form="implicit_row", expected_field_count=1, expected_record_size=4)
    entries, _ = map_table_entries(layouts["class_combat_rating_scalar"], table, class_roster=[1, 2, 11],
                                   level_stride=ls, rating_stride=rs)
    assert next(e for e in entries if e["wow_class_id"] == 1 and e["rating_id"] == 6)["value"] == 7.0
    assert all(e["wow_class_id"] != 10 for e in entries)


def test_explicit_id_uses_id_not_ordinal_and_rejects_duplicates():
    layouts, ls, rs = _policy()
    layout = layouts["combat_ratings"].__class__(  # clone with explicit-id physical form
        **{**layouts["combat_ratings"].__dict__, "physical_form": "explicit_id",
           "key_source": "explicit_id", "expected_field_count": 2, "expected_record_size": 8,
           "value_cell": 1, "id_cell": 0})
    # explicit ids place (rating 6, level 60) -> index 659; give it a distinctive value
    pairs = [(659, 99.0), (0, 1.0)]
    table = parse_gametable(_explicit(pairs), physical_form="explicit_id", expected_field_count=2,
                            expected_record_size=8, value_cell=1, id_cell=0)
    entries, _ = map_table_entries(layout, table, class_roster=[], level_stride=ls, rating_stride=rs)
    assert next(e for e in entries if e["rating_id"] == 6 and e["level"] == 60)["value"] == 99.0
    dup = parse_gametable(_explicit([(5, 1.0), (5, 2.0)]), physical_form="explicit_id",
                          expected_field_count=2, expected_record_size=8, value_cell=1, id_cell=0)
    with pytest.raises(ValueError):
        map_table_entries(layout, dup, class_roster=[], level_stride=ls, rating_stride=rs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_axis.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_axis_policy'`.

- [ ] **Step 3: Add `GameTableLayout` + `CHR_CLASSES` to `dbc_layouts.py`**

```python
# coa_client_extract/dbc_layouts.py  (append)
@dataclass(frozen=True)
class GameTableLayout:
    key: str
    source_dbc: str
    physical_form: str          # "implicit_row" | "explicit_id"
    key_source: str             # "ordinal" | "explicit_id"
    expected_field_count: int
    expected_record_size: int
    value_cell: int
    id_cell: int | None
    index_kind: str             # rating_by_level | class_rating_scalar | class_by_level | class_only
    axes: tuple[str, ...]
    class_indexed: bool
    supported: dict
    index_offset: int = 0
    semantics: str = "proven"


# ChrClasses is a normal named DBC, NOT a GameTable. Pinned 3.3.5a columns: ClassID @0,
# powerType @2, first localized (enUS) name @5.
CHR_CLASSES = DbcLayout(
    name="ChrClasses", expected_field_count=60, expected_record_size=60 * 4,
    columns={"id": FieldSpec(0, "uint32"), "power_type": FieldSpec(2, "int32"),
             "name": FieldSpec(5, "str")},
)
```

- [ ] **Step 4: Add `load_axis_policy` + `map_table_entries` to `wow_constants.py`**

```python
# coa_client_extract/wow_constants.py  (append)
from .dbc_layouts import GameTableLayout
from .wdbc import GameTable


def load_axis_policy(payload: dict) -> tuple[dict[str, GameTableLayout], int, int]:
    level_stride = int(payload["level_stride"])
    rating_stride = int(payload["rating_stride"])
    defaults = payload.get("defaults", {})
    layouts: dict[str, GameTableLayout] = {}
    for group in ("tables", "recon_gated"):
        for key, spec in payload.get(group, {}).items():
            layouts[key] = GameTableLayout(
                key=key, source_dbc=spec["source_dbc"],
                physical_form=spec.get("physical_form", defaults["physical_form"]),
                key_source=spec.get("key_source", defaults["key_source"]),
                expected_field_count=int(spec.get("expected_field_count", defaults["expected_field_count"])),
                expected_record_size=int(spec.get("expected_record_size", defaults["expected_record_size"])),
                value_cell=int(spec.get("value_cell", defaults["value_cell"])),
                id_cell=spec.get("id_cell", defaults["id_cell"]),
                index_kind=spec["index_kind"], axes=tuple(spec["axes"]),
                class_indexed=bool(spec["class_indexed"]), supported=spec.get("supported", {}),
                index_offset=int(spec.get("index_offset", 0)),
                semantics=spec.get("semantics", "proven"))
    return layouts, level_stride, rating_stride


def _build_index(layout: GameTableLayout, table: GameTable) -> dict[int, float]:
    if layout.key_source == "explicit_id":
        index: dict[int, float] = {}
        for r in table.rows:
            if r["id"] in index:
                raise ValueError(f"{layout.key}: duplicate explicit id {r['id']}")
            index[r["id"]] = r["value"]
        return index
    return {r["ordinal"]: r["value"] for r in table.rows}


def map_table_entries(layout: GameTableLayout, table: GameTable, *, class_roster: list[int],
                      level_stride: int, rating_stride: int) -> tuple[list[dict], dict]:
    """Invert the reference index into explicit-coordinate entries. Uses the explicit id as the
    index when the physical form carries one (validating uniqueness), else the row ordinal.
    Never derives class width from a count."""
    by_index = _build_index(layout, table)
    entries: list[dict] = []

    def emit(index: int, coords: dict) -> None:
        if index in by_index:
            entries.append({**coords, "value": by_index[index]})

    if layout.index_kind == "rating_by_level":
        for rating_id in range(layout.supported["rating_id"]["min"], layout.supported["rating_id"]["max"] + 1):
            for level in range(layout.supported["level"]["min"], layout.supported["level"]["max"] + 1):
                emit(rating_id * level_stride + (level - 1), {"rating_id": rating_id, "level": level})
    elif layout.index_kind == "class_rating_scalar":
        for wow_class_id in class_roster:
            for rating_id in range(layout.supported["rating_id"]["min"], layout.supported["rating_id"]["max"] + 1):
                emit((wow_class_id - 1) * rating_stride + rating_id + layout.index_offset,
                     {"wow_class_id": wow_class_id, "rating_id": rating_id})
    elif layout.index_kind == "class_by_level":
        for wow_class_id in class_roster:
            for level in range(layout.supported["level"]["min"], layout.supported["level"]["max"] + 1):
                emit((wow_class_id - 1) * level_stride + (level - 1), {"wow_class_id": wow_class_id, "level": level})
    elif layout.index_kind == "class_only":
        for wow_class_id in class_roster:
            emit(wow_class_id - 1, {"wow_class_id": wow_class_id})
    else:
        raise ValueError(f"unknown index_kind {layout.index_kind!r}")

    counts = {"source_records": table.record_count, "emitted_entries": len(entries),
              "padding_records": table.record_count - len(entries)}
    return entries, counts
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_wow_constants_axis.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add coa_client_extract/dbc_layouts.py coa_client_extract/wow_constants.py tests/test_wow_constants_axis.py
git commit -m "M1.14D Task 3: GameTableLayout (physical form + cells), axis mapping (explicit-id), ChrClasses 0/2/5"
```

---

## Task 4: Class axis + default-power map

**Files:**
- Modify: `coa_client_extract/wow_constants.py`
- Test: `tests/test_wow_constants_class_axis.py`

**Interfaces:**
- Produces: `build_class_axis(chr_rows, *, reference_expected_ids, reference_holes, power_type_enum) -> dict` returning `{"namespace","reference_expected_ids","reference_holes","observed_client_ids","comparison","default_power_type_by_wow_class_id"}` with `comparison ∈ {"exact","extended","changed","ambiguous"}`; `class_roster(class_axis) -> list[int]`. Raises `ValueError` on duplicate ChrClasses ids or an unmapped power type.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wow_constants_class_axis.py
import pytest
from coa_client_extract.wow_constants import build_class_axis, class_roster

REF = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11]
POWER = {"map": {"0": "mana", "1": "rage", "3": "energy"}}


def _rows(pairs):  # (id, power_type)
    return [{"id": i, "power_type": p, "name": f"C{i}"} for i, p in pairs]


def test_exact_and_default_power_map():
    axis = build_class_axis(_rows([(i, 0) for i in REF]), reference_expected_ids=REF,
                            reference_holes=[10], power_type_enum=POWER)
    assert axis["comparison"] == "exact" and class_roster(axis) == REF
    assert axis["default_power_type_by_wow_class_id"]["1"] == "mana"


def test_extended_when_superset():
    axis = build_class_axis(_rows([(i, 0) for i in REF] + [(12, 3)]), reference_expected_ids=REF,
                            reference_holes=[10], power_type_enum=POWER)
    assert axis["comparison"] == "extended"
    assert axis["default_power_type_by_wow_class_id"]["12"] == "energy"


def test_changed_when_reference_id_missing():
    axis = build_class_axis(_rows([(1, 0), (2, 1)]), reference_expected_ids=REF,
                            reference_holes=[10], power_type_enum=POWER)
    assert axis["comparison"] == "changed"


def test_duplicate_and_unmapped_power_raise():
    with pytest.raises(ValueError):
        build_class_axis(_rows([(1, 0), (1, 0)]), reference_expected_ids=REF,
                         reference_holes=[10], power_type_enum=POWER)
    with pytest.raises(ValueError):
        build_class_axis(_rows([(1, 99)]), reference_expected_ids=[1], reference_holes=[],
                         power_type_enum=POWER)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_class_axis.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_class_axis'`.

- [ ] **Step 3: Implement `build_class_axis` + `class_roster`**

```python
# coa_client_extract/wow_constants.py  (append)
def build_class_axis(chr_rows: list[dict], *, reference_expected_ids: list[int],
                     reference_holes: list[int], power_type_enum: dict) -> dict:
    ids = [int(r["id"]) for r in chr_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ChrClasses ids")
    power_map = power_type_enum.get("map", {})
    default_power: dict[str, str] = {}
    for r in chr_rows:
        pt = str(int(r["power_type"]))
        if pt not in power_map:
            raise ValueError(f"class {r['id']}: unmapped power_type {pt}")
        default_power[str(int(r["id"]))] = power_map[pt]

    observed = sorted(ids)
    ref = sorted(reference_expected_ids)
    ref_set, obs_set = set(ref), set(observed)
    if obs_set == ref_set:
        comparison = "exact"
    elif obs_set > ref_set:
        comparison = "extended"
    elif obs_set < ref_set:
        comparison = "changed"
    else:
        comparison = "ambiguous"
    return {"namespace": "chr_classes", "reference_expected_ids": ref,
            "reference_holes": sorted(reference_holes), "observed_client_ids": observed,
            "comparison": comparison, "default_power_type_by_wow_class_id": default_power}


def class_roster(class_axis: dict) -> list[int]:
    return list(class_axis["observed_client_ids"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wow_constants_class_axis.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/wow_constants.py tests/test_wow_constants_class_axis.py
git commit -m "M1.14D Task 4: class axis (reference vs observed) + default-power map"
```

---

## Task 5: Deep reconnaissance + report

**Files:**
- Modify: `coa_client_extract/wow_constants.py`
- Test: `tests/test_wow_constants_recon.py`

**Interfaces:**
- Produces: `recon(backend, root, attach, *, axis_policy, rating_enum, power_type_enum, reference_class_axis, chr_layout=CHR_CLASSES) -> dict`. Per-table findings: `available`, `physical_form` (classified from the header), `source_records`, `drift`, `finite_ok`, `duplicate_ids`, `coverage` (emitted vs expected), `padding_records`, `monotonic_violations`, `extended_class_out_of_storage`, `observed_rating_ids`. Plus `class_axis`, `enum_coverage` (`unmapped_rating_ids`, `unmapped_power_types`), and `class_context_resolution` (default `"unproven"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wow_constants_recon.py
import struct
from pathlib import Path
from coa_client_extract.archive_backend import FakeArchiveBackend
from coa_client_extract.wow_constants import recon, load_authored_input, load_axis_policy


def _implicit(values):
    return struct.pack("<4sIIII", b"WDBC", len(values), 1, 4, 0) + b"".join(
        struct.pack("<f", v) for v in values)


def _chr_classes(pairs):  # (id, power_type)
    strings = b"\x00" + b"".join(f"C{i}".encode() + b"\x00" for i, _ in pairs)
    rows, off = [], 1
    for i, p in pairs:
        cells = [0] * 60
        cells[0], cells[2], cells[5] = i, p, off      # id@0, power@2, name@5
        off += len(f"C{i}") + 1
        rows.append(struct.pack("<" + "I" * 60, *cells))
    return struct.pack("<4sIIII", b"WDBC", len(pairs), 60, 240, len(strings)) + b"".join(rows) + strings


def _backend():
    ids = [(i, 0) for i in [1,2,3,4,5,6,7,8,9,11]]
    e = {
        "DBFilesClient\\gtCombatRatings.dbc": [(Path("patch-M.MPQ"), _implicit([float(i) for i in range(3200)]))],
        "DBFilesClient\\gtOCTClassCombatRatingScalar.dbc": [(Path("patch-M.MPQ"), _implicit([1.0] * (12 * 32)))],
        "DBFilesClient\\gtChanceToMeleeCrit.dbc": [(Path("patch-M.MPQ"), _implicit([0.05] * (12 * 100)))],
        "DBFilesClient\\gtChanceToMeleeCritBase.dbc": [(Path("patch-M.MPQ"), _implicit([0.01] * 12))],
        "DBFilesClient\\gtChanceToSpellCrit.dbc": [(Path("patch-M.MPQ"), _implicit([0.05] * (12 * 100)))],
        "DBFilesClient\\gtChanceToSpellCritBase.dbc": [(Path("patch-M.MPQ"), _implicit([0.01] * 12))],
        "DBFilesClient\\gtRegenMPPerSpt.dbc": [(Path("patch-M.MPQ"), _implicit([0.1] * (12 * 100)))],
        "DBFilesClient\\ChrClasses.dbc": [(Path("patch-M.MPQ"), _chr_classes(ids))],
    }
    return FakeArchiveBackend(e), Path("common.MPQ"), (Path("patch-M.MPQ"),)


def _inputs():
    axis = load_authored_input("gt_axis_policy")
    layouts, ls, rs = load_axis_policy(axis.payload)
    return ((layouts, ls, rs), load_authored_input("rating_enum").payload,
            load_authored_input("power_type_enum").payload, axis.payload["class_axis"])


def test_recon_reports_findings_class_axis_and_context():
    backend, root, attach = _backend()
    axis_policy, rating_enum, power_enum, ref_axis = _inputs()
    r = recon(backend, root, attach, axis_policy=axis_policy, rating_enum=rating_enum,
              power_type_enum=power_enum, reference_class_axis=ref_axis)
    cr = r["tables"]["combat_ratings"]
    assert cr["available"] and cr["source_records"] == 3200 and cr["drift"] is False
    assert cr["physical_form"] == "implicit_row" and cr["finite_ok"] is True
    assert cr["coverage"]["emitted_entries"] == 2500
    assert r["class_axis"]["comparison"] == "exact"
    assert r["enum_coverage"]["unmapped_rating_ids"] == []
    assert r["class_context_resolution"] == "unproven"
    assert r["tables"]["oct_regen_mp"]["available"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_recon.py -v`
Expected: FAIL with `ImportError: cannot import name 'recon'`.

- [ ] **Step 3: Implement `recon` (deep findings)**

```python
# coa_client_extract/wow_constants.py  (append)
import math
from .archive_backend import ArchiveBackend
from .dbc_layouts import CHR_CLASSES
from .errors import ArchiveError
from .wdbc import classify_physical_form, parse_dbc, parse_gametable


def _monotonic_violations(entries: list[dict], group_axis: str, order_axis: str) -> int:
    from collections import defaultdict
    series = defaultdict(list)
    for e in entries:
        if group_axis in e and order_axis in e:
            series[e[group_axis]].append((e[order_axis], e["value"]))
    violations = 0
    for pts in series.values():
        pts.sort()
        violations += sum(1 for (_, a), (_, b) in zip(pts, pts[1:]) if b < a)  # nondecreasing
    return violations


def recon(backend: ArchiveBackend, root, attach, *, axis_policy, rating_enum, power_type_enum,
          reference_class_axis, chr_layout=CHR_CLASSES) -> dict:
    layouts, level_stride, rating_stride = axis_policy

    chr_member = backend.read_effective_file(root, attach, "DBFilesClient\\ChrClasses.dbc")
    chr_tbl = parse_dbc(chr_member.data, chr_layout)
    class_axis = build_class_axis(chr_tbl.rows,
                                  reference_expected_ids=reference_class_axis["reference_expected_ids"],
                                  reference_holes=reference_class_axis["reference_holes"],
                                  power_type_enum=power_type_enum)
    roster = class_roster(class_axis)

    rating_supported = set(rating_enum.get("supported", {}))
    observed_ratings: set[int] = set()
    tables: dict[str, dict] = {}
    for key, layout in layouts.items():
        try:
            member = backend.read_effective_file(root, attach, f"DBFilesClient\\{layout.source_dbc}.dbc")
        except ArchiveError:
            tables[key] = {"available": False, "source_dbc": layout.source_dbc}
            continue
        table = parse_gametable(member.data, physical_form=layout.physical_form,
                                expected_field_count=layout.expected_field_count,
                                expected_record_size=layout.expected_record_size,
                                value_cell=layout.value_cell, id_cell=layout.id_cell)
        physical = classify_physical_form(table.field_count, table.record_size)
        finite_ok = all(math.isfinite(r["value"]) for r in table.rows)
        try:
            entries, counts = map_table_entries(layout, table, class_roster=roster,
                                                level_stride=level_stride, rating_stride=rating_stride)
            dup = False
        except ValueError:
            entries, counts, dup = [], {"emitted_entries": 0}, True
        observed_ratings |= {e["rating_id"] for e in entries if "rating_id" in e}
        max_class = max(roster) if (layout.class_indexed and roster) else 0
        out_of_storage = layout.class_indexed and (max_class - 1) * level_stride >= table.record_count \
            and layout.index_kind in ("class_by_level",)
        tables[key] = {"available": True, "source_dbc": layout.source_dbc, "physical_form": physical,
                       "declared_physical_form": layout.physical_form, "source_records": table.record_count,
                       "drift": table.drift, "finite_ok": finite_ok, "duplicate_ids": dup,
                       "coverage": counts, "padding_records": counts.get("padding_records", 0),
                       "monotonic_violations": _monotonic_violations(entries, "rating_id", "level")
                       if key == "combat_ratings" else _monotonic_violations(entries, "wow_class_id", "level"),
                       "extended_class_out_of_storage": bool(out_of_storage),
                       "class_indexed": layout.class_indexed, "semantics": layout.semantics}

    return {"tables": tables, "class_axis": class_axis,
            "enum_coverage": {"unmapped_rating_ids": sorted(r for r in observed_ratings
                                                            if str(r) not in rating_supported),
                              "unmapped_power_types": []},
            "class_context_resolution": "unproven"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wow_constants_recon.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/wow_constants.py tests/test_wow_constants_recon.py
git commit -m "M1.14D Task 5: deep reconnaissance (physical form, finiteness, coverage, monotonicity, enum, class axis)"
```

---

## Task 6: Minimal `wow-constants --recon-only` CLI

**Files:**
- Modify: `coa_client_extract/wow_constants.py` (recon orchestration + report writer)
- Modify: `coa_client_extract/cli.py` (subcommand, recon-only path only)
- Test: `tests/test_wow_constants_cli.py` (recon-only cases)

**Interfaces:**
- Produces: `run_recon(client_root, out_dir, *, backend, plan) -> dict` (writes `coa_wow_constants_recon.json`, returns the report); `wow_constants_command(client_root, out_dir, *, backend=None, stormlib_path=None, recon_only=False) -> dict` in `cli.py` (Task 6 wires only `recon_only=True`; the canonical branch is added in Task 10); the `wow-constants` subparser with `--recon-only`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wow_constants_cli.py
import json
import struct
from pathlib import Path
import pytest
from coa_client_extract.archive_backend import FakeArchiveBackend
from coa_client_extract.cli import main, wow_constants_command
from coa_client_extract.errors import BackendUnavailable


def _client(tmp_path: Path) -> Path:
    data = tmp_path / "Data"
    data.mkdir()
    for name in ("common.MPQ", "patch.MPQ", "patch-M.MPQ"):
        (data / name).write_bytes(b"MPQ\x1a")
    return data


def _implicit(values):
    return struct.pack("<4sIIII", b"WDBC", len(values), 1, 4, 0) + b"".join(
        struct.pack("<f", v) for v in values)


def _chr_classes(pairs):
    strings = b"\x00" + b"".join(f"C{i}".encode() + b"\x00" for i, _ in pairs)
    rows, off = [], 1
    for i, p in pairs:
        cells = [0] * 60
        cells[0], cells[2], cells[5] = i, p, off
        off += len(f"C{i}") + 1
        rows.append(struct.pack("<" + "I" * 60, *cells))
    return struct.pack("<4sIIII", b"WDBC", len(pairs), 60, 240, len(strings)) + b"".join(rows) + strings


def make_backend(**overrides):
    ids = [(i, 0) for i in [1,2,3,4,5,6,7,8,9,11]]
    e = {
        "DBFilesClient\\gtCombatRatings.dbc": [(Path("patch-M.MPQ"), _implicit([float(i) for i in range(3200)]))],
        "DBFilesClient\\gtOCTClassCombatRatingScalar.dbc": [(Path("patch-M.MPQ"), _implicit([1.0] * (12 * 32)))],
        "DBFilesClient\\gtChanceToMeleeCrit.dbc": [(Path("patch-M.MPQ"), _implicit([0.05] * (12 * 100)))],
        "DBFilesClient\\gtChanceToMeleeCritBase.dbc": [(Path("patch-M.MPQ"), _implicit([0.01] * 12))],
        "DBFilesClient\\gtChanceToSpellCrit.dbc": [(Path("patch-M.MPQ"), _implicit([0.05] * (12 * 100)))],
        "DBFilesClient\\gtChanceToSpellCritBase.dbc": [(Path("patch-M.MPQ"), _implicit([0.01] * 12))],
        "DBFilesClient\\gtRegenMPPerSpt.dbc": [(Path("patch-M.MPQ"), _implicit([0.1] * (12 * 100)))],
        "DBFilesClient\\ChrClasses.dbc": [(Path("patch-M.MPQ"), _chr_classes(ids))],
    }
    for k, v in overrides.items():
        key = "DBFilesClient\\" + k + ".dbc"
        if v is None:
            e.pop(key, None)
        else:
            e[key] = [(Path("patch-M.MPQ"), v)]
    return FakeArchiveBackend(e)


def test_recon_only_writes_report_not_snapshot(tmp_path):
    out = tmp_path / "out"
    report = wow_constants_command(_client(tmp_path), out, backend=make_backend(), recon_only=True)
    assert report["class_axis"]["comparison"] == "exact"
    assert (out / "coa_wow_constants_recon.json").is_file()
    assert not (out / "coa_wow_constants.json").exists()


def test_cli_recon_only_fails_closed_without_stormlib(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise BackendUnavailable("StormLib not found")
    monkeypatch.setattr("coa_client_extract.stormlib_backend.StormLibBackend", boom, raising=False)
    rc = main(["wow-constants", "--client-root", str(_client(tmp_path)),
               "--out", str(tmp_path / "o"), "--recon-only"])
    assert rc == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'wow_constants_command'`.

- [ ] **Step 3: Add `run_recon` to `wow_constants.py`**

```python
# coa_client_extract/wow_constants.py  (append)
import json as _json
from pathlib import Path


def run_recon(client_root, out_dir, *, backend, plan) -> dict:
    root, attach = plan.open_chain
    axis = load_authored_input("gt_axis_policy")
    layouts, ls, rs = load_axis_policy(axis.payload)
    report = recon(backend, root, attach, axis_policy=(layouts, ls, rs),
                   rating_enum=load_authored_input("rating_enum").payload,
                   power_type_enum=load_authored_input("power_type_enum").payload,
                   reference_class_axis=axis.payload["class_axis"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "coa_wow_constants_recon.json").write_text(
        _json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
```

- [ ] **Step 4: Wire the subcommand + recon-only path in `cli.py`**

```python
# coa_client_extract/cli.py  (add near regenerate)
def wow_constants_command(client_root: Path, out_dir: Path, *, backend: ArchiveBackend | None = None,
                          stormlib_path: str | None = None, recon_only: bool = False) -> dict:
    if backend is None:
        from .stormlib_backend import StormLibBackend
        backend = StormLibBackend(stormlib_path=stormlib_path)  # may raise BackendUnavailable
    plan = discover_plan(client_root)
    from .wow_constants import run_recon
    if recon_only:
        return run_recon(client_root, out_dir, backend=backend, plan=plan)
    from .wow_constants import run_extract          # added in Task 10
    return run_extract(client_root, out_dir, backend=backend, plan=plan,
                       extractor_commit=_extractor_commit(), client_build=_client_build(plan))
```

In `main`, add the subparser + dispatch:

```python
    wc = sub.add_parser("wow-constants", help="extract coa-wow-constants-v1 GameTable primitives")
    wc.add_argument("--client-root", required=True, type=Path)
    wc.add_argument("--out", required=True, type=Path)
    wc.add_argument("--stormlib", default=None)
    wc.add_argument("--recon-only", action="store_true")
```

```python
    if args.command == "wow-constants":
        try:
            wow_constants_command(args.client_root, args.out, stormlib_path=args.stormlib,
                                  recon_only=args.recon_only)
        except BackendUnavailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0
```

- [ ] **Step 5: Run the recon-only tests to verify they pass**

Run: `pytest tests/test_wow_constants_cli.py -k recon_only -v`
Expected: PASS (2 passed). (The canonical CLI tests are added in Task 10.)

- [ ] **Step 6: Commit**

```bash
git add coa_client_extract/wow_constants.py coa_client_extract/cli.py tests/test_wow_constants_cli.py
git commit -m "M1.14D Task 6: minimal wow-constants --recon-only CLI (fails closed w/o StormLib)"
```

---

## Task 7: Real-client recon adjudication checkpoint (HARD HOLD POINT — manual)

> **This task gates every canonical task below (8–10, 14).** No canonical `coa_wow_constants.json` may be generated or trusted until the real-client recon is reviewed and the authored data frozen. It requires the local Ascension client and a built StormLib; it produces no code, only frozen/adjudicated authored data. The executable recon CLI now exists (Task 6). If you cannot run the real client here, STOP and hand this checkpoint to the maintainer before Task 8.

**Files:**
- Modify (freeze to observed reality): `coa_client_extract/data/gt_axis_policy_v1.json`, `rating_enum_v1.json`, `wotlk_reference_anchors_v1.json`
- Create (only if the client axis is not `exact`): `reports/client_extract/wow_class_axis_adjudication.json` (tracked)
- Create (git-ignored, real): `reports/client_extract/coa_wow_constants_recon.json`

- [ ] **Step 1: Run recon against the real client**

```bash
COA_CLIENT_ROOT=/path/to/ascension-live/Data \
python -m coa_client_extract wow-constants --client-root "$COA_CLIENT_ROOT" \
  --out reports/client_extract --recon-only
```

- [ ] **Step 2: Review `reports/client_extract/coa_wow_constants_recon.json` and adjudicate**

- **Physical form**: for any `gt*.dbc` whose `physical_form` != `declared_physical_form`, update that table in `gt_axis_policy_v1.json` (`physical_form`/`key_source`/`expected_field_count`/`expected_record_size`/`value_cell`/`id_cell`) to the observed form.
- **Findings must be clean** on proven-required tables: `finite_ok == true`, `duplicate_ids == false`, `drift == false`, `extended_class_out_of_storage == false`, and `enum_coverage.unmapped_rating_ids == []`. Any violation is adjudicated before freezing (fix the policy/enum, or record why the client legitimately differs).
- **Class axis**: if `comparison == "exact"`, proceed. If `extended`/`changed`/`ambiguous`, create the tracked `reports/client_extract/wow_class_axis_adjudication.json` with `{"schema": "wow-class-axis-adjudication-v1", "accepted_comparison": "<value>", "observed_client_ids": [...], "rationale": "...", "reviewer": "...", "date": "..."}`. This file is required by canonical extraction (Task 10) and its hash is manifest-bound.
- **Recon-gated tables**: for each present table whose role you establish, flip its `semantics` to `proven` in `gt_axis_policy_v1.json`; leave the rest `unproven`.
- **Anchors**: verify each `combat_ratings` raw anchor against the observed value; keep as documented reference (record match/deviation — never delete because the client differs). Add a few more table-tagged raw anchors if the client makes them available.

- [ ] **Step 3: Commit the frozen authored data (+ adjudication if created)**

```bash
git add coa_client_extract/data/gt_axis_policy_v1.json coa_client_extract/data/rating_enum_v1.json \
        coa_client_extract/data/wotlk_reference_anchors_v1.json
# if created:
git add reports/client_extract/wow_class_axis_adjudication.json
git commit -m "M1.14D Task 7: freeze GameTable axis policy/enums/anchors from real-client recon"
```

---

## Task 8: Reference comparison + snapshot assembly

**Files:**
- Modify: `coa_client_extract/wow_constants.py`
- Test: `tests/test_wow_constants_snapshot.py`

**Interfaces:**
- Produces: `reference_comparison(entries, anchors, *, axes, anchor_set_version, anchor_set_sha256) -> dict` (`scope: "anchors"`, keyed on `axes`; `checked`/`equal`/`different`/`status`); `build_snapshot(*, client_build, provenance, class_axis, game_tables, rules, rating_enum, power_type_enum) -> dict` producing the `coa-wow-constants-v1` document (rejects non-finite entry values).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wow_constants_snapshot.py
import math
import pytest
from coa_client_extract.wow_constants import reference_comparison, build_snapshot


def test_reference_comparison_is_anchor_scoped_on_axes():
    entries = [{"rating_id": 10, "level": 60, "value": 14.0},
               {"rating_id": 10, "level": 80, "value": 40.0}]
    anchors = [{"table": "combat_ratings", "rating_id": 10, "level": 60, "expected": 14.0, "tolerance": 0.5},
               {"table": "combat_ratings", "rating_id": 10, "level": 80, "expected": 45.9, "tolerance": 0.5}]
    rc = reference_comparison(entries, anchors, axes=("rating_id", "level"),
                              anchor_set_version="v1", anchor_set_sha256="ab")
    assert rc["scope"] == "anchors" and rc["checked"] == 2 and rc["equal"] == 1 and rc["different"] == 1
    assert rc["status"] == "differs_on_checked_anchors"


def test_build_snapshot_shape_and_rejects_non_finite():
    ok = build_snapshot(client_build="3.3.5a+patch-M", provenance={"backend": "fake", "source_dbcs": {}},
        class_axis={"namespace": "chr_classes", "comparison": "exact", "observed_client_ids": [1]},
        game_tables={"combat_ratings": {"axes": ["rating_id", "level"], "class_indexed": False,
                     "entries": [{"rating_id": 0, "level": 1, "value": 1.0}]}},
        rules={"base_energy": {"value": 100}},
        rating_enum={"version": "cr-3.3.5a-v1", "supported": {"0": "weapon_skill"}},
        power_type_enum={"version": "m1.14c-power-v1", "map": {"0": "mana"}})
    assert ok["schema_version"] == "coa-wow-constants-v1"
    assert set(ok) >= {"schema_version", "client_build", "provenance", "class_axis", "enum_maps",
                       "game_tables", "rules"}
    with pytest.raises(ValueError):
        build_snapshot(client_build="t", provenance={}, class_axis={},
            game_tables={"t": {"axes": ["x"], "class_indexed": False,
                         "entries": [{"x": 0, "value": math.inf}]}},
            rules={}, rating_enum={}, power_type_enum={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_snapshot.py -v`
Expected: FAIL with `ImportError: cannot import name 'reference_comparison'`.

- [ ] **Step 3: Implement `reference_comparison` + `build_snapshot`**

```python
# coa_client_extract/wow_constants.py  (append)
WOW_CONSTANTS_SCHEMA = "coa-wow-constants-v1"


def reference_comparison(entries: list[dict], anchors: list[dict], *, axes: tuple[str, ...],
                         anchor_set_version: str, anchor_set_sha256: str) -> dict:
    index = {tuple(e[a] for a in axes): e["value"] for e in entries}
    checked = equal = different = 0
    for anchor in anchors:
        try:
            key = tuple(anchor[a] for a in axes)
        except KeyError:
            continue
        if key not in index:
            continue
        checked += 1
        if abs(index[key] - anchor["expected"]) <= anchor.get("tolerance", 0.0):
            equal += 1
        else:
            different += 1
    status = ("matches_on_checked_anchors" if checked and different == 0
              else "differs_on_checked_anchors" if checked else "no_anchors_checked")
    return {"scope": "anchors", "anchor_set_version": anchor_set_version,
            "anchor_set_sha256": anchor_set_sha256, "checked": checked, "equal": equal,
            "different": different, "status": status}


def build_snapshot(*, client_build: str, provenance: dict, class_axis: dict, game_tables: dict,
                   rules: dict, rating_enum: dict, power_type_enum: dict) -> dict:
    for key, table in game_tables.items():
        for entry in table.get("entries", []):
            if not math.isfinite(entry["value"]):
                raise ValueError(f"{key}: non-finite value in entries")
    return {"schema_version": WOW_CONSTANTS_SCHEMA, "client_build": client_build,
            "provenance": provenance, "class_axis": class_axis,
            "enum_maps": {"rating_enum": rating_enum, "power_type": power_type_enum},
            "game_tables": game_tables, "rules": rules}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wow_constants_snapshot.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/wow_constants.py tests/test_wow_constants_snapshot.py
git commit -m "M1.14D Task 8: axis-scoped reference comparison + snapshot assembly"
```

---

## Task 9: `write_wow_constants` — manifest-last with hashed authored inputs

**Files:**
- Modify: `coa_client_extract/artifacts.py`
- Test: `tests/test_wow_constants_write.py`

**Interfaces:**
- Produces: `write_wow_constants(snapshot, out_dir, *, authored_inputs, source_dbc_sha256, class_context_resolution, extractor_commit, client_build, table_summary, class_axis_adjudication=None) -> dict` — writes `coa_wow_constants.json` then `coa_wow_constants.manifest.json` last; manifest binds artifact hash+length, every authored input (version+sha256), the optional adjudication, and `class_context_resolution`.

- [ ] **Step 1: Write the failing test (includes a real interrupted-write test)**

```python
# tests/test_wow_constants_write.py
import hashlib
import json
from pathlib import Path
import pytest
from coa_client_extract.artifacts import write_wow_constants, _atomic_write_bytes


class _AI:
    def __init__(self, name, version, sha256):
        self.name, self.version, self.sha256 = name, version, sha256


def _inputs():
    return [_AI("wow_rules", "wow-rules-v1", "a" * 64), _AI("rating_enum", "cr-3.3.5a-v1", "b" * 64),
            _AI("power_type_enum", "m1.14c-power-v1", "c" * 64),
            _AI("gt_axis_policy", "gt-layout-v1", "d" * 64),
            _AI("wotlk_reference_anchors", "wotlk-335a-anchors-v1", "e" * 64)]


def _write(out: Path, **over):
    snap = {"schema_version": "coa-wow-constants-v1", "client_build": "3.3.5a+patch-M"}
    kw = dict(authored_inputs=_inputs(), source_dbc_sha256={"gtCombatRatings": "f" * 64},
              class_context_resolution="unproven", extractor_commit="deadbeef",
              client_build="3.3.5a+patch-M", table_summary={})
    kw.update(over)
    return write_wow_constants(snap, out, **kw)


def test_manifest_binds_artifact_and_every_authored_input(tmp_path):
    manifest = _write(tmp_path)
    art = tmp_path / "coa_wow_constants.json"
    assert manifest["artifact"]["sha256"] == hashlib.sha256(art.read_bytes()).hexdigest()
    assert manifest["artifact"]["byte_length"] == art.stat().st_size
    assert set(manifest["authored_inputs"]) == {"rules", "rating_enum", "power_type_enum",
                                                "axis_layout_policy", "reference_anchors"}
    assert manifest["authored_inputs"]["rules"] == {"version": "wow-rules-v1", "sha256": "a" * 64}
    assert manifest["class_context_resolution"] == "unproven"


def test_adjudication_bound_when_present(tmp_path):
    adj = {"name": "class_axis_adjudication", "version": "wow-class-axis-adjudication-v1",
           "sha256": "9" * 64}
    manifest = _write(tmp_path, class_axis_adjudication=adj)
    assert manifest["authored_inputs"]["class_axis_adjudication"] == {
        "version": "wow-class-axis-adjudication-v1", "sha256": "9" * 64}


def test_interrupted_write_leaves_no_valid_manifest(tmp_path, monkeypatch):
    # Simulate a crash after the artifact is written but before the manifest marker.
    orig = _atomic_write_bytes
    calls = {"n": 0}

    def flaky(data, path):
        calls["n"] += 1
        if calls["n"] == 2:                       # the manifest write
            raise OSError("disk full")
        return orig(data, path)
    monkeypatch.setattr("coa_client_extract.artifacts._atomic_write_bytes", flaky)
    with pytest.raises(OSError):
        _write(tmp_path)
    assert (tmp_path / "coa_wow_constants.json").exists()
    assert not (tmp_path / "coa_wow_constants.manifest.json").exists()  # no valid marker
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_write.py -v`
Expected: FAIL with `ImportError: cannot import name 'write_wow_constants'`.

- [ ] **Step 3: Implement `write_wow_constants`**

```python
# coa_client_extract/artifacts.py  (append)
from datetime import date

_AUTHORED_MANIFEST_KEYS = {"wow_rules": "rules", "rating_enum": "rating_enum",
                           "power_type_enum": "power_type_enum",
                           "gt_axis_policy": "axis_layout_policy",
                           "wotlk_reference_anchors": "reference_anchors",
                           "class_axis_adjudication": "class_axis_adjudication"}


def write_wow_constants(snapshot: dict, out_dir: Path, *, authored_inputs, source_dbc_sha256: dict,
                        class_context_resolution: str, extractor_commit: str, client_build: str,
                        table_summary: dict, class_axis_adjudication=None) -> dict:
    art_path = out_dir / "coa_wow_constants.json"
    manifest_path = out_dir / "coa_wow_constants.manifest.json"
    body = (json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    inputs = list(authored_inputs)
    if class_axis_adjudication is not None:
        inputs.append(class_axis_adjudication)
    authored = {_AUTHORED_MANIFEST_KEYS[ai.name]: {"version": ai.version, "sha256": ai.sha256}
                for ai in inputs}

    manifest = {
        "schema_version": "coa-wow-constants-manifest-v1",
        "artifact": {"path": art_path.name, "sha256": _sha256_bytes(body), "byte_length": len(body)},
        "source_dbc_sha256": dict(source_dbc_sha256), "authored_inputs": authored,
        "class_context_resolution": class_context_resolution, "table_summary": dict(table_summary),
        "extractor_commit": extractor_commit, "client_build": client_build,
        "extraction_date": date.today().isoformat(),
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest_path.unlink()                 # remove stale marker first
    _atomic_write_bytes(body, art_path)         # write artifact
    _atomic_write_bytes(manifest_bytes, manifest_path)  # write marker LAST
    return manifest
```

Note: `class_axis_adjudication` is passed as an object exposing `.name`/`.version`/`.sha256` (an `AuthoredInput`); the test uses a `dict`-shaped stand-in, so also accept a mapping — adjust the append to wrap a dict:

```python
    if class_axis_adjudication is not None:
        adj = class_axis_adjudication
        if isinstance(adj, dict):
            from types import SimpleNamespace
            adj = SimpleNamespace(**adj)
        inputs.append(adj)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wow_constants_write.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/artifacts.py tests/test_wow_constants_write.py
git commit -m "M1.14D Task 9: write_wow_constants (manifest-last, hashed inputs, adjudication, interrupt-safe)"
```

---

## Task 10: Full canonical extraction + CLI (mandatory tables, adjudication gate)

**Files:**
- Modify: `coa_client_extract/wow_constants.py` (`run_extract`)
- Test: `tests/test_wow_constants_cli.py` (canonical cases)

**Interfaces:**
- Produces: `run_extract(client_root, out_dir, *, backend, plan, extractor_commit, client_build, adjudication_path=None) -> dict`. Enforces: every proven-required table available (else `MissingRequiredTable`); strict `parse_gametable` (drift → raise, no output); class axis `exact` → proceed, else require a tracked adjudication file (hash-bound) or raise; emits `game_tables` with `domains`, `counts`, `reference_comparison`; writes via `write_wow_constants`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wow_constants_cli.py  (append; reuses _client/make_backend/_implicit from Task 6)
import hashlib
from coa_client_extract.wow_constants import run_extract
from coa_client_extract.errors import DbcDriftError


def _plan(client_root):
    from coa_client_extract.archive_plan import discover_plan
    return discover_plan(client_root)


def test_canonical_extract_writes_snapshot_and_manifest(tmp_path):
    out = tmp_path / "out"
    manifest = run_extract(_client(tmp_path), out, backend=make_backend(), plan=_plan(_client(tmp_path)),
                           extractor_commit="c0ffee", client_build="3.3.5a+patch-M")
    snap = json.loads((out / "coa_wow_constants.json").read_text())
    assert snap["schema_version"] == "coa-wow-constants-v1"
    assert snap["class_axis"]["comparison"] == "exact"
    ct = snap["game_tables"]["combat_ratings"]
    assert next(e for e in ct["entries"] if e["rating_id"] == 6 and e["level"] == 60)["value"] == 659.0
    # raw anchors match combat_ratings -> anchors are actually checked
    assert ct["reference_comparison"]["checked"] >= 1
    assert manifest["class_context_resolution"] == "unproven"


def test_missing_required_table_fails_closed(tmp_path):
    from coa_client_extract.wow_constants import MissingRequiredTable
    b = make_backend(gtChanceToMeleeCrit=None)
    with pytest.raises(MissingRequiredTable):
        run_extract(_client(tmp_path), tmp_path / "o", backend=b, plan=_plan(_client(tmp_path)),
                    extractor_commit="x", client_build="y")
    assert not (tmp_path / "o" / "coa_wow_constants.json").exists()


def test_strict_drift_produces_no_output(tmp_path):
    # gtCombatRatings with a 2-field header where the policy expects 1 field -> strict drift
    bad = struct.pack("<4sIIII", b"WDBC", 1, 2, 8, 0) + struct.pack("<ff", 1.0, 2.0)
    b = make_backend(gtCombatRatings=bad)
    with pytest.raises(DbcDriftError):
        run_extract(_client(tmp_path), tmp_path / "o", backend=b, plan=_plan(_client(tmp_path)),
                    extractor_commit="x", client_build="y")
    assert not (tmp_path / "o" / "coa_wow_constants.json").exists()


def test_non_exact_axis_requires_adjudication(tmp_path):
    from coa_client_extract.wow_constants import ClassAxisAdjudicationRequired
    # drop class 9 -> observed subset -> comparison "changed"
    ids = [(i, 0) for i in [1,2,3,4,5,6,7,8,11]]
    strings = b"\x00" + b"".join(f"C{i}".encode() + b"\x00" for i, _ in ids)
    rows, off = [], 1
    for i, p in ids:
        cells = [0] * 60
        cells[0], cells[2], cells[5] = i, p, off
        off += len(f"C{i}") + 1
        rows.append(struct.pack("<" + "I" * 60, *cells))
    chr_bytes = struct.pack("<4sIIII", b"WDBC", len(ids), 60, 240, len(strings)) + b"".join(rows) + strings
    b = make_backend(ChrClasses=chr_bytes)
    with pytest.raises(ClassAxisAdjudicationRequired):
        run_extract(_client(tmp_path), tmp_path / "o", backend=b, plan=_plan(_client(tmp_path)),
                    extractor_commit="x", client_build="y")
    # with a tracked adjudication file, it proceeds
    adj = tmp_path / "adj.json"
    adj.write_text(json.dumps({"schema": "wow-class-axis-adjudication-v1", "accepted_comparison": "changed",
                               "observed_client_ids": [1,2,3,4,5,6,7,8,11], "rationale": "test", "version": "v1"}))
    manifest = run_extract(_client(tmp_path), tmp_path / "o2", backend=b, plan=_plan(_client(tmp_path)),
                           extractor_commit="x", client_build="y", adjudication_path=str(adj))
    assert manifest["authored_inputs"]["class_axis_adjudication"]["sha256"] == \
        hashlib.sha256(adj.read_bytes()).hexdigest()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_cli.py -k "canonical or required or drift or adjudication" -v`
Expected: FAIL with `ImportError: cannot import name 'run_extract'`.

- [ ] **Step 3: Implement `run_extract` (+ error classes) in `wow_constants.py`**

```python
# coa_client_extract/wow_constants.py  (append)
import hashlib


class MissingRequiredTable(RuntimeError):
    pass


class ClassAxisAdjudicationRequired(RuntimeError):
    pass


def run_extract(client_root, out_dir, *, backend, plan, extractor_commit, client_build,
                adjudication_path: str | None = None) -> dict:
    root, attach = plan.open_chain
    axis_in = load_authored_input("gt_axis_policy")
    rating_in = load_authored_input("rating_enum")
    power_in = load_authored_input("power_type_enum")
    rules_in = load_authored_input("wow_rules")
    anchors_in = load_authored_input("wotlk_reference_anchors")
    layouts, ls, rs = load_axis_policy(axis_in.payload)

    report = recon(backend, root, attach, axis_policy=(layouts, ls, rs),
                   rating_enum=rating_in.payload, power_type_enum=power_in.payload,
                   reference_class_axis=axis_in.payload["class_axis"])
    class_axis = report["class_axis"]

    adjudication = None
    if class_axis["comparison"] != "exact":
        if not adjudication_path or not Path(adjudication_path).is_file():
            raise ClassAxisAdjudicationRequired(
                f"class axis comparison={class_axis['comparison']} requires a tracked adjudication file")
        raw = Path(adjudication_path).read_bytes()
        payload = _json.loads(raw)
        from types import SimpleNamespace
        adjudication = SimpleNamespace(name="class_axis_adjudication",
                                       version=payload.get("version", "wow-class-axis-adjudication-v1"),
                                       sha256=hashlib.sha256(raw).hexdigest())

    roster = class_roster(class_axis)
    anchors = anchors_in.payload["anchors"]
    game_tables: dict = {}
    source_dbc_sha: dict = {}
    table_summary: dict = {}
    for key, layout in layouts.items():
        info = report["tables"][key]
        proven_required = layout.semantics == "proven" and key in axis_in.payload["tables"]
        if not info["available"]:
            if proven_required:
                raise MissingRequiredTable(f"proven-required table {layout.source_dbc} is absent")
            continue
        if layout.semantics == "unproven":
            continue
        member = backend.read_effective_file(root, attach, f"DBFilesClient\\{layout.source_dbc}.dbc")
        table = parse_gametable(member.data, physical_form=layout.physical_form,
                                expected_field_count=layout.expected_field_count,
                                expected_record_size=layout.expected_record_size,
                                value_cell=layout.value_cell, id_cell=layout.id_cell, strict=True)
        entries, counts = map_table_entries(layout, table, class_roster=roster,
                                            level_stride=ls, rating_stride=rs)
        rc = reference_comparison(entries, [a for a in anchors if a.get("table") == key],
                                  axes=layout.axes, anchor_set_version=anchors_in.version,
                                  anchor_set_sha256=anchors_in.sha256)
        game_tables[key] = {"source_dbc": layout.source_dbc, "physical_form": layout.physical_form,
                            "axes": list(layout.axes), "class_indexed": layout.class_indexed,
                            "domains": layout.supported, "drift": table.drift, "counts": counts,
                            "reference_comparison": rc, "entries": entries}
        source_dbc_sha[layout.source_dbc] = hashlib.sha256(member.data).hexdigest()
        table_summary[key] = {**counts, "drift": table.drift,
                              "reference_comparison_status": rc["status"]}

    chr_member = backend.read_effective_file(root, attach, "DBFilesClient\\ChrClasses.dbc")
    source_dbc_sha["ChrClasses"] = hashlib.sha256(chr_member.data).hexdigest()
    provenance = {"backend": getattr(backend, "name", "unknown"),
                  "backend_version": getattr(backend, "version", "unknown"),
                  "source_dbcs": {k: {"sha256": v} for k, v in source_dbc_sha.items()}}
    snapshot = build_snapshot(client_build=client_build, provenance=provenance, class_axis=class_axis,
                              game_tables=game_tables, rules=rules_in.payload["rules"],
                              rating_enum=rating_in.payload, power_type_enum=power_in.payload)

    from .artifacts import write_wow_constants
    return write_wow_constants(
        snapshot, Path(out_dir),
        authored_inputs=[rules_in, rating_in, power_in, axis_in, anchors_in],
        source_dbc_sha256=source_dbc_sha, class_context_resolution=report["class_context_resolution"],
        extractor_commit=extractor_commit, client_build=client_build, table_summary=table_summary,
        class_axis_adjudication=adjudication)
```

Then extend the `cli.py` `wow-constants` argparser with `--adjudication` and pass it through `wow_constants_command` → `run_extract(..., adjudication_path=...)`.

- [ ] **Step 4: Run the canonical tests to verify they pass**

Run: `pytest tests/test_wow_constants_cli.py -v`
Expected: PASS (all recon-only + canonical cases).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/wow_constants.py coa_client_extract/cli.py tests/test_wow_constants_cli.py
git commit -m "M1.14D Task 10: canonical extract + CLI (mandatory tables, strict drift, adjudication gate)"
```

---

## Task 11: `WowConstantsRepository` — manifest-verifying consumer seam

**Files:**
- Create: `coa_meta/wow_constants.py`
- Test: `tests/test_wow_constants_repository.py`

**Interfaces:**
- Produces: `WowConstantsRepository` with `from_dict(doc) -> repo` (structure validation) and `load(path) -> repo` (also verifies the sibling manifest schema, artifact path, sha256, byte length, and matching `client_build`); lookups for every proven-required table (`combat_rating_ratio`, `class_combat_rating_scalar`, `melee_crit_per_agi`, `melee_crit_base`, `spell_crit_per_int`, `spell_crit_base`, `mana_regen_per_spirit`), plus `default_power_type(wow_class_id)`, `rule(key)`, `rating_name(rating_id)`, `table_provenance(key)`. Raises `WowConstantsLoadError` (structure/manifest) or `LookupError` (missing coordinate / non-namespace id).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wow_constants_repository.py
import hashlib
import json
import math
from pathlib import Path
import pytest
from coa_meta.wow_constants import WowConstantsRepository, WowConstantsLoadError

COA_CLASS_TYPE_ID = 33


def _doc(**over):
    doc = {
        "schema_version": "coa-wow-constants-v1", "client_build": "3.3.5a+patch-M",
        "provenance": {"source_dbcs": {"gtCombatRatings": {"sha256": "z"}}},
        "class_axis": {"namespace": "chr_classes", "observed_client_ids": [1, 8, 11],
                       "default_power_type_by_wow_class_id": {"8": "mana"}},
        "enum_maps": {"rating_enum": {"version": "cr", "supported": {"10": "crit_spell"}},
                      "power_type": {"version": "p", "map": {"0": "mana"}}},
        "game_tables": {
            "combat_ratings": {"source_dbc": "gtCombatRatings", "axes": ["rating_id", "level"],
                "class_indexed": False, "counts": {"emitted_entries": 1},
                "entries": [{"rating_id": 10, "level": 60, "value": 14.0}]},
            "class_combat_rating_scalar": {"source_dbc": "gtOCTClassCombatRatingScalar",
                "axes": ["wow_class_id", "rating_id"], "class_indexed": True,
                "counts": {"emitted_entries": 1}, "entries": [{"wow_class_id": 8, "rating_id": 10, "value": 1.0}]}},
        "rules": {"gcd_floor_ms": {"value": 1000, "authority": "wotlk_reference",
                                   "ascension_verification": "unverified", "applies_to": ["all_spells"]}}}
    doc.update(over)
    return doc


def _write_pair(tmp_path, doc, *, tamper=False):
    art = tmp_path / "coa_wow_constants.json"
    body = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()
    art.write_bytes(body)
    manifest = {"schema_version": "coa-wow-constants-manifest-v1",
                "artifact": {"path": "coa_wow_constants.json",
                             "sha256": hashlib.sha256(body if not tamper else b"x").hexdigest(),
                             "byte_length": len(body)},
                "client_build": doc["client_build"]}
    (tmp_path / "coa_wow_constants.manifest.json").write_text(json.dumps(manifest))
    return art


def test_rejects_wrong_schema_version():
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.from_dict(_doc(schema_version="coa-wow-constants-v2"))


def test_all_required_lookups_and_power_map():
    repo = WowConstantsRepository.from_dict(_doc())
    assert repo.combat_rating_ratio(10, 60) == 14.0
    assert repo.class_combat_rating_scalar(wow_class_id=8, rating_id=10) == 1.0
    assert repo.default_power_type(8) == "mana"
    assert repo.rating_name(10) == "crit_spell"
    assert repo.table_provenance("combat_ratings")["sha256"] == "z"


def test_class_lookup_is_keyword_only_and_rejects_coa_id():
    repo = WowConstantsRepository.from_dict(_doc())
    with pytest.raises(TypeError):
        repo.class_combat_rating_scalar(8, 10)
    with pytest.raises(LookupError):
        repo.class_combat_rating_scalar(wow_class_id=COA_CLASS_TYPE_ID, rating_id=10)


def test_missing_coordinate_and_non_finite_and_duplicate():
    repo = WowConstantsRepository.from_dict(_doc())
    with pytest.raises(LookupError):
        repo.combat_rating_ratio(10, 61)
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.from_dict(_doc(game_tables={"combat_ratings": {"axes": ["rating_id", "level"],
            "class_indexed": False, "entries": [{"rating_id": 10, "level": 60, "value": math.inf}]}}))
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.from_dict(_doc(game_tables={"combat_ratings": {"axes": ["rating_id", "level"],
            "class_indexed": False, "entries": [{"rating_id": 10, "level": 60, "value": 1.0},
                                                {"rating_id": 10, "level": 60, "value": 2.0}]}}))


def test_rule_missing_labels_rejected():
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.from_dict(_doc(rules={"x": {"value": 1}}))


def test_load_verifies_manifest_hash(tmp_path):
    art = _write_pair(tmp_path, _doc())
    repo = WowConstantsRepository.load(art)
    assert repo.combat_rating_ratio(10, 60) == 14.0


def test_load_rejects_tampered_manifest(tmp_path):
    art = _write_pair(tmp_path, _doc(), tamper=True)
    with pytest.raises(WowConstantsLoadError):
        WowConstantsRepository.load(art)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wow_constants_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'coa_meta.wow_constants'`.

- [ ] **Step 3: Implement `WowConstantsRepository`**

```python
# coa_meta/wow_constants.py
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

WOW_CONSTANTS_SCHEMA_VERSION = "coa-wow-constants-v1"
WOW_CONSTANTS_MANIFEST_SCHEMA = "coa-wow-constants-manifest-v1"
_REQUIRED_RULE_LABELS = ("authority", "ascension_verification", "applies_to")


class WowConstantsLoadError(ValueError):
    pass


class WowConstantsRepository:
    """Loads coa-wow-constants-v1 (verifying its sibling manifest), validates structure, and looks
    up RAW values by coordinate with provenance. It performs no calculation and never maps a CoA
    class-type id into a wow_class_id."""

    def __init__(self, tables, class_axis, rules, rating_enum, provenance):
        self._tables, self._class_axis = tables, class_axis
        self._rules, self._rating_enum, self._provenance = rules, rating_enum, provenance

    @classmethod
    def load(cls, path: str | Path) -> "WowConstantsRepository":
        path = Path(path)
        body = path.read_bytes()
        manifest_path = path.with_name("coa_wow_constants.manifest.json")
        if not manifest_path.is_file():
            raise WowConstantsLoadError("missing sibling manifest")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("schema_version") != WOW_CONSTANTS_MANIFEST_SCHEMA:
            raise WowConstantsLoadError("bad manifest schema_version")
        art = manifest.get("artifact", {})
        if art.get("path") != path.name:
            raise WowConstantsLoadError("manifest artifact path mismatch")
        if art.get("sha256") != hashlib.sha256(body).hexdigest():
            raise WowConstantsLoadError("manifest artifact hash mismatch (tampered or stale)")
        if art.get("byte_length") != len(body):
            raise WowConstantsLoadError("manifest byte_length mismatch")
        doc = json.loads(body)
        if manifest.get("client_build") != doc.get("client_build"):
            raise WowConstantsLoadError("manifest/artifact client_build mismatch")
        return cls.from_dict(doc)

    @classmethod
    def from_dict(cls, doc: dict) -> "WowConstantsRepository":
        if doc.get("schema_version") != WOW_CONSTANTS_SCHEMA_VERSION:
            raise WowConstantsLoadError(f"unsupported schema_version {doc.get('schema_version')!r}")
        class_axis = doc.get("class_axis") or {}
        rating_enum = (doc.get("enum_maps") or {}).get("rating_enum") or {}
        supported = set((rating_enum.get("supported") or {}))
        indexed: dict[str, dict] = {}
        for key, table in (doc.get("game_tables") or {}).items():
            axes = tuple(table.get("axes") or ())
            if not axes:
                raise WowConstantsLoadError(f"{key}: missing axes")
            seen: dict[tuple, float] = {}
            for entry in table.get("entries") or []:
                value = entry.get("value")
                if value is None or not math.isfinite(value):
                    raise WowConstantsLoadError(f"{key}: non-finite/missing value")
                if "rating_id" in entry and str(entry["rating_id"]) not in supported:
                    raise WowConstantsLoadError(f"{key}: unmapped rating_id {entry['rating_id']}")
                coord = tuple(entry[a] for a in axes)
                if coord in seen:
                    raise WowConstantsLoadError(f"{key}: duplicate coordinate {coord}")
                seen[coord] = float(value)
            counts = table.get("counts") or {}
            if "emitted_entries" in counts and counts["emitted_entries"] != len(seen):
                raise WowConstantsLoadError(f"{key}: counts.emitted_entries != number of entries")
            indexed[key] = {"axes": axes, "class_indexed": bool(table.get("class_indexed")),
                            "source_dbc": table.get("source_dbc"), "by_coord": seen}
        rules = doc.get("rules") or {}
        for name, rule in rules.items():
            if any(label not in rule for label in _REQUIRED_RULE_LABELS):
                raise WowConstantsLoadError(f"rule {name!r} missing a required label")
        return cls(indexed, class_axis, rules, rating_enum, doc.get("provenance") or {})

    # -- lookups (raw values; no computation) --
    def _lookup(self, key: str, coord: tuple) -> float:
        table = self._tables.get(key)
        if table is None:
            raise LookupError(f"no table {key!r}")
        try:
            return table["by_coord"][coord]
        except KeyError:
            raise LookupError(f"{key}: no value at {dict(zip(table['axes'], coord))}")

    def _require_wow_class(self, wow_class_id: int) -> None:
        observed = set(self._class_axis.get("observed_client_ids") or [])
        if wow_class_id not in observed:
            raise LookupError(f"wow_class_id {wow_class_id} not in ChrClasses namespace {sorted(observed)}; "
                              f"class context is M1.16's to resolve")

    def combat_rating_ratio(self, rating_id: int, level: int) -> float:
        return self._lookup("combat_ratings", (rating_id, level))

    def class_combat_rating_scalar(self, *, wow_class_id: int, rating_id: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("class_combat_rating_scalar", (wow_class_id, rating_id))

    def melee_crit_per_agi(self, *, wow_class_id: int, level: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("melee_crit_per_agi", (wow_class_id, level))

    def melee_crit_base(self, *, wow_class_id: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("melee_crit_base", (wow_class_id,))

    def spell_crit_per_int(self, *, wow_class_id: int, level: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("spell_crit_per_int", (wow_class_id, level))

    def spell_crit_base(self, *, wow_class_id: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("spell_crit_base", (wow_class_id,))

    def mana_regen_per_spirit(self, *, wow_class_id: int, level: int) -> float:
        self._require_wow_class(wow_class_id)
        return self._lookup("mana_regen_per_spirit", (wow_class_id, level))

    def default_power_type(self, wow_class_id: int) -> str:
        mapping = self._class_axis.get("default_power_type_by_wow_class_id") or {}
        if str(wow_class_id) not in mapping:
            raise LookupError(f"no default power type for wow_class_id {wow_class_id}")
        return mapping[str(wow_class_id)]

    def rule(self, key: str) -> dict:
        if key not in self._rules:
            raise LookupError(f"no rule {key!r}")
        return dict(self._rules[key])

    def rating_name(self, rating_id: int) -> str:
        name = (self._rating_enum.get("supported") or {}).get(str(rating_id))
        if name is None:
            raise LookupError(f"unmapped rating_id {rating_id}")
        return name

    def table_provenance(self, key: str) -> dict:
        table = self._tables.get(key)
        if table is None:
            raise LookupError(f"no table {key!r}")
        src = table.get("source_dbc")
        return dict((self._provenance.get("source_dbcs") or {}).get(src, {}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wow_constants_repository.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add coa_meta/wow_constants.py tests/test_wow_constants_repository.py
git commit -m "M1.14D Task 11: WowConstantsRepository (manifest-verifying, all tables, provenance, no computation)"
```

---

## Task 12: Modeling-standard synthetic oracles

**Files:**
- Test: `tests/test_wow_constants_oracles.py`

- [ ] **Step 1: Write the tests (test-only oracles; never repository behavior)**

```python
# tests/test_wow_constants_oracles.py
import struct
from coa_client_extract.wow_constants import load_authored_input, load_axis_policy, map_table_entries
from coa_client_extract.wdbc import parse_gametable
from coa_meta.wow_constants import WowConstantsRepository


def _implicit(values):
    return struct.pack("<4sIIII", b"WDBC", len(values), 1, 4, 0) + b"".join(
        struct.pack("<f", v) for v in values)


def test_rating_to_percent_reference_formula_at_60_and_80():
    doc = {"schema_version": "coa-wow-constants-v1", "client_build": "t",
           "class_axis": {"observed_client_ids": [8], "default_power_type_by_wow_class_id": {}},
           "enum_maps": {"rating_enum": {"supported": {"10": "crit_spell"}}, "power_type": {"map": {}}},
           "game_tables": {
               "combat_ratings": {"axes": ["rating_id", "level"], "class_indexed": False,
                   "entries": [{"rating_id": 10, "level": 60, "value": 14.0},
                               {"rating_id": 10, "level": 80, "value": 45.9}]},
               "class_combat_rating_scalar": {"axes": ["wow_class_id", "rating_id"], "class_indexed": True,
                   "entries": [{"wow_class_id": 8, "rating_id": 10, "value": 1.0}]}},
           "rules": {}}
    repo = WowConstantsRepository.from_dict(doc)
    scalar = repo.class_combat_rating_scalar(wow_class_id=8, rating_id=10)  # test-only division
    assert abs(scalar / repo.combat_rating_ratio(10, 60) - 1 / 14.0) < 1e-6
    assert abs(scalar / repo.combat_rating_ratio(10, 80) - 1 / 45.9) < 1e-6


def test_raw_divisor_nondecreasing_within_rating_id_with_plateaus():
    layouts, ls, rs = load_axis_policy(load_authored_input("gt_axis_policy").payload)
    values = [0.0] * 3200
    for level in range(1, 101):
        values[10 * 100 + (level - 1)] = float(level // 2)  # nondecreasing with plateaus
    table = parse_gametable(_implicit(values), physical_form="implicit_row",
                            expected_field_count=1, expected_record_size=4)
    entries, _ = map_table_entries(layouts["combat_ratings"], table, class_roster=[],
                                   level_stride=ls, rating_stride=rs)
    r10 = sorted((e["level"], e["value"]) for e in entries if e["rating_id"] == 10)
    assert all(b >= a for (_, a), (_, b) in zip(r10, r10[1:]))
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_wow_constants_oracles.py -v`
Expected: PASS (2 passed).

- [ ] **Step 3: Commit**

```bash
git add tests/test_wow_constants_oracles.py
git commit -m "M1.14D Task 12: modeling oracles (rating->% at 60/80, within-rating monotonicity)"
```

---

## Task 13: Schema doc, ignore rules, policy-gate registration

**Files:**
- Create: `docs/data/wow-constants-schema.md`
- Modify: `.gitignore`
- Modify: `docs/DECISIONS.md`

- [ ] **Step 1: Write `docs/data/wow-constants-schema.md`**

Document the `coa-wow-constants-v1` top-level shape (`schema_version`, `client_build`, `provenance`, `class_axis`, `enum_maps`, `game_tables`, `rules`); `game_tables[key]` fields (`source_dbc`, `physical_form`, `axes`, `class_indexed`, `domains`, `drift`, `counts` = `source_records`/`emitted_entries`/`padding_records`, `reference_comparison`, `entries` with explicit coordinates); `class_axis` (`reference_expected_ids`, `reference_holes`, `observed_client_ids`, `comparison`, `default_power_type_by_wow_class_id`); the `rules` label schema; and the manifest (`coa-wow-constants-manifest-v1`: `artifact`, `source_dbc_sha256`, `authored_inputs` version+sha256 incl. optional `class_axis_adjudication`, `class_context_resolution`, `table_summary`). State the reference indexing contract and that rating→% (`class_scalar / combat_rating`) is identified, not computed. Cross-reference `client-spell-schema.md` for the shared `power_type` map.

- [ ] **Step 2: Add ignore rules to `.gitignore`**

```
# M1.14D client-derived WoW constants — regenerate from your own client
reports/client_extract/coa_wow_constants_recon.json
coa_scraper/dist/coa_wow_constants.json
coa_scraper/dist/coa_wow_constants.manifest.json
```

(The tracked `reports/client_extract/wow_class_axis_adjudication.json` must NOT be ignored.)

- [ ] **Step 3: Register the artifact under the M1.14C forward policy gate in `docs/DECISIONS.md`**

Add one sentence to Decision 18 (or its M1.14C redistribution note): `coa_wow_constants.json` and its manifest are client-derived and fall under the same mandatory forward policy gate (before M1.16 consumes any client-derived output, or any canonical public release, one policy decision must cover them consistently with `coa_client_spell_coa.jsonl` and `coa_mechanics.jsonl`).

- [ ] **Step 4: Verify no tracked client-derived bytes and commit**

Run: `git status --porcelain` — confirm no `coa_wow_constants.json`/recon report is staged.

```bash
git add docs/data/wow-constants-schema.md .gitignore docs/DECISIONS.md
git commit -m "M1.14D Task 13: wow-constants schema doc, ignore rules, policy-gate registration"
```

---

## Task 14: Client-tier acceptance + StormLib tier + full green

**Files:**
- Test: `tests/test_wow_constants_acceptance.py` (`client` marker)
- Test: `tests/test_wow_constants_stormlib.py` (`stormlib` marker)

- [ ] **Step 1: Write the `client`-marked acceptance test**

```python
# tests/test_wow_constants_acceptance.py
import json
import os
from pathlib import Path
import pytest
from coa_client_extract.cli import wow_constants_command
from coa_meta.wow_constants import WowConstantsRepository

CLIENT_ROOT = Path(os.environ.get("COA_CLIENT_ROOT", "/nonexistent"))


@pytest.mark.client
@pytest.mark.skipif(not CLIENT_ROOT.is_dir(), reason="Ascension client not installed at COA_CLIENT_ROOT")
def test_real_client_snapshot_is_structurally_sound(tmp_path):
    out = tmp_path / "out"
    manifest = wow_constants_command(CLIENT_ROOT, out)
    repo = WowConstantsRepository.load(out / "coa_wow_constants.json")
    assert manifest["class_context_resolution"] in ("unproven", "actor_wow_class_id", "versioned_bridge")
    assert repo.combat_rating_ratio(10, 60) > 0                     # context-free lookup resolves
    snap = json.loads((out / "coa_wow_constants.json").read_text())
    rc = snap["game_tables"]["combat_ratings"]["reference_comparison"]
    # anchors are table-tagged raw combat_ratings values -> they ARE checked (never no_anchors_checked)
    assert rc["status"] in ("matches_on_checked_anchors", "differs_on_checked_anchors")
```

- [ ] **Step 2: Write the `stormlib`-marked synthetic-MPQ test**

```python
# tests/test_wow_constants_stormlib.py
import os
import struct
from pathlib import Path
import pytest

pytestmark = pytest.mark.stormlib


def _stormlib_available() -> bool:
    try:
        from coa_client_extract.stormlib_backend import StormLibBackend
        StormLibBackend()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _stormlib_available(), reason="StormLib shared library not installed")
def test_recon_runs_over_a_real_stormlib_backend(tmp_path):
    # Build a minimal synthetic MPQ with the proven-required gt tables + ChrClasses and confirm the
    # real StormLib-backed path reads them (mirrors tests/test_client_extract_integration_stormlib.py).
    from coa_client_extract.stormlib_backend import StormLibBackend
    from coa_client_extract.archive_plan import discover_plan
    from coa_client_extract.wow_constants import run_recon
    from tests.mpq_fixture import build_synthetic_mpq  # helper used by the M1.14A stormlib tier

    data = tmp_path / "Data"
    data.mkdir()
    build_synthetic_mpq(data, gametables=True)         # extends the existing helper to add gt*/ChrClasses
    plan = discover_plan(data)
    report = run_recon(data, tmp_path / "out", backend=StormLibBackend(), plan=plan)
    assert report["tables"]["combat_ratings"]["available"] is True
```

> If `tests/mpq_fixture.py`/`build_synthetic_mpq` does not yet exist, model this test on the existing `tests/test_client_extract_integration_stormlib.py` MPQ construction and extend that helper to add the gt tables + ChrClasses. Keep it `stormlib`-marked so the default suite skips it.

- [ ] **Step 3: Run the default suite (env-gated tiers deselected) and confirm green**

Run: `pytest tests/test_wow_constants_*.py -v`
Expected: PASS for default-tier tests; `acceptance` (client) and `stormlib` deselected by the repo default `addopts = "-m 'not stormlib and not client'"`.

- [ ] **Step 4: Run the full package suite**

Run: `pytest -q`
Expected: PASS (existing suite + new M1.14D default-tier tests); env-gated tiers deselected.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wow_constants_acceptance.py tests/test_wow_constants_stormlib.py
git commit -m "M1.14D Task 14: client-tier acceptance + StormLib-tier recon + full-suite green"
```

---

## Self-Review

**1. Spec coverage** — class-axis gate → Tasks 3/4/11 (+ `class_context_resolution` manifest 9/10); recon-first + reference contract → 5/6/7; float+explicit-id reader → 1/3; tiered scope → 2/7/10; enum maps hashed → 2/9; single snapshot + manifest-last + hashed inputs → 8/9; verification-labelled rules → 2; thin non-computing reader with provenance → 11; testing (synthetic/`stormlib`/`client`; 60/80 oracle; monotonicity; NaN/Inf; missing-vs-zero; sparse class 10; +1 offset; explicit-id + duplicate ids; native-namespace enforcement; manifest tamper; interrupted write; hash-change per input; missing required table; strict drift; non-exact-axis adjudication) → 1–14; redistribution + policy gate → 13.

**2. Placeholder scan** — no "TBD/handle edge cases"; every code step shows complete code; Task 7 is a manual checkpoint with concrete adjudication criteria; the StormLib fixture note (Task 14) points at the existing M1.14A integration test to extend, not a placeholder.

**3. Type consistency** — `GameTable`/`parse_gametable`/`classify_physical_form` (1) reused unchanged in 3/5/10/12; `GameTableLayout`/`load_axis_policy`/`map_table_entries` identical across 3/5/10; `AuthoredInput` fields identical across 2/9/10; `build_class_axis`/`class_roster` identical across 4/5/10; `recon`/`run_recon`/`run_extract` signatures consistent across 5/6/10; `reference_comparison`/`build_snapshot` identical across 8/10; `write_wow_constants` signature identical across 9/10; `WowConstantsRepository.from_dict`/`load` + method set identical across 11/12/14.

> **Executor note:** Ordering is load-bearing. Tasks 1–6 build the recon tool on synthetic fixtures and need no client. **Task 7 is a hard hold point** requiring the real Ascension client + StormLib; Tasks 8–10 (canonical) and Task 14's real run must not be trusted until Task 7 freezes the authored data. If the client is unavailable here, complete Tasks 1–6 and 8–13 against synthetic fixtures, then surface Task 7 to the maintainer before any real extraction.
