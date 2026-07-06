# M1.11G Backend Verification and Trust Heuristic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backend-only trust/audit heuristic for theorycraft outputs without exposing trust scores in the user-facing guide until Phase 2 logs exist.

**Architecture:** Implement trust scoring as a separate sidecar pipeline over report data and internal metadata. Keep `MetaReport`, `GuideBuildCard`, and rendered HTML free of backend trust fields by default. Add a curated watchlist schema for severe known mismatch risks, but treat entries as low-confidence internal QA signals until empirical logs are available.

**Tech Stack:** Python dataclasses, JSON data files, existing `coa_meta` reporting/calibration modules, pytest.

---

## File Structure

- Create `coa_meta/backend_trust.py`: trust dataclasses, component scoring, watchlist matching, sidecar report builder.
- Create `coa_meta/data/live_sanity_watchlist.json`: low-confidence internal watchlist entries.
- Create `docs/data/backend-trust-schema.md`: sidecar artifact schema.
- Create `tests/test_backend_trust.py`: unit tests for scoring, watchlist matching, sidecar serialization, and no guide leakage.
- Modify `coa_meta/cli.py`: add `--write-backend-trust` and optional `--backend-trust-out`.
- Modify `coa_meta/reporting.py`: write sidecar only through `write_report_outputs` or a helper, not through build serialization.
- Modify `tests/test_cli.py`: verify CLI flags.
- Modify `tests/test_guide_builder.py` and `tests/test_guide_rendering.py`: verify trust data is not user-facing.
- Update `docs/ROADMAP.md` and `docs/README.md`.

## Task 1: Backend Trust Schema and Dataclasses

**Files:**

- Create: `coa_meta/backend_trust.py`
- Create: `tests/test_backend_trust.py`
- Create: `docs/data/backend-trust-schema.md`

- [ ] **Step 1: Write failing schema tests**

Create `tests/test_backend_trust.py`:

```python
from coa_meta.backend_trust import (
    BACKEND_TRUST_SCHEMA_VERSION,
    TrustComponent,
    TrustResult,
    trust_label_from_score,
)


def test_trust_result_serializes_component_scores_without_user_copy():
    result = TrustResult(
        schema_version=BACKEND_TRUST_SCHEMA_VERSION,
        subject_id="Testclass:Damage:build-1",
        trust_label="medium",
        score=0.66,
        components=(
            TrustComponent(component_id="mechanics_coverage", score=0.7, weight=0.25, notes=("Some inferred mechanics.",)),
        ),
        watchlist_matches=tuple(),
        warnings=("mechanics_inferred",),
    )

    payload = result.to_dict()

    assert payload["schema_version"] == "coa-backend-trust-v1"
    assert payload["trust_label"] == "medium"
    assert payload["components"][0]["component_id"] == "mechanics_coverage"
    assert "user_facing_text" not in payload


def test_trust_label_thresholds_are_coarse():
    assert trust_label_from_score(0.86) == "high"
    assert trust_label_from_score(0.60) == "medium"
    assert trust_label_from_score(0.30) == "low"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py -q
```

Expected: fails with missing module.

- [ ] **Step 3: Implement dataclasses**

Create `coa_meta/backend_trust.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BACKEND_TRUST_SCHEMA_VERSION = "coa-backend-trust-v1"


@dataclass(frozen=True)
class TrustComponent:
    component_id: str
    score: float
    weight: float
    notes: tuple[str, ...] = tuple()

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "score": round(self.score, 4),
            "weight": round(self.weight, 4),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class TrustResult:
    schema_version: str
    subject_id: str
    trust_label: str
    score: float
    components: tuple[TrustComponent, ...]
    watchlist_matches: tuple[str, ...] = tuple()
    warnings: tuple[str, ...] = tuple()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject_id": self.subject_id,
            "trust_label": self.trust_label,
            "score": round(self.score, 4),
            "components": [component.to_dict() for component in self.components],
            "watchlist_matches": list(self.watchlist_matches),
            "warnings": list(self.warnings),
        }


def trust_label_from_score(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"
```

