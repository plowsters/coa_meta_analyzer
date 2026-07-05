# M1.10A/B Guide IA and Asset Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first static guide-site slice: player-facing guide index/spec pages plus icon, tooltip, and AscensionDB spell-link integration.

**Architecture:** Keep `coa-meta-report-v1` JSON canonical. Build a derived guide model from `MetaReport`, normalized entries, optional DB tooltip rows, and optional local assets, then render static GitHub Pages-friendly HTML/CSS/JS. Move bulky guide HTML out of `coa_meta.reporting` while preserving existing wrapper functions and `meta-report.html` compatibility.

**Tech Stack:** Python 3.14 stdlib, dataclasses, JSON/JSONL artifacts, existing `coa_meta` package, pytest, static HTML/CSS/JavaScript.

---

## File Structure

Create:

- `coa_meta/guide_models.py`: immutable guide dataclasses and `to_dict()` helpers.
- `coa_meta/guide_tooltips.py`: AscensionDB spell URL helper, DB tooltip JSONL loader, tooltip sanitizer/fallback builder.
- `coa_meta/guide_assets.py`: guide asset catalog, icon resolver, placeholder asset records.
- `coa_meta/guide_builder.py`: converts `MetaReport` plus normalized entries/tooltips/assets into `GuideSite`.
- `coa_meta/guide_rendering.py`: renders index/spec HTML and static CSS/JS strings.
- `coa_meta/guide_writer.py`: writes `index.html`, `meta-report.html`, spec pages, CSS/JS, manifests, and tooltip catalog.
- `tests/test_guide_tooltips.py`
- `tests/test_guide_assets.py`
- `tests/test_guide_builder.py`
- `tests/test_guide_rendering.py`
- `tests/fixtures/guide_db_tooltips.jsonl`

Modify:

- `coa_meta/reporting.py`: delegate HTML rendering/writing to guide modules; keep public functions.
- `coa_meta/cli.py`: add optional `--db-tooltips` argument for richer guide tooltips.
- `tests/test_report_writers.py`: update expected HTML output structure and compatibility alias checks.
- `docs/README.md`: document the richer HTML guide output command after implementation.

Do not modify:

- Build legality, scoring, APL generation, simulation, role inference, scraper enrichment behavior, or normalized schema generation.

---

## Task 1: Tooltip Catalog and AscensionDB Links

**Files:**

- Create: `coa_meta/guide_tooltips.py`
- Create: `tests/test_guide_tooltips.py`
- Create: `tests/fixtures/guide_db_tooltips.jsonl`

- [ ] **Step 1: Add the DB tooltip fixture**

Create `tests/fixtures/guide_db_tooltips.jsonl`:

```jsonl
{"kind":"spell","id":2001,"status":"matched","name":"Damage Talent","icon":"spell_nature_poison","tooltip_html":"<div><b>Damage Talent</b><br />Deals bonus Nature damage.</div>","tooltip_text":"Damage Talent Deals bonus Nature damage.","required_level":10,"linked_spell_ids":[],"linked_item_ids":[],"entry_id":201,"builder_name":"Damage Talent","name_match":true,"provenance":{"url":"https://db.ascension.gg/?spell=2001&power","fetched_at":"2026-07-05T00:00:00Z"}}
```

- [ ] **Step 2: Write failing tooltip tests**

Create `tests/test_guide_tooltips.py`:

```python
from __future__ import annotations

from pathlib import Path

from coa_meta.guide_tooltips import (
    ascension_spell_url,
    build_node_tooltip,
    load_db_tooltip_rows,
    sanitize_tooltip_html,
)
from coa_meta.repository import TalentRepository


FIXTURES = Path(__file__).parent / "fixtures"


def test_ascension_spell_url_uses_public_spell_page():
    assert ascension_spell_url(2001) == "https://db.ascension.gg/?spell=2001"


def test_load_db_tooltip_rows_indexes_matched_spells():
    rows = load_db_tooltip_rows(FIXTURES / "guide_db_tooltips.jsonl")

    assert rows[2001]["name"] == "Damage Talent"
    assert rows[2001]["status"] == "matched"


def test_build_node_tooltip_prefers_db_tooltip_html():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    node = repo.node_by_id(201)
    rows = load_db_tooltip_rows(FIXTURES / "guide_db_tooltips.jsonl")

    tooltip = build_node_tooltip(node, rows)

    assert tooltip.tooltip_id == "spell:2001"
    assert tooltip.db_url == "https://db.ascension.gg/?spell=2001"
    assert "Deals bonus Nature damage." in tooltip.text
    assert tooltip.source == "ascension_db"


def test_build_node_tooltip_falls_back_to_normalized_text():
    repo = TalentRepository.from_entries(FIXTURES / "meta_report_fixture.jsonl")
    node = repo.node_by_id(202)

    tooltip = build_node_tooltip(node, {})

    assert tooltip.tooltip_id == "spell:2002"
    assert tooltip.source == "normalized"
    assert "Requires investment in Damage." in tooltip.text


def test_sanitize_tooltip_html_removes_script_and_event_attributes():
    html = sanitize_tooltip_html('<span onclick="bad()">Safe</span><script>bad()</script>')

    assert "Safe" in html
    assert "onclick" not in html
    assert "script" not in html
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_guide_tooltips.py -q
```

Expected: fail because `coa_meta.guide_tooltips` does not exist.

- [ ] **Step 4: Implement tooltip module**

Create `coa_meta/guide_tooltips.py`:

