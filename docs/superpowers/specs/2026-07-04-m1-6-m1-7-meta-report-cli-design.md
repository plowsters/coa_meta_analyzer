# M1.6/M1.7 Meta Report Runner, CLI, and Packaging Design

## Scope

This spec covers Phase 1 Milestone 1.6 and Milestone 1.7 from [ROADMAP.md](../../ROADMAP.md):

- M1.6: Meta Report Runner
- M1.7: Packaging, CLI, and Tests

M1.6 and M1.7 are designed together because the report runner needs a stable command surface, fixture strategy, and release path. They should be implemented separately so the report model can land before packaging and CLI hardening.

## Current Context

M1.1 through M1.5 established the durable Phase 1 pipeline:

- `coa_scraper/dist/coa_entries.jsonl` contains normalized `coa-normalized-v1` talent and ability records.
- `coa_scraper/dist/coa_classes.json` contains class and tab metadata.
- `coa_meta/repository.py` loads normalized nodes into `TalentRepository`.
- `coa_meta/builds.py` validates legal build states.
- `coa_meta/search.py` performs deterministic legal build search.
- `coa_meta/profiles.py` and `coa_meta/scoring.py` load data-driven scoring profiles and emit projected theory scores.
- `coa_meta/apl_profiles.py` and `coa_meta/apl.py` load APL profiles and generate structured rotation scaffolds.

The current data includes 21 classes and 91 class/spec-like tab records. Some class metadata tabs are not valid reportable specs:

- `Class` contains combat-relevant class-wide nodes and should be available to every spec for that class.
- `None` currently appears only as metadata for a few classes and has no normalized node rows.
- `Chronomancer -> Blessings` appears in class metadata but has no Chronomancer nodes.
- `Sun Cleric -> Blessings` has normalized nodes and should be treated as a real Sun Cleric spec tree.

Current benchmarking on this workspace showed all-class top-3 search in about 34 seconds with low beam settings and about 57 seconds with stricter budget filtering. A 91 spec-row report is expected to be several minutes serial and materially faster when parallelized by independent scope.

## Goals

M1.6 goals:

- Add a report orchestration layer that runs class/spec build search, theory scoring, explanation, and APL generation.
- Generate the default Phase 1 report for every reportable class/spec pair.
- Use one default `baseline_single_target` encounter profile.
- Rank the top 3 builds per class/spec by projected DPS index and confidence.
- Emit canonical JSON plus Markdown and static HTML derived from the same model.
- Include selected nodes, score breakdown, generated APL, assumptions, provenance, warnings, and confidence labels.
- Keep projected DPS index distinct from observed DPS in every output.
- Include optional HTML image/icon enhancement from captured scraper assets when available.

M1.7 goals:

- Provide the release command path, preferably `python -m coa_meta meta ...`.
- Keep CLI commands thin and delegate business logic to package modules.
- Add fixture-backed unit tests for loading, legality, scoring, APL generation, report output, and CLI routing.
- Add a smoke test for the Phase 1 report path against the current captured `dist` artifacts.
- Make browser capture tests separate from package/report tests.

## Non-Goals

- No raw DPS, simulated DPS, observed DPS, or empirical ranking.
- No combat log or SavedVariables ingestion.
- No event-driven simulator.
- No web application.
- No dependency on browser automation for report tests.
- No requirement that HTML assets exist for report generation to succeed.
- No complete fix for trainer/source/level data gaps. That is a follow-up M1.8 data milestone.

## Selected Approach

Use a scoped report runner with an explicit eligibility policy.

The runner expands requested class/spec/level/encounter combinations into `BuildScope` records. For each scope, the eligibility policy resolves the legal node pool, the existing build searcher generates candidates, the scorer ranks them, the APL generator emits rotation scaffolds, and report writers serialize the canonical report.

This keeps every class and spec on the same algorithmic path. Class-specific behavior should come from normalized data, scoring profiles, and APL profiles rather than Python branches.

## Architecture

Recommended module layout:

```text
coa_meta/
  cli.py
  __main__.py
  reporting.py
  report_assets.py
tests/
  fixtures/
  test_report_eligibility.py
  test_meta_report_runner.py
  test_report_writers.py
  test_cli.py
  test_phase1_smoke.py
docs/
  data/
    meta-report-schema.md
```

`coa_meta/reporting.py` owns report dataclasses, scope expansion, eligibility, report orchestration, JSON serialization, Markdown rendering, and HTML rendering.