- [ ] **Step 4: Document schema**

Create `docs/data/backend-trust-schema.md`:

```markdown
# Backend Trust Schema

Schema version: `coa-backend-trust-v1`

Backend trust reports are internal Phase 1 QA artifacts. They are not rendered in guide HTML and must not be presented as player-facing empirical confidence until Phase 2 logs exist.

## Trust Result

- `schema_version`
- `subject_id`
- `trust_label`
- `score`
- `components`
- `watchlist_matches`
- `warnings`

## Component

- `component_id`
- `score`
- `weight`
- `notes`

Trust scores are coarse internal diagnostics. They are not observed DPS, HPS, mitigation, or player performance.
```

- [ ] **Step 5: Verify and commit**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py -q
```

Expected: tests pass.

Commit:

```bash
git add coa_meta/backend_trust.py tests/test_backend_trust.py docs/data/backend-trust-schema.md
git commit -m "Add backend trust schema"
```

## Task 2: Live Sanity Watchlist

**Files:**

- Create: `coa_meta/data/live_sanity_watchlist.json`
- Modify: `coa_meta/backend_trust.py`
- Modify: `tests/test_backend_trust.py`

- [ ] **Step 1: Write failing watchlist tests**

Add:

```python
from coa_meta.backend_trust import load_live_sanity_watchlist, match_watchlist


def test_live_sanity_watchlist_entries_are_backend_only():
    entries = load_live_sanity_watchlist()

    assert entries
    assert all(entry.not_user_facing for entry in entries)
    assert all(entry.confidence in {"low", "medium", "high"} for entry in entries)
    assert any(entry.class_name == "Venomancer" for entry in entries)


