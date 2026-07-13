# M1.14B Client Attribution and CoA Advancement Graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the client's `CharacterAdvancement.dbc` CoA advancement graph, attribute every spell to CoA/Reborn/stock from client-native evidence, emit the `coa-client-advancement-v1` artifact plus class-type/essence metadata, and prove it node-by-node against the CoA Builder oracle — without rewiring the legality/tree pipeline (that stays M1.15).

**Architecture:** Additive to the M1.14A `coa_client_extract` module. Reuse its `ArchiveBackend`, header-driven `wdbc` reader, `manifest`, and provenance. New pure modules (`class_types`, `advancement`, `attribution`, `parity`) are unit-tested through synthetic fixtures and the existing `FakeArchiveBackend`; the exact `CharacterAdvancement` column layout is *decoded and semantically validated* against the real client (client tier), never assumed from a matching WDBC header.

**Tech Stack:** Python 3 (stdlib only for the package: `struct`, `dataclasses`, `hashlib`, `json`, `pathlib`), `pytest` with markers `stormlib`/`client`, StormLib (extraction-time only).

Design spec: [M1.14B Client Attribution and CoA Advancement Graph](../specs/2026-07-13-m1-14-b-client-attribution-and-graph-design.md).

## Global Constraints

- **Additive only.** Do not modify the Builder graph pipeline, `coa_meta` repository, reports, or guides. M1.14B produces artifacts + a parity report; nothing downstream consumes them yet.
- **StormLib is extraction-time only.** Never import it from `coa_meta`/report/guide paths. Default `pytest` run (`-m 'not stormlib and not client'`) must stay green with no StormLib and no client, via `FakeArchiveBackend` + synthetic fixtures.
- **Fail closed** (Decision 20). The regenerate CLI writes *nothing* without StormLib. Read the **effective patch-chain** copy of every table (never `patch-M` directly).
- **Committed fixtures are synthetic / self-authored** — never client asset bytes (redistribution boundary).
- **The Builder is never an input** to membership or mode attribution. It is the oracle used only to *measure* the model (the parity report). Curated display aliases are presentation metadata with provenance, not attribution inputs.
- **Semantic validation gates canonical emission.** A layout field that is not proven to `confidence: high` (FK resolves, adjacency resolves in its proven domain, scalars in range) blocks emission of that field — a matching WDBC header is not sufficient.
- **Verified structural anchors** (real client, 2026-07-13): `CharacterAdvancement.dbc` node id = column 0, spell id = column 5, class-type FK = column 32. Every other column is decoded, not assumed.
- **Class taxonomy:** `CharacterAdvancementClassTypes` ids 14–34 = 21 playable CoA classes; **35 = `ConquestOfAzeroth` sentinel (non-playable)**; 36–46 = Reborn. Alpha→display aliases (curated): `22 SonOfArugal→Bloodmage`, `16 DemonHunter→Felsworn`, `21 Monk→Templar`.
- **Observed headers** (expected values for drift checks; real client): `CharacterAdvancement` field_count 179 / record_size 692; `CharacterAdvancementClassTypes` 23 / 92; `CharacterAdvancementTabTypes` 19 / 76; `CharacterAdvancementCategories` 39 / 156; `CharacterAdvancementEssence` 9 / 36; `SkillLine` 56 / 224; `SkillLineAbility` 14 / 56.

---

## File Structure

**New files:**
- `coa_client_extract/class_types.py` — resolve `CharacterAdvancementClassTypes`/`TabTypes` into a versioned classification (`kind`), apply curated display aliases, assert the 21-class cardinality.
- `coa_client_extract/advancement.py` — read `CharacterAdvancement`, join companions, build `AdvancementNode`s with legality + `field_confidence` + raw slots; run semantic validators.
- `coa_client_extract/attribution.py` — participation model (`is_coa`/`modes`/`exclusive_mode`) + `memberships[]` from the node graph; deterministic truth table; skill-line fallback.
- `coa_client_extract/parity.py` — node-level (multiset) Builder-parity report + flip gate (`flip_ready`/`flip_blockers`).
- `coa_client_extract/decode_advancement.py` — the client-tier decode harness that determines the `CharacterAdvancement` column layout by JSON-correlation + semantic proof and writes a decode report.
- `tests/test_client_extract_class_types.py`, `tests/test_client_extract_advancement.py`, `tests/test_client_extract_advancement_semantic.py`, `tests/test_client_extract_attribution.py`, `tests/test_client_extract_parity.py`
- `docs/data/client-advancement-schema.md`, `docs/data/client-class-types-schema.md`

**Modified files:**
- `coa_client_extract/errors.py` — add `DbcSemanticError`.
- `coa_client_extract/wdbc.py` — add `parse_positional` + `PositionalDbc` (raw index-keyed reader for wide tables).
- `coa_client_extract/dbc_layouts.py` — add companion layouts, the `CharacterAdvancementLayout` dataclass, and the decoded `CHARACTER_ADVANCEMENT` constant (no essence-cap layout — caps are constants, essence is extracted raw).
- `coa_client_extract/artifacts.py` — advancement/class-type/tab-type/raw-essence record writers; fill `coa_attribution` + `memberships[]` on spell records.
- `coa_client_extract/cli.py` — wire the new readers and outputs into `regenerate`.
- `tests/test_client_extract_artifacts.py`, `tests/test_client_extract_cli.py`, `tests/test_client_extract_acceptance.py` — extend.
- `docs/data/client-spell-schema.md`, `docs/data/client-content-schema.md`, `docs/DECISIONS.md`, `docs/superpowers/specs/2026-07-06-m1-14-client-dbc-data-foundation-design.md`, `docs/ROADMAP.md`.

**Shared interfaces (defined by the tasks below; listed here so tasks can be read out of order):**
- `class_types.ClassType(class_type_id:int, internal:str, display:str, kind:str, display_source:str="client", display_evidence:tuple[str,...]=())` — `kind ∈ {"coa_class","coa_system","reborn","stock","meta","unknown"}`.
- `class_types.resolve_class_types(table: DbcTable) -> dict[int, ClassType]`
- `class_types.resolve_tab_types(table: DbcTable) -> dict[int, str]`
- `class_types.assert_playable_cardinality(resolved: dict[int, ClassType]) -> None`
- `dbc_layouts.CharacterAdvancementLayout` — named column fields (below).
- `advancement.AdvancementNode` — dataclass (below).
- `advancement.read_advancement(ca: wdbc.PositionalDbc, class_types, tab_types, layout) -> list[AdvancementNode]` (consumes positional `{index: value}` rows).
- `advancement.validate_semantics(nodes, class_types, tab_types) -> None` (raises `DbcSemanticError`).
- `attribution.AttributionResult(is_coa:bool, modes:tuple[str,...], exclusive_mode:str|None, confidence:str)`
- `attribution.attribute(nodes, class_types, skill_line_index=None) -> dict[int, SpellAttribution]` where `SpellAttribution` has `.result: AttributionResult` and `.memberships: list[dict]`.
- `attribution.build_skill_line_index(skill_line_ability_rows, coa_line_ids=COA_CLASS_BAND_SKILL_LINES) -> dict[int,str]`
- `parity.build_parity_report(nodes, builder_entries, *, low_confidence_fields=(), unresolved_layout_columns=(), adjacency_mismatches=0, legality_diffs=(), essence_progression_decoded=False, provenance=None) -> dict` (carries `multiset_recall`/`multiset_precision`, `per_class`, `flip_blockers`, `flip_ready`).
- `parity.flip_gate_inputs(layout) -> tuple[list[str], list[str], int]` — `(low_confidence_fields, unresolved_layout_columns, adjacency_mismatches)` derived from a resolved `CharacterAdvancementLayout`.

---

## Task 1: Class-type / tab-type resolver with cardinality assertion

**Files:**
- Create: `coa_client_extract/class_types.py`
- Test: `tests/test_client_extract_class_types.py`

**Interfaces:**
- Consumes: `wdbc.DbcTable` (from M1.14A) — `.rows: list[dict]` with a resolved `id` and a `name` string column.
- Produces: `ClassType`, `resolve_class_types`, `resolve_tab_types`, `assert_playable_cardinality`, `PLAYABLE_COA_IDS`, `COA_SENTINEL_ID`, `DISPLAY_ALIASES`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client_extract_class_types.py
import pytest

from coa_client_extract.class_types import (
    ClassType, resolve_class_types, resolve_tab_types,
    assert_playable_cardinality, DISPLAY_ALIASES, COA_SENTINEL_ID,
)


class _Table:
    """Minimal stand-in for wdbc.DbcTable: only .rows is used here."""
    def __init__(self, rows): self.rows = rows


def _class_rows():
    # (id, name) pairs mirroring CharacterAdvancementClassTypes bands.
    named = {
        2: "Hunter", 11: "DeathKnight", 12: "General", 13: "Hero",
        14: "Barbarian", 15: "WitchDoctor", 16: "DemonHunter", 21: "Monk",
        22: "SonOfArugal", 33: "Venomancer", 34: "Runemaster",
        35: "ConquestOfAzeroth", 36: "RebornHunter", 46: "RebornGeneral",
    }
    # fill the whole 2..46 range so the cardinality check has all playable ids
    for i in range(2, 47):
        named.setdefault(i, f"Class{i}")
    return _Table([{"id": i, "name": named[i]} for i in sorted(named)])


def test_resolves_kind_bands_and_sentinel():
    resolved = resolve_class_types(_class_rows())
    assert resolved[33].kind == "coa_class"
    assert resolved[33].display == "Venomancer"
    assert resolved[COA_SENTINEL_ID].kind == "coa_system"   # 35, non-playable
    assert resolved[36].kind == "reborn"
    assert resolved[2].kind == "stock"
    assert resolved[12].kind == "meta"                       # General/Hero


def test_unknown_class_id_is_unknown_not_stock():
    # an id outside every known band must be "unknown" (flagged), never silently bucketed "stock"
    resolved = resolve_class_types(_Table([{"id": 99, "name": "Mystery"}]))
    assert resolved[99].kind == "unknown"


def test_applies_curated_display_aliases_without_touching_identity():
    resolved = resolve_class_types(_class_rows())
    assert resolved[22].internal == "SonOfArugal"
    assert resolved[22].display == "Bloodmage"
    assert resolved[16].display == "Felsworn"
    assert resolved[21].display == "Templar"
    assert set(DISPLAY_ALIASES) == {22, 16, 21}


def test_cardinality_exactly_21_playable():
    resolved = resolve_class_types(_class_rows())
    assert_playable_cardinality(resolved)   # must not raise


def test_cardinality_raises_when_not_21():
    rows = [r for r in _class_rows().rows if r["id"] != 34]  # drop one playable class
    with pytest.raises(ValueError, match="expected 21 playable"):
        assert_playable_cardinality(resolve_class_types(_Table(rows)))


