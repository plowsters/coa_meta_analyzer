# M1.11G Backend Verification and Trust Heuristic Design

## Purpose

M1.11G adds a backend-only verification and trust layer for theorycraft outputs. It should help maintainers detect fragile recommendations, known live-meta mismatches, incomplete mechanics, unstable rotation candidates, and stale source artifacts.

This milestone must not add a new player-facing "trust" or "confidence" section to the guide site. Until Phase 2 has real logs, trust output belongs in internal sidecar artifacts, tests, and developer-facing diagnostics only.

## Current State

The repo already has:

- `coa_meta/calibration.py`: additive calibration record scaffolding.
- `docs/data/calibration-schema.md`: log/addon calibration schema.
- role provenance from M1.11B.
- mechanics coverage from M1.11D/E action catalogs.
- rotation-guide reliability from M1.11E.
- report disclaimers that output is theorycraft based on CoA Builder and `db.ascension.gg`.
- Phase 2 roadmap items for AscensionLogs/addon ingestion and Vercel upload simulation.

The missing piece is a backend trust heuristic that combines these signals without pretending they are empirical truth.

## User Constraint

M1.11G is a backend verification/trust heuristic. It should not be included in the user-facing report until Phase 2 when logs are available.

Interpretation:

- Do not render trust scores in guide HTML.
- Do not add trust badges to spec cards.
- Do not present "calibrated" claims in user report text.
- Do allow a maintainer sidecar JSON/Markdown artifact for CI, local QA, and future P2 calibration.
- Do allow internal selection/debug code to read the trust result later, but M1.11G should not materially alter published recommendations by default.

## Research Notes

SimulationCraft is an event-driven WoW simulator. Its README describes why proc-heavy combat makes closed-form calculators inaccurate and why event simulation is useful for stat weights and raid/dungeon scenarios. It is GPL-3.0 licensed, so this project should continue using clean-room architecture references only.

WoWAnalyzer is a log-analysis tool that turns Warcraft Logs data into metrics and suggestions. Its repository is AGPL-3.0 licensed, so it is useful as a boundary model, not as reusable implementation code.

AscensionLogsCompanion is MIT licensed and directly relevant as a future Phase 2 capture reference. Its README says it captures gear, talents, CharacterAdvancement builds, and mystic enchants, serializes/compresses combatant-info data, and embeds chunked sentinel payloads into `WoWCombatLog.txt` for `ascensionlogs.gg`. The same README states that the data scope includes inspectable gear/talents and client-side Ascension state, and not chat/account/UI state. A CoA-specific sample is still required before relying on it for CoA class/spec/essence state.

Sources:

- SimulationCraft: <https://github.com/simulationcraft/simc>
- WoWAnalyzer: <https://github.com/WoWAnalyzer/WoWAnalyzer>
- AscensionLogsCompanion: <https://github.com/Ascension-Addons/AscensionLogsCompanion>

## Scope

M1.11G includes:

- `coa-backend-trust-v1` schema.
- Trust dimensions for source completeness, role certainty, mechanics coverage, rotation simulation coverage, candidate stability, source freshness, and known live-meta watchlist entries.
- A curated live sanity watchlist for severe known theory/live mismatch concerns.
- Internal sidecar artifact writing, disabled by default unless explicitly requested.
- Tests proving trust output is not serialized into guide-facing models or rendered HTML.
- Phase 2 compatibility notes for AscensionLogs/addon evidence.

M1.11G excludes:

- Importing real logs.
- Decoding AscensionLogsCompanion payloads.
- Adjusting public build rankings from anecdotal rankings.
- Showing trust scores in guide pages.
- Claiming any spec is empirically calibrated.

## Trust Model

Trust is not the same as player-facing confidence.

Trust answers: "How much should a maintainer trust this recommendation internally?"

Primary dimensions:

- `source_completeness`: normalized builder records, class metadata, AscensionDB enrichment, icon/tooltips, layout artifacts.
- `role_certainty`: authoritative role map vs inference/configuration.
- `mechanics_coverage`: percent of selected active actions with mechanics records and no missing effect data.
- `rotation_coverage`: simulated candidate count, unsupported conditions/effects, action count, sparse primary rules.
- `candidate_stability`: spread between top rotation/build candidates, reliability labels, duplicate-cluster collapse behavior.
- `live_sanity`: curated watchlist entries for known severe mismatch risks.
- `freshness`: source artifact timestamps/manifest hashes when available.
- `empirical_evidence`: sample size and variance, always zero/none in M1.11G unless a test fixture is supplied.