def test_watchlist_matches_class_spec_and_role():
    entries = load_live_sanity_watchlist()

    matches = match_watchlist(entries, class_name="Venomancer", source_spec_name="Stalking", guide_role="melee_dps")

    assert matches
    assert matches[0].not_user_facing is True
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py::test_live_sanity_watchlist_entries_are_backend_only tests/test_backend_trust.py::test_watchlist_matches_class_spec_and_role -q
```

Expected: fails with missing watchlist APIs.

- [ ] **Step 3: Add watchlist data**

Create `coa_meta/data/live_sanity_watchlist.json`:

```json
[
  {
    "schema_version": "coa-live-sanity-watchlist-v1",
    "watchlist_id": "venomancer-stalking-theory-overrank-risk",
    "class_name": "Venomancer",
    "source_spec_name": "Stalking",
    "guide_role": "melee_dps",
    "concern": "Current theory output may over-rank Venomancer relative to observed live-server expectations.",
    "direction": "theory_may_be_high",
    "severity": "medium",
    "evidence_type": "owner_observation",
    "evidence": ["Project owner reported Runemaster, Primalist DPS, and Knight of Xoroth DPS outperform current Venomancer-heavy report ordering."],
    "confidence": "low",
    "source": "project_owner",
    "status": "watch",
    "not_user_facing": true,
    "expires_after": "p2_log_calibration"
  },
  {
    "schema_version": "coa-live-sanity-watchlist-v1",
    "watchlist_id": "runemaster-dps-theory-underrank-risk",
    "class_name": "Runemaster",
    "source_spec_name": "*",
    "guide_role": "*_dps",
    "concern": "Current theory output may under-rank Runemaster DPS specs until coefficients and logs are calibrated.",
    "direction": "theory_may_be_low",
    "severity": "medium",
    "evidence_type": "owner_observation",
    "evidence": ["Project owner reported Runemaster DPS outperforming current theory ranking on live servers."],
    "confidence": "low",
    "source": "project_owner",
    "status": "watch",
    "not_user_facing": true,
    "expires_after": "p2_log_calibration"
  },
  {
    "schema_version": "coa-live-sanity-watchlist-v1",
    "watchlist_id": "primalist-dps-theory-underrank-risk",
    "class_name": "Primalist",
    "source_spec_name": "*",
    "guide_role": "*_dps",
    "concern": "Current theory output may under-rank Primalist DPS specs until coefficients, resource behavior, and logs are calibrated.",
    "direction": "theory_may_be_low",
    "severity": "medium",
    "evidence_type": "owner_observation",
    "evidence": ["Project owner reported Primalist DPS outperforming current theory ranking on live servers."],
    "confidence": "low",
    "source": "project_owner",
    "status": "watch",
    "not_user_facing": true,
    "expires_after": "p2_log_calibration"
  },
  {
    "schema_version": "coa-live-sanity-watchlist-v1",
    "watchlist_id": "knight-of-xoroth-dps-theory-underrank-risk",
    "class_name": "Knight of Xoroth",
    "source_spec_name": "*",
    "guide_role": "*_dps",
    "concern": "Current theory output may under-rank Knight of Xoroth DPS specs until weapon, pet, and cooldown interactions are calibrated.",
    "direction": "theory_may_be_low",
    "severity": "medium",
    "evidence_type": "owner_observation",
    "evidence": ["Project owner reported Knight of Xoroth DPS outperforming current theory ranking on live servers."],
    "confidence": "low",
    "source": "project_owner",
    "status": "watch",
    "not_user_facing": true,
    "expires_after": "p2_log_calibration"
  },
  {
    "schema_version": "coa-live-sanity-watchlist-v1",
    "watchlist_id": "felsworn-dps-theory-relative-band-risk",
    "class_name": "Felsworn",
    "source_spec_name": "*",
    "guide_role": "*_dps",
    "concern": "Current theory output may separate Felsworn too far from Venomancer even though owner observation suggests similar live DPS bands.",
    "direction": "relative_band_uncertain",
    "severity": "low",
    "evidence_type": "owner_observation",
    "evidence": ["Project owner reported Felsworn DPS pulling similar DPS to Venomancer on live servers."],
    "confidence": "low",
    "source": "project_owner",
    "status": "watch",
    "not_user_facing": true,
    "expires_after": "p2_log_calibration"
  },
  {
    "schema_version": "coa-live-sanity-watchlist-v1",
    "watchlist_id": "cultist-dps-theory-relative-band-risk",
    "class_name": "Cultist",
    "source_spec_name": "*",
    "guide_role": "*_dps",
    "concern": "Current theory output may separate Cultist too far from Venomancer even though owner observation suggests similar live DPS bands.",
    "direction": "relative_band_uncertain",
    "severity": "low",
    "evidence_type": "owner_observation",
    "evidence": ["Project owner reported Cultist DPS pulling similar DPS to Venomancer on live servers."],
    "confidence": "low",
    "source": "project_owner",
    "status": "watch",
    "not_user_facing": true,
    "expires_after": "p2_log_calibration"
  },
  {
    "schema_version": "coa-live-sanity-watchlist-v1",
    "watchlist_id": "barbarian-dps-theory-relative-band-risk",
    "class_name": "Barbarian",
    "source_spec_name": "*",
    "guide_role": "*_dps",
    "concern": "Current theory output may separate Barbarian too far from Venomancer even though owner observation suggests similar live DPS bands.",
    "direction": "relative_band_uncertain",
    "severity": "low",
    "evidence_type": "owner_observation",
    "evidence": ["Project owner reported Barbarian DPS pulling similar DPS to Venomancer on live servers."],
    "confidence": "low",
    "source": "project_owner",
    "status": "watch",
    "not_user_facing": true,
    "expires_after": "p2_log_calibration"
  }
]
```

- [ ] **Step 4: Implement loader and matcher**

Add to `coa_meta/backend_trust.py`:

```python
import json
from pathlib import Path

WATCHLIST_PATH = Path(__file__).parent / "data" / "live_sanity_watchlist.json"