def test_tab_types_resolve_names():
    tabs = _Table([{"id": 1, "name": "Class"}, {"id": 49, "name": "Brewing"}])
    assert resolve_tab_types(tabs) == {1: "Class", 49: "Brewing"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_extract_class_types.py -v`
Expected: FAIL with `ModuleNotFoundError: coa_client_extract.class_types`.

- [ ] **Step 3: Write the implementation**

```python
# coa_client_extract/class_types.py
from __future__ import annotations

from dataclasses import dataclass

# Verified against the real client (2026-07-13). Ids are CharacterAdvancementClassTypes row ids.
PLAYABLE_COA_IDS = range(14, 35)      # 14..34 inclusive = 21 playable CoA classes
COA_SENTINEL_ID = 35                  # ConquestOfAzeroth: umbrella sentinel, NOT playable
_REBORN_IDS = range(36, 47)
_META_IDS = {12, 13}                  # General, Hero
_STOCK_IDS = range(2, 12)             # Hunter..DeathKnight

# Curated alpha->display aliases (presentation metadata only; never change class_type_id or
# attribution). Alpha classes revamped into current classes; owner- and Builder-confirmed.
DISPLAY_ALIASES: dict[int, str] = {22: "Bloodmage", 16: "Felsworn", 21: "Templar"}
_ALIAS_EVIDENCE = ("builder_class_name", "project_owner_confirmation")


@dataclass(frozen=True)
class ClassType:
    class_type_id: int
    internal: str            # raw client name (independently recoverable identity)
    display: str             # internal, unless a curated alias overrides it
    kind: str                # coa_class | coa_system | reborn | stock | meta
    display_source: str = "client"
    display_evidence: tuple[str, ...] = ()


def _kind(cid: int) -> str:
    if cid == COA_SENTINEL_ID:
        return "coa_system"
    if cid in PLAYABLE_COA_IDS:
        return "coa_class"
    if cid in _REBORN_IDS:
        return "reborn"
    if cid in _META_IDS:
        return "meta"
    if cid in _STOCK_IDS:
        return "stock"
    return "unknown"     # outside every known band: possible new class / drift, never silently stock


def resolve_class_types(table) -> dict[int, ClassType]:
    out: dict[int, ClassType] = {}
    for row in table.rows:
        cid = row["id"]
        internal = row.get("name") or ""
        if cid in DISPLAY_ALIASES:
            out[cid] = ClassType(cid, internal, DISPLAY_ALIASES[cid], _kind(cid),
                                  "curated_alias", _ALIAS_EVIDENCE)
        else:
            out[cid] = ClassType(cid, internal, internal, _kind(cid))
    return out


def resolve_tab_types(table) -> dict[int, str]:
    return {row["id"]: (row.get("name") or "") for row in table.rows}


def assert_playable_cardinality(resolved: dict[int, ClassType]) -> None:
    playable = [c for c in resolved.values() if c.kind == "coa_class"]
    if len(playable) != 21:
        raise ValueError(
            f"expected 21 playable CoA classes, resolved {len(playable)}: "
            f"{sorted(c.class_type_id for c in playable)}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_client_extract_class_types.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/class_types.py tests/test_client_extract_class_types.py
git commit -m "M1.14B: class-type/tab-type resolver with 21-class cardinality assertion"
```

---

## Task 2: `DbcSemanticError` + positional reader + companion layouts + `CharacterAdvancementLayout`

**Files:**
- Modify: `coa_client_extract/errors.py`
- Modify: `coa_client_extract/wdbc.py`
- Modify: `coa_client_extract/dbc_layouts.py`
- Test: `tests/test_client_extract_advancement_semantic.py` (created here; extended in Tasks 3–4)

**Interfaces:**
- Produces: `errors.DbcSemanticError`; `wdbc.parse_positional(data, expected_field_count, expected_record_size, *, strict=False) -> PositionalDbc` (`.rows: list[{cell_index: uint32}]`, `.cell_count`, `.strings`, `.drift`, `.read_string(offset)`); `dbc_layouts.CHARACTER_ADVANCEMENT_CLASS_TYPES`, `..._TAB_TYPES`, `..._ESSENCE`, `..._SKILL_LINE_ABILITY`; `dbc_layouts.CharacterAdvancementLayout` (indices **and** a per-field `confidence` map); `dbc_layouts.CHARACTER_ADVANCEMENT` (anchors-only default, overwritten by the Task 3 decode).

Why a positional reader: M1.14A's `parse_dbc` returns rows keyed by the *named* columns a layout declares — right for the small spell family, wrong for a 173-cell advancement record whose columns are addressed by index. `parse_positional` returns each row as `{column_index: uint32}`, which the advancement reader/decoder index directly. The companion tables (ClassTypes/TabTypes) keep using named `parse_dbc` because they need their string `name` column (col 1).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client_extract_advancement_semantic.py
import struct

from coa_client_extract.errors import DbcSemanticError, ExtractError
from coa_client_extract.wdbc import parse_positional
from coa_client_extract.dbc_layouts import (
    CHARACTER_ADVANCEMENT_CLASS_TYPES, CharacterAdvancementLayout, CHARACTER_ADVANCEMENT,
)


def test_semantic_error_is_extract_error():
    assert issubclass(DbcSemanticError, ExtractError)


def test_class_types_layout_headers_match_observed_client():
    lt = CHARACTER_ADVANCEMENT_CLASS_TYPES
    assert lt.expected_field_count == 23
    assert lt.expected_record_size == 92
    assert lt.columns["id"].index == 0
    assert lt.columns["name"].index == 1          # verified on real client


def test_advancement_layout_defaults_to_anchors_only():
    lt = CHARACTER_ADVANCEMENT
    assert (lt.node_id_col, lt.spell_id_col, lt.class_type_col) == (0, 5, 32)
    # unresolved fields default to None/() and no field is proven until the decode fills confidence
    assert lt.ae_cost_col is None
    assert lt.connected_node_cols == ()
    assert lt.confidence == {}


def test_parse_positional_returns_index_keyed_rows_and_strings():
    import pytest
    from coa_client_extract.errors import DbcDriftError
    strings = b"\x00Adrenal Venom\x00"
    rec0 = struct.pack("<III", 6086, 1, 805775)   # col1 = string offset 1 -> "Adrenal Venom"
    rec1 = struct.pack("<III", 6096, 0, 12345)
    data = struct.pack("<4sIIII", b"WDBC", 2, 3, 12, len(strings)) + rec0 + rec1 + strings
    raw = parse_positional(data, 3, 12)
    assert raw.drift is False
    assert raw.cell_count == 3 and raw.record_size == 12
    assert raw.rows[0] == {0: 6086, 1: 1, 2: 805775}
    assert raw.rows[1][0] == 6096
    assert raw.strings == strings                 # string block retained for name/icon correlation
    assert raw.read_string(1) == "Adrenal Venom"


def test_parse_positional_rejects_truncation():
    import pytest
    from coa_client_extract.errors import DbcDriftError
    # header claims 2 records * 12 bytes + 4-byte string block, but body is short
    data = struct.pack("<4sIIII", b"WDBC", 2, 3, 12, 4) + struct.pack("<III", 1, 0, 0)
    with pytest.raises(DbcDriftError, match="truncated"):
        parse_positional(data, 3, 12)


def test_parse_positional_rejects_non_divisible_record_size():
    import pytest
    from coa_client_extract.errors import DbcDriftError
    data = struct.pack("<4sIIII", b"WDBC", 0, 3, 13, 0)   # 13 not divisible by 4
    with pytest.raises(DbcDriftError, match="record_size"):
        parse_positional(data, 3, 13)


def test_parse_positional_strict_raises_on_drift():
    import pytest
    from coa_client_extract.errors import DbcDriftError
    data = struct.pack("<4sIIII", b"WDBC", 0, 99, 12, 0)  # field_count 99 != expected 3
    assert parse_positional(data, 3, 12).drift is True    # non-strict: flagged
    with pytest.raises(DbcDriftError):
        parse_positional(data, 3, 12, strict=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_extract_advancement_semantic.py -v`
Expected: FAIL with `ImportError` for `DbcSemanticError` / `parse_positional` / `CharacterAdvancementLayout`.

- [ ] **Step 3a: Add `DbcSemanticError` to `errors.py`**

Append to `coa_client_extract/errors.py`:

```python
class DbcSemanticError(ExtractError):
    """A DBC column layout matched its WDBC header but failed semantic validation
    (foreign keys, adjacency domain, or value ranges). Distinct from DbcDriftError,
    which is a structural header mismatch."""
```

- [ ] **Step 3b: Add `parse_positional` to `wdbc.py`**

Append to `coa_client_extract/wdbc.py` (reuses the existing `_HEADER`, `_MAGIC`, `_CELL`):

```python
@dataclass(frozen=True)
class PositionalDbc:
    field_count: int          # logical field count from the header (may exceed cell_count)
    cell_count: int           # record_size // 4 — the number of addressable 4-byte cells
    record_size: int
    record_count: int
    rows: list[dict]          # each row: {cell_index: uint32_value}
    strings: bytes            # retained string block, for name/icon correlation
    drift: bool

    def read_string(self, offset: int) -> str:
        if offset <= 0 or offset >= len(self.strings):
            return ""
        end = self.strings.find(b"\x00", offset)
        if end < 0:
            end = len(self.strings)
        return self.strings[offset:end].decode("utf-8", "replace")


def parse_positional(data: bytes, expected_field_count: int, expected_record_size: int,
                     *, strict: bool = False) -> PositionalDbc:
    """Decode every record as raw {cell_index: uint32} cells plus the string block, without a named
    layout. Used for wide custom tables (CharacterAdvancement) addressed by index during decode.

    Note the logical/raw distinction: the real CharacterAdvancement header reports field_count 179
    while record_size 692 holds only 173 four-byte cells. Cells are addressed 0..cell_count-1;
    field_count is preserved for provenance and drift, not for indexing."""
    if len(data) < _HEADER.size:
        raise DbcDriftError("file smaller than DBC header")
    magic, record_count, field_count, record_size, string_size = _HEADER.unpack_from(data, 0)
    if magic != _MAGIC:
        raise DbcDriftError(f"bad magic {magic!r}, expected WDBC")
    if record_size % _CELL != 0:
        raise DbcDriftError(f"record_size {record_size} not a multiple of {_CELL}")
    records_start = _HEADER.size
    string_start = records_start + record_count * record_size
    expected_len = string_start + string_size
    if len(data) < expected_len:
        raise DbcDriftError(f"truncated ({len(data)} bytes, expected >= {expected_len})")
    drift = field_count != expected_field_count or record_size != expected_record_size
    if drift and strict:
        raise DbcDriftError(
            f"field_count {field_count} / record_size {record_size} != expected "
            f"{expected_field_count} / {expected_record_size}")
    strings = data[string_start:string_start + string_size]
    cell_count = record_size // _CELL
    rows: list[dict] = []
    for i in range(record_count):
        base = records_start + i * record_size
        rows.append({c: struct.unpack_from("<I", data, base + c * _CELL)[0] for c in range(cell_count)})
    return PositionalDbc(field_count, cell_count, record_size, record_count, rows, strings, drift)
```

- [ ] **Step 3c: Add companion layouts + the advancement layout to `dbc_layouts.py`**

Append to `coa_client_extract/dbc_layouts.py`:

```python
from dataclasses import dataclass, field

# --- CoA advancement companion tables (headers + name column verified on the real client 2026-07-13) ---
# Col 0 = row id; col 1 = name string (verified) for the two *Types tables. Essence has no strings.
CHARACTER_ADVANCEMENT_CLASS_TYPES = DbcLayout(
    name="CharacterAdvancementClassTypes", expected_field_count=23, expected_record_size=92,
    columns={"id": FieldSpec(0, "uint32"), "name": FieldSpec(1, "str")},
)
CHARACTER_ADVANCEMENT_TAB_TYPES = DbcLayout(
    name="CharacterAdvancementTabTypes", expected_field_count=19, expected_record_size=76,
    columns={"id": FieldSpec(0, "uint32"), "name": FieldSpec(1, "str")},
)
CHARACTER_ADVANCEMENT_ESSENCE = DbcLayout(
    name="CharacterAdvancementEssence", expected_field_count=9, expected_record_size=36,
    columns={"id": FieldSpec(0, "uint32")},   # per-level progression, extracted raw (Task 6)
)
# SkillLineAbility: id(0), skill_line(1), spell(2). CoA class-band skill lines are ids 475..495.
CHARACTER_ADVANCEMENT_SKILL_LINE_ABILITY = DbcLayout(
    name="SkillLineAbility", expected_field_count=14, expected_record_size=56,
    columns={"id": FieldSpec(0, "uint32"), "skill_line": FieldSpec(1, "uint32"),
             "spell": FieldSpec(2, "uint32")},
)
COA_CLASS_BAND_SKILL_LINES = range(475, 496)   # verified: the 21 CoA class display-name skill lines


@dataclass(frozen=True)
class CharacterAdvancementLayout:
    """Resolved column map for CharacterAdvancement.dbc. Only the three anchors are known a
    priori (verified: node id col 0, spell id col 5, class-type FK col 32). Every other field is
    filled by the Task 3 decode harness and semantically validated before use; None / () means
    'not yet resolved to high confidence' and blocks that field from canonical emission."""
    node_id_col: int = 0
    spell_id_col: int = 5
    class_type_col: int = 32
    tab_type_col: int | None = None
    entry_type_col: int | None = None
    name_col: int | None = None
    icon_col: int | None = None
    ae_cost_col: int | None = None
    te_cost_col: int | None = None
    required_level_col: int | None = None
    required_tab_ae_col: int | None = None
    required_tab_te_col: int | None = None
    max_rank_col: int | None = None
    row_col: int | None = None
    column_col: int | None = None
    node_type_col: int | None = None
    connected_node_cols: tuple[int, ...] = ()
    required_id_cols: tuple[int, ...] = ()
    header_field_count: int = 179
    header_record_size: int = 692
    # Per-legality-field proof from the Task 3 decode: field name -> "high" | "medium" | "unproven".
    # read_advancement emits a field into `legality` ONLY when its confidence is "high"; a configured
    # column with no "high" confidence is treated as unproven and withheld (never assumed).
    confidence: dict = field(default_factory=dict)


# Anchors-only default; Task 3's client-tier decode overwrites this with the resolved columns and
# their proven confidence. The anchors themselves (node_id/spell_id/class_type) are structurally
# verified, but legality fields stay unproven until decode fills `confidence`.
CHARACTER_ADVANCEMENT = CharacterAdvancementLayout()
```

There is deliberately **no** essence-cap layout: per-class essence caps are the documented uniform
constants (AE 26 / TE 25), not a DBC-decoded quantity, so `CharacterAdvancementEssence` is extracted
raw (Task 6, `build_essence_raw_records`) rather than decoded into caps. Do not add a cap-column
layout — that would re-introduce the contradiction the design review resolved.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_client_extract_advancement_semantic.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/errors.py coa_client_extract/wdbc.py coa_client_extract/dbc_layouts.py tests/test_client_extract_advancement_semantic.py
git commit -m "M1.14B: DbcSemanticError, hardened parse_positional, CoA advancement layouts + confidence"
```

---

## Task 3: Column-decode harness (client tier) — determine & prove the layout

**Files:**
- Create: `coa_client_extract/decode_advancement.py`
- Test: `tests/test_client_extract_advancement_semantic.py` (extend with a synthetic decode test)

This task produces the *method* that resolves every column and **proves** it (with recorded evidence, uniqueness margins, and a minimum-nonzero floor), plus an executable decode command. The correlation/proof functions are unit-tested on synthetic data (default tier); running against the real client to emit the report + resolved layout is client tier. A field is `high` only when it clears the score threshold, beats the runner-up by a margin, has enough non-zero evidence, and (for FKs/adjacency) resolves into the correct domain.

**Interfaces:**
- Consumes: `wdbc.PositionalDbc` (rows + string block), `class_types.resolve_class_types`/`resolve_tab_types`, the loose `CharacterAdvancementData.json` (schema key), `dbc_layouts.CharacterAdvancementLayout`.
- Produces: `decode_advancement.correlate_scalar(pairs, json_field) -> ScalarProof(column, score, runner_up, margin, nonzero) | None`, `decode_advancement.prove_adjacency_domain(ca_rows, node_ids, candidate_cols, *, min_nonzero) -> tuple[str, tuple[int,...]]`, `decode_advancement.decode_layout(ca, class_types, tab_types, json_entries, *, score_threshold=0.85, margin_threshold=0.15, min_nonzero=50) -> tuple[CharacterAdvancementLayout, dict]`, `decode_advancement.write_report(report, path)`, and the CLI subcommand `python -m coa_client_extract decode-advancement`.

- [ ] **Step 1: Write the failing tests (evidence-based correlation + strict adjacency proof)**

```python
# append to tests/test_client_extract_advancement_semantic.py
from coa_client_extract.decode_advancement import (
    correlate_scalar, prove_adjacency_domain, decode_layout,
)


def _pairs(json_field, values, ca_cols):
    # values: list of ints; ca_cols: dict col->list aligned with values. Builds (json,row) pairs.
    pairs = []
    for i, v in enumerate(values):
        je = {"Spells": [1000 + i], json_field: v}
        row = {5: 1000 + i, **{c: col[i] for c, col in ca_cols.items()}}
        pairs.append((je, row))
    return pairs


def test_correlate_scalar_records_margin_and_nonzero():
    vals = [i % 4 for i in range(200)]
    # col 7 == field; col 9 is pure noise (constant); col 8 partially agrees
    ca = {7: vals, 8: [v if i % 2 else 0 for i, v in enumerate(vals)], 9: [3] * 200}
    proof = correlate_scalar(_pairs("AECost", vals, ca), "AECost")
    assert proof.column == 7 and proof.score == 1.0
    assert proof.runner_up < proof.score and proof.margin > 0.15
    assert proof.nonzero >= 50


def test_correlate_scalar_none_when_no_min_evidence():
    # only 10 pairs -> below the 50-nonzero floor -> no proof
    vals = [1] * 10
    assert correlate_scalar(_pairs("AECost", vals, {7: vals}), "AECost") is None


def test_prove_adjacency_rejects_all_zero_and_out_of_domain():
    node_ids = {10, 11, 12, 13}
    rows = [{0: 10, 20: 11, 21: 0}, {0: 11, 20: 12, 21: 13}, {0: 12, 20: 13, 21: 0},
            {0: 13, 20: 10, 21: 12}]
    assert prove_adjacency_domain(rows, node_ids, (20, 21), min_nonzero=3)[0] == "node_id"
    # all-zero block: no evidence -> unresolved (not a silent pass)
    zeros = [{0: n, 40: 0} for n in node_ids]
    assert prove_adjacency_domain(zeros, node_ids, (40,), min_nonzero=1)[0] == "unresolved"
    # out-of-domain value -> unresolved
    bad = [{0: 10, 50: 99999}]
    assert prove_adjacency_domain(bad, node_ids, (50,), min_nonzero=1)[0] == "unresolved"


def test_decode_layout_marks_unproven_fields_unproven():
    # a table where AECost is cleanly in col 7 but RequiredLevel has no matching column
    vals = [i % 4 for i in range(200)]
    ca_rows = [{0: 500 + i, 5: 1000 + i, 7: vals[i]} for i in range(200)]
    json_entries = [{"Spells": [1000 + i], "AECost": vals[i], "RequiredLevel": 99} for i in range(200)]
    from coa_client_extract.wdbc import PositionalDbc
    ca = PositionalDbc(179, 173, 692, 200, ca_rows, b"\x00", drift=False)
    layout, report = decode_layout(ca, {}, {}, json_entries)
    assert layout.confidence.get("ae_cost_col") == "high"
    assert report["fields"]["ae_cost_col"]["column"] == 7
    assert report["fields"]["required_level_col"]["confidence"] != "high"  # no clean column
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_extract_advancement_semantic.py -k "correlate or adjacency or decode_layout" -v`
Expected: FAIL with `ImportError`/`ModuleNotFoundError` for `decode_advancement`.

- [ ] **Step 3: Write the decode harness**

```python
# coa_client_extract/decode_advancement.py
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .dbc_layouts import CharacterAdvancementLayout

# JSON field (loose CharacterAdvancementData.json) -> layout attribute it resolves. Extend as the
# decode proves more fields; every entry here is proven, never assumed.
_SCALAR_FIELDS = {
    "AECost": "ae_cost_col", "TECost": "te_cost_col", "RequiredLevel": "required_level_col",
    "RequiredAEInvestment": "required_tab_ae_col", "RequiredTEInvestment": "required_tab_te_col",
    "Column": "column_col",
}


@dataclass(frozen=True)
class ScalarProof:
    column: int
    score: float
    runner_up: float
    margin: float
    nonzero: int


def _s32(u: int) -> int:
    return u - 0x100000000 if u >= 0x80000000 else u


def correlate_scalar(pairs, json_field, *, min_nonzero: int = 50) -> ScalarProof | None:
    """Rank every column by exact-match fraction against json_field over (json, row) pairs, and
    return the winner WITH its uniqueness margin over the runner-up and its non-zero evidence
    count. Returns None when the best column lacks >= min_nonzero non-zero matched values (guards
    against zero-dominated columns matching a mostly-zero field by accident)."""
    cols = set().union(*[set(r) for _, r in pairs]) if pairs else set()
    scored = []
    for c in cols:
        matched = total = nonzero = 0
        for je, row in pairs:
            if json_field in je and c in row:
                total += 1
                jv = je[json_field]
                if row[c] == jv or _s32(row[c]) == jv:
                    matched += 1
                    if row[c] != 0:
                        nonzero += 1
        if total >= min_nonzero:
            scored.append((matched / total, nonzero, c))
    if not scored:
        return None
    scored.sort(reverse=True)
    top = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    if top[1] < min_nonzero:
        return None
    return ScalarProof(top[2], round(top[0], 4), round(runner, 4), round(top[0] - runner, 4), top[1])


def prove_adjacency_domain(ca_rows, node_ids, candidate_cols, *, min_nonzero: int = 50) -> tuple[str, tuple[int, ...]]:
    """Prove the candidate columns are node-id references: every non-zero value resolves to an
    existing node id (col-0 domain), and there is at least min_nonzero non-zero evidence across
    the block (an all-zero block is 'unresolved', never a silent pass). Zero is padding."""
    nonzero = 0
    for row in ca_rows:
        for c in candidate_cols:
            v = row.get(c, 0)
            if v:
                nonzero += 1
                if v not in node_ids:
                    return "unresolved", ()
    if nonzero < min_nonzero:
        return "unresolved", ()
    return "node_id", tuple(candidate_cols)


def _unique_spell_pairs(ca_rows, json_entries):
    json_by_spell = defaultdict(list)
    for e in json_entries:
        sps = e.get("Spells") or []
        if len(sps) == 1:
            json_by_spell[int(sps[0])].append(e)
    ca_by_spell = defaultdict(list)
    for r in ca_rows:
        if r.get(5):
            ca_by_spell[r[5]].append(r)
    pairs = []
    for sp in set(json_by_spell) & set(ca_by_spell):
        if len(json_by_spell[sp]) == 1 and len(ca_by_spell[sp]) == 1:
            pairs.append((json_by_spell[sp][0], ca_by_spell[sp][0]))
    return pairs


def decode_layout(ca, class_types, tab_types, json_entries, *,
                  score_threshold: float = 0.85, margin_threshold: float = 0.15,
                  min_nonzero: int = 50) -> tuple[CharacterAdvancementLayout, dict]:
    """Resolve the non-anchor columns from the loose-JSON schema key with recorded evidence, and
    prove adjacency independently for the connection and prerequisite blocks. A scalar field is
    `high` only when score >= score_threshold AND margin >= margin_threshold AND nonzero >=
    min_nonzero; otherwise it is left None with confidence 'unproven' (blocks canonical emission).
    Returns (layout, report). The report is the machine-readable evidence for the flip gate."""
    ca_rows = ca.rows
    node_ids = {r.get(0) for r in ca_rows if r.get(0)}
    pairs = _unique_spell_pairs(ca_rows, json_entries)
    report = {"schema_version": "coa-ca-decode-report-v2", "unique_pairs": len(pairs),
              "thresholds": {"score": score_threshold, "margin": margin_threshold,
                             "min_nonzero": min_nonzero},
              "fields": {}}
    kwargs: dict = {}
    confidence: dict = {}

    def _record(field_attr, proof: ScalarProof | None):
        if proof is None:
            report["fields"][field_attr] = {"confidence": "unproven", "column": None}
            return
        high = (proof.score >= score_threshold and proof.margin >= margin_threshold
                and proof.nonzero >= min_nonzero)
        report["fields"][field_attr] = {
            "column": proof.column, "score": proof.score, "runner_up": proof.runner_up,
            "margin": proof.margin, "nonzero": proof.nonzero,
            "confidence": "high" if high else "low",
        }
        if high:
            kwargs[field_attr] = proof.column
            confidence[_LEGALITY_NAME.get(field_attr, field_attr)] = "high"

    for json_field, attr in _SCALAR_FIELDS.items():
        _record(attr, correlate_scalar(pairs, json_field, min_nonzero=min_nonzero))

    # Adjacency: locate contiguous node-ref blocks and prove each independently. The candidate
    # blocks are discovered by the operator from the decode report's per-column node-id-hit rate
    # (recorded below); prove them here so an all-zero or out-of-domain block cannot pass.
    report["node_id_hit_rate"] = _node_id_hit_rate(ca_rows, node_ids)
    layout = CharacterAdvancementLayout(**kwargs, confidence=confidence)
    return layout, report


# decode attr -> the legality field name read_advancement emits (so confidence keys line up)
_LEGALITY_NAME = {
    "ae_cost_col": "ae_cost", "te_cost_col": "te_cost", "required_level_col": "required_level",
    "required_tab_ae_col": "required_tab_ae", "required_tab_te_col": "required_tab_te",
    "max_rank_col": "max_rank", "row_col": "row", "column_col": "col",
    "connected_node_cols": "connected_node_ids", "required_id_cols": "required_ids",
}


def _node_id_hit_rate(ca_rows, node_ids) -> dict:
    """Per-column fraction of non-zero values that resolve to a node id — the operator uses this
    to nominate adjacency-block candidates, which decode/validation then prove."""
    cols = set().union(*[set(r) for r in ca_rows]) if ca_rows else set()
    out = {}
    for c in sorted(cols):
        nz = [r[c] for r in ca_rows if r.get(c)]
        if nz:
            out[str(c)] = round(sum(1 for v in nz if v in node_ids) / len(nz), 3)
    return out


def write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_client_extract_advancement_semantic.py -k "correlate or adjacency or decode_layout" -v`
Expected: PASS.

- [ ] **Step 5: Add the executable `decode-advancement` CLI subcommand**

In `cli.py`, add a `decode-advancement` subcommand so Step 6 is reproducible, not manual prose. It opens the client (StormLib), reads `CharacterAdvancement` positionally + the companions + the loose JSON, runs `decode_layout`, writes the report, and prints a ready-to-paste `CHARACTER_ADVANCEMENT = CharacterAdvancementLayout(...)` block (indices + `confidence`) for the operator to commit into `dbc_layouts.py`. Add a default-tier test that the subcommand's arg wiring parses (`main(["decode-advancement","--help"])`-style or a monkeypatched backend), and a `@pytest.mark.client` test that it runs end-to-end and every adapter-fed field it emits is `confidence: high`.

- [ ] **Step 6: Commit + client-tier decode run**

```bash
git add coa_client_extract/decode_advancement.py coa_client_extract/cli.py tests/test_client_extract_advancement_semantic.py
git commit -m "M1.14B: evidence-based CharacterAdvancement decode + decode-advancement command"
```

Then run the real decode (requires `COA_CLIENT_ROOT` + StormLib), which proves adjacency independently for `ConnectedNodes` and `RequiredIDs`, resolves tab/entry/name/icon/rank/row the same evidence-based way, writes `reports/client_extract/coa_ca_decode_report.json`, and emits the `CHARACTER_ADVANCEMENT` constant (indices + `confidence`) to paste into `dbc_layouts.py`. Any field not reaching `high` stays out of `confidence` and is Builder-fallback (adapter). Commit the report + constant:

```bash
python -m coa_client_extract decode-advancement \
  --client-root "$COA_CLIENT_ROOT" \
  --content-json "$COA_CLIENT_ROOT/Content/CharacterAdvancementData.json" \
  --out reports/client_extract/coa_ca_decode_report.json
git add coa_client_extract/dbc_layouts.py reports/client_extract/coa_ca_decode_report.json
git commit -m "M1.14B: decoded + validated CharacterAdvancement layout from real client"
```

---

## Task 4: Advancement graph reader + semantic validators

**Files:**
- Create: `coa_client_extract/advancement.py`
- Test: `tests/test_client_extract_advancement.py`; extend `tests/test_client_extract_advancement_semantic.py`

**Interfaces:**
- Consumes: `wdbc.PositionalDbc` (positional `{index: value}` rows for CharacterAdvancement), `class_types.ClassType`/`resolve_*`, `dbc_layouts.CharacterAdvancementLayout`, `errors.DbcSemanticError`.
- Produces: `AdvancementNode`, `read_advancement(ca, class_types, tab_types, layout)`, `validate_semantics(nodes, class_types, tab_types)`.
- Note: the synthetic tests pass a tiny `_Table` whose `.rows` are `{index: value}` dicts — the same shape `wdbc.parse_positional(...).rows` produces, so the reader is identical in tests and real use. `AdvancementNode` carries no spell name (the current name comes from the `coa-client-spell-v1` join at record-build time, not from the CharacterAdvancement string block).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client_extract_advancement.py
import pytest

from coa_client_extract.class_types import resolve_class_types, resolve_tab_types
from coa_client_extract.dbc_layouts import CharacterAdvancementLayout
from coa_client_extract.advancement import AdvancementNode, read_advancement, validate_semantics
from coa_client_extract.errors import DbcSemanticError


class _Table:
    def __init__(self, rows): self.rows = rows


def _class_types():
    rows = [{"id": i, "name": n} for i, n in {
        2: "Hunter", 15: "WitchDoctor", 33: "Venomancer", 35: "ConquestOfAzeroth", 36: "RebornHunter",
    }.items()]
    return resolve_class_types(_Table(rows))


def _tab_types():
    return resolve_tab_types(_Table([{"id": 1, "name": "Class"}, {"id": 49, "name": "Brewing"}]))


def _layout(confidence=None):
    return CharacterAdvancementLayout(
        node_id_col=0, spell_id_col=5, class_type_col=32, tab_type_col=6, entry_type_col=7,
        ae_cost_col=8, required_level_col=9, connected_node_cols=(10, 11), required_id_cols=(12,),
        max_rank_col=13, confidence=confidence if confidence is not None else {
            "ae_cost": "high", "required_level": "high",
            "connected_node_ids": "high", "required_ids": "high", "max_rank": "high",
        },
    )


def _ca(rows):
    # rows are dicts keyed by column index (decoded raw), the shape parse_positional produces.
    return _Table(rows)


def _row(node_id, spell, cls, tab=1, entry=0, ae=1, lvl=0, c1=0, c2=0, req=0, rank=1):
    return {0: node_id, 5: spell, 32: cls, 6: tab, 7: entry, 8: ae, 9: lvl,
            10: c1, 11: c2, 12: req, 13: rank}


def test_reads_node_with_ownership_and_confidence_gated_legality():
    ca = _ca([_row(6086, 805775, 33, tab=1, entry=0, ae=1, c1=0, c2=0)])
    n = read_advancement(ca, _class_types(), _tab_types(), _layout())[0]
    assert isinstance(n, AdvancementNode)
    assert n.node_id == 6086 and n.spell_id == 805775
    assert n.class_type_id == 33 and n.class_display == "Venomancer"
    assert n.tab_name == "Class" and n.entry_type == "Ability"
    assert n.legality["ae_cost"] == 1 and n.field_confidence["ae_cost"] == "high"
    assert n.legality["required_ids"] == []            # 0 padding dropped


def test_unproven_legality_field_is_withheld():
    # confidence lacks ae_cost -> it must NOT appear in legality even though the column is set
    layout = _layout(confidence={"required_level": "high"})
    n = read_advancement(_ca([_row(1, 100, 33)]), _class_types(), _tab_types(), layout)[0]
    assert "ae_cost" not in n.legality
    assert "required_level" in n.legality


def test_shared_spell_yields_two_nodes():
    ca = _ca([_row(7131, 503748, 15, tab=49, entry=1), _row(12264, 503748, 15, tab=1, entry=0)])
    nodes = read_advancement(ca, _class_types(), _tab_types(), _layout())
    assert {n.node_id for n in nodes} == {7131, 12264}
    assert {n.tab_name for n in nodes} == {"Brewing", "Class"}


def test_validate_semantics_rejects_dangling_adjacency():
    nodes = read_advancement(_ca([_row(1, 100, 33, c1=999)]), _class_types(), _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="dangling"):
        validate_semantics(nodes, _class_types(), _tab_types())


def test_validate_semantics_rejects_out_of_range_level():
    nodes = read_advancement(_ca([_row(1, 100, 33, lvl=999)]), _class_types(), _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="required_level"):
        validate_semantics(nodes, _class_types(), _tab_types())


def test_validate_semantics_rejects_unknown_class_band():
    ct = resolve_class_types(_Table([{"id": 99, "name": "Mystery"}]))
    nodes = read_advancement(_ca([_row(1, 100, 99)]), ct, _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="unknown class"):
        validate_semantics(nodes, ct, _tab_types())


def test_validate_semantics_rejects_duplicate_and_zero_node_ids():
    dup = read_advancement(_ca([_row(1, 100, 33), _row(1, 101, 33)]), _class_types(), _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="duplicate node"):
        validate_semantics(dup, _class_types(), _tab_types())
    zero = read_advancement(_ca([_row(0, 100, 33)]), _class_types(), _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="node id 0"):
        validate_semantics(zero, _class_types(), _tab_types())


def test_validate_semantics_rejects_unknown_tab_and_entry():
    bad_tab = read_advancement(_ca([_row(1, 100, 33, tab=777)]), _class_types(), _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="unknown tab"):
        validate_semantics(bad_tab, _class_types(), _tab_types())
    bad_entry = read_advancement(_ca([_row(1, 100, 33, entry=99)]), _class_types(), _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="unknown entry_type"):
        validate_semantics(bad_entry, _class_types(), _tab_types())


def test_validate_semantics_rejects_self_reference_and_excessive_cost():
    self_ref = read_advancement(_ca([_row(5, 100, 33, c1=5)]), _class_types(), _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="self-reference"):
        validate_semantics(self_ref, _class_types(), _tab_types())
    huge = read_advancement(_ca([_row(1, 100, 33, ae=100000)]), _class_types(), _tab_types(), _layout())
    with pytest.raises(DbcSemanticError, match="ae_cost"):
        validate_semantics(huge, _class_types(), _tab_types())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_extract_advancement.py -v`
Expected: FAIL with `ModuleNotFoundError: coa_client_extract.advancement`.

- [ ] **Step 3: Write the implementation**

```python
# coa_client_extract/advancement.py
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .errors import DbcSemanticError

_ENTRY_TYPES = {0: "Ability", 1: "Talent", 2: "Trait", 3: "TalentAbility"}
_MAX_LEVEL = 60
# Plausibility ceilings (cells are unsigned, so a mis-mapped column reads as a huge int — an
# upper bound catches that where a negative check cannot). Generous but far below a stray uint32.
_MAX_COST = 500
_MAX_RANK = 20
_MAX_ROWCOL = 200

# Which legality fields are node-id references (validated against the node-id domain).
_ADJ_FIELDS = ("connected_node_ids", "required_ids")
# Scalar legality fields with an inclusive upper bound.
_BOUNDS = {"ae_cost": _MAX_COST, "te_cost": _MAX_COST, "required_tab_ae": _MAX_COST,
           "required_tab_te": _MAX_COST, "max_rank": _MAX_RANK, "row": _MAX_ROWCOL, "col": _MAX_ROWCOL}


@dataclass(frozen=True)
class AdvancementNode:
    node_id: int
    spell_id: int
    class_type_id: int
    class_internal: str
    class_display: str
    class_kind: str
    tab_type_id: int
    tab_name: str
    entry_type: str
    essence_kind: str          # "ability" | "talent" | "" (derived from entry_type)
    legality: dict
    field_confidence: dict
    raw: dict                  # {cell_index: value} preserved for audit (explicit indices)


def _slots(row: dict, cols) -> list[int]:
    # gather node ids from fixed slot columns, dropping 0 padding, de-duped, sorted
    seen: list[int] = []
    for c in cols:
        v = row.get(c, 0)
        if v and v not in seen:
            seen.append(v)
    return sorted(seen)


def _essence_kind(entry_type: str) -> str:
    if entry_type in ("Ability", "TalentAbility"):
        return "ability"
    if entry_type == "Talent":
        return "talent"
    return ""


def read_advancement(ca, class_types, tab_types, layout) -> list[AdvancementNode]:
    """Build nodes from positional rows. A legality field is emitted ONLY when the layout proved
    it to `high` confidence (layout.confidence); a configured-but-unproven column is withheld, so
    a mis-decoded column never becomes canonical output."""
    L = layout
    conf_map = L.confidence or {}
    nodes: list[AdvancementNode] = []
    for row in ca.rows:
        cid = row.get(L.class_type_col, 0)
        ct = class_types.get(cid)
        etype = (_ENTRY_TYPES.get(row.get(L.entry_type_col), "")
                 if L.entry_type_col is not None else "")
        legality, conf = {}, {}

        def emit(name, value):
            if conf_map.get(name) == "high":     # gate every legality field on proven confidence
                legality[name] = value
                conf[name] = "high"

        for name, col in (
            ("ae_cost", L.ae_cost_col), ("te_cost", L.te_cost_col),
            ("required_level", L.required_level_col),
            ("required_tab_ae", L.required_tab_ae_col), ("required_tab_te", L.required_tab_te_col),
            ("max_rank", L.max_rank_col), ("row", L.row_col), ("col", L.column_col),
        ):
            if col is not None:
                emit(name, row.get(col, 0))
        if L.connected_node_cols:
            emit("connected_node_ids", _slots(row, L.connected_node_cols))
        if L.required_id_cols:
            emit("required_ids", _slots(row, L.required_id_cols))

        nodes.append(AdvancementNode(
            node_id=row.get(L.node_id_col, 0), spell_id=row.get(L.spell_id_col, 0),
            class_type_id=cid,
            class_internal=(ct.internal if ct else ""),
            class_display=(ct.display if ct else ""),
            class_kind=(ct.kind if ct else "unknown"),
            tab_type_id=row.get(L.tab_type_col, 0) if L.tab_type_col is not None else 0,
            tab_name=tab_types.get(row.get(L.tab_type_col, 0), "") if L.tab_type_col is not None else "",
            entry_type=etype, essence_kind=_essence_kind(etype),
            legality=legality, field_confidence=conf,
            raw=dict(row),
        ))
    return nodes


def validate_semantics(nodes, class_types, tab_types) -> None:
    """Reject a mis-decoded or structurally invalid graph. A matching WDBC header is not enough:
    ownership FKs must resolve, adjacency must resolve in the node-id domain, and scalars must be
    plausible. Any failure raises DbcSemanticError (blocks canonical emission)."""
    node_ids = {n.node_id for n in nodes}
    dup = [nid for nid, c in Counter(n.node_id for n in nodes).items() if c > 1]
    if dup:
        raise DbcSemanticError(f"duplicate node ids: {sorted(dup)[:10]}")
    for n in nodes:
        if n.node_id == 0:
            raise DbcSemanticError("node id 0 is invalid")
        if n.class_kind == "unknown":
            raise DbcSemanticError(f"node {n.node_id}: unknown class type {n.class_type_id}")
        if n.tab_type_id and n.tab_type_id not in tab_types:
            raise DbcSemanticError(f"node {n.node_id}: unknown tab type {n.tab_type_id}")
        if n.entry_type == "":
            raise DbcSemanticError(f"node {n.node_id}: unknown entry_type")
        for adj_field in _ADJ_FIELDS:
            for ref in n.legality.get(adj_field, []):
                if ref == n.node_id:
                    raise DbcSemanticError(f"node {n.node_id}: self-reference in {adj_field}")
                if ref not in node_ids:
                    raise DbcSemanticError(f"node {n.node_id}: dangling {adj_field} reference {ref}")
        lvl = n.legality.get("required_level")
        if lvl is not None and not (lvl == 0 or 1 <= lvl <= _MAX_LEVEL):
            raise DbcSemanticError(
                f"node {n.node_id}: required_level {lvl} outside {{0}} u [1,{_MAX_LEVEL}]")
        for field_name, ceiling in _BOUNDS.items():
            v = n.legality.get(field_name)
            if v is not None and v > ceiling:
                raise DbcSemanticError(f"node {n.node_id}: {field_name} {v} exceeds ceiling {ceiling}")
```

Note: `validate_semantics` requires `entry_type` and (when present) `tab_type` to resolve, which
means those ownership columns must be decoded before extraction passes — enforcing the decode rather
than shipping a graph with unknown ownership. Per-spec reachability/orphan invariants are covered
end-to-end by the Task 7 parity report (exact Builder equality implies a well-formed per-spec graph).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_client_extract_advancement.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/advancement.py tests/test_client_extract_advancement.py
git commit -m "M1.14B: CharacterAdvancement graph reader + semantic validators (FK/adjacency/range)"
```

---

## Task 5: Attribution — participation model + memberships

**Files:**
- Create: `coa_client_extract/attribution.py`
- Test: `tests/test_client_extract_attribution.py`

**Interfaces:**
- Consumes: `advancement.AdvancementNode`, `class_types.ClassType`.
- Produces: `AttributionResult`, `SpellAttribution`, `attribute(nodes, class_types, skill_line_index=None)`, `build_skill_line_index(skill_line_ability_rows, coa_line_ids=COA_CLASS_BAND_SKILL_LINES)`, `COA_CLASS_BAND_SKILL_LINES`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client_extract_attribution.py
from coa_client_extract.attribution import attribute, AttributionResult
from coa_client_extract.advancement import AdvancementNode


def _node(node_id, spell_id, cid, kind, display, tab_id=1, tab="Class", etype="Ability"):
    return AdvancementNode(
        node_id=node_id, spell_id=spell_id, class_type_id=cid, class_internal=display,
        class_display=display, class_kind=kind, tab_type_id=tab_id, tab_name=tab,
        entry_type=etype, essence_kind="ability", legality={}, field_confidence={}, raw={},
    )


def test_coa_membership_is_high_confidence_coa():
    nodes = [_node(1, 805775, 33, "coa_class", "Venomancer")]
    res = attribute(nodes, {})
    a = res[805775].result
    assert a.is_coa is True and a.modes == ("coa",) and a.exclusive_mode == "coa"
    assert a.confidence == "high"


def test_unknown_kind_contributes_no_mode_not_stock():
    # a node on an out-of-band (unknown) class must NOT be silently attributed as stock.
    nodes = [_node(1, 960, 999, "unknown", "???")]
    a = attribute(nodes, {})[960].result
    assert a.is_coa is False and a.modes == () and a.exclusive_mode is None
    assert a.confidence == "low"


def test_build_skill_line_index_maps_class_band_spells_only():
    from coa_client_extract.attribution import build_skill_line_index
    rows = [
        {0: 1, 1: 480, 2: 7777},   # class-band line (475-495) -> coa
        {0: 2, 1: 44, 2: 1234},    # stock skill line -> ignored
        {0: 3, 1: 495, 2: 0},      # class-band but no spell -> ignored
    ]
    assert build_skill_line_index(rows) == {7777: "coa"}


def test_shared_spell_aggregates_memberships():
    nodes = [
        _node(7131, 503748, 15, "coa_class", "Witch Doctor", 49, "Brewing", "Talent"),
        _node(12264, 503748, 15, "coa_class", "Witch Doctor", 1, "Class", "Ability"),
    ]
    res = attribute(nodes, {})
    assert len(res[503748].memberships) == 2
    assert {m["tab_name"] for m in res[503748].memberships} == {"Brewing", "Class"}


def test_coa_plus_reborn_is_multimode_not_conflict():
    nodes = [
        _node(1, 900, 33, "coa_class", "Venomancer"),
        _node(2, 900, 36, "reborn", "RebornHunter"),
    ]
    a = attribute(nodes, {})[900].result
    assert a.is_coa is True
    assert a.modes == ("coa", "reborn") and a.exclusive_mode is None


def test_stock_membership_does_not_overwrite_coa():
    nodes = [
        _node(1, 950, 33, "coa_class", "Venomancer"),
        _node(2, 950, 2, "stock", "Hunter"),
    ]
    a = attribute(nodes, {})[950].result
    assert a.is_coa is True
    assert set(a.modes) == {"coa", "stock"}


def test_skill_line_fallback_for_graph_absent_spell():
    res = attribute([], {}, skill_line_index={7777: "coa"})
    a = res[7777].result
    assert a.is_coa is True and a.confidence == "medium"


def test_id_only_is_unknown_low():
    # a spell with no advancement node and no skill line is simply absent from the result;
    # callers treat absence as is_coa: false / low. Assert it is not present.
    res = attribute([], {}, skill_line_index={})
    assert 123456 not in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_extract_attribution.py -v`
Expected: FAIL with `ModuleNotFoundError: coa_client_extract.attribution`.

- [ ] **Step 3: Write the implementation**

```python
# coa_client_extract/attribution.py
from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict

# class-kind -> participation mode. An unrecognized kind is deliberately absent:
# `.get(kind)` returns None so an out-of-band class contributes NO mode (never a
# silent "stock" default, which would mislabel unknowns as legal stock content).
_KIND_TO_MODE = {"coa_class": "coa", "coa_system": "coa", "reborn": "reborn",
                 "stock": "stock", "meta": "stock"}

# Class-band SkillLines for the 21 CoA classes (SkillLine ids 475-495 inclusive),
# used only for the medium-confidence fallback below.
COA_CLASS_BAND_SKILL_LINES = range(475, 496)


@dataclass(frozen=True)
class AttributionResult:
    is_coa: bool
    modes: tuple[str, ...]
    exclusive_mode: str | None
    confidence: str


@dataclass
class SpellAttribution:
    result: AttributionResult
    memberships: list[dict] = field(default_factory=list)


def build_skill_line_index(skill_line_ability_rows, coa_line_ids=COA_CLASS_BAND_SKILL_LINES):
    """Map spell_id -> "coa" for abilities whose SkillLine is in the CoA class band.

    Rows are positional dicts from `parse_positional(SkillLineAbility)`:
    col 1 = SkillLine FK, col 2 = Spell FK (standard 3.3.5 SkillLineAbility layout).
    This is a medium-confidence fallback for spells absent from CharacterAdvancement.dbc.
    """
    coa_lines = set(coa_line_ids)
    index: dict[int, str] = {}
    for row in skill_line_ability_rows:
        skill_line = row.get(1)
        spell_id = row.get(2)
        if skill_line in coa_lines and spell_id:
            index[spell_id] = "coa"
    return index


def attribute(nodes, class_types, skill_line_index=None) -> dict[int, SpellAttribution]:
    by_spell: dict[int, list] = defaultdict(list)
    for n in nodes:
        if n.spell_id:
            by_spell[n.spell_id].append(n)

    out: dict[int, SpellAttribution] = {}
    for spell_id, spell_nodes in by_spell.items():
        modes, memberships = [], []
        for n in spell_nodes:
            mode = _KIND_TO_MODE.get(n.class_kind)   # None for an unknown kind
            if mode and mode not in modes:
                modes.append(mode)
            memberships.append({
                "mode": mode or "unknown", "class_type_id": n.class_type_id,
                "class_internal": n.class_internal, "class_display": n.class_display,
                "tab_type_id": n.tab_type_id, "tab_name": n.tab_name,
                "node_id": n.node_id, "entry_type": n.entry_type,
            })
        modes = tuple(sorted(modes))
        is_coa = "coa" in modes
        # A graph-present spell with at least one recognized mode is high confidence;
        # if every node was an unknown kind, no mode is claimed -> low confidence.
        confidence = "high" if modes else "low"
        out[spell_id] = SpellAttribution(
            AttributionResult(is_coa, modes,
                              modes[0] if len(modes) == 1 else None, confidence),
            memberships,
        )

    # Skill-line fallback for spells absent from the graph (medium confidence, coa only).
    for spell_id, mode in (skill_line_index or {}).items():
        if spell_id not in out and mode == "coa":
            out[spell_id] = SpellAttribution(
                AttributionResult(True, ("coa",), "coa", "medium"), [])
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_client_extract_attribution.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/attribution.py tests/test_client_extract_attribution.py
git commit -m "M1.14B: participation-model attribution (is_coa/modes/exclusive_mode + memberships)"
```

---

## Task 6: Artifact writers + fill spell attribution

**Files:**
- Modify: `coa_client_extract/artifacts.py`
- Test: extend `tests/test_client_extract_artifacts.py`

**Interfaces:**
- Consumes: `advancement.AdvancementNode`, `class_types.ClassType`, `attribution.SpellAttribution`.
- Produces: `build_advancement_records(nodes, *, provenance, spell_names=None, attribution=None) -> list[dict]`, `build_class_type_records(class_types) -> list[dict]`, `build_tab_type_records(tab_types) -> list[dict]`, `build_essence_raw_records(essence, *, provenance) -> list[dict]`, `fill_spell_attribution(spell_records, attribution) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_client_extract_artifacts.py
from coa_client_extract.artifacts import (
    build_advancement_records, build_class_type_records, build_tab_type_records,
    build_essence_raw_records, fill_spell_attribution,
)
from coa_client_extract.advancement import AdvancementNode
from coa_client_extract.attribution import AttributionResult, SpellAttribution
from coa_client_extract.class_types import ClassType


def _node():
    return AdvancementNode(
        node_id=6086, spell_id=805775, class_type_id=33, class_internal="Venomancer",
        class_display="Venomancer", class_kind="coa_class", tab_type_id=1, tab_name="Class",
        entry_type="Ability", essence_kind="ability",
        legality={"ae_cost": 1, "connected_node_ids": [6096, 7235], "required_ids": []},
        field_confidence={"ae_cost": "high", "connected_node_ids": "high"},
        raw={0: 6086, 5: 805775, 32: 33},
    )


def test_advancement_record_shape():
    attr = {805775: SpellAttribution(AttributionResult(True, ("coa",), "coa", "high"), [])}
    recs = build_advancement_records([_node()], provenance={"client_build": "3.3.5a+patch-CZZ"},
                                     spell_names={805775: "Adrenal Venom"}, attribution=attr)
    r = recs[0]
    assert r["schema_version"] == "coa-client-advancement-v1"
    assert r["node_id"] == 6086 and r["spell_id"] == 805775
    assert r["name"] == "Adrenal Venom"                 # joined from the client spell artifact
    assert r["class"]["display"] == "Venomancer" and r["class"]["kind"] == "coa_class"
    assert r["tab"] == {"tab_type_id": 1, "name": "Class"}
    assert r["legality"]["connected_node_ids"] == [6096, 7235]
    assert r["field_confidence"]["ae_cost"] == "high"
    assert r["raw"]["cols"] == {0: 6086, 5: 805775, 32: 33}    # index-keyed audit map
    assert r["provenance"]["client_build"] == "3.3.5a+patch-CZZ"
    assert r["coa_attribution"] == {"is_coa": True, "modes": ["coa"],
                                    "exclusive_mode": "coa", "confidence": "high"}


def test_advancement_record_attribution_absent_is_low():
    r = build_advancement_records([_node()], provenance={})[0]
    assert r["coa_attribution"] == {"is_coa": False, "modes": [],
                                    "exclusive_mode": None, "confidence": "low"}


def test_class_type_record_records_alias_provenance():
    cts = {22: ClassType(22, "SonOfArugal", "Bloodmage", "coa_class", "curated_alias",
                         ("builder_class_name", "project_owner_confirmation"))}
    r = build_class_type_records(cts)[0]
    assert r["schema_version"] == "coa-client-class-types-v1"
    assert r["internal"] == "SonOfArugal" and r["display"] == "Bloodmage"
    assert r["kind"] == "coa_class"
    assert r["display_source"] == "curated_alias"
    assert r["display_evidence"] == ["builder_class_name", "project_owner_confirmation"]


def test_tab_type_record_shape():
    recs = build_tab_type_records({1: "Class", 49: "Brewing"})
    assert {x["tab_type_id"]: x["name"] for x in recs} == {1: "Class", 49: "Brewing"}
    assert all(x["schema_version"] == "coa-client-tab-types-v1" for x in recs)


def test_fill_spell_attribution_replaces_unknown_and_keeps_raw_signals():
    spells = [{"schema_version": "coa-client-spell-v1", "spell_id": 805775,
               "coa_attribution": {"status": "unknown", "archive_family": "other", "id_range": "high"}}]
    membership = {"mode": "coa", "class_type_id": 33, "tab_name": "Class", "node_id": 6086}
    attr = {805775: SpellAttribution(
        AttributionResult(True, ("coa",), "coa", "high"), [membership])}
    rec = fill_spell_attribution(spells, attr)[0]
    a = rec["coa_attribution"]
    assert a["is_coa"] is True and a["modes"] == ["coa"] and a["exclusive_mode"] == "coa"
    assert a["archive_family"] == "other" and a["id_range"] == "high"   # raw signals retained
    assert "status" not in a
    assert rec["memberships"] == [membership]           # memberships attached, never discarded


def test_fill_spell_attribution_absent_spell_is_low():
    spells = [{"spell_id": 999, "coa_attribution": {"status": "unknown"}}]
    rec = fill_spell_attribution(spells, {})[0]
    assert rec["coa_attribution"] == {"is_coa": False, "modes": [],
                                      "exclusive_mode": None, "confidence": "low"}
    assert rec["memberships"] == []


def test_essence_raw_records_preserve_cells_and_provenance():
    # CharacterAdvancementEssence is per-level progression, extracted RAW (undecoded semantics);
    # caps are the documented constants AE 26 / TE 25, NOT decoded here.
    class _Ess:
        rows = [{0: 1, 1: 60, 2: 26}, {0: 2, 1: 61, 2: 25}]
    recs = build_essence_raw_records(_Ess(), provenance={"client_build": "3.3.5a+patch-CZZ"})
    assert len(recs) == 2
    assert recs[0]["schema_version"] == "coa-client-essence-v1"
    assert recs[0]["cols"] == {0: 1, 1: 60, 2: 26}      # raw cells, no column meaning asserted
    assert recs[0]["provenance"]["client_build"] == "3.3.5a+patch-CZZ"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_extract_artifacts.py -v`
Expected: FAIL with `ImportError` for the new functions (`build_tab_type_records`, `build_essence_raw_records`).

- [ ] **Step 3: Add the writers to `artifacts.py`**

Append to `coa_client_extract/artifacts.py`:

```python
def _attribution_block(attr) -> dict:
    """One participation block from a SpellAttribution, or the low/absent default."""
    if attr is None:
        return {"is_coa": False, "modes": [], "exclusive_mode": None, "confidence": "low"}
    r = attr.result
    return {"is_coa": r.is_coa, "modes": list(r.modes),
            "exclusive_mode": r.exclusive_mode, "confidence": r.confidence}


def build_advancement_records(nodes, *, provenance: dict, spell_names: dict | None = None,
                              attribution: dict | None = None) -> list[dict]:
    spell_names = spell_names or {}
    attribution = attribution or {}
    records = []
    for n in nodes:
        records.append({
            "schema_version": "coa-client-advancement-v1",
            "node_id": n.node_id,
            "spell_id": n.spell_id,
            "name": spell_names.get(n.spell_id, ""),   # current name from coa-client-spell-v1 join
            "class": {"class_type_id": n.class_type_id, "internal": n.class_internal,
                      "display": n.class_display, "kind": n.class_kind},
            "tab": {"tab_type_id": n.tab_type_id, "name": n.tab_name},
            "entry_type": n.entry_type,
            "essence_kind": n.essence_kind,
            "legality": n.legality,
            "field_confidence": n.field_confidence,
            "raw": {"cols": dict(n.raw)},              # index-keyed {cell_index: value} audit map
            "provenance": dict(provenance),
            "coa_attribution": _attribution_block(attribution.get(n.spell_id)),
        })
    return records


def build_class_type_records(class_types) -> list[dict]:
    out = []
    for ct in class_types.values():
        out.append({
            "schema_version": "coa-client-class-types-v1",
            "class_type_id": ct.class_type_id,
            "internal": ct.internal, "display": ct.display, "kind": ct.kind,
            "display_source": ct.display_source,
            "display_evidence": list(ct.display_evidence),
        })
    return out


def build_tab_type_records(tab_types) -> list[dict]:
    """Emit coa-client-tab-types-v1 from the resolved {tab_type_id: name} map."""
    return [{"schema_version": "coa-client-tab-types-v1", "tab_type_id": tid, "name": name}
            for tid, name in sorted(tab_types.items())]


def build_essence_raw_records(essence, *, provenance: dict) -> list[dict]:
    """Emit CharacterAdvancementEssence RAW as coa-client-essence-v1.

    This table is per-level/per-tier essence *progression* data, NOT per-class caps (caps are the
    documented uniform constants AE 26 / TE 25). Its per-level semantics are undecoded, so M1.14B
    ships the raw index-keyed cells + provenance for auditability and lists `essence_progression`
    as an M1.15 flip-blocker in the parity report. No column meaning is asserted here."""
    return [{"schema_version": "coa-client-essence-v1", "cols": dict(row),
             "provenance": dict(provenance)} for row in essence.rows]


def fill_spell_attribution(spell_records, attribution) -> list[dict]:
    for rec in spell_records:
        # Retain the M1.14A raw signals (archive_family/id_range) as provenance (spec: archive
        # family is kept as raw provenance only), and replace the M1.14A `status: unknown`.
        raw = rec.get("coa_attribution", {})
        keep = {k: raw[k] for k in ("archive_family", "id_range") if k in raw}
        attr = attribution.get(rec.get("spell_id"))
        block = _attribution_block(attr)
        block.update(keep)
        rec["coa_attribution"] = block
        # Stable multi-membership: attach the aggregated memberships[] (never a scalar that flips
        # to an array, never discarded). Absent attribution -> empty list.
        rec["memberships"] = list(attr.memberships) if attr is not None else []
    return spell_records
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_client_extract_artifacts.py -v`
Expected: PASS (existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/artifacts.py tests/test_client_extract_artifacts.py
git commit -m "M1.14B: advancement/class-type/tab-type/raw-essence writers + fill spell attribution (memberships)"
```

---

## Task 7: Node-level (multiset) Builder-parity report

**Files:**
- Create: `coa_client_extract/parity.py`
- Test: `tests/test_client_extract_parity.py`

**Interfaces:**
- Consumes: `advancement.AdvancementNode`; Builder entries as dicts with `spell_id`, `class_name`, `tab_name`, `entry_type` (the shape of `coa_scraper/dist/coa_entries.jsonl`).
- Produces: `build_parity_report(nodes, builder_entries, *, low_confidence_fields=(), unresolved_layout_columns=(), adjacency_mismatches=0, legality_diffs=(), essence_progression_decoded=False, provenance=None) -> dict`. The report carries `multiset_recall`/`multiset_precision`, `per_class`, `flip_blockers[]`, and the `flip_ready` boolean; the CLI (Task 8) assembles the gate inputs (which adapter fields decoded below `high`, which configured layout columns stayed unproven, adjacency-mismatch count, the Decision-22-classified legality diffs, and whether the essence progression is decoded).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client_extract_parity.py
from coa_client_extract.parity import build_parity_report
from coa_client_extract.advancement import AdvancementNode


def _node(node_id, spell_id, display, tab, etype="Ability"):
    return AdvancementNode(
        node_id=node_id, spell_id=spell_id, class_type_id=33, class_internal=display,
        class_display=display, class_kind="coa_class", tab_type_id=1, tab_name=tab,
        entry_type=etype, essence_kind="ability", legality={}, field_confidence={}, raw={},
    )


def _builder(spell_id, display, tab, etype="Ability"):
    return {"spell_id": spell_id, "class_name": display, "tab_name": tab, "entry_type": etype}


def test_multiset_ownership_counts_duplicate_spell():
    # shared spell 503748 -> two Witch Doctor nodes; both present in Builder
    nodes = [
        _node(1, 503748, "Witch Doctor", "Brewing", "Talent"),
        _node(2, 503748, "Witch Doctor", "Class", "Ability"),
    ]
    builder = [
        _builder(503748, "Witch Doctor", "Brewing", "Talent"),
        _builder(503748, "Witch Doctor", "Class", "Ability"),
    ]
    rep = build_parity_report(nodes, builder)
    assert rep["builder_records"] == 2 and rep["client_nodes"] == 2
    assert rep["unique_spell_recall"] == 1.0
    assert rep["multiset_recall"] == 1.0 and rep["multiset_precision"] == 1.0
    assert rep["builder_only_records"] == 0 and rep["client_only_records"] == 0
    assert rep["per_class"]["Witch Doctor"] == {
        "client_nodes": 2, "builder_records": 2, "client_only": 0, "builder_only": 0}


def test_missing_multiplicity_blocks_flip_via_recall():
    nodes = [_node(1, 503748, "Witch Doctor", "Brewing", "Talent")]   # only one of two
    builder = [
        _builder(503748, "Witch Doctor", "Brewing", "Talent"),
        _builder(503748, "Witch Doctor", "Class", "Ability"),
    ]
    rep = build_parity_report(nodes, builder)
    assert rep["unique_spell_recall"] == 1.0            # spell present
    assert rep["multiset_recall"] < 1.0                 # but a node instance is missing
    assert rep["builder_only_records"] == 1
    assert rep["flip_ready"] is False
    assert "builder_only_node_instances" in rep["flip_blockers"]


def test_extra_client_node_blocks_flip_via_precision_not_just_recall():
    # THE false-100% guard: the client covers every Builder node (recall 1.0) but adds an extra
    # wrongly-attributed CoA node. A recall-only metric reports 100%; precision catches the extra.
    nodes = [
        _node(1, 503748, "Witch Doctor", "Brewing", "Talent"),
        _node(2, 999999, "Witch Doctor", "Class", "Ability"),   # not in Builder
    ]
    builder = [_builder(503748, "Witch Doctor", "Brewing", "Talent")]
    rep = build_parity_report(nodes, builder)
    assert rep["multiset_recall"] == 1.0                # every Builder node covered
    assert rep["multiset_precision"] < 1.0              # but the client has an extra
    assert rep["client_only_records"] == 1
    assert rep["flip_ready"] is False
    assert "client_only_node_instances" in rep["flip_blockers"]


def test_flip_blockers_only_essence_when_ownership_exact_and_clean():
    nodes = [_node(1, 503748, "Witch Doctor", "Brewing", "Talent")]
    builder = [_builder(503748, "Witch Doctor", "Brewing", "Talent")]
    rep = build_parity_report(nodes, builder)          # essence undecoded by default
    assert rep["multiset_recall"] == 1.0 and rep["multiset_precision"] == 1.0
    assert set(rep["flip_blockers"]) == {"essence_progression"}
    assert rep["flip_ready"] is False                  # M1.14B validates but never flips


def test_decision22_class_b_difference_does_not_block_but_class_a_does():
    nodes = [_node(1, 503748, "Witch Doctor", "Brewing", "Talent")]
    builder = [_builder(503748, "Witch Doctor", "Brewing", "Talent")]
    rep = build_parity_report(
        nodes, builder,
        low_confidence_fields=["ae_cost"],
        unresolved_layout_columns=["required_level_col"],
        adjacency_mismatches=3,
        legality_diffs=[
            {"class": "a", "field": "te_cost", "node_id": 1},   # extraction defect -> blocks
            {"class": "b", "field": "ae_cost", "node_id": 1},   # proven current diff -> no block
        ],
        essence_progression_decoded=True,      # this one resolved, so NOT a blocker here
    )
    b = set(rep["flip_blockers"])
    assert "low_confidence:ae_cost" in b
    assert "unresolved_layout_column:required_level_col" in b
    assert "adjacency_mismatch" in b
    assert "legality_defect:te_cost" in b      # class (a) blocks
    assert "legality_defect:ae_cost" not in b  # class (b) never blocks (Decision 22)
    assert "essence_progression" not in b
    assert rep["flip_ready"] is False


def test_provenance_pins_merged():
    rep = build_parity_report([], [], provenance={"client_build": "3.3.5a+patch-CZZ"})
    assert rep["provenance"]["client_build"] == "3.3.5a+patch-CZZ"


def test_flip_gate_inputs_splits_unresolved_from_low_confidence():
    from coa_client_extract.parity import flip_gate_inputs
    from coa_client_extract.dbc_layouts import CharacterAdvancementLayout
    layout = CharacterAdvancementLayout(
        tab_type_col=3, entry_type_col=4,
        ae_cost_col=5,                       # resolved but not proven high -> low_confidence
        required_level_col=None,             # never resolved -> unresolved
        connected_node_cols=(7, 8),          # resolved but not proven high -> adjacency mismatch
        required_id_cols=(),                 # never resolved -> unresolved
        confidence={"ae_cost": "medium", "connected_node_ids": "low",
                    "tab_type": "high", "entry_type": "high"},
    )
    low, unresolved, adj = flip_gate_inputs(layout)
    assert "ae_cost" in low
    assert "required_level" in unresolved and "required_ids" in unresolved
    assert adj == 1                          # connected_node_ids resolved but < high

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_extract_parity.py -v`
Expected: FAIL with `ModuleNotFoundError: coa_client_extract.parity`.

- [ ] **Step 3: Write the implementation**

```python
# coa_client_extract/parity.py
from __future__ import annotations

from collections import Counter

# adapter fields -> the CharacterAdvancementLayout attribute holding their column index.
# Scalar/FK columns first, then the two adjacency slot-lists (handled separately).
_SCALAR_FIELD_COLS = {
    "ae_cost": "ae_cost_col", "te_cost": "te_cost_col", "required_level": "required_level_col",
    "required_tab_ae": "required_tab_ae_col", "required_tab_te": "required_tab_te_col",
    "max_rank": "max_rank_col", "row": "row_col", "col": "column_col",
    "tab_type": "tab_type_col", "entry_type": "entry_type_col",
}
_ADJACENCY_FIELD_COLS = {"connected_node_ids": "connected_node_cols", "required_ids": "required_id_cols"}


def flip_gate_inputs(layout):
    """Derive (low_confidence_fields, unresolved_layout_columns, adjacency_mismatches) from a
    resolved CharacterAdvancementLayout, for `build_parity_report`. A field whose column was never
    resolved (None / empty) is 'unresolved'; a field whose column IS resolved but did not prove to
    `high` confidence is 'low_confidence' (or, for the two adjacency slot-lists, an adjacency
    mismatch). Both categories block the flip."""
    conf = layout.confidence or {}
    low: list[str] = []
    unresolved: list[str] = []
    for field, attr in _SCALAR_FIELD_COLS.items():
        col = getattr(layout, attr)
        if col is None:
            unresolved.append(field)
        elif conf.get(field) != "high":
            low.append(field)
    adjacency_mismatches = 0
    for field, attr in _ADJACENCY_FIELD_COLS.items():
        cols = getattr(layout, attr)
        if not cols:
            unresolved.append(field)
        elif conf.get(field) != "high":
            adjacency_mismatches += 1
    return low, unresolved, adjacency_mismatches


def _key(spell_id, class_name, tab_name, entry_type):
    return (int(spell_id), class_name, tab_name, entry_type)


def build_parity_report(nodes, builder_entries, *,
                        low_confidence_fields=(),
                        unresolved_layout_columns=(),
                        adjacency_mismatches=0,
                        legality_diffs=(),
                        essence_progression_decoded=False,
                        provenance=None) -> dict:
    """Node-level (multiset) Builder-parity report + flip gate.

    Ownership is a multiset over the compound identity (spell_id, class, tab, entry_type): the
    shared spell 503748 is two distinct Witch Doctor nodes, counted twice, not collapsed. The flip
    gate requires EXACT multiset equality — both recall AND precision must be 1.0 — so a client
    graph that covers every Builder node but adds extra/wrongly-attributed CoA nodes is NOT
    flip-ready (recall alone would falsely report 100%). `legality_diffs` are already classified
    into the Decision 22 buckets; only classes (a) extraction defect and (d) unresolved block —
    class (b) proven-current differences are recorded but never block (the client wins offline)."""
    # Scope the client side to CoA-class nodes; the Builder oracle is CoA-only, so Reborn/stock
    # nodes would otherwise flood client_only_records with meaningless entries.
    coa_nodes = [n for n in nodes if n.spell_id and n.class_kind == "coa_class"]
    client_keys = Counter(
        _key(n.spell_id, n.class_display, n.tab_name, n.entry_type) for n in coa_nodes)
    builder_keys = Counter(
        _key(e["spell_id"], e["class_name"], e.get("tab_name", ""), e.get("entry_type", ""))
        for e in builder_entries)

    inter = client_keys & builder_keys        # Counter intersection = min multiplicity per key
    inter_total = sum(inter.values())
    client_total = sum(client_keys.values())
    builder_total = sum(builder_keys.values())
    builder_only = builder_keys - client_keys
    client_only = client_keys - builder_keys
    builder_only_total = sum(builder_only.values())
    client_only_total = sum(client_only.values())

    client_spells = {n.spell_id for n in coa_nodes}
    builder_spells = {int(e["spell_id"]) for e in builder_entries}

    # per-class client vs builder node counts (+ the asymmetric-only tallies)
    client_by_class = Counter(n.class_display for n in coa_nodes)
    builder_by_class = Counter(e["class_name"] for e in builder_entries)
    only_client_by_class, only_builder_by_class = Counter(), Counter()
    for k, c in client_only.items():
        only_client_by_class[k[1]] += c
    for k, c in builder_only.items():
        only_builder_by_class[k[1]] += c
    per_class = {}
    for cls in set(client_by_class) | set(builder_by_class):
        per_class[cls] = {
            "client_nodes": client_by_class.get(cls, 0),
            "builder_records": builder_by_class.get(cls, 0),
            "client_only": only_client_by_class.get(cls, 0),
            "builder_only": only_builder_by_class.get(cls, 0),
        }

    multiset_recall = round(inter_total / builder_total, 4) if builder_total else 1.0
    multiset_precision = round(inter_total / client_total, 4) if client_total else 1.0

    # Flip gate: any ownership/identity/adjacency/confidence defect blocks. A proven legality VALUE
    # difference (Decision 22 class (b)) is recorded but does NOT block. essence_progression is a
    # standing M1.14B blocker (undecoded) until M1.15 decodes it.
    legality_blockers = [d for d in legality_diffs if d.get("class") in ("a", "d")]
    flip_blockers: list[str] = []
    if builder_only_total:
        flip_blockers.append("builder_only_node_instances")
    if client_only_total:
        flip_blockers.append("client_only_node_instances")
    if adjacency_mismatches:
        flip_blockers.append("adjacency_mismatch")
    flip_blockers += [f"low_confidence:{f}" for f in low_confidence_fields]
    flip_blockers += [f"unresolved_layout_column:{c}" for c in unresolved_layout_columns]
    flip_blockers += [f"legality_defect:{d.get('field', '?')}" for d in legality_blockers]
    if not essence_progression_decoded:
        flip_blockers.append("essence_progression")

    report = {
        "schema_version": "coa-builder-parity-v1",
        "builder_records": builder_total,
        "client_nodes": client_total,
        "unique_spell_recall": round(len(client_spells & builder_spells) / len(builder_spells), 4)
                               if builder_spells else 1.0,
        "multiset_recall": multiset_recall,
        "multiset_precision": multiset_precision,
        "builder_only_records": builder_only_total,
        "client_only_records": client_only_total,
        "builder_only_sample": [list(k) for k in list(builder_only)[:20]],
        "client_only_sample": [list(k) for k in list(client_only)[:20]],
        "per_class": per_class,
        "adjacency_mismatches": adjacency_mismatches,
        "legality_diffs": [dict(d) for d in legality_diffs],
        "flip_blockers": flip_blockers,
        # Exact multiset equality (recall AND precision == 1.0) plus no other blocker.
        "flip_ready": (not flip_blockers
                       and multiset_recall == 1.0 and multiset_precision == 1.0),
    }
    if provenance:
        report["provenance"] = dict(provenance)   # Decision 10 reproducibility pins
    return report
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_client_extract_parity.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/parity.py tests/test_client_extract_parity.py
git commit -m "M1.14B: node-level (multiset) Builder-parity report + flip gate"
```

---

## Task 8: CLI wiring — regenerate emits new artifacts + parity report

**Files:**
- Modify: `coa_client_extract/cli.py`
- Test: extend `tests/test_client_extract_cli.py`

**Interfaces:**
- Consumes: everything above, plus `class_types`, `advancement`, `attribution`, `parity`, and the loose JSON for the parity oracle path (optional `--builder-entries`).
- Produces: adds `coa_client_advancement.jsonl`, `coa_client_class_types.jsonl`, and (when `--builder-entries` given) `coa_builder_parity_report.json` to `regenerate` outputs; fills attribution on the spell artifact.

This task **modifies** `tests/test_client_extract_cli.py`: M1.14B makes `regenerate` read the CoA advancement tables, so the existing `_fake_backend()`/`_synthetic_layouts()` must gain them and the existing attribution assertions change (`status: "unknown"` → `is_coa`, with the raw `archive_family`/`id_range` retained).

- [ ] **Step 1: Extend the fake backend + layouts and update assertions**

Add these helpers to `tests/test_client_extract_cli.py` and extend `_fake_backend()`/`_synthetic_layouts()`:

```python
def _pos_dbc(rows, fc, rs):
    # positional DBC (no string block); rows: list of {col: int}
    import struct
    body = b"".join(struct.pack("<" + "I" * (rs // 4), *[r.get(c, 0) for c in range(rs // 4)]) for r in rows)
    return struct.pack("<4sIIII", b"WDBC", len(rows), fc, rs, 0) + body


def _named_dbc(rows, fc, rs, strings):
    import struct
    body = b"".join(struct.pack("<" + "I" * (rs // 4), *[r.get(c, 0) for c in range(rs // 4)]) for r in rows)
    return struct.pack("<4sIIII", b"WDBC", len(rows), fc, rs, len(strings)) + body + strings


def _ca_tables():
    # CharacterAdvancement: one Venomancer node for 805775 (small synthetic layout, 10 cells/40 bytes)
    ca = _pos_dbc([{0: 6086, 1: 805775, 2: 33, 3: 1, 4: 0, 5: 1, 6: 0, 7: 0, 8: 0, 9: 0}], 10, 40)
    # ClassTypes: 21 playable (14..34) + sentinel (35) + one stock (2); only 33 is named "Venomancer"
    ct_strings = b"\x00Venomancer\x00"
    ct_rows = [{0: i, 1: (1 if i == 33 else 0)} for i in list(range(14, 35)) + [35, 2]]
    ct = _named_dbc(ct_rows, 23, 92, ct_strings)
    tt = _named_dbc([{0: 1, 1: 1}], 19, 76, b"\x00Class\x00")   # tab id 1 -> "Class"
    ess = _pos_dbc([{0: 1, 1: 60, 2: 26}], 9, 36)               # raw progression row (semantics undecoded)
    sla = _pos_dbc([], 14, 56)                                  # empty SkillLineAbility (fallback unused)
    return ca, ct, tt, ess, sla
```

In `_fake_backend()`, add the five tables to `entries` (all supplied by `common.MPQ` like the spell family):

```python
    ca, ct, tt, ess, sla = _ca_tables()
    entries["DBFilesClient\\CharacterAdvancement.dbc"] = [(Path("common.MPQ"), ca)]
    entries["DBFilesClient\\CharacterAdvancementClassTypes.dbc"] = [(Path("common.MPQ"), ct)]
    entries["DBFilesClient\\CharacterAdvancementTabTypes.dbc"] = [(Path("common.MPQ"), tt)]
    entries["DBFilesClient\\CharacterAdvancementEssence.dbc"] = [(Path("common.MPQ"), ess)]
    entries["DBFilesClient\\SkillLineAbility.dbc"] = [(Path("common.MPQ"), sla)]
```

In `_synthetic_layouts()`, add the small advancement layout keyed as the CLI expects:

```python
    from coa_client_extract.dbc_layouts import CharacterAdvancementLayout
    layouts["CharacterAdvancementLayout"] = CharacterAdvancementLayout(
        node_id_col=0, spell_id_col=1, class_type_col=2, tab_type_col=3, entry_type_col=4,
        ae_cost_col=5, required_level_col=6, connected_node_cols=(7, 8), required_id_cols=(9,),
        header_field_count=10, header_record_size=40,
    )
    return layouts
```

Update the existing assertions in `test_regenerate_writes_artifacts_with_injected_backend`: replace the `status`/attribution block with the participation model and add the new-artifact checks:

```python
    # attribution is now filled from the client advancement graph (805775 -> Venomancer node)
    assert spell["coa_attribution"]["is_coa"] is True
    assert spell["coa_attribution"]["modes"] == ["coa"]
    assert spell["coa_attribution"]["archive_family"] == "base"   # raw M1.14A signal retained
    assert spell["coa_attribution"]["id_range"] == "high"
    assert spell["memberships"][0]["class_display"] == "Venomancer"   # stable memberships[] attached
    adv = [json.loads(l) for l in (out / "coa_client_advancement.jsonl").read_text().splitlines()]
    assert adv[0]["schema_version"] == "coa-client-advancement-v1"
    assert adv[0]["class"]["display"] == "Venomancer" and adv[0]["name"] == "Adrenal Venom"
    assert adv[0]["coa_attribution"]["is_coa"] is True
    assert adv[0]["raw"]["cols"]["0"] == 6086       # index-keyed audit map (JSON stringifies int keys)
    assert (out / "coa_client_class_types.jsonl").is_file()
    tabs = [json.loads(l) for l in (out / "coa_client_tab_types.jsonl").read_text().splitlines()]
    assert tabs[0]["schema_version"] == "coa-client-tab-types-v1" and tabs[0]["name"] == "Class"
    ess = [json.loads(l) for l in (out / "coa_client_essence.jsonl").read_text().splitlines()]
    assert ess[0]["schema_version"] == "coa-client-essence-v1"      # raw progression, undecoded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client_extract_cli.py -v`
Expected: FAIL — `regenerate` does not yet read CharacterAdvancement / emit `coa_client_advancement.jsonl`, and the updated `is_coa` assertion is unmet.

- [ ] **Step 3: Extend `regenerate` in `cli.py`**

In `coa_client_extract/cli.py`, after the existing spell/content extraction and before writing outputs, add the advancement pipeline. Read the companion tables through the backend (effective chain), resolve class/tab types, read + validate the advancement graph, attribute spells, and write the new artifacts:

```python
# --- inside regenerate(), after content_records is built, before out_dir writes ---
import hashlib
from .class_types import resolve_class_types, resolve_tab_types, assert_playable_cardinality
from .advancement import read_advancement, validate_semantics
from .attribution import attribute, build_skill_line_index
from .artifacts import (
    build_advancement_records, build_class_type_records, build_tab_type_records,
    build_essence_raw_records, fill_spell_attribution,
)
from .wdbc import parse_dbc, parse_positional
from .dbc_layouts import (
    CHARACTER_ADVANCEMENT_CLASS_TYPES, CHARACTER_ADVANCEMENT_TAB_TYPES, CHARACTER_ADVANCEMENT,
    CHARACTER_ADVANCEMENT_ESSENCE, CHARACTER_ADVANCEMENT_SKILL_LINE_ABILITY,
)

def read_named(name, layout):
    m = backend.read_effective_file(root, attach, f"DBFilesClient\\{name}.dbc")
    return m, parse_dbc(m.data, layout)          # named columns incl. "name" (col 1)

def read_positional(name, fc, rs):
    m = backend.read_effective_file(root, attach, f"DBFilesClient\\{name}.dbc")
    return m, parse_positional(m.data, fc, rs)   # {index: value} rows

ct_member, ct_tbl = read_named("CharacterAdvancementClassTypes", CHARACTER_ADVANCEMENT_CLASS_TYPES)
tt_member, tt_tbl = read_named("CharacterAdvancementTabTypes", CHARACTER_ADVANCEMENT_TAB_TYPES)
ca_layout = (layouts.get("CharacterAdvancementLayout") if layouts else None) or CHARACTER_ADVANCEMENT
ca_member, ca_raw = read_positional("CharacterAdvancement",
                                    ca_layout.header_field_count, ca_layout.header_record_size)
ess_member, ess_raw = read_positional("CharacterAdvancementEssence",
                                      CHARACTER_ADVANCEMENT_ESSENCE.expected_field_count,
                                      CHARACTER_ADVANCEMENT_ESSENCE.expected_record_size)
sla_member, sla_raw = read_positional("SkillLineAbility",
                                      CHARACTER_ADVANCEMENT_SKILL_LINE_ABILITY.expected_field_count,
                                      CHARACTER_ADVANCEMENT_SKILL_LINE_ABILITY.expected_record_size)

# CharacterAdvancement is now a canonical CoA-overridden table too: fail closed before writing if
# StormLib's applied order disagrees with the plan's declared load order (same rule as Spell).
validate_load_order(plan, ca_member)

class_types = resolve_class_types(ct_tbl)
tab_types = resolve_tab_types(tt_tbl)
assert_playable_cardinality(class_types)         # exactly 21 playable CoA classes (raises otherwise)

nodes = read_advancement(ca_raw, class_types, tab_types, ca_layout)
validate_semantics(nodes, class_types, tab_types)   # raises before any write -> fail closed
skill_index = build_skill_line_index(sla_raw.rows)  # medium-confidence fallback for graph-absent spells
spell_attr = attribute(nodes, class_types, skill_line_index=skill_index)

adv_provenance = {
    "client_build": _client_build(plan),
    "source_dbcs": {"CharacterAdvancement": ca_member.effective_archive.name,
                    "CharacterAdvancementClassTypes": ct_member.effective_archive.name},
    "supersedes": {"source_file": "CharacterAdvancementData.json"},
    "header_drift": ca_raw.drift,                # header vs layout-expected header; recorded for audit
    "extraction_date": date.today().isoformat(),
}
# current names come from the already-extracted spell records (Spell.dbc), not the CA string block
spell_names = {r["spell_id"]: r.get("name", "") for r in spell_records}
adv_records = build_advancement_records(nodes, provenance=adv_provenance,
                                        spell_names=spell_names, attribution=spell_attr)
class_type_records = build_class_type_records(class_types)
tab_type_records = build_tab_type_records(tab_types)
essence_records = build_essence_raw_records(ess_raw, provenance=adv_provenance)  # raw; semantics undecoded
spell_records = fill_spell_attribution(spell_records, spell_attr)
```

Then add the outputs (the raw essence artifact is always emitted, even if its per-level semantics
are undecoded — the raw cells plus provenance are the deliverable; its decode is an M1.15 flip-blocker):

```python
outputs["coa_client_advancement.jsonl"] = write_jsonl(adv_records, out_dir / "coa_client_advancement.jsonl")
outputs["coa_client_class_types.jsonl"] = write_jsonl(class_type_records, out_dir / "coa_client_class_types.jsonl")
outputs["coa_client_tab_types.jsonl"] = write_jsonl(tab_type_records, out_dir / "coa_client_tab_types.jsonl")
outputs["coa_client_essence.jsonl"] = write_jsonl(essence_records, out_dir / "coa_client_essence.jsonl")
```

If a `--builder-entries` path is provided, also build and write the parity report with the flip-gate
inputs derived from the resolved layout (essence progression is undecoded in M1.14B, so it is always a
standing blocker — the report validates the graph but never reports `flip_ready`):

```python
if builder_entries_path:
    from .parity import build_parity_report, flip_gate_inputs
    builder_path = Path(builder_entries_path)
    builder_entries = [json.loads(l) for l in builder_path.read_text().splitlines()]
    low_conf, unresolved_cols, adj_mismatches = flip_gate_inputs(ca_layout)
    pins = {
        "client_build": _client_build(plan),
        "source_dbc_sha256": {
            "CharacterAdvancement": hashlib.sha256(ca_member.data).hexdigest(),
            "CharacterAdvancementClassTypes": hashlib.sha256(ct_member.data).hexdigest(),
            "CharacterAdvancementTabTypes": hashlib.sha256(tt_member.data).hexdigest(),
            "CharacterAdvancementEssence": hashlib.sha256(ess_member.data).hexdigest(),
            "Spell": hashlib.sha256(spell_member.data).hexdigest(),
        },
        "builder_entries_file": builder_path.name,
        "builder_entries_sha256": hashlib.sha256(builder_path.read_bytes()).hexdigest(),
        "layout_version": "m1-14-b",
        "playable_class_count": sum(1 for c in class_types.values() if c.kind == "coa_class"),
        "extraction_date": date.today().isoformat(),
    }
    report = build_parity_report(
        nodes, builder_entries,
        low_confidence_fields=low_conf, unresolved_layout_columns=unresolved_cols,
        adjacency_mismatches=adj_mismatches, essence_progression_decoded=False, provenance=pins,
    )
    outputs["coa_builder_parity_report.json"] = write_json(
        report, out_dir / "coa_builder_parity_report.json")
```

Add the `--builder-entries` argument to the `regenerate` subparser (and the `builder_entries_path`
parameter to `regenerate(...)`, default `None`) and thread it through. `ExtractedMember.data` carries
the raw bytes for the sha256 pins.

- [ ] **Step 4: Run the full client-extract test module**

Run: `python -m pytest tests/ -k client_extract -v`
Expected: PASS (all client-extract tests, including the new CLI test).

- [ ] **Step 5: Commit**

```bash
git add coa_client_extract/cli.py tests/test_client_extract_cli.py
git commit -m "M1.14B: wire advancement/attribution/parity into regenerate CLI"
```

---

## Task 9: Schema docs + Decisions + roadmap/umbrella updates

**Files:**
- Create: `docs/data/client-advancement-schema.md`, `docs/data/client-class-types-schema.md`
- Modify: `docs/data/client-spell-schema.md`, `docs/data/client-content-schema.md`, `docs/DECISIONS.md`, `docs/superpowers/specs/2026-07-06-m1-14-client-dbc-data-foundation-design.md`, `docs/ROADMAP.md`

- [ ] **Step 1: Write `docs/data/client-advancement-schema.md`**

Document `coa-client-advancement-v1`: every field from the Task 6 record shape (`node_id` = canonical identity, `spell_id` many-to-one, `class`/`tab`/`entry_type`/`essence_kind`, `legality` with the `{0} ∪ [1,60]` required-level rule, `field_confidence` — only `high` fields feed the M1.15 adapter, `raw.cols` for audit, per-table `provenance`, and the `coa_attribution` participation block). State that node identity is the advancement-row id, not the spell id, and cite the shared-spell `503748` example.

- [ ] **Step 2: Write `docs/data/client-class-types-schema.md` (also covering tab-types + raw essence)**

Document `coa-client-class-types-v1`: `class_type_id`, `internal`, `display`, `kind` (`coa_class`/`coa_system`/`reborn`/`stock`/`meta`), `display_source` (`client`|`curated_alias`), `display_evidence`. State the bands (14–34 playable, 35 sentinel, 36–46 Reborn) and the three curated aliases with provenance. In the same file, document the two companion metadata artifacts emitted alongside it: `coa-client-tab-types-v1` (`tab_type_id`, `name`) and `coa-client-essence-v1` (index-keyed `cols` + `provenance`) — stating explicitly that the essence artifact is the raw per-level *progression* table with undecoded semantics (an `essence_progression` flip-blocker for M1.15), and that per-class essence *caps* are the documented constants AE 26 / TE 25, not a decoded DBC value.

- [ ] **Step 3: Update `client-spell-schema.md` and `client-content-schema.md`**

In `client-spell-schema.md`, replace the M1.14A `coa_attribution.status: "unknown"` description with the filled participation block (`is_coa`/`modes`/`exclusive_mode`/`confidence`), and note the alpha→display rename does not affect the client `class_type_id`. In `client-content-schema.md`, note the loose `CharacterAdvancementData.json` is superseded by `CharacterAdvancement.dbc` and retained only as a QA drift signal.

- [ ] **Step 4: Update `docs/DECISIONS.md`**

Amend Decision 18 (archive-family mechanism replaced by the `CharacterAdvancement.dbc` registry; principle unchanged). Add Decision 21 (staged, per-field Decision 1 supersession, gated on node-level parity + semantic validation) and Decision 22 (client DBC = canonical offline legality source; live corrections via user-reported verified overrides; Builder removed from the authority chain; four-way discrepancy classification with only extraction/unresolved blocking). Copy the precedence and classification wording verbatim from the spec's Decision impacts section.

- [ ] **Step 5: Update the umbrella spec + roadmap status**

In the M1.14 umbrella spec, update the M1.14B row/section: attribution source is `CharacterAdvancement.dbc` (not archive family), and it also carries the graph/legality (staged to M1.15). In `docs/ROADMAP.md`, mark M1.14B status and link this spec + plan.

- [ ] **Step 6: Commit**

```bash
git add docs/
git commit -m "M1.14B: schema docs, Decisions 18/21/22, roadmap + umbrella updates"
```

---

## Task 10: Native integration (stormlib tier) + client-tier acceptance test

**Files:**
- Modify: `tests/test_client_extract_integration_stormlib.py`, `tests/test_client_extract_acceptance.py`

**Interfaces:**
- Consumes: the real client via `COA_CLIENT_ROOT` + StormLib; the Builder oracle `coa_scraper/dist/coa_entries.jsonl`.

- [ ] **Step 0: Update the existing acceptance assertion**

M1.14B fills attribution, so in `tests/test_client_extract_acceptance.py` the existing
`test_spell_805775_is_current_adrenal_venom` assertion `assert venom["coa_attribution"]["status"] == "unknown"`
(≈ line 34) must become:

```python
    assert venom["coa_attribution"]["is_coa"] is True          # M1.14B fills attribution
    assert "coa" in venom["coa_attribution"]["modes"]
    assert venom["coa_attribution"]["archive_family"] == family_of(effective)   # raw signal retained
```

- [ ] **Step 1: Add a stormlib-tier CharacterAdvancement override test**

In `tests/test_client_extract_integration_stormlib.py` (M1.14A's native tier, `@pytest.mark.stormlib`, miniature self-authored MPQs), add a case: a base archive contains a `CharacterAdvancement.dbc`; a patch archive overrides it; assert `read_effective_file` returns the patch bytes and the `ExtractedMember` provenance names the patch as `effective_archive` (per-table provenance for the advancement family). Mirror the existing miniature-MPQ construction already in that file; only the logical path (`DBFilesClient\\CharacterAdvancement.dbc`) and asserted bytes change.

- [ ] **Step 2: Write the acceptance test (marked `client`)**

The acceptance test drives the **real `regenerate` API** (the same entry point M1.14A's acceptance
test uses — `regenerate(CLIENT_ROOT, tmp_path, ...)`), not hand-assembled fixtures. It reads the
emitted artifacts and the parity report. Note the strict `flip_blockers == {"essence_progression"}`
bar: it only holds once Task 3's client-tier decode has proven every adapter field to `high` and
written the resolved columns + confidence into the `CHARACTER_ADVANCEMENT` layout constant. A
different blocker is a real finding — a field that failed to decode (fix the layout) or a
client-vs-Builder legality diff misclassified as (a)/(d) instead of a genuine (b) client-wins
difference (Decision 22).

```python
# append to tests/test_client_extract_acceptance.py
# (module already sets `pytestmark = pytest.mark.client` and defines CLIENT_ROOT)


@pytest.mark.skipif(not CLIENT_ROOT.is_dir(), reason="Ascension client not installed at COA_CLIENT_ROOT")
def test_real_client_advancement_parity(tmp_path):
    from coa_client_extract.cli import regenerate
    from coa_client_extract.errors import BackendUnavailable

    builder_path = Path("coa_scraper/dist/coa_entries.jsonl")
    try:
        regenerate(CLIENT_ROOT, tmp_path, builder_entries_path=str(builder_path))
    except BackendUnavailable:
        pytest.skip("StormLib not available")

    # --- class taxonomy: exactly 21 playable CoA classes, ConquestOfAzeroth (35) sentinel excluded ---
    class_types = [json.loads(l) for l in
                   (tmp_path / "coa_client_class_types.jsonl").read_text().splitlines()]
    playable = [c for c in class_types if c["kind"] == "coa_class"]
    assert len(playable) == 21
    assert all(c["class_type_id"] != 35 for c in playable)

    # --- node-level (multiset) Builder-parity: EXACT ownership (recall AND precision) after rename ---
    report = json.loads((tmp_path / "coa_builder_parity_report.json").read_text())
    assert report["unique_spell_recall"] == 1.0
    assert report["multiset_recall"] == 1.0 and report["multiset_precision"] == 1.0
    assert report["builder_only_records"] == 0 and report["client_only_records"] == 0
    assert report["provenance"]["source_dbc_sha256"]["CharacterAdvancement"]   # reproducibility pins
    assert report["provenance"]["playable_class_count"] == 21
    # M1.14B validates but never flips: essence progression is undecoded, so once every adapter
    # field is proven `high` it is the SOLE standing blocker (adjacency proven -> no adjacency_mismatch).
    assert set(report["flip_blockers"]) == {"essence_progression"}
    assert report["flip_ready"] is False

    # --- 805775 is current "Adrenal Venom" on a Venomancer node; attribution filled ---
    adv = [json.loads(l) for l in
           (tmp_path / "coa_client_advancement.jsonl").read_text().splitlines()]
    venom = [n for n in adv if n["spell_id"] == 805775]
    assert venom and any(n["class"]["display"] == "Venomancer" for n in venom)
    assert any(n["name"] == "Adrenal Venom" for n in venom)
    assert all(n["coa_attribution"]["is_coa"] is True for n in venom)

    # --- shared spell 503748 = two distinct Witch Doctor nodes (node identity != spell identity) ---
    assert len([n for n in adv if n["spell_id"] == 503748]) == 2
    spells = {json.loads(l)["spell_id"]: json.loads(l) for l in
              (tmp_path / "coa_client_spell.jsonl").read_text().splitlines()}
    assert 503748 in spells and len(spells[503748]["memberships"]) == 2
    assert all(m["class_display"] == "Witch Doctor" for m in spells[503748]["memberships"])
```

- [ ] **Step 3: Run the acceptance test against the real client**

Run: `COA_CLIENT_ROOT="$HOME/Games/ascension-wow/drive_c/Program Files/Ascension Launcher/resources/ascension-live/Data" python -m pytest tests/test_client_extract_acceptance.py -m client -v`
Expected: PASS. If `multiset_recall`/`multiset_precision` < 1.0, inspect `builder_only_sample`/`client_only_sample` — a builder-only gap is an undecoded column or a genuine client-vs-Builder difference (client wins per Decision 22; it must not be an extraction defect); a client-only entry is an over-attributed or mis-renamed node (an extraction defect — fix it).

- [ ] **Step 4: Regenerate the real artifacts + parity report**

```bash
python -m coa_client_extract regenerate \
  --client-root "$HOME/Games/ascension-wow/drive_c/Program Files/Ascension Launcher/resources/ascension-live/Data" \
  --out reports/client_extract \
  --builder-entries coa_scraper/dist/coa_entries.jsonl
```
Confirm `reports/client_extract/` contains `coa_client_advancement.jsonl`, `coa_client_class_types.jsonl`, `coa_client_tab_types.jsonl`, `coa_client_essence.jsonl`, `coa_client_spell.jsonl` (attribution filled), and `coa_builder_parity_report.json` with `multiset_recall: 1.0` and `multiset_precision: 1.0` (and `flip_blockers: ["essence_progression"]`).

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest` (default tier — must be green without StormLib/client) then the marked tiers if available (`-m stormlib`, `-m client`).

```bash
git add tests/test_client_extract_acceptance.py tests/test_client_extract_integration_stormlib.py
git commit -m "M1.14B: stormlib-tier CA override + client-tier acceptance (exact multiset parity, essence-only blocker)"
```

---

## Self-Review Notes (for the executor)

- **Decode dependency:** Tasks 4–10 reference the `CHARACTER_ADVANCEMENT` layout constant produced by Task 3 Step 6 (client tier). Synthetic unit tests supply their own `CharacterAdvancementLayout`, so Tasks 4–8 are fully testable *without* the client; only Task 3 Step 6 and Task 10 require the real install. Do Task 3's client decode before Task 10.
- **Reader split in `regenerate`:** M1.14A's `regenerate` has a local `read_table(name)` for the spell family. Task 8 adds `read_named(name, layout)` (named columns — companion `*Types` tables, whose `name` is the verified col 1, no decode needed) and `read_positional(name, fc, rs)` (index-keyed cells — the wide `CharacterAdvancement`/`Essence` tables). Keep `read_table` for the spell family untouched.
- **Only `high`-confidence fields are emitted into `legality`/adapter.** A field left `None` in the layout is simply absent from `legality`; that is intended (it becomes Builder-fallback in M1.15), not a bug.
- **Essence: caps are constants, the table is extracted raw.** Per-class essence *caps* are the documented uniform constants (AE 26 / TE 25) and live in the existing `coa_scraper/dist/coa_essence_caps.json`; M1.14B does **not** decode caps from a DBC. `CharacterAdvancementEssence` is per-level *progression* data: `build_essence_raw_records` emits it raw (index-keyed cells + provenance) as `coa-client-essence.jsonl`, and its per-level decode is surfaced as the `essence_progression` entry in the parity report's `flip_blockers` — an M1.15 leveling-gate item, not an M1.14B blocker. Do not add an essence-cap column layout or fabricate cap column indices.
- **Do not rewire `coa_meta`.** If any task tempts you to touch `repository.py` or reports, stop — that is M1.15.