```python
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .domain import TalentNode
from .guide_models import GuideTooltip

DB_HOST = "https://db.ascension.gg"
_ALLOWED_TAGS = {"br", "span", "strong", "em", "small", "p", "div", "b", "i"}


def ascension_spell_url(spell_id: int | None) -> str | None:
    if spell_id is None:
        return None
    return f"{DB_HOST}/?spell={int(spell_id)}"


def load_db_tooltip_rows(path: Path | str | None) -> dict[int, dict[str, Any]]:
    if path is None:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    rows: dict[int, dict[str, Any]] = {}
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "spell" and row.get("status") == "matched":
            spell_id = int(row["id"])
            rows[spell_id] = row
    return rows


def build_node_tooltip(node: TalentNode, db_rows: dict[int, dict[str, Any]]) -> GuideTooltip:
    db_row = db_rows.get(node.spell_id or -1)
    if db_row:
        text = str(db_row.get("tooltip_text") or node.description_text or node.name)
        tooltip_html = sanitize_tooltip_html(str(db_row.get("tooltip_html") or ""))
        source = "ascension_db"
        confidence = "high" if db_row.get("name_match") else "medium"
        warnings = () if db_row.get("name_match") else ("db_name_mismatch",)
    else:
        text = node.description_text or node.name
        tooltip_html = html.escape(text)
        source = "normalized"
        confidence = "medium" if node.description_text else "low"
        warnings = ()

    header = f"<strong>{html.escape(node.name)}</strong>"
    body = tooltip_html if tooltip_html else html.escape(text)
    return GuideTooltip(
        tooltip_id=f"spell:{node.spell_id}" if node.spell_id is not None else f"entry:{node.entry_id}",
        entry_id=node.entry_id,
        spell_id=node.spell_id,
        name=node.name,
        html=f"{header}<div>{body}</div>",
        text=text,
        db_url=ascension_spell_url(node.spell_id),
        source=source,
        source_confidence=confidence,
        warnings=warnings,
    )


def sanitize_tooltip_html(value: str) -> str:
    text = re.sub(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", "", value, flags=re.I | re.S)
    text = re.sub(r"\s+on[a-zA-Z]+\s*=\s*(['\"]).*?\1", "", text)
    text = re.sub(r"\s+on[a-zA-Z]+\s*=\s*[^\s>]+", "", text)

    def replace_tag(match: re.Match[str]) -> str:
        slash, tag_name, attrs = match.group(1), match.group(2).lower(), match.group(3) or ""
        if tag_name not in _ALLOWED_TAGS:
            return html.escape(match.group(0))
        if slash:
            return f"</{tag_name}>"
        if tag_name == "span":
            class_match = re.search(r'class\s*=\s*([\"\'])(.*?)\1', attrs, flags=re.I)
            if class_match:
                safe_class = html.escape(class_match.group(2), quote=True)
                return f'<span class="{safe_class}">'
        return f"<{tag_name}>"

    return re.sub(r"<\s*(/?)\s*([a-zA-Z0-9]+)([^>]*)>", replace_tag, text)
```

- [ ] **Step 5: Run tooltip tests**

Run:

```bash
python -m pytest tests/test_guide_tooltips.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add coa_meta/guide_tooltips.py tests/test_guide_tooltips.py tests/fixtures/guide_db_tooltips.jsonl
git commit -m "feat: add guide tooltip catalog"
```

---

## Task 2: Guide Dataclasses

**Files:**

- Create: `coa_meta/guide_models.py`
- Create: `tests/test_guide_builder.py`

- [ ] **Step 1: Write failing guide model tests**

Create `tests/test_guide_builder.py` with the first model-level expectations:

```python
from __future__ import annotations

from pathlib import Path

from coa_meta.guide_builder import build_guide_site
from coa_meta.reporting import MetaReportRunner, MetaRunConfig


FIXTURES = Path(__file__).parent / "fixtures"


def _report():
    return MetaReportRunner(
        MetaRunConfig(
            entries_path=FIXTURES / "meta_report_fixture.jsonl",
            classes_path=FIXTURES / "meta_classes.json",
            class_names=("Testclass",),
            top=1,
            beam_width=2,
            branch_width=2,
            require_budget_fraction=0.0,
        )
    ).run()


def test_build_guide_site_creates_index_and_spec_routes():
    site = build_guide_site(
        _report(),
        entries_path=FIXTURES / "meta_report_fixture.jsonl",
        db_tooltips_path=FIXTURES / "guide_db_tooltips.jsonl",
    )

    assert site.index_path == "index.html"
    assert site.legacy_index_path == "meta-report.html"
    assert [spec.slug for spec in site.specs] == ["testclass-damage", "testclass-support"]
    assert site.specs[0].href == "specs/testclass-damage.html"


def test_guide_site_has_metric_definitions_and_player_facing_sections():
    site = build_guide_site(_report(), entries_path=FIXTURES / "meta_report_fixture.jsonl")

    assert "projected_dps_index" in site.metric_definitions
    assert "confidence" in site.metric_definitions
    assert "Overview" in site.specs[0].sections
    assert "Abilities and Talents" in site.specs[0].sections


def test_guide_nodes_include_links_tooltips_and_icons():
    site = build_guide_site(
        _report(),
        entries_path=FIXTURES / "meta_report_fixture.jsonl",
        db_tooltips_path=FIXTURES / "guide_db_tooltips.jsonl",
    )
    damage = site.specs[0]
    node = next(item for item in damage.nodes if item.entry_id == 201)

    assert node.db_url == "https://db.ascension.gg/?spell=2001"
    assert node.tooltip_id == "spell:2001"
    assert node.asset.asset_id.startswith("icon:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_guide_builder.py -q
```

Expected: fail because `coa_meta.guide_builder` and `coa_meta.guide_models` do not exist.

- [ ] **Step 3: Implement guide dataclasses**