@dataclass(frozen=True)
class LiveSanityWatchlistEntry:
    watchlist_id: str
    class_name: str
    source_spec_name: str
    guide_role: str
    concern: str
    direction: str
    severity: str
    evidence_type: str
    evidence: tuple[str, ...]
    confidence: str
    source: str
    status: str
    not_user_facing: bool
    expires_after: str


def load_live_sanity_watchlist(path: Path | str = WATCHLIST_PATH) -> tuple[LiveSanityWatchlistEntry, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(
        LiveSanityWatchlistEntry(
            watchlist_id=str(item["watchlist_id"]),
            class_name=str(item["class_name"]),
            source_spec_name=str(item["source_spec_name"]),
            guide_role=str(item["guide_role"]),
            concern=str(item["concern"]),
            direction=str(item["direction"]),
            severity=str(item["severity"]),
            evidence_type=str(item["evidence_type"]),
            evidence=tuple(str(value) for value in item.get("evidence", [])),
            confidence=str(item["confidence"]),
            source=str(item["source"]),
            status=str(item["status"]),
            not_user_facing=bool(item["not_user_facing"]),
            expires_after=str(item["expires_after"]),
        )
        for item in raw
    )


def match_watchlist(
    entries: tuple[LiveSanityWatchlistEntry, ...],
    *,
    class_name: str,
    source_spec_name: str,
    guide_role: str,
) -> tuple[LiveSanityWatchlistEntry, ...]:
    return tuple(
        entry
        for entry in entries
        if _matches(entry.class_name, class_name)
        and _matches(entry.source_spec_name, source_spec_name)
        and _matches_role(entry.guide_role, guide_role)
    )


def _matches(pattern: str, value: str) -> bool:
    return pattern == "*" or pattern.casefold() == value.casefold()


def _matches_role(pattern: str, value: str) -> bool:
    if pattern == "*":
        return True
    if pattern == "*_dps":
        return value.endswith("_dps")
    return pattern == value
```

- [ ] **Step 5: Verify and commit**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py -q
```

Expected: tests pass.

Commit:

```bash
git add coa_meta/backend_trust.py coa_meta/data/live_sanity_watchlist.json tests/test_backend_trust.py
git commit -m "Add backend live sanity watchlist"
```

## Task 3: Compute Trust Components for Report Builds

**Files:**

- Modify: `coa_meta/backend_trust.py`
- Modify: `tests/test_backend_trust.py`

- [ ] **Step 1: Write failing component tests**

Add:

```python
from coa_meta.backend_trust import trust_for_build_payload


def test_trust_for_build_payload_combines_role_mechanics_rotation_and_watchlist():
    build = {
        "rank": 1,
        "warnings": ["missing_mechanics:2001"],
        "rotation_guide": {
            "reliability": "medium",
            "simulation_summary": {
                "unsupported_condition_count": 0,
                "unsupported_effect_count": 1,
                "action_count": 20,
            },
            "warnings": [],
        },
        "provenance": {
            "role_provenance": {"source": "curated", "confidence": "high"}
        },
    }

    trust = trust_for_build_payload(
        class_name="Venomancer",
        source_spec_name="Stalking",
        guide_role="melee_dps",
        build=build,
        watchlist=load_live_sanity_watchlist(),
    )

    assert trust.trust_label in {"low", "medium"}
    assert any(component.component_id == "mechanics_coverage" for component in trust.components)
    assert trust.watchlist_matches
```

- [ ] **Step 2: Run failing test**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py::test_trust_for_build_payload_combines_role_mechanics_rotation_and_watchlist -q
```

Expected: fails because `trust_for_build_payload` is missing.

- [ ] **Step 3: Implement component scoring**

Add:

```python
def trust_for_build_payload(
    *,
    class_name: str,
    source_spec_name: str,
    guide_role: str,
    build: dict[str, Any],
    watchlist: tuple[LiveSanityWatchlistEntry, ...],
) -> TrustResult:
    matches = match_watchlist(watchlist, class_name=class_name, source_spec_name=source_spec_name, guide_role=guide_role)
    role = _role_component(build)
    mechanics = _mechanics_component(build)
    rotation = _rotation_component(build)
    watch = _watchlist_component(matches)
    components = (role, mechanics, rotation, watch)
    score = sum(component.score * component.weight for component in components) / sum(component.weight for component in components)
    warnings = tuple(str(warning) for warning in build.get("warnings", []))
    return TrustResult(
        schema_version=BACKEND_TRUST_SCHEMA_VERSION,
        subject_id=f"{class_name}:{source_spec_name}:rank-{build.get('rank', 'unknown')}",
        trust_label=trust_label_from_score(score),
        score=score,
        components=components,
        watchlist_matches=tuple(entry.watchlist_id for entry in matches),
        warnings=warnings,
    )
```

Implement helper components:

```python
def _role_component(build: dict[str, Any]) -> TrustComponent:
    role_source = ((build.get("provenance") or {}).get("role_provenance") or {}).get("source", "")
    confidence = ((build.get("provenance") or {}).get("role_provenance") or {}).get("confidence", "")
    score = 1.0 if role_source in {"authoritative", "curated"} and confidence == "high" else 0.65
    return TrustComponent("role_certainty", score=score, weight=0.20, notes=(f"source:{role_source or 'unknown'}",))


def _mechanics_component(build: dict[str, Any]) -> TrustComponent:
    warnings = " ".join(str(warning) for warning in build.get("warnings", []))
    score = 0.45 if "missing_mechanics" in warnings else 0.85
    return TrustComponent("mechanics_coverage", score=score, weight=0.30, notes=tuple(build.get("warnings", [])))


def _rotation_component(build: dict[str, Any]) -> TrustComponent:
    guide = build.get("rotation_guide") or {}
    summary = guide.get("simulation_summary") or {}
    reliability = guide.get("reliability", "")
    penalty = 0.0
    penalty += 0.20 if summary.get("unsupported_condition_count", 0) else 0.0
    penalty += 0.10 if summary.get("unsupported_effect_count", 0) else 0.0
    base = {"high": 0.9, "medium": 0.7, "low": 0.45}.get(reliability, 0.4)
    return TrustComponent("rotation_coverage", score=max(0.0, base - penalty), weight=0.30, notes=tuple(guide.get("warnings", [])))


def _watchlist_component(matches: tuple[LiveSanityWatchlistEntry, ...]) -> TrustComponent:
    if not matches:
        return TrustComponent("live_sanity_watchlist", score=1.0, weight=0.20, notes=tuple())
    severe = any(entry.severity == "high" for entry in matches)
    return TrustComponent(
        "live_sanity_watchlist",
        score=0.35 if severe else 0.55,
        weight=0.20,
        notes=tuple(entry.watchlist_id for entry in matches),
    )
```

- [ ] **Step 4: Verify**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/backend_trust.py tests/test_backend_trust.py
git commit -m "Score backend trust for report builds"
```

## Task 4: Sidecar Report Builder

**Files:**

- Modify: `coa_meta/backend_trust.py`
- Modify: `tests/test_backend_trust.py`

- [ ] **Step 1: Write failing sidecar tests**

Add:

```python
from coa_meta.backend_trust import build_backend_trust_report


def test_backend_trust_report_serializes_separate_sidecar():
    report = {
        "schema_version": "coa-meta-report-v1",
        "spec_results": [
            {
                "class_name": "Venomancer",
                "source_spec_name": "Stalking",
                "spec_name": "Stalking",
                "role": "melee_dps",
                "top_builds": [{"rank": 1, "warnings": [], "provenance": {}, "rotation_guide": {}}],
            }
        ],
    }

    trust_report = build_backend_trust_report(report, watchlist=load_live_sanity_watchlist())
    payload = trust_report.to_dict()

    assert payload["schema_version"] == "coa-backend-trust-v1"
    assert payload["spec_results"][0]["build_trust"][0]["subject_id"].startswith("Venomancer:Stalking")
```

- [ ] **Step 2: Run failing test**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py::test_backend_trust_report_serializes_separate_sidecar -q
```

Expected: fails because sidecar report builder is missing.

- [ ] **Step 3: Implement sidecar report**

Add dataclasses:

```python
from datetime import datetime, timezone


@dataclass(frozen=True)
class BackendTrustSpecResult:
    class_name: str
    source_spec_name: str
    role: str
    build_trust: tuple[TrustResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "source_spec_name": self.source_spec_name,
            "role": self.role,
            "build_trust": [item.to_dict() for item in self.build_trust],
        }


@dataclass(frozen=True)
class BackendTrustReport:
    schema_version: str
    generated_at: str
    spec_results: tuple[BackendTrustSpecResult, ...]
    warnings: tuple[str, ...] = tuple()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "spec_results": [item.to_dict() for item in self.spec_results],
            "warnings": list(self.warnings),
        }