Trust labels:

- `high`: source and mechanics coverage are strong, role is authoritative/curated high confidence, rotation candidates are stable, and no live sanity watchlist flags apply.
- `medium`: plausible but missing some mechanics or candidate stability signals.
- `low`: missing major mechanics/role/source data, unstable simulated rotation output, or known severe live sanity mismatch risk.
- `blocked`: backend cannot evaluate the result because required inputs are absent or malformed.

M1.11G should emit numeric component scores internally, but avoid presenting a single false-precision decimal as a user-facing claim.

## Live Sanity Watchlist

Create `coa_meta/data/live_sanity_watchlist.json`.

This file is not a ranking table and not proof. It is a provenance-tracked internal watchlist for severe theory/live mismatch concerns. Initial entries should cover the user-reported concerns:

- Runemaster DPS generally outperforming current report expectations.
- Primalist DPS generally outperforming current report expectations.
- Knight of Xoroth DPS generally outperforming current report expectations.
- Felsworn, Cultist, and Barbarian DPS being closer to Venomancer than theory output suggests.
- Venomancer being over-ranked by current theory output.

Fields:

- `schema_version`
- `watchlist_id`
- `class_name`
- `source_spec_name`
- `guide_role`
- `concern`
- `direction`
- `severity`
- `evidence_type`
- `evidence`
- `confidence`
- `source`
- `status`
- `not_user_facing`
- `expires_after`

Allowed `evidence_type` values:

- `owner_observation`
- `curated_note`
- `sample_log`
- `aggregate_log`
- `disabled`

M1.11G default entries should use `owner_observation` or `curated_note`, `confidence=low`, and `not_user_facing=true`. P2 can promote entries only when logs exist.

## Backend Artifact

Add an optional sidecar artifact:

```text
reports/meta/backend-trust-report.json
```

This artifact should not be linked from `index.html` or spec pages.

Schema outline:

- `schema_version`: `coa-backend-trust-v1`
- `generated_at`
- `source_report`
- `summary`
- `spec_results`
- `watchlist_matches`
- `warnings`

Each spec/build trust row:

- class/spec/build identity
- trust label
- component scores
- blocking/missing inputs
- watchlist matches
- internal notes

## CLI and API Boundary

Preferred CLI behavior:

- Default `python -m coa_meta meta` does not write backend trust.
- Add `--write-backend-trust` to write the sidecar artifact.
- Add `--backend-trust-out` only if a custom sidecar path is needed.

Do not add `backend_trust` to `BuildReport.to_dict()` or `GuideBuildCard.to_dict()` in M1.11G. If internal code needs it later, pass it as a separate object.

## Phase 2 Log Compatibility

AscensionLogsCompanion is promising but unproven for CoA. The Phase 2 probe should:

1. Collect one CoA `WoWCombatLog.txt` with AscensionLogsCompanion enabled.
2. Search for `ALC_CI_v1`.
3. Decode one payload if present.
4. Verify whether CoA class/spec/ability essence/talent essence/ranks/spell IDs are present.
5. Decide whether to implement an `AscensionLogsCompanionAdapter` or continue with the project-owned `CoADataLogger`.

M1.11G should only reserve interfaces:

- `EmpiricalEvidenceSummary`
- `TrustEvidenceSource`
- `sample_size`
- `variance`
- `calibrated_metrics`

These fields remain empty in normal Phase 1 output.

## Acceptance Criteria

- Backend trust can be computed for a meta report object without changing guide-facing report JSON.
- Optional sidecar artifact is written only when requested.
- Guide HTML does not contain trust scores or watchlist concern text.
- Watchlist entries are provenance-tracked and low-confidence by default.
- Severe known mismatch concerns can lower backend trust without claiming empirical truth.
- Existing calibration scaffolding remains additive and works without logs.
- The design leaves a clear Phase 2 path for AscensionLogs/addon evidence.

## Risks

- Trust scores can become another misleading metric. Mitigation: keep backend-only in P1 and component-based.
- Watchlist entries can ossify anecdote as truth. Mitigation: low confidence, expiry, provenance, and no user-facing display.
- Sidecar artifact may be mistaken for public guide data. Mitigation: do not link it in HTML and name it `backend-trust`.
- Log compatibility may fail for CoA. Mitigation: probe before adapter implementation.