Create `coa_meta/guide_models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GuideMetricDefinition:
    metric_id: str
    label: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class GuideAsset:
    asset_id: str
    kind: str
    label: str
    href: str | None
    source: str
    missing: bool = False
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class GuideTooltip:
    tooltip_id: str
    entry_id: int
    spell_id: int | None
    name: str
    html: str
    text: str
    db_url: str | None
    source: str
    source_confidence: str
    warnings: tuple[str, ...] = tuple()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "coa-guide-tooltip-v1",
            "tooltip_id": self.tooltip_id,
            "entry_id": self.entry_id,
            "spell_id": self.spell_id,
            "name": self.name,
            "html": self.html,
            "text": self.text,
            "db_url": self.db_url,
            "source": self.source,
            "source_confidence": self.source_confidence,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class GuideNode:
    entry_id: int
    spell_id: int | None
    name: str
    class_name: str
    tab_name: str
    essence_kind: str
    required_level: int
    ae_cost: int
    te_cost: int
    tags: tuple[str, ...]
    active: bool
    db_url: str | None
    tooltip_id: str
    asset: GuideAsset

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["tags"] = list(self.tags)
        data["asset"] = self.asset.to_dict()
        return data


@dataclass(frozen=True)
class GuideBuildCard:
    rank: int
    label: str
    confidence_label: str
    projected_dps_index: float
    node_ids: tuple[int, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "label": self.label,
            "confidence_label": self.confidence_label,
            "projected_dps_index": self.projected_dps_index,
            "node_ids": list(self.node_ids),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class GuideSpec:
    slug: str
    href: str
    class_name: str
    spec_name: str
    role: str
    confidence_label: str
    warning_count: int
    summary: str
    sections: tuple[str, ...]
    builds: tuple[GuideBuildCard, ...]
    nodes: tuple[GuideNode, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "href": self.href,
            "class_name": self.class_name,
            "spec_name": self.spec_name,
            "role": self.role,
            "confidence_label": self.confidence_label,
            "warning_count": self.warning_count,
            "summary": self.summary,
            "sections": list(self.sections),
            "builds": [build.to_dict() for build in self.builds],
            "nodes": [node.to_dict() for node in self.nodes],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class GuideSite:
    schema_version: str
    generated_at: str
    index_path: str
    legacy_index_path: str
    specs: tuple[GuideSpec, ...]
    metric_definitions: dict[str, GuideMetricDefinition]
    tooltips: dict[str, GuideTooltip]
    assets: dict[str, GuideAsset]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "index_path": self.index_path,
            "legacy_index_path": self.legacy_index_path,
            "specs": [spec.to_dict() for spec in self.specs],
            "metric_definitions": {
                key: value.to_dict() for key, value in self.metric_definitions.items()
            },
            "tooltips": {key: value.to_dict() for key, value in self.tooltips.items()},
            "assets": {key: value.to_dict() for key, value in self.assets.items()},
            "warnings": list(self.warnings),
        }
```

- [ ] **Step 4: Run model import tests**

Run:

```bash
python -m pytest tests/test_guide_builder.py -q
```

Expected: still fail because `build_guide_site` is not implemented. This confirms the model module imports cleanly.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/guide_models.py tests/test_guide_builder.py
git commit -m "feat: add guide site models"
```

---

## Task 3: Asset Catalog

**Files:**

- Create: `coa_meta/guide_assets.py`
- Create: `tests/test_guide_assets.py`

- [ ] **Step 1: Write failing asset tests**

Create `tests/test_guide_assets.py`:

```python
from __future__ import annotations

from pathlib import Path

from coa_meta.guide_assets import GuideAssetCatalog


def test_icon_placeholder_is_deterministic_without_asset_root():
    catalog = GuideAssetCatalog()

    asset = catalog.icon_for("Interface\\Icons\\Shared_Strike", "Shared Strike")

    assert asset.asset_id == "icon:sharedstrike"
    assert asset.href is None
    assert asset.missing is True
    assert asset.source == "placeholder"


def test_icon_resolves_matching_local_file(tmp_path: Path):
    icon = tmp_path / "Shared_Strike.png"
    icon.write_bytes(b"fake")
    catalog = GuideAssetCatalog(asset_root=tmp_path)

    asset = catalog.icon_for("Interface\\Icons\\Shared_Strike", "Shared Strike")

    assert asset.asset_id == "icon:sharedstrike"
    assert asset.href == "Shared_Strike.png"
    assert asset.missing is False
    assert asset.source == "asset_root"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_guide_assets.py -q
```

Expected: fail because `coa_meta.guide_assets` does not exist.

- [ ] **Step 3: Implement asset catalog**

Create `coa_meta/guide_assets.py`:

```python
from __future__ import annotations

from pathlib import Path

from .guide_models import GuideAsset


class GuideAssetCatalog:
    def __init__(self, asset_root: Path | str | None = None):
        self.asset_root = Path(asset_root) if asset_root else None
        self._assets: dict[str, GuideAsset] = {}

    @property
    def assets(self) -> dict[str, GuideAsset]:
        return dict(self._assets)

    def icon_for(self, icon: str | None, label: str) -> GuideAsset:
        slug = _asset_slug((icon or label).split("\\")[-1])
        asset_id = f"icon:{slug or _asset_slug(label) or 'missing'}"
        if asset_id in self._assets:
            return self._assets[asset_id]

        path = self._find_local_icon(slug)
        if path is None:
            asset = GuideAsset(
                asset_id=asset_id,
                kind="icon",
                label=label,
                href=None,
                source="placeholder",
                missing=True,
            )
        else:
            href = path.name
            asset = GuideAsset(
                asset_id=asset_id,
                kind="icon",
                label=label,
                href=href,
                source="asset_root",
                missing=False,
                source_path=str(path),
            )
        self._assets[asset_id] = asset
        return asset

    def _find_local_icon(self, slug: str) -> Path | None:
        if not slug or self.asset_root is None or not self.asset_root.exists():
            return None
        for path in self.asset_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            if slug in _asset_slug(path.stem):
                return path
        return None