def build_backend_trust_report(
    report_payload: dict[str, Any],
    *,
    watchlist: tuple[LiveSanityWatchlistEntry, ...],
) -> BackendTrustReport:
    specs: list[BackendTrustSpecResult] = []
    for spec in report_payload.get("spec_results", []):
        class_name = str(spec.get("class_name", ""))
        source_spec_name = str(spec.get("source_spec_name") or spec.get("spec_name") or "")
        role = str(spec.get("role", ""))
        builds = tuple(
            trust_for_build_payload(
                class_name=class_name,
                source_spec_name=source_spec_name,
                guide_role=role,
                build=dict(build),
                watchlist=watchlist,
            )
            for build in spec.get("top_builds", [])
        )
        specs.append(BackendTrustSpecResult(class_name, source_spec_name, role, builds))
    return BackendTrustReport(
        schema_version=BACKEND_TRUST_SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        spec_results=tuple(specs),
    )
```

- [ ] **Step 4: Verify and commit**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py -q
```

Expected: tests pass.

Commit:

```bash
git add coa_meta/backend_trust.py tests/test_backend_trust.py
git commit -m "Build backend trust sidecar reports"
```

## Task 5: CLI Sidecar Flag Without Guide Leakage

**Files:**

- Modify: `coa_meta/cli.py`
- Modify: `coa_meta/reporting.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_guide_builder.py`
- Modify: `tests/test_guide_rendering.py`