`coa_meta/report_assets.py` owns optional local asset resolution for HTML. It must be best-effort and must not be required for JSON or Markdown generation.

`coa_meta/cli.py` owns argument parsing and command dispatch only. It should call package APIs and should not contain scoring, legality, APL, or rendering rules.

`coa_meta/__main__.py` exposes `python -m coa_meta`.

## Core Data Model

```text
BuildScope
- class_name
- spec_id
- spec_name
- level
- encounter_profile_id
- search_profile_id
- scoring_profile_id
- apl_profile_id
- top

EligibilityPolicy
- reportable_specs(repository, classes_metadata)
- eligible_nodes(repository, scope)
- warnings_for_scope(repository, classes_metadata, scope)

MetaReportRunner
- expand scopes from run config
- run search/scoring/APL for every scope
- collect warnings and provenance
- return MetaReport

ReportWriters
- JSON writer
- Markdown writer
- static HTML writer
```

The canonical report schema should be versioned as `coa-meta-report-v1`.

```text
MetaReport
- schema_version
- generated_at
- input_artifacts
- run_config
- assumptions
- warnings
- class_summaries[]
- spec_results[]

SpecResult
- class_name
- spec_id
- spec_name
- level
- encounter_profile_id
- search_profile_id
- scoring_profile_id
- apl_profile_id
- top_builds[]
- warnings

BuildResult
- rank
- projected_dps_index
- confidence_label
- selected_nodes
- score_breakdown
- generated_apl
- explanation
- provenance
- warnings
```

## Scope Expansion

Default M1.6 run:

- all reportable class/spec pairs
- level `60`
- encounter profile `baseline_single_target`
- top `3`
- built-in default search profile
- built-in scoring/APL profile resolution with generic fallback

The CLI/config should allow subsets without changing the model:

- selected class or classes
- selected spec or specs
- selected level
- selected encounter profile ids
- selected search profile
- selected top count
- selected output formats and output directory

If multiple encounter profiles are requested, the runner emits separate `SpecResult` rows per class/spec/encounter profile. M1.6 should not run the full encounter matrix by default.

## Reportable Specs and Shared Pools

Reportable specs are class tabs that have normalized node rows and are not classified as shared pools.

Shared pools:

- `Class` is included in each spec's eligible node pool for the same class.
- `Class` is not emitted as a standalone ranked spec.
- `None` is excluded in M1.6 because it has no normalized node rows.
- Metadata-only tabs are excluded and reported as warnings.

The current `Chronomancer -> Blessings` metadata row should produce a warning because it has no Chronomancer nodes. The current `Sun Cleric -> Blessings` normalized node set should be treated as a Sun Cleric reportable spec.

## Level Filtering Skeleton

The report runner should support level as a first-class scope field even though current class/trainer level data is incomplete.

```text
eligible_nodes(class, spec, level) =
  spec_tree_nodes(class, spec, level)
  + shared_class_nodes(class, level)

spec_tree_nodes =
  nodes where node.class_name == scope.class_name
  and node.tab_id == scope.spec_id
  and node.required_level <= scope.level

shared_class_nodes =
  nodes where node.class_name == scope.class_name
  and node.tab_name == "Class"
  and node.required_level <= scope.level
```

Phase 1 interpretation:

- `required_level=0` means available or unknown.
- Level 60 reports include every level-eligible node under current artifacts.
- Lower-level reports filter known `required_level` values and warn that shared class/trainer source data is incomplete.
- The report must not imply exact lower-level trainer availability until scraper data improves.

The legal build engine should operate over an injected eligible-node set so class/spec filtering happens before search and validation. Existing budget, rank, prerequisite, tab gate, and level checks still apply.

## Search and Ranking

M1.6 should start with conservative deterministic search settings that finish reliably on current hardware. The selected default is top 3 builds per reportable spec for one encounter profile.

Search configuration should be serializable in `run_config`:

- `top`
- `beam_width`
- `branch_width`
- `require_budget_fraction`
- optional worker count

Ranking rules:

- Within a `SpecResult`, rank builds by projected DPS index, then confidence, then deterministic build key.
- Class summaries are derived from spec results and must be labeled as summaries.
- Reports must not merge spec ranking and build ranking into one ambiguous table.
- Empty result scopes should produce warning rows instead of failing the entire report.

Parallelism should be scope-level only. Each class/spec/encounter scope is independent, making multiprocessing straightforward in a later implementation pass. Output ordering must remain deterministic even if execution is parallel.

## HTML Assets