def _asset_slug(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())
```

- [ ] **Step 4: Run asset tests**

Run:

```bash
python -m pytest tests/test_guide_assets.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/guide_assets.py tests/test_guide_assets.py
git commit -m "feat: add guide asset catalog"
```

---

## Task 4: Guide Site Builder

**Files:**

- Create: `coa_meta/guide_builder.py`
- Modify: `tests/test_guide_builder.py`

- [ ] **Step 1: Run existing builder tests to verify failure**

Run:

```bash
python -m pytest tests/test_guide_builder.py -q
```

Expected: fail because `coa_meta.guide_builder` does not exist.

- [ ] **Step 2: Implement guide builder**

Create `coa_meta/guide_builder.py`:

```python
from __future__ import annotations

from pathlib import Path

from .guide_assets import GuideAssetCatalog
from .guide_models import (
    GuideBuildCard,
    GuideMetricDefinition,
    GuideNode,
    GuideSite,
    GuideSpec,
)
from .guide_tooltips import build_node_tooltip, load_db_tooltip_rows
from .reporting import MetaReport, slugify_key
from .repository import TalentRepository

GUIDE_SITE_SCHEMA_VERSION = "coa-guide-site-v1"
GUIDE_SECTIONS = (
    "Overview",
    "Recommended Builds",
    "Talents",
    "Rotation",
    "Stats",
    "Weapons and Armor",
    "Abilities and Talents",
    "Warnings",
    "Data Notes",
)


def build_guide_site(
    report: MetaReport,
    *,
    entries_path: Path | str,
    db_tooltips_path: Path | str | None = None,
    asset_root: Path | str | None = None,
) -> GuideSite:
    data = report.to_dict()
    repository = TalentRepository.from_entries(entries_path)
    db_rows = load_db_tooltip_rows(db_tooltips_path)
    assets = GuideAssetCatalog(asset_root)
    tooltips = {}
    specs = []

    for result in data["spec_results"]:
        class_name = result["class_name"]
        spec_name = result["spec_name"]
        slug = f"{slugify_key(class_name)}-{slugify_key(spec_name)}"
        relevant_nodes = [
            node for node in repository.nodes_for_class(class_name)
            if node.tab_name in {"Class", spec_name}
        ]
        guide_nodes = []
        for node in sorted(relevant_nodes, key=lambda item: (item.tab_name != "Class", item.row, item.col, item.name)):
            tooltip = build_node_tooltip(node, db_rows)
            tooltips[tooltip.tooltip_id] = tooltip
            asset = assets.icon_for(node.raw.get("icon") or node.raw.get("iconPath") or node.name, node.name)
            guide_nodes.append(
                GuideNode(
                    entry_id=node.entry_id,
                    spell_id=node.spell_id,
                    name=node.name,
                    class_name=node.class_name,
                    tab_name=node.tab_name,
                    essence_kind=node.essence_kind,
                    required_level=node.required_level,
                    ae_cost=node.ae_cost,
                    te_cost=node.te_cost,
                    tags=tuple(node.tags),
                    active=not node.is_passive,
                    db_url=tooltip.db_url,
                    tooltip_id=tooltip.tooltip_id,
                    asset=asset,
                )
            )

        builds = tuple(_build_cards(result))
        warnings = tuple(result.get("warnings", []))
        confidence = builds[0].confidence_label if builds else "low"
        summary = _summary_text(result)
        specs.append(
            GuideSpec(
                slug=slug,
                href=f"specs/{slug}.html",
                class_name=class_name,
                spec_name=spec_name,
                role=result["role"],
                confidence_label=confidence,
                warning_count=len(warnings),
                summary=summary,
                sections=GUIDE_SECTIONS if warnings else tuple(section for section in GUIDE_SECTIONS if section != "Warnings"),
                builds=builds,
                nodes=tuple(guide_nodes),
                warnings=warnings,
            )
        )

    return GuideSite(
        schema_version=GUIDE_SITE_SCHEMA_VERSION,
        generated_at=data["generated_at"],
        index_path="index.html",
        legacy_index_path="meta-report.html",
        specs=tuple(specs),
        metric_definitions=_metric_definitions(),
        tooltips=tooltips,
        assets=assets.assets,
        warnings=tuple(data.get("warnings", [])),
    )


def _build_cards(result: dict) -> list[GuideBuildCard]:
    cards = []
    for build in result.get("top_builds", []):
        node_ids = tuple(node["node_id"] for node in build.get("selected_nodes", []))
        cards.append(
            GuideBuildCard(
                rank=int(build["rank"]),
                label=f"Build {build['rank']}",
                confidence_label=str(build["confidence_label"]),
                projected_dps_index=float(build["projected_dps_index"]),
                node_ids=node_ids,
                warnings=tuple(build.get("warnings", [])),
            )
        )
    return cards


def _summary_text(result: dict) -> str:
    strengths = result.get("summary", {}).get("strengths") or []
    if strengths:
        return str(strengths[0])
    return "Early theorycraft guide generated from normalized CoA builder data."


def _metric_definitions() -> dict[str, GuideMetricDefinition]:
    return {
        "projected_dps_index": GuideMetricDefinition(
            metric_id="projected_dps_index",
            label="Projected DPS Index",
            description="A relative theorycraft score. It is not observed DPS, simulated DPS, or a log parse.",
        ),
        "confidence": GuideMetricDefinition(
            metric_id="confidence",
            label="Confidence",
            description="How much source data supports this recommendation. Low confidence means the guide is using more tooltip inference.",
        ),
    }
```

- [ ] **Step 3: Run builder tests**

Run:

```bash
python -m pytest tests/test_guide_builder.py -q
```

Expected: pass.

- [ ] **Step 4: Run related tests**

Run:

```bash
python -m pytest tests/test_guide_builder.py tests/test_guide_tooltips.py tests/test_guide_assets.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/guide_builder.py tests/test_guide_builder.py
git commit -m "feat: build guide site model"
```

---

## Task 5: Static Guide Rendering

**Files:**

- Create: `coa_meta/guide_rendering.py`
- Create: `tests/test_guide_rendering.py`

- [ ] **Step 1: Write failing rendering tests**

Create `tests/test_guide_rendering.py`:

```python
from __future__ import annotations