- [ ] **Step 1: Write failing CLI test**

Add to `tests/test_cli.py`:

```python
def test_meta_cli_accepts_backend_trust_sidecar_flag(monkeypatch, tmp_path):
    captured = {}

    def fake_write_outputs(report, out_dir, formats, **kwargs):
        captured.update(kwargs)
        return (Path(out_dir) / "meta-report.json", Path(out_dir) / "backend-trust-report.json")

    monkeypatch.setattr(cli, "MetaReportRunner", DummyRunner)
    monkeypatch.setattr(cli, "write_report_outputs", fake_write_outputs)

    exit_code = cli.main([
        "meta",
        "--entries", "coa_scraper/dist/coa_entries.jsonl",
        "--write-backend-trust",
        "--format", "json",
        "--out", str(tmp_path),
    ])

    assert exit_code == 0
    assert captured["write_backend_trust"] is True
```

- [ ] **Step 2: Write no-leakage tests**

Add to `tests/test_guide_rendering.py`:

```python
def test_spec_html_does_not_render_backend_trust_text():
    html = render_spec_html(_site(), next(item for item in _site().specs if item.spec_name == "Damage"))

    assert "backend trust" not in html.lower()
    assert "live sanity" not in html.lower()
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
PYTHONPATH=. pytest tests/test_cli.py::test_meta_cli_accepts_backend_trust_sidecar_flag tests/test_guide_rendering.py::test_spec_html_does_not_render_backend_trust_text -q
```

Expected: CLI test fails because the flag is missing. No-leakage test may already pass and should stay green.

- [ ] **Step 4: Add CLI flags**

In `coa_meta/cli.py`, add:

