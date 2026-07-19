# M1.14E0 Correctness & Publication Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute **inline** (superpowers:executing-plans) with task-sized commits and human review checkpoints after Task 5 and after Task 7. The proof model, join representation, recon lifecycle, policy binding, publisher, and Node reader share load-bearing invariants — one continuous implementer, not one subagent per task. Steps use `- [ ]`.

**Goal:** Land the M1.14E foundation with correctness/transactional guarantees that are enforced *and non-bypassable*: per-field **and per-value** decode gating; a recon hard hold with an explicit `blocked → review_required → verified` lifecycle that *discovers* every emitted DBC-derived value (never re-checking the policy's own cell) and never writes the policy; a policy bound to the exact client bytes it was proven against, which canonical regeneration re-checks and requires `verified`; a full `coa-client-spell-v2` + `coa-client-spell-projection-v2` (with matching Node validation and v1 rejection) whose raw observations are built from `RecordView`, with a distinct **join observation** for side-table-joined values; and a collision-safe transactional publisher whose generation manifest binds source + policy + anchor + enum hashes, with retention (not prune-all) and a canonical path that **requires** the generation pointer.

**Architecture:** Verified against the post-D tree (441d55f). `parse_dbc` decodes and loses the raw u32 → raw observations come from `RecordView`. `Envelope` holds one cell; joined values use `JoinObservation`. Decode is withheld both per-field (proof) and per-value (domain). Recon *proposes* a policy delta; a human authors the policy; `regenerate()` runs only against a `verified`, client-bound policy.

**Tech Stack:** Python 3.11 stdlib (`struct`, `json`, `hashlib`, `uuid`, `math`, `resource`, `subprocess`, `time`, `tempfile`, `dataclasses`, `pathlib`); pytest (`stormlib`/`client` markers); Node 18.

## Global Constraints

Verbatim from `docs/superpowers/specs/2026-07-18-m1-14-e-mechanics-extraction-completion-design.md`.

- **Evidence boundary.** No emulator core is authority; `"reference"` is a candidate, never a pass. Proof states `("verified","reference","unproven","contradicted")`.
- **Per-field decode gate.** `decoded` populated only when `semantic_promotion_eligible(proof)` (integrity∧layout∧interpretation verified) and finite; `raw_u32` always retained. `make_envelope` accepts only `state=="present"`; non-present states come from `absent_envelope`. `Envelope` is token-guarded against direct construction; `raw_u32` rejects `bool`/out-of-domain; `decoded_reason ∈ {decoded,proof_withheld,non_finite,not_present,value_out_of_domain}`.
- **Per-value domain gate (unknown-symbol amendment).** Even a `verified` field withholds its **normalized** value (`null`) when the specific value is an unseen enum/bit (`power_type==7`, an unknown school bit): the observation records it **in-band** via `make_domain_gated_envelope` (`decoded_reason: "value_out_of_domain"`, raw retained), and the extract manifest aggregates an `unknown_symbol_inventory: {power_type: [...], school_bits: [...]}`. Enums use exact membership (`refine_enum`); masks accept any valid bit combination (`refine_mask`, so `20 == 4|16` passes). The artifact stays valid.
- **Join observation ≠ envelope.** A side-table-joined value (`cast_time_ms`, `duration_ms`, `range_min/max_yd`) is a `JoinObservation` with `components` (spell index cell, side row-id cell, side value cell — each a raw envelope), a **composed** proof over all parts + both files' integrity, and a `decoded` value only when every part is `semantic_promotion_eligible` and the composed proof is verified. Hashing/decoding operate on the exact byte buffers used for extraction (no hash/read race).
- **Recon lifecycle.** `status ∈ {blocked, review_required, verified}`. `blocked` = evidence collection failed (report written, CLI exit 3). `review_required` = discovery succeeded but the results are not yet reviewed/bound (exit 4). `verified` = discoveries agree with an already-reviewed, hash-bound policy (exit 0). Recon **discovers by scanning** (never assumes the policy's cell) and emits a `proposed_policy_delta`; it **never writes the policy**.
- **Non-bypassable hard hold.** `regenerate()` re-opens the client, re-hashes each source DBC, and runs only when the policy is `verified` and its `bound.client_build` + per-DBC sha256 match the opened client; otherwise it fails closed (exit 3).
- **Discovery is genuine.** Anchor columns and the **joined (index cell, side value cell) pair** are found by scanning, using multiple distinct anchors (an instant spell *plus* several distinct nonzero cast times / durations / ranges), nonzero support, valid-nonzero FK fraction (zero excluded), minimum distinct ids, and a unique winner / runner-up margin. A single "instant→0" anchor never proves a value column.
- **v2, not mutation.** `coa-client-spell-v2` (full record) + `coa-client-spell-projection-v2` + its manifest; normalized scalars stay scalar/`null`; raw/proof lives in a separate `field_observations` block; the Node reader validates v2 rows and **rejects v1 with "regenerate with M1.14E"**; every populated normalized value must have an eligible matching observation.
- **Record-bounded reads** (`(last+1)*4 <= record_size`). **Real budgets:** actual serialized output bytes, elapsed time, and peak RSS (recon measured in a **subprocess** so `ru_maxrss` is that run's; Linux `ru_maxrss` is KiB — normalized).
- **Transactional family.** UUIDv4 generation; `gen-<uuid>/` `exist_ok=False`; children streamed to temp + hashed; immutable generation-local manifest = a **superset of all ten** v1 fields (incl. a deterministic `outputs` **index view** derived from `children`, for *migrated* resolvers only — **not** backward-compat for unmigrated v1 consumers, who receive a pointer + v2 records they cannot read, hence the Task 7 migration) **plus** a monotonic `published_at` (ns) + `predecessor_generation_id` (the pointer's prior target captured at publish), bound source-DBC `{sha256,header,archive}`, `policy_sha256`, `anchor_set_sha256`, `enum_policy_sha256`; a validated pointer published last; Python **and** Node resolvers re-validate. **Retention is a separate, best-effort maintenance op — publish never prunes:** a `prune-generations` command follows the `predecessor_generation_id` chain (ordered by `published_at`) to keep the current + previous generation and removes older `gen-*` only past a grace period **and under a quiescent window / advisory lock**; absent enforced quiescence the semantics are documented best-effort (a random UUID + date-only field cannot identify the predecessor, so the explicit chain + `published_at` are load-bearing).
- **Producer publishes the pointer; the consumer requires it.** `regenerate()` (producer) **publishes** the generation pointer as an output — it never takes a pointer as input. The **Node mechanics build (consumer) requires `--client-extract-pointer`** for a canonical run and validates it; the legacy fixed-path projection mode runs only under the repository's **existing `--allow-fallback-mechanics`** degraded path (reused, not a new overlapping `--allow-degraded` flag).
- **Fail closed** without StormLib. **Redistribution:** recon report + `gen-*` git-ignored (both `reports/client_extract/` and `coa_scraper/dist/`); fixtures synthetic; policy tracked with embedded evidence + hashes.
- **Mandatory client-tier recon.**

---

## Field adjudication matrix (E0) — every DBC-derived value; metadata/attribution follow separate contracts

| Emitted value | Source cell(s) | E0 discovery/adjudication | Unproven ⇒ |
|---|---|---|---|
| `spell_id` | Spell@0 uint32 | id anchor (M1.14A/B, unique, no dupes) | verified |
| `name` | Spell@136 str | normalized-exact anchor over 7 stock spells; `StringObservation` | verified |
| `power_type` | Spell@41 int32 | anchor + per-value `refine_enum({-2,0..6})` | verified (value-gated) |
| `school_mask` | Spell@225 uint32 | anchor + per-value `refine_mask({1,2,4,8,16,32,64})` | verified (value-gated) |
| `cast_time_ms` | Spell.casting_time_index → SpellCastTimes(id,base_ms) | **joined-pair** scan (index cell + value cell) w/ multiple distinct cast-time anchors; composed proof | raw-only (null) |
| `duration_ms` | Spell.duration_index → SpellDuration(id,base_ms) | joined-pair scan w/ multiple distinct duration anchors | raw-only (null) |
| `range_min_yd`/`range_max_yd` | Spell.range_index → SpellRange(id,min,max) | joined-pair scan w/ multiple distinct range anchors | raw-only (null) |
| `spell_icon_id` | Spell.spell_icon_id → SpellIcon.id | index cell by FK-validity scan | raw-only (null) |
| `description` | Spell@170 str | anchor (Eviscerate 2098 "combo point"); interpretation `reference`; `StringObservation` | raw-decodable, not promoted |

Each joined value's contributing **side-table id cell** (`SpellCastTimes.id@0`, `SpellDuration.id@0`, `SpellRange.id@0`) is part of the joined-pair proof. **`category` is OMITTED from E0's emitted schema** — it has no proven cell and no E0 discovery method, so it is neither normalized nor observed until a later task discovers it (a raw-only field with no established cell cannot be emitted honestly). String fields (`name`, `description`) use `StringObservation` (offset + resolved text); the numeric normalized↔observation consistency check applies only to numeric scalars/joins, not strings. The joined-value anchor set (cast/duration/range) records **concrete `{spell_id, expected_value, evidence}` triples** — an instant spell (→ `0`) plus **≥2 distinct nonzero** values per side table, each with independent evidence — established and frozen during the Task 8 client recon, never merely "several nonzero values." The matrix covers every DBC-derived value E0 emits; provenance/attribution/membership fields follow their existing M1.14A/B contracts.

---

## Task 1: Proof gate, envelope, join observation, per-value domain gate

**Files:** Create `coa_client_extract/spell_proof.py`; Test `tests/test_spell_proof.py`

**Interfaces:** `FieldProof`, `raw_decode_eligible`, `semantic_promotion_eligible`, `compose_proof(*proofs)`; `Envelope` (token-guarded) via `make_envelope(raw_u32, *, kind, proof, evidence_ref)` (state fixed `"present"`), `absent_envelope(*, proof, evidence_ref, state)`, and `make_domain_gated_envelope(raw_u32, *, kind, proof, evidence_ref, refine)`; `StringObservation` via `make_string_observation(raw_offset, resolved, *, proof, evidence_ref)`; `JoinObservation` via `make_join(components, *, resolution, decode)` where `resolution ∈ {resolved,index_zero,side_row_missing}` (a malformed FK fails closed upstream and never publishes); `refine_enum(value, allowed)` and `refine_mask(value, allowed_bits)`.

- [ ] **Step 1: Write the failing test** — covering: full-predicate gate (integrity unproven ⇒ withheld); `non_finite` vs `proof_withheld`; `make_envelope` rejects `bool`/out-of-domain; token-guard blocks direct `Envelope(...)`; `compose_proof` yields the **weakest** facet; `make_join(resolution="resolved")` decodes only when the composed proof is promotion-eligible, `"index_zero"` → `state=="not_applicable"`, `"side_row_missing"` → `state=="unresolved"`, empty components raise; `refine_enum(7, {-2,0..6})` → `(None, False)`; `refine_mask(20, {1,2,4,8,16,32,64})` → `(20, True)`, `refine_mask(128, …)` → `(None, False)`; `make_domain_gated_envelope` with an out-of-domain value → `decoded is None`, `decoded_reason=="value_out_of_domain"`; `make_string_observation` carries `resolved` only when promotion-eligible.

- [ ] **Step 2–5:** red → implement (`compose_proof` = per-facet min over `verified>reference>unproven>contradicted`; `make_join` maps `resolution` to `not_applicable`/`unresolved`/`resolved` and decodes only when the composed proof is promotion-eligible **and** the decoder returns a finite number; `refine_enum`/`refine_mask` gate scalar-enum vs bitmask domains) → green → commit `M1.14E0 Task 1: proof gate + present-only envelope + string/join observations + enum/mask + domain-gated envelope`.

```python
# coa_client_extract/spell_proof.py  (complete)
from __future__ import annotations
import math, struct
from dataclasses import dataclass, field

PROOF_STATES = ("verified", "reference", "unproven", "contradicted")
_KINDS = ("int32", "uint32", "float"); _STATES = ("present", "not_applicable", "unresolved")
_TOKEN = object()
_ORDER = {"verified": 3, "reference": 2, "unproven": 1, "contradicted": 0}
_INV = {v: k for k, v in _ORDER.items()}


@dataclass(frozen=True)
class FieldProof:
    integrity: str; layout: str; interpretation: str
    def __post_init__(self):
        for v in (self.integrity, self.layout, self.interpretation):
            if v not in PROOF_STATES: raise ValueError(f"proof state {v!r}")
    def to_dict(self):
        return {"integrity": self.integrity, "layout": self.layout, "interpretation": self.interpretation}


def raw_decode_eligible(p): return p.integrity == "verified" and p.layout == "verified"
def semantic_promotion_eligible(p): return raw_decode_eligible(p) and p.interpretation == "verified"


def compose_proof(*proofs):
    keys = ("integrity", "layout", "interpretation")
    return FieldProof(*[_INV[min(_ORDER[getattr(p, k)] for p in proofs)] for k in keys])


def _decode(raw_u32, kind):
    if kind == "uint32": return {"kind": "uint32", "value": raw_u32}
    if kind == "int32": return {"kind": "int32", "value": struct.unpack("<i", struct.pack("<I", raw_u32))[0]}
    (v,) = struct.unpack("<f", struct.pack("<I", raw_u32))
    return None if not math.isfinite(v) else {"kind": "float", "value": v}


@dataclass(frozen=True)
class Envelope:
    state: str; raw_u32: int | None; decoded: dict | None; decoded_reason: str
    proof: FieldProof; evidence_ref: str
    _token: object = field(default=None, repr=False, compare=False)
    def __post_init__(self):
        if self._token is not _TOKEN: raise TypeError("construct via make_envelope()/absent_envelope()")
    def to_dict(self):
        return {"state": self.state, "raw_u32": self.raw_u32, "decoded": self.decoded,
                "decoded_reason": self.decoded_reason, "proof": self.proof.to_dict(),
                "evidence_ref": self.evidence_ref}


def _validate(kind, evidence_ref):
    if kind not in _KINDS: raise ValueError(f"unknown kind {kind!r}")
    if not evidence_ref: raise ValueError("evidence_ref must be non-empty")


def make_envelope(raw_u32, *, kind, proof, evidence_ref) -> Envelope:
    _validate(kind, evidence_ref)
    if type(raw_u32) is not int or not (0 <= raw_u32 < 2**32):   # rejects bool + out-of-domain
        raise ValueError(f"raw_u32 {raw_u32!r} outside the 32-bit cell domain")
    if semantic_promotion_eligible(proof):
        decoded = _decode(raw_u32, kind); reason = "decoded" if decoded is not None else "non_finite"
    else:
        decoded, reason = None, "proof_withheld"
    return Envelope("present", raw_u32, decoded, reason, proof, evidence_ref, _TOKEN)


def absent_envelope(*, proof, evidence_ref, state) -> Envelope:
    _validate("uint32", evidence_ref)
    if state not in ("not_applicable", "unresolved"): raise ValueError("absent requires a non-present state")
    return Envelope(state, None, None, "not_present", proof, evidence_ref, _TOKEN)


@dataclass(frozen=True)
class JoinObservation:
    state: str; components: dict; composed_proof: FieldProof; decoded: object | None; decoded_reason: str
    _token: object = field(default=None, repr=False, compare=False)
    def __post_init__(self):
        if self._token is not _TOKEN: raise TypeError("construct via make_join()")
    def to_dict(self):
        return {"state": self.state, "components": {k: v.to_dict() for k, v in self.components.items()},
                "composed_proof": self.composed_proof.to_dict(), "decoded": self.decoded,
                "decoded_reason": self.decoded_reason}


def make_join(components: dict, *, resolution, decode) -> JoinObservation:
    """resolution ∈ {resolved, index_zero, side_row_missing}. index_zero = no FK (not_applicable);
    side_row_missing = nonzero FK with no matching side row (recoverable → unresolved). A structurally
    MALFORMED/impossible reference is caught by open_view/RecordView integrity and fails closed BEFORE
    make_join — it is never turned into a publishable observation."""
    if not components:
        raise ValueError("join requires components")
    composed = compose_proof(*(e.proof for e in components.values()))
    if resolution == "index_zero":
        return JoinObservation("not_applicable", components, composed, None, "index_zero", _TOKEN)
    if resolution == "side_row_missing":
        return JoinObservation("unresolved", components, composed, None, "side_row_missing", _TOKEN)
    if resolution != "resolved":
        raise ValueError(f"invalid join resolution {resolution!r} (fail closed)")
    if not semantic_promotion_eligible(composed):
        return JoinObservation("resolved", components, composed, None, "proof_withheld", _TOKEN)
    value = decode(components)
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and \
        (not isinstance(value, float) or math.isfinite(value))
    return JoinObservation("resolved", components, composed, value if ok else None,
                           "decoded" if ok else "non_finite", _TOKEN)


def refine_enum(value, allowed):
    """Exact-membership gate for a scalar enum (e.g. power_type ∈ {-2,0..6})."""
    return (value, True) if value in allowed else (None, False)


def refine_mask(value, allowed_bits):
    """Bitmask gate: every SET bit must be allowed; a valid combination like 20 (4|16) passes, zero
    (no school) passes, an unknown bit is withheld."""
    bad = [1 << b for b in range(32) if (value >> b) & 1 and (1 << b) not in allowed_bits]
    return (None, False) if bad else (value, True)


def make_domain_gated_envelope(raw_u32, *, kind, proof, evidence_ref, refine):
    """Build the envelope, then withhold the decoded value IN-BAND (decoded_reason='value_out_of_domain')
    when `refine(value) -> (normalized, in_domain)` reports an unknown value — so a consumer distinguishes
    'unknown symbol' from ordinary absence. Raw is retained."""
    env = make_envelope(raw_u32, kind=kind, proof=proof, evidence_ref=evidence_ref)
    if env.decoded is None or refine(env.decoded["value"])[1]:
        return env
    return Envelope("present", env.raw_u32, None, "value_out_of_domain", proof, evidence_ref, _TOKEN)


@dataclass(frozen=True)
class StringObservation:
    state: str; raw_offset: int | None; resolved: str | None; decoded_reason: str
    proof: FieldProof; evidence_ref: str
    _token: object = field(default=None, repr=False, compare=False)
    def __post_init__(self):
        if self._token is not _TOKEN: raise TypeError("construct via make_string_observation()")
    def to_dict(self):
        return {"state": self.state, "raw_offset": self.raw_offset, "resolved": self.resolved,
                "decoded_reason": self.decoded_reason, "proof": self.proof.to_dict(),
                "evidence_ref": self.evidence_ref}


def make_string_observation(raw_offset, resolved, *, proof, evidence_ref) -> StringObservation:
    """A string cell is a string-block OFFSET; the normalized value is text. Consumers match on
    `resolved` text, never on a raw u32 (strings are not comparable in the numeric envelope contract)."""
    if type(raw_offset) is not int or not (0 <= raw_offset < 2**32):
        raise ValueError("raw_offset out of domain")
    if not evidence_ref:
        raise ValueError("evidence_ref required")
    if semantic_promotion_eligible(proof):
        if not isinstance(resolved, str):
            raise ValueError("resolved must be a str when promotion-eligible")
        return StringObservation("present", raw_offset, resolved, "decoded", proof, evidence_ref, _TOKEN)
    return StringObservation("present", raw_offset, None, "proof_withheld", proof, evidence_ref, _TOKEN)
```

`_KINDS` gains no string member — strings use `StringObservation` (offset + resolved text), so the numeric envelope contract stays numeric. Enum/mask/domain tests: `refine_mask(20, {1,2,4,8,16,32,64})` → `(20, True)`; `refine_mask(128, …)` → `(None, False)`; `refine_enum(7, {-2,0,1,2,3,4,5,6})` → `(None, False)`; `make_domain_gated_envelope` with an out-of-domain value → `decoded is None and decoded_reason == "value_out_of_domain"`; `make_join(..., resolution="index_zero", ...)` → `state=="not_applicable"`, and `"side_row_missing"` → `state=="unresolved"`.

---

## Task 2: Record-bounded selective DBC reader (self-contained)

**Files:** Create `coa_client_extract/recordview.py`; Test `tests/test_recordview.py`

- [ ] **Step 1: Write the failing test** — per-record bounds (a cell in record N is unreadable from record N-1), `cells(start, width, stride)`, checked `read_string`, bad magic. **Step 2:** red. **Step 3: Implement** `open_view`/`DbcView(record/records/read_string)`/`RecordView(u32/cells)` with `(last+1)*4 <= record_size` bounds and strided reads. **Step 4:** green. **Step 5:** commit `M1.14E0 Task 2: record-bounded selective DBC reader`.

```python
# coa_client_extract/recordview.py  (complete)
from __future__ import annotations
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from .errors import DbcDriftError
_H = struct.Struct("<4sIIII"); _MAGIC = b"WDBC"; _CELL = 4

@dataclass(frozen=True)
class RecordView:
    _data: bytes; _base: int; record_size: int
    def _chk(self, cell, width=1, stride=1):
        if cell < 0 or stride < 1 or width < 1: raise DbcDriftError(f"bad cell/width/stride")
        last = cell + (width - 1) * stride
        if (last + 1) * _CELL > self.record_size: raise DbcDriftError(f"cell {last} out of record bounds")
    def u32(self, cell):
        self._chk(cell); return struct.unpack_from("<I", self._data, self._base + cell * _CELL)[0]
    def cells(self, start, width, stride=1):
        self._chk(start, width, stride)
        return [struct.unpack_from("<I", self._data, self._base + (start + k*stride)*_CELL)[0] for k in range(width)]

@dataclass(frozen=True)
class DbcView:
    _data: bytes; record_count: int; field_count: int; record_size: int; _sstart: int; _ssize: int
    def record(self, i):
        if not (0 <= i < self.record_count): raise DbcDriftError(f"record {i} out of range")
        return RecordView(self._data, _H.size + i * self.record_size, self.record_size)
    def records(self) -> Iterator[RecordView]:
        for i in range(self.record_count): yield self.record(i)
    @property
    def cell_count(self): return self.record_size // _CELL
    def require_dense(self):                              # Spell-family tables must be dense
        if self.field_count * _CELL != self.record_size:
            raise DbcDriftError(f"field_count {self.field_count}*4 != record_size {self.record_size}")
        return self
    def read_string(self, off):                          # STRICT: for a proven string field
        if off < 0 or off >= self._ssize: raise DbcDriftError(f"string offset {off} out of block")
        if off == 0: return ""
        block = self._data[self._sstart:self._sstart + self._ssize]
        end = block.find(b"\x00", off)
        if end < 0: raise DbcDriftError(f"unterminated string at offset {off}")
        return block[off:end].decode("utf-8", "replace")
    def try_string(self, off):                           # LENIENT: for discovery scanning of any cell
        try: return self.read_string(off)
        except DbcDriftError: return None

def open_view(data) -> DbcView:
    if len(data) < _H.size: raise DbcDriftError("file smaller than DBC header")
    magic, rc, fc, rs, ss = _H.unpack_from(data, 0)
    if magic != _MAGIC: raise DbcDriftError(f"bad magic {magic!r}")
    if rs <= 0 or rs % _CELL != 0: raise DbcDriftError(f"bad record_size {rs}")
    sstart = _H.size + rc * rs
    if len(data) != sstart + ss:                          # reject unadjudicated trailing / short bytes
        raise DbcDriftError(f"length {len(data)} != header-implied {sstart + ss}")
    return DbcView(data, rc, fc, rs, sstart, ss)
```

The Task 2 tests additionally cover: an out-of-range string offset **raises**, an unterminated string **raises**, trailing/short bytes **raise**, and `require_dense()` raises when `field_count*4 != record_size`. Discovery scanning (Task 3) uses `try_string`; canonical extraction of a proven string field uses strict `read_string`; Spell-family opens call `require_dense()`.

---

## Task 3: Recon hard hold — lifecycle, joined-pair discovery, proposed delta, real budgets

**Files:** Create `coa_client_extract/spell_mechanics.py`; Test `tests/test_spell_mechanics_recon.py`

**Behavior:** discover (never re-check the policy's cell): anchor columns by scanning (normalized-exact for `name`); the **joined `(index_cell, side_value_cell)` pair** for each of cast/duration/range by scanning candidate index cells (FK-validity vs the side id set, zero excluded, min support, min distinct) × candidate side value cells validated by **multiple distinct value anchors** (e.g. an instant spell→0 *and* ≥2 distinct nonzero cast times), requiring a **unique** pair; the `spell_icon_id` index cell by FK scan; the enum/bit domains (bits `1..1<<31`). Emit `status`, `blocking_findings`, `proposed_policy_delta` (discovered cells + evidence), full pins (per-DBC sha256+header+archive, policy/anchor/enum hashes, backend id, validated patch-chain/load order, extractor commit, client_build), and **real budgets** (serialized report bytes, elapsed, subprocess peak-RSS KiB→MiB). `blocked` when evidence collection fails (required table missing/unreadable per **policy**, expected-absent present, drift/malformed, dup ids, no unique pair, over-budget); else `review_required` until discoveries match a bound `verified` policy → `verified`. **Recon never writes the policy.** CLI: `blocked`→3, `review_required`→4, `verified`→0.

- [ ] Steps: failing tests (synthetic client, **fixture-specific anchor set passed explicitly**): verified path with a bound policy; `review_required` when unbound; `blocked` on wrong-cell anchor / expected-absent-present / zero-heavy decoy failing the pair scan; `proposed_policy_delta` names the discovered cells; pins include side-table sha256. → red → implement (scanning discovery incl. `discover_join_pair`, lifecycle, subprocess RSS, real report bytes) → green → commit `M1.14E0 Task 3: recon lifecycle (blocked/review_required/verified), joined-pair discovery, proposed delta, real budgets`.

> **Checkpoint after Task 5** (below) covers Tasks 3–5 together per the review.

---

## Task 4: Policy (human-authored) covering every emitted value + client binding + validated loader

**Files:** Create `coa_client_extract/data/spell_layout_v1.json`, `coa_client_extract/spell_layout.py`; Test `tests/test_spell_layout.py`

The policy is **authored by a human from recon's `proposed_policy_delta`** (recon never writes it). It carries per-value `{cell, kind, layout, interpretation, promotion, evidence}` for every matrix field (incl. `spell_id` + the side-table id/value cells), where **`kind ∈ {int32, uint32, float, string}`** (`string` ⇒ a `StringObservation`, a distinct observation type, not a numeric envelope) and **`promotion ∈ {normalized, raw_only}`** makes a field's raw-only status *explicit* rather than inferred from its facets (an intentionally raw-only field legitimately keeps `reference`/`unproven` facets). It also carries `required_tables`/`expected_absent`, `anchor_set` (+sha256), `enum_policy` (`power_types`, `school_bits`, +sha256), `bound = {client_build, source_dbc_sha256:{Spell,SpellCastTimes,SpellDuration,SpellRange,SpellIcon}}`, and an explicit top-level **`reviewed: true|false`** — the authoritative human-review flag. `regenerate` runs only when `reviewed==true` **and** `bound` matches the opened client (never inferring review from per-field facets). Anchor-proven fields ship `promotion:normalized`/`verified`; joined/FK fields ship `unproven` with `null` cells until the mandatory client recon (Task 8) fills them + `bound`, a human flips them, and sets `reviewed`. Loader validates schema/table identity, proof states, the `kind` domain, `0<=cell<field_count`, per-table cell uniqueness, evidence presence, **`enum_policy.school_bits` are distinct powers of two `< 2**32`**, and hash self-consistency; builders emit only `promotion:normalized` + `verified` columns.

- [ ] Steps: author JSON → loader tests (reject out-of-bounds/dup-cell/bad-state/wrong-table/hash-mismatch; `bound` round-trips) → red → implement validating loader → green → commit `M1.14E0 Task 4: human-authored full-value policy with client binding + validated loader`.

---

## Task 5: v2 record + projection-v2 + Node validation + per-value gate + join observations

**Files:** Modify `coa_client_extract/dbc_layouts.py`, `coa_client_extract/artifacts.py`, `coa_client_extract/cli.py`, `coa_scraper/scripts/lib/mechanics-projection.mjs`; Test `tests/test_client_extract_regression.py`, `coa_scraper/tests/mechanics-projection.test.mjs`

**Atomic v2 migration (all in this task):**
- `build_client_spell_records` builds full `coa-client-spell-v2` from `RecordView`: normalized `mechanics` (scalar/`null`); a `field_observations` block of `Envelope`/`JoinObservation` (joins for cast/duration/range); the projection writer emits `coa-client-spell-projection-v2` + its manifest.
- **Per-value gate:** `power_type` via `make_domain_gated_envelope` + `refine_enum({-2,0..6})`; `school_mask` via `refine_mask({1,2,4,8,16,32,64})`. An out-of-domain value ⇒ normalized `null`, `decoded_reason:"value_out_of_domain"`, raw retained, and an `unknown_symbol_inventory` counter in the extract manifest. Tests: `power_type==7` → null + inventory; `school_mask==20` (`4|16`) → **accepted**; an unknown school bit → withheld. String fields (`name`, `description`) emit `StringObservation` (offset + resolved).
- **Node reader** (`mechanics-projection.mjs`) validates v2 rows, **rejects a v1 `schema_version` with "regenerate with M1.14E"**, asserts **every populated numeric normalized value has an eligible matching observation** (string fields matched on `resolved` text, not raw), and **stops treating table-level `schema_match_confidence_by_dbc` as mechanical-field certification** — per-field/per-value observation proof is now authoritative.
- **Client-binding hard hold:** `regenerate()` re-hashes sources and blocks unless the policy is `verified` + `bound` matches.

- [ ] Steps: Python regression (corrected anchors; `power_type==7`→null+retained; a raw-only field→null+envelope; join observation for `cast_time_ms`; mismatched `bound`→block) + Node test (v2 accepted, v1 rejected, normalized↔observation consistency) → red → implement → run existing `tests/test_client_extract_artifacts.py`/`test_client_spell_projection.py` + the Node projection test, **enumerating each changed assertion in the commit** → green → commit `M1.14E0 Task 5: coa-client-spell-v2 + projection-v2 + Node v2 validation/v1-rejection + per-value gate + join observations + client-binding hold`.

> **CHECKPOINT (Tasks 3–5):** stop for human review of proof/value gates, recon lifecycle + joined-pair discovery, and the v2 schema/observation/data-path before publisher work.

---

## Task 6: Collision-safe publisher, hash-binding manifest, retention

**Files:** Create `coa_client_extract/publish.py`; Modify `coa_client_extract/manifest.py`; Test `tests/test_publish_generation.py`

**Contract:** `uuid4().hex` id; `gen-<id>/` `exist_ok=False`; staging rejects abs/`..`/dup/reserved names + empty schema; JSONL streamed to temp + hashed + counted; non-JSONL child `records=1` (defined). `build_manifest_v2` = **superset of all ten v1 fields** (incl. a deterministic `outputs` **index view** derived from `children`, for *migrated* resolvers — **not** v1 back-compat) **plus** `generation_id`, `published_at` (ns), `predecessor_generation_id` (the pointer's prior target at publish), `children` (exact child inventory), the `unknown_symbol_inventory`, and **binding**: source-DBC `{sha256,header,archive}`, `policy_sha256`, `anchor_set_sha256`, `enum_policy_sha256`. Pointer `{schema_version:"coa-client-extract-pointer-v1", generation_id, manifest_path, manifest_sha256}` published last. `resolve_active_generation` validates pointer schema, `gen-<id>/` containment, manifest hash, and each child's path (no traversal)/sha256/bytes/records/schema/uniqueness. **Retention is a separate best-effort maintenance op — `publish` never prunes:** a `prune-generations` command follows the `predecessor_generation_id` chain (ordered by `published_at`) to keep the current (pointer target) + previous generation and removes older `gen-*` only past `grace_seconds` **under a quiescent window / advisory lock** (documented best-effort otherwise).

- [ ] **Step 1: failing tests** — positive publish/resolve; **negative resolver**: generation mismatch, manifest-hash tamper, child path traversal, missing child, byte-length mismatch, record-count mismatch, duplicate child, malformed child schema; `exist_ok=False` collision raises; content collision-safety (A's bytes intact after B); `outputs` present + equals a `children`-derived index map; `unknown_symbol_inventory` + `published_at` + `predecessor_generation_id` + binding hashes present; `prune-generations` keeps current+previous via the predecessor chain (best-effort, no-op without a quiescent window). → red → implement → green → commit `M1.14E0 Task 6: uuid publisher, binding manifest-v2 (outputs compat + source/policy/anchor/enum hashes), validated resolver, grace-period retention`.

---

## Task 7: Migrate the family + Node resolver + canonical-requires-pointer + completeness check

**Files:** Modify `coa_client_extract/cli.py`, `coa_client_extract/artifacts.py`, `coa_scraper/scripts/build-mechanics-artifacts.mjs`, `coa_scraper/scripts/lib/mechanics-projection.mjs`, `coa_scraper/scripts/lib/generation.mjs` (new); Tests: `tests/test_client_extract_cli.py`, `tests/test_spell_mechanics_cli.py`, `tests/test_e0_end_to_end.py`, `coa_scraper/tests/*`

- **Producer publishes / consumer requires.** `regenerate` (producer) **publishes** the generation pointer as an output and never takes a pointer as input. `build-mechanics-artifacts.mjs` (consumer) **requires `--client-extract-pointer`** for a canonical run; the fixed-path `--projection`/`--projection-manifest` mode runs only under the **existing `--allow-fallback-mechanics`** degraded path (reused — no new overlapping `--allow-degraded` flag). Passing both the pointer and legacy flags is an error.
- **Node `resolveGeneration`** (`generation.mjs`) performs **equivalent** validation to the Python resolver (pointer schema, containment, manifest hash, per-child path/hash/bytes/count/schema) and returns resolved paths — Node never receives an unchecked filename.
- **Migration inventory (all direct-path consumers):** `cli.regenerate`, `artifacts.write_client_spell_projection`, `tests/test_client_extract_cli.py`, `tests/test_client_extract_acceptance.py`, the enum-coverage/projection tests, the mechanics-build default paths, `mechanics-projection.mjs`, the regeneration + schema docs, the M1.14C forward-policy-gate references.
- **Migration-completeness check** (`tests/test_e0_migration_complete.py`): grep the tree for lingering fixed `coa_client_spell_coa.jsonl` / `coa_client_spell_projection.manifest.json` paths outside an explicit compatibility whitelist; fail if any unlisted match remains.
- **End-to-end** (`tests/test_e0_end_to_end.py`): publish a generation → `node generation.mjs` resolves+validates it → `build-mechanics-artifacts.mjs --client-extract-pointer …` produces `coa_mechanics.jsonl`.

- [ ] Steps: add the `mechanics-recon` subcommand (exit 3/4/0 per lifecycle; 2 without StormLib) + tests → migrate `regenerate` to `GenerationWriter` (**publishes** the pointer) → make the Node build **require** the pointer + validate it → Node resolver + build migration → completeness + e2e tests → run pytest + Node suite → commit `M1.14E0 Task 7: transactional regenerate publishes pointer; pointer-required validating Node build; migration + completeness + e2e`.

> **CHECKPOINT (Tasks 6–7):** human review of publisher/manifest binding, Node validation parity, and migration completeness before docs/commit.

---

## Task 8: Docs, ignore rules, dual-language + mandatory client recon (fills the policy)

**Files:** `.gitignore`, `docs/DECISIONS.md`, `docs/data/client-spell-schema.md` (→ v2), `docs/data/spell-mechanics-recon-schema.md`, `docs/data/client-extract-generation-schema.md`, `tests/test_e0_client_recon.py`

- [ ] Ignore `gen-*/`, `coa_client_extract_manifest.json`, `coa_spell_mechanics_recon.json` under `reports/client_extract/` **and** `coa_scraper/dist/`.
- [ ] DECISIONS.md — only E0-implemented decisions: proven+hash-bound+**client-bound** policy; recon reports a proposed delta and never self-approves/writes the policy; `regenerate` runs only against a `verified` bound policy and **publishes** the pointer (the consumer requires it); the **unknown-symbol amendment** (unseen enum/bit ⇒ raw retained + normalized withheld + inventoried, artifact stays valid; masks accept valid bit combinations); transactional UUID generation with binding + separate-maintenance retention. No E1 stub.
- [ ] Schema docs — **update `docs/data/client-spell-schema.md` to `coa-client-spell-v2`** (normalized `mechanics` + `field_observations` block, `StringObservation`, join observations, per-value `value_out_of_domain`) and the projection to `coa-client-spell-projection-v2`; new recon schema (`status` lifecycle, `blocking_findings`, `layout_proof`, `index_fk`, `join_pairs`, `enum_domains`, `proposed_policy_delta` + the manual-adjudication procedure, `source_pins`, `budget`) and generation schema (pointer, manifest-v2 superset + `outputs` compat + binding hashes + `unknown_symbol_inventory`, resolver validation, maintenance retention).
- [ ] `tests/test_e0_client_recon.py` (`@pytest.mark.client`): two **stable** assertions against the real client — (a) with an intentionally-**unbound fixture policy** (cells/`bound` nulled) → `status=="review_required"` and `proposed_policy_delta` names the discovered cells; (b) with the **committed reviewed policy** → `status=="verified"`, anchors `ok`, join pairs unique, `SpellEffect` absent. The one-time manual adjudication (review `proposed_policy_delta` → author cells + `bound` → flip to `verified`) is the **documented procedure in the recon schema doc**, not a test that flips state.
- [ ] `pytest -q`, `pytest -m client -q`, Node suite green → commit `M1.14E0 Task 8: recon+generation schema docs, ignore rules, decisions; Python+Node+client suites green`.

---

## Self-Review

**Spec coverage:** per-field + per-value decode gates (T1,T5) with `power_type==7`/unknown-bit tests; join observation for side-table joins (T1,T5); record-bounded reader restored in full (T2); recon lifecycle blocked/review_required/verified + joined-pair discovery + proposed delta + real subprocess budgets, recon never writes the policy (T3); human-authored policy with client binding covering every DBC-derived value incl. side-table id/value cells (T4); atomic v2 record + projection-v2 + Node v2 validation + v1 rejection + normalized↔observation consistency + client-binding hold (T5); publisher with `outputs` compat + source/policy/anchor/enum binding + validated resolver + grace-period retention (T6); canonical-requires-pointer + Node validation parity + migration inventory + completeness + e2e (T7); ignore/docs/dual-language/mandatory-client, policy filled from the delta (T8). Checkpoints after T5 and T7.

**Placeholder scan:** none — Task 2 is self-contained; recon-pending policy cells are honest `unproven` filled from the mandatory client run; the matrix classifies every DBC-derived value.

**Type consistency:** `make_envelope`(present-only)/`absent_envelope`/`make_domain_gated_envelope`/`make_string_observation`/`make_join(resolution=…)`/`compose_proof`/`refine_enum`/`refine_mask` (T1) used in T5; `RecordView` (T2) in T3/T5; recon lifecycle status + `proposed_policy_delta` + policy `bound` (T3–T4) drive T5/T8; `GenerationWriter`/`resolve_active_generation`/`build_manifest_v2`/`prune_generations` (T6) and the Node `resolveGeneration` parity (T7) are consistent.