from pathlib import Path

from coa_meta.guide_builder import build_guide_site
from coa_meta.guide_rendering import GUIDE_CSS, GUIDE_JS, render_index_html, render_spec_html
from coa_meta.reporting import MetaReportRunner, MetaRunConfig


FIXTURES = Path(__file__).parent / "fixtures"


def _site():
    report = MetaReportRunner(
        MetaRunConfig(
            entries_path=FIXTURES / "meta_report_fixture.jsonl",
            classes_path=FIXTURES / "meta_classes.json",
            class_names=("Testclass",),
            top=1,
            beam_width=2,
            branch_width=2,
            require_budget_fraction=0.0,
        )
    ).run()
    return build_guide_site(report, entries_path=FIXTURES / "meta_report_fixture.jsonl")


def test_render_index_html_uses_player_facing_guide_shell():
    html = render_index_html(_site())

    assert "<!doctype html>" in html
    assert "CoA Meta Guides" in html
    assert "Open guide" in html
    assert "data-role=" in html
    assert "beam search" not in html.lower()


def test_render_spec_html_includes_sections_and_omits_empty_warnings():
    site = _site()
    spec = next(item for item in site.specs if item.spec_name == "Damage")

    html = render_spec_html(site, spec)

    assert "Overview" in html
    assert "Abilities and Talents" in html
    assert "Stat priorities are early theorycraft" in html
    assert 'id="warnings"' not in html


def test_render_spec_html_links_spell_and_tooltip_ids():
    site = _site()
    spec = next(item for item in site.specs if item.spec_name == "Damage")

    html = render_spec_html(site, spec)

    assert "https://db.ascension.gg/?spell=2001" in html
    assert 'data-tooltip-id="spell:2001"' in html


def test_static_assets_have_fel_void_theme_and_no_network_fetch():
    assert "#65f06b" in GUIDE_CSS
    assert "#8f5cff" in GUIDE_CSS
    assert "fetch(" not in GUIDE_JS
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_guide_rendering.py -q
```

Expected: fail because `coa_meta.guide_rendering` does not exist.

- [ ] **Step 3: Implement renderer**

Create `coa_meta/guide_rendering.py` with these public names:

```python
from __future__ import annotations

import html
import json
from typing import Any

from .guide_models import GuideSite, GuideSpec

GUIDE_CSS = """
:root {
  --bg: #09050f;
  --panel: #130b1e;
  --panel-2: #1c102c;
  --fel: #65f06b;
  --void: #8f5cff;
  --warning: #f5c542;
  --text: #f5f1ff;
  --muted: #bdb4d3;
  --border: rgba(143, 92, 255, 0.35);
}
* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, system-ui, sans-serif; background: radial-gradient(circle at top, #24113b 0, var(--bg) 42rem); color: var(--text); }
a { color: var(--fel); }
.site-shell { max-width: 1280px; margin: 0 auto; padding: 28px; }
.hero { padding: 28px; border: 1px solid var(--border); background: linear-gradient(135deg, rgba(101,240,107,.12), rgba(143,92,255,.13)); border-radius: 10px; box-shadow: 0 0 32px rgba(101,240,107,.08); }
.guide-grid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); margin-top: 22px; }
.guide-card, .panel { border: 1px solid var(--border); background: rgba(19,11,30,.92); border-radius: 8px; padding: 18px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px; border: 1px solid var(--border); border-radius: 999px; color: var(--muted); font-size: .85rem; }
.warning { border-color: rgba(245,197,66,.55); color: var(--warning); }
.guide-nav { display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0; position: sticky; top: 0; padding: 10px 0; background: rgba(9,5,15,.9); backdrop-filter: blur(8px); }
.node-list { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.node-card { display: grid; grid-template-columns: 42px 1fr; gap: 10px; align-items: center; border: 1px solid rgba(101,240,107,.18); border-radius: 8px; padding: 10px; background: rgba(255,255,255,.03); }
.icon-frame { width: 42px; height: 42px; border-radius: 6px; border: 1px solid var(--fel); display: grid; place-items: center; color: var(--fel); background: rgba(101,240,107,.09); box-shadow: inset 0 0 12px rgba(101,240,107,.12); }
.tooltip { position: fixed; z-index: 20; max-width: 360px; padding: 12px; border: 1px solid var(--void); border-radius: 8px; background: #09050f; box-shadow: 0 0 28px rgba(143,92,255,.25); }
@media (max-width: 720px) { .site-shell { padding: 16px; } .hero { padding: 20px; } }
"""

GUIDE_JS = """
(() => {
  const tooltipData = window.COA_TOOLTIPS || {};
  let active;
  function removeTooltip() {
    if (active) active.remove();
    active = null;
  }
  function showTooltip(target) {
    const id = target.getAttribute("data-tooltip-id");
    const tip = tooltipData[id];
    if (!tip) return;
    removeTooltip();
    active = document.createElement("div");
    active.className = "tooltip";
    active.innerHTML = tip.html || tip.text || "";
    document.body.appendChild(active);
    const rect = target.getBoundingClientRect();
    active.style.left = Math.min(rect.left, window.innerWidth - active.offsetWidth - 16) + "px";
    active.style.top = Math.min(rect.bottom + 8, window.innerHeight - active.offsetHeight - 16) + "px";
  }
  document.addEventListener("mouseover", event => {
    const target = event.target.closest("[data-tooltip-id]");
    if (target) showTooltip(target);
  });
  document.addEventListener("mouseout", event => {
    if (event.target.closest("[data-tooltip-id]")) removeTooltip();
  });
  document.addEventListener("click", event => {
    const filter = event.target.closest("[data-role-filter]");
    if (!filter) return;
    const role = filter.getAttribute("data-role-filter");
    document.querySelectorAll("[data-role]").forEach(card => {
      card.hidden = role !== "all" && card.getAttribute("data-role") !== role;
    });
  });
})();
"""