```python
meta.add_argument("--write-backend-trust", action="store_true")
meta.add_argument("--backend-trust-out", type=Path, default=None)
```

Pass through to `write_report_outputs`:

```python
write_backend_trust=args.write_backend_trust,
backend_trust_out=args.backend_trust_out,
```

- [ ] **Step 5: Write sidecar in report output helper**

Modify `write_report_outputs` in `coa_meta/reporting.py` to accept:

```python
write_backend_trust: bool = False
backend_trust_out: Path | None = None
```

When enabled:

```python
from .backend_trust import build_backend_trust_report, load_live_sanity_watchlist

trust_report = build_backend_trust_report(report.to_dict(), watchlist=load_live_sanity_watchlist())
trust_path = backend_trust_out or out_dir / "backend-trust-report.json"
trust_path.write_text(json.dumps(trust_report.to_dict(), indent=2), encoding="utf-8")
outputs.append(trust_path)
```

Do not add trust fields to `MetaReport.to_dict()`, `GuideBuildCard`, or `render_spec_html`.

- [ ] **Step 6: Verify**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py tests/test_cli.py tests/test_guide_builder.py tests/test_guide_rendering.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git add coa_meta/cli.py coa_meta/reporting.py tests/test_cli.py tests/test_guide_builder.py tests/test_guide_rendering.py
git commit -m "Write backend trust sidecar on request"
```

## Task 6: Docs and Roadmap

**Files:**

- Modify: `docs/data/backend-trust-schema.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/README.md`
- Modify: `docs/NEXT_STEPS_DATA_COLLECTION.md`

- [ ] **Step 1: Document backend-only guarantee**

In `docs/data/backend-trust-schema.md`, add:

```markdown
## User-Facing Boundary

Phase 1 guide HTML must not render backend trust scores, watchlist concerns, or live sanity labels. The sidecar exists for maintainers and future Phase 2 calibration only.
```

- [ ] **Step 2: Update roadmap**

Mark M1.11G as implemented once all tasks pass. Keep Phase 2 AscensionLogs/addon ingestion as planned.

- [ ] **Step 3: Keep AscensionLogsCompanion probe deferred**

In `docs/NEXT_STEPS_DATA_COLLECTION.md`, confirm that the Phase 2 probe still requires a CoA sample log with `ALC_CI_v1` before an adapter is built.

- [ ] **Step 4: Verify docs and tests**

Run:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py tests/test_cli.py tests/test_guide_rendering.py -q
git diff --check
```

Expected: tests pass and no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add docs/data/backend-trust-schema.md docs/ROADMAP.md docs/README.md docs/NEXT_STEPS_DATA_COLLECTION.md
git commit -m "Document backend trust heuristic boundary"
```

## Final M1.11G Verification

Run focused tests:

```bash
PYTHONPATH=. pytest tests/test_backend_trust.py tests/test_calibration_hooks.py tests/test_meta_report_runner.py tests/test_cli.py tests/test_guide_builder.py tests/test_guide_rendering.py -q
```

Run full suite:

```bash
PYTHONPATH=. pytest
```

Run a fixture smoke with sidecar enabled:

```bash
PYTHONPATH=. python -m coa_meta meta \
  --entries tests/fixtures/meta_report_fixture.jsonl \
  --classes tests/fixtures/meta_classes.json \
  --out /tmp/coa-backend-trust-smoke \
  --format json \
  --write-backend-trust
```

Expected:

- `/tmp/coa-backend-trust-smoke/meta-report.json` exists.
- `/tmp/coa-backend-trust-smoke/backend-trust-report.json` exists.
- no spec HTML is generated unless requested.
- meta report JSON does not contain `backend_trust`.

## Self-Review Checklist

- Backend trust is sidecar-only.
- Watchlist entries default to low confidence and `not_user_facing=true`.
- Guide HTML does not render backend trust or live sanity text.
- No empirical claims are made before logs exist.
- AscensionLogsCompanion remains a Phase 2 probe, not a dependency.
- No GPL/AGPL code is copied.