HTML can use captured assets when available, but assets are optional.

`AssetResolver` should support:

- class or tree background images from captured `coa_scraper/data/raw` files
- node icon identifiers from normalized node `icon` values
- fallback to text-only display when no local asset can be resolved

JSON should preserve icon identifiers and any resolved asset metadata, but JSON correctness must not depend on local image files. Markdown should remain text-first.

The HTML report should be static and local. It should not require network access, a dev server, or browser automation.

## Error Handling and Warnings

Report generation should fail only for unrecoverable input or configuration errors:

- missing required artifact file
- unsupported schema version
- malformed scoring or APL profile
- selected class/spec/encounter does not exist
- output path cannot be written

Recoverable issues should become report warnings:

- metadata tab has no normalized nodes
- lower-level run depends on incomplete class/trainer level data
- generic scoring or APL profile fallback was used
- no valid builds found for a scope
- generated APL has low-confidence inferred conditions
- asset lookup failed

Warnings should appear in JSON and near the top of Markdown/HTML.

## CLI Design

M1.7 should expose a thin CLI:

```bash
python -m coa_meta meta \
  --entries coa_scraper/dist/coa_entries.jsonl \
  --classes coa_scraper/dist/coa_classes.json \
  --out reports/meta \
  --format json --format md --format html
```

Useful options:

```text
meta
  --entries PATH
  --classes PATH
  --level INT
  --class NAME
  --spec NAME_OR_ID
  --encounter-profile ID
  --top INT
  --beam-width INT
  --branch-width INT
  --require-budget-fraction FLOAT
  --workers INT
  --format json|md|html
  --out PATH
  --asset-root PATH
```

The CLI should provide clear nonzero exits for unrecoverable failures. Recoverable report warnings should not make the command fail.

## Packaging

M1.7 should add minimal packaging metadata for the existing package layout. A full `src/` migration is not required for Phase 1 unless it becomes necessary for packaging correctness.

Expected deliverables:

- `pyproject.toml`
- package data inclusion for built-in scoring and APL profiles
- `python -m coa_meta` entry path
- optional console script if packaging remains simple
- documented test command

The library API should remain usable without invoking the CLI.

## Testing Strategy

M1.6 tests:

- reportable spec discovery excludes `Class`, `None`, and metadata-only tabs.
- `Class` nodes are included in each spec eligible pool.
- level filtering excludes nodes above the selected level when `required_level` is known.
- lower-level scopes emit incomplete trainer/source warnings.
- empty scope results become report warnings.
- JSON report schema includes run config, provenance, warnings, spec results, top builds, scoring, and APL data.
- Markdown and HTML render from the same report model.
- HTML asset lookup failure does not fail report generation.

M1.7 tests:

- CLI argument parsing dispatches to report runner with the expected config.
- package data profiles load from installed/imported package context.
- small fixtures cover schema loading, legality, scoring, APL, and report writers.
- smoke test runs the Phase 1 meta path against current captured artifacts.
- browser capture tests remain outside normal package tests.

Preferred verification command remains:

```bash
python -m pytest -q
```

## Documentation Updates

M1.6 should add:

- `docs/data/meta-report-schema.md`
- command examples for JSON, Markdown, and HTML output
- explanation that projected DPS index is not observed DPS
- explanation of reportable specs, shared `Class` pool, and current lower-level data limitations

M1.7 should update:

- README or project docs with package installation/use
- roadmap status if the milestone exits are met
- test command and fixture notes

## M1.8 Follow-Up: Scraper Source and Level Fidelity

M1.8 should improve data collection so lower-level calculations and source-aware eligibility can become real rather than approximate.

Goals for M1.8:

- distinguish spec tree, class-wide pool, trainer, misc/system, and bad metadata sources
- capture real level availability for trainer and class-wide abilities
- investigate `db.ascension.gg` and any direct API/source payloads
- preserve source confidence and provenance fields
- add validation reports for metadata-only tabs and cross-class tab contamination
- allow M1.6 reports to rerun with exact level-aware eligibility when the data supports it

M1.8 should not be required for the default M1.6 level 60 report.

## Implementation Boundary

M1.6 implementation should stop when the library can generate JSON, Markdown, and static HTML reports from current artifacts through package APIs.

M1.7 implementation should start after M1.6 is verified and should focus on packaging, CLI entry points, fixture hardening, and release-path tests.

The implementation plan should be written as separate M1.6 and M1.7 sections so each milestone can be developed, tested, and committed independently.