def render_index_html(site: GuideSite) -> str:
    roles = sorted({spec.role for spec in site.specs})
    filters = '<button data-role-filter="all">All</button>' + "".join(
        f'<button data-role-filter="{_e(role)}">{_e(_label(role))}</button>' for role in roles
    )
    cards = "".join(_render_spec_card(spec) for spec in site.specs)
    tooltips = _tooltip_script(site)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>CoA Meta Guides</title><link rel=\"stylesheet\" href=\"assets/guide.css\">"
        "</head><body><main class=\"site-shell\">"
        "<section class=\"hero\"><h1>CoA Meta Guides</h1>"
        "<p>Player-facing theorycraft guides generated from normalized Conquest of Azeroth builder data.</p></section>"
        f"<section class=\"panel\"><h2>Find Your Guide</h2>{filters}</section>"
        f"<section class=\"guide-grid\">{cards}</section>"
        f"{tooltips}<script src=\"assets/guide.js\"></script>"
        "</main></body></html>"
    )


def render_spec_html(site: GuideSite, spec: GuideSpec) -> str:
    nav = "".join(f'<a href="#{_anchor(section)}">{_e(section)}</a>' for section in spec.sections)
    warnings = ""
    if spec.warnings:
        items = "".join(f"<li>{_e(warning)}</li>" for warning in spec.warnings)
        warnings = f'<section class="panel warning" id="warnings"><h2>Warnings</h2><ul>{items}</ul></section>'
    nodes = "".join(_render_node(node) for node in spec.nodes)
    builds = "".join(_render_build(build) for build in spec.builds)
    tooltips = _tooltip_script(site)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{_e(spec.class_name)} {_e(spec.spec_name)} Guide</title>"
        "<link rel=\"stylesheet\" href=\"../assets/guide.css\"></head><body><main class=\"site-shell\">"
        f'<p><a href="../index.html">Back to guides</a></p><section class="hero" id="overview">'
        f"<h1>{_e(spec.class_name)} - {_e(spec.spec_name)}</h1><p>{_e(spec.summary)}</p>"
        f'<span class="chip">{_e(_label(spec.role))}</span> <span class="chip">{_e(spec.confidence_label)} confidence</span></section>'
        f'<nav class="guide-nav">{nav}</nav>'
        f'<section class="panel" id="recommended-builds"><h2>Recommended Builds</h2><p>Early theorycraft picks.</p>{builds}</section>'
        '<section class="panel" id="talents"><h2>Talents</h2><p>Interactive tree view arrives in M1.10C.</p></section>'
        '<section class="panel" id="rotation"><h2>Rotation</h2><p>Use the generated priority notes as an early rotation scaffold.</p></section>'
        '<section class="panel warning" id="stats"><h2>Stats</h2><p>Stat priorities are early theorycraft until simulations or combat logs are available.</p></section>'
        '<section class="panel" id="weapons-and-armor"><h2>Weapons and Armor</h2><p>Gear targeting is low confidence until item data is complete.</p></section>'
        f'<section class="panel" id="abilities-and-talents"><h2>Abilities and Talents</h2><div class="node-list">{nodes}</div></section>'
        f"{warnings}<section class=\"panel\" id=\"data-notes\"><h2>Data Notes</h2><p>Generated: {_e(site.generated_at)}</p></section>"
        f"{tooltips}<script src=\"../assets/guide.js\"></script>"
        "</main></body></html>"
    )


def _render_spec_card(spec: GuideSpec) -> str:
    warning = '<span class="chip warning">Warnings</span>' if spec.warning_count else ""
    return (
        f'<article class="guide-card" data-role="{_e(spec.role)}">'
        f"<h2>{_e(spec.class_name)} - {_e(spec.spec_name)}</h2>"
        f"<p>{_e(spec.summary)}</p><p><span class=\"chip\">{_e(_label(spec.role))}</span> "
        f"<span class=\"chip\">{_e(spec.confidence_label)} confidence</span> {warning}</p>"
        f'<p><a href="{_e(spec.href)}">Open guide</a></p></article>'
    )


def _render_build(build: Any) -> str:
    return (
        '<article class="guide-card">'
        f"<h3>{_e(build.label)}</h3><p><span class=\"chip\">{_e(build.confidence_label)} confidence</span> "
        f"<span class=\"chip\" data-tooltip-id=\"metric:projected_dps_index\">Projected Index {build.projected_dps_index:.1f}</span></p>"
        "</article>"
    )


def _render_node(node: Any) -> str:
    icon = node.name[:2].upper()
    link = f'<a href="{_e(node.db_url)}" data-tooltip-id="{_e(node.tooltip_id)}">{_e(node.name)}</a>' if node.db_url else _e(node.name)
    return (
        '<article class="node-card">'
        f'<span class="icon-frame">{_e(icon)}</span><span>{link}<br>'
        f'<small>{_e(node.tab_name)} - {_e(node.essence_kind)} - Level {node.required_level}</small></span></article>'
    )


def _tooltip_script(site: GuideSite) -> str:
    payload = {key: value.to_dict() for key, value in site.tooltips.items()}
    payload["metric:projected_dps_index"] = {
        "html": "<strong>Projected DPS Index</strong><div>A relative theorycraft score, not observed DPS.</div>",
        "text": "A relative theorycraft score, not observed DPS.",
    }
    return f"<script>window.COA_TOOLTIPS = {json.dumps(payload, sort_keys=True)};</script>"


def _anchor(value: str) -> str:
    return value.lower().replace(" ", "-")


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)
```

- [ ] **Step 4: Run rendering tests**

Run:

```bash
python -m pytest tests/test_guide_rendering.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/guide_rendering.py tests/test_guide_rendering.py
git commit -m "feat: render static guide pages"
```

---

## Task 6: Guide Writer and Reporting Integration

**Files:**

- Create: `coa_meta/guide_writer.py`
- Modify: `coa_meta/reporting.py`
- Modify: `tests/test_report_writers.py`

- [ ] **Step 1: Update report writer tests first**

Modify `tests/test_report_writers.py`:

```python
def test_writes_json_markdown_and_html_outputs(tmp_path):
    report = _report()

    written = write_report_outputs(
        report,
        tmp_path,
        formats=("json", "md", "html"),
        entries_path=FIXTURES / "meta_report_fixture.jsonl",
        db_tooltips_path=FIXTURES / "guide_db_tooltips.jsonl",
    )

    names = {path.name for path in written}
    assert {"meta-report.json", "meta-report.md", "meta-report.html", "index.html"}.issubset(names)
    assert (tmp_path / "specs" / "testclass-damage.html").exists()
    assert (tmp_path / "assets" / "guide.css").exists()
    assert (tmp_path / "assets" / "guide.js").exists()
    assert (tmp_path / "assets" / "tooltip-catalog.json").exists()
    data = json.loads((tmp_path / "meta-report.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == "coa-meta-report-v1"
```

Also update `test_markdown_and_html_include_warnings_and_theorycraft_label` to call:

```python
html = render_html_report(report, entries_path=FIXTURES / "meta_report_fixture.jsonl")
```

Expected assertions:

```python
assert "CoA Meta Guides" in html
assert "Open guide" in html
assert "beam search" not in html.lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_report_writers.py -q
```

Expected: fail because writer signatures and guide writer are not implemented.

- [ ] **Step 3: Implement guide writer**

Create `coa_meta/guide_writer.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from .guide_builder import build_guide_site
from .guide_rendering import GUIDE_CSS, GUIDE_JS, render_index_html, render_spec_html
from .reporting import MetaReport


def render_guide_index_html(
    report: MetaReport,
    *,
    entries_path: Path | str,
    db_tooltips_path: Path | str | None = None,
    asset_root: Path | str | None = None,
) -> str:
    site = build_guide_site(
        report,
        entries_path=entries_path,
        db_tooltips_path=db_tooltips_path,
        asset_root=asset_root,
    )
    return render_index_html(site)


def write_guide_site(
    report: MetaReport,
    out_dir: Path | str,
    *,
    entries_path: Path | str,
    db_tooltips_path: Path | str | None = None,
    asset_root: Path | str | None = None,
) -> tuple[Path, ...]:
    output_dir = Path(out_dir)
    site = build_guide_site(
        report,
        entries_path=entries_path,
        db_tooltips_path=db_tooltips_path,
        asset_root=asset_root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = output_dir / "assets"
    spec_dir = output_dir / "specs"
    asset_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    index_html = render_index_html(site)
    for name in (site.index_path, site.legacy_index_path):
        path = output_dir / name
        path.write_text(index_html, encoding="utf-8")
        written.append(path)

    css_path = asset_dir / "guide.css"
    css_path.write_text(GUIDE_CSS.strip() + "\n", encoding="utf-8")
    written.append(css_path)
    js_path = asset_dir / "guide.js"
    js_path.write_text(GUIDE_JS.strip() + "\n", encoding="utf-8")
    written.append(js_path)

    tooltip_path = asset_dir / "tooltip-catalog.json"
    tooltip_path.write_text(
        json.dumps({key: value.to_dict() for key, value in site.tooltips.items()}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    written.append(tooltip_path)

    manifest_path = asset_dir / "guide-site-manifest.json"
    manifest_path.write_text(json.dumps(site.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    written.append(manifest_path)

    for spec in site.specs:
        path = output_dir / spec.href
        path.write_text(render_spec_html(site, spec), encoding="utf-8")
        written.append(path)

    return tuple(written)
```

- [ ] **Step 4: Modify reporting wrappers**

In `coa_meta/reporting.py`, import the guide writer inside functions to avoid circular imports:

```python
def render_html_report(
    report: MetaReport,
    asset_resolver: Any | None = None,
    entries_path: Path | str | None = None,
    db_tooltips_path: Path | str | None = None,
) -> str:
    if entries_path is not None:
        from .guide_writer import render_guide_index_html

        return render_guide_index_html(
            report,
            entries_path=entries_path,
            db_tooltips_path=db_tooltips_path,
            asset_root=getattr(asset_resolver, "asset_root", None),
        )
    ...
```

Change `write_report_outputs` signature:

```python
def write_report_outputs(
    report: MetaReport,
    out_dir: Path | str,
    formats: tuple[str, ...] = ("json", "md", "html"),
    asset_resolver: Any | None = None,
    entries_path: Path | str | None = None,
    db_tooltips_path: Path | str | None = None,
) -> tuple[Path, ...]:
```

In the `fmt == "html"` branch:

```python
if entries_path is not None:
    from .guide_writer import write_guide_site

    written.extend(
        write_guide_site(
            report,
            output_dir,
            entries_path=entries_path,
            db_tooltips_path=db_tooltips_path,
            asset_root=getattr(asset_resolver, "asset_root", None),
        )
    )
    continue
```

Leave the old inline HTML path as fallback when `entries_path` is not supplied, so older tests or callers remain compatible.

- [ ] **Step 5: Run report writer tests**

Run:

```bash
python -m pytest tests/test_report_writers.py tests/test_guide_rendering.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add coa_meta/guide_writer.py coa_meta/reporting.py tests/test_report_writers.py
git commit -m "feat: write static guide site outputs"
```

---

## Task 7: CLI Integration

**Files:**

- Modify: `coa_meta/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_meta_cli_passes_guide_context_to_writer(monkeypatch, tmp_path):
    written = {}

    def fake_write_outputs(report, out_dir, formats, asset_resolver=None, entries_path=None, db_tooltips_path=None):
        written["entries_path"] = entries_path
        written["db_tooltips_path"] = db_tooltips_path
        written["asset_resolver"] = asset_resolver
        return (Path(out_dir) / "index.html",)

    monkeypatch.setattr(cli, "MetaReportRunner", DummyRunner)
    monkeypatch.setattr(cli, "write_report_outputs", fake_write_outputs)

    exit_code = cli.main(
        [
            "meta",
            "--entries",
            "coa_scraper/dist/coa_entries.jsonl",
            "--classes",
            "coa_scraper/dist/coa_classes.json",
            "--db-tooltips",
            "coa_scraper/dist/coa_db_spell_tooltips.jsonl",
            "--asset-root",
            "coa_scraper/data/raw",
            "--format",
            "html",
            "--out",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert written["entries_path"] == Path("coa_scraper/dist/coa_entries.jsonl")
    assert written["db_tooltips_path"] == Path("coa_scraper/dist/coa_db_spell_tooltips.jsonl")
    assert written["asset_resolver"] is not None
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_cli.py::test_meta_cli_passes_guide_context_to_writer -q
```

Expected: fail because `--db-tooltips` is not recognized and writer call does not pass entries path.

- [ ] **Step 3: Implement CLI argument and writer call**

In `coa_meta/cli.py`, add parser argument:

```python
meta.add_argument("--db-tooltips", type=Path, default=None, help="Optional AscensionDB tooltip JSONL for static guide tooltips")
```

Change the writer call:

```python
outputs = write_report_outputs(
    report,
    args.out,
    formats=formats,
    asset_resolver=asset_resolver,
    entries_path=args.entries,
    db_tooltips_path=args.db_tooltips,
)
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python -m pytest tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add coa_meta/cli.py tests/test_cli.py
git commit -m "feat: pass guide context through meta CLI"
```

---

## Task 8: End-to-End HTML Smoke and Docs

**Files:**

- Modify: `docs/README.md`
- Modify: `docs/superpowers/specs/2026-07-05-m1-10-a-b-guide-ia-assets-design.md` only if implementation clarifies behavior.

- [ ] **Step 1: Run focused guide tests**

Run:

```bash
python -m pytest tests/test_guide_tooltips.py tests/test_guide_assets.py tests/test_guide_builder.py tests/test_guide_rendering.py tests/test_report_writers.py tests/test_cli.py -q
```

Expected: pass.

- [ ] **Step 2: Run full Python suite**

Run:

```bash
python -m pytest -q
```

Expected: pass.

- [ ] **Step 3: Run a real static guide smoke**

Run:

```bash
python -m coa_meta meta \
  --entries coa_scraper/dist/coa_entries.jsonl \
  --classes coa_scraper/dist/coa_classes.json \
  --db-tooltips coa_scraper/dist/coa_db_spell_tooltips.jsonl \
  --out /tmp/coa-m110-guide-smoke \
  --format html \
  --class Venomancer \
  --spec Stalking \
  --top 1
```

Expected:

- stderr includes `[coa-meta] Complete`.
- `/tmp/coa-m110-guide-smoke/index.html` exists.
- `/tmp/coa-m110-guide-smoke/meta-report.html` exists.
- `/tmp/coa-m110-guide-smoke/specs/venomancer-stalking.html` exists.
- `/tmp/coa-m110-guide-smoke/assets/guide.css` exists.
- `/tmp/coa-m110-guide-smoke/assets/tooltip-catalog.json` exists.

- [ ] **Step 4: Inspect generated HTML for obvious regressions**

Run:

```bash
python - <<'PY'
from pathlib import Path
root = Path("/tmp/coa-m110-guide-smoke")
index = (root / "index.html").read_text(encoding="utf-8")
spec = (root / "specs" / "venomancer-stalking.html").read_text(encoding="utf-8")
assert "CoA Meta Guides" in index
assert "Open guide" in index
assert "Abilities and Talents" in spec
assert "https://db.ascension.gg/?spell=" in spec
assert "beam search" not in (index + spec).lower()
print("guide smoke ok")
PY
```

Expected: `guide smoke ok`.

- [ ] **Step 5: Update README guide command**

In `docs/README.md`, extend the Phase 1 Meta Report Command section with:

````markdown
For the M1.10 static guide-site renderer, include DB tooltip enrichment when available:

```bash
python -m coa_meta meta \
  --entries coa_scraper/dist/coa_entries.jsonl \
  --classes coa_scraper/dist/coa_classes.json \
  --db-tooltips coa_scraper/dist/coa_db_spell_tooltips.jsonl \
  --out reports/meta \
  --format html
```

This writes `index.html`, `meta-report.html`, `specs/*.html`, and static assets under `reports/meta/assets/`.
````

- [ ] **Step 6: Commit docs and final implementation**

```bash
git add docs/README.md
git commit -m "docs: document static guide output"
```

---

## Final Verification

- [ ] Run full test suite:

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] Confirm no generated artifacts are staged accidentally:

```bash
git status --short
git diff --cached --name-only
```

Expected: only intentional source/test/docs files are staged or committed.

- [ ] Produce final implementation summary with:

- Commits created.
- Tests run.
- Smoke output path.
- Remaining limitations: placeholders for class/spec hero media, no interactive talent tree until M1.10C, no build diversity until M1.10D, no role taxonomy split until M1.10E.

## Self-Review Checklist

- Spec coverage: A information architecture is covered by guide model, renderer, writer, CLI, and docs tasks. B asset and tooltip integration is covered by tooltip catalog, asset catalog, guide builder, writer manifests, and tests.
- Placeholder scan: no task uses "TBD" or vague "add tests" instructions without concrete assertions.
- Type consistency: public names are consistent across tasks: `GuideSite`, `GuideSpec`, `GuideNode`, `GuideAsset`, `GuideTooltip`, `build_guide_site`, `render_index_html`, `render_spec_html`, `write_guide_site`.
- Scope: plan stops before talent-tree interaction, build diversity, and final role taxonomy, matching the A/B boundary.
