# M1.12 Public-Release UI Quick Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the visible UI/UX defects that block a public GitHub Pages launch — icons instead of two-letter abbreviations, spec icons on the index, a select-to-include role filter, updated disclaimer copy, a header GitHub link, a footer, and removal of leveling-path boilerplate — without any engine/data/legality changes.

**Architecture:** All changes are in the guide presentation layer (`coa_meta/guide_assets.py`, `guide_rendering.py`, `guide_models.py`, `guide_builder.py`) plus the display-only reason string in `leveling_path.py`. Icons resolve to AscensionDB's icon CDN by slug; role-filter and page-chrome are static HTML/CSS/JS in the renderer. Work is implemented as durable behavior/content so the M1.13 fel/void redesign inherits the wiring.

**Tech Stack:** Python 3, dataclasses, pytest. No new dependencies.

## Global Constraints

- No engine, data, legality, scoring, or simulation changes (M1.12 is UI-only).
- Repository URL: `https://github.com/plowsters/coa_meta_analyzer`. Issues URL: `https://github.com/plowsters/coa_meta_analyzer/issues`.
- Footer copyright entity: `CoA Meta Analyzer` (project name), year `2026`.
- Disclaimer copy (verbatim): `Theorycrafting projections based on CoA Builder and Ascension data. Further accuracy tuning through combat logs/simming may be added if CoA stays online and pending CoA compatibility with AscensionLogs.`
- AscensionDB icon URL template: `https://db.ascension.gg/static/images/wow/icons/large/{icon}.jpg`.
- Icon URL slug rule mirrors `coa_scraper/scripts/lib/icon-assets.mjs::sanitizeIconToken`: take the last path segment, drop the image extension, lowercase, replace runs of non-alphanumerics with a single `_`, trim leading/trailing `_`.
- Two-letter abbreviation is retained only as the final fallback when no icon slug exists.
- Tests must assert the new intended behavior, not snapshot current output.

---

### Task 1: AscensionDB remote icon resolution

**Files:**
- Modify: `coa_meta/guide_assets.py`
- Modify: `coa_meta/guide_builder.py:66-70` (icon token no longer falls back to node name)
- Modify: `coa_meta/guide_rendering.py:692-699` (`_render_icon_content`)
- Test: `tests/test_guide_assets.py`

**Interfaces:**
- Produces: `GuideAssetCatalog.icon_for(icon, label, *, local_path=None)` now returns a `GuideAsset` with `source="ascension_db_remote"`, `missing=False`, and an absolute `https://db.ascension.gg/...` `href` when a real icon slug is present and no local asset resolves. `href=None, missing=True, source="placeholder"` only when no slug exists.

- [ ] **Step 1: Update the failing test for remote resolution**

In `tests/test_guide_assets.py` replace `test_icon_placeholder_is_deterministic_without_asset_root` with:

```python
def test_icon_resolves_remote_ascensiondb_url_without_local_asset():
    catalog = GuideAssetCatalog()

    asset = catalog.icon_for("Interface\\Icons\\Shared_Strike", "Shared Strike")

    assert asset.asset_id == "icon:sharedstrike"
    assert asset.href == "https://db.ascension.gg/static/images/wow/icons/large/shared_strike.jpg"
    assert asset.missing is False
    assert asset.source == "ascension_db_remote"


def test_icon_falls_back_to_placeholder_without_slug_or_asset():
    catalog = GuideAssetCatalog()

    asset = catalog.icon_for("", "Adrenal Venom")

    assert asset.href is None
    assert asset.missing is True
    assert asset.source == "placeholder"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_guide_assets.py -q`
Expected: FAIL (remote branch not implemented).

- [ ] **Step 3: Implement remote resolution in `guide_assets.py`**

Add the template and slug helper near the bottom helpers:

```python
ASCENSIONDB_ICON_URL_TEMPLATE = "https://db.ascension.gg/static/images/wow/icons/large/{icon}.jpg"


def _icon_url_slug(value: str) -> str:
    stem = value.replace("\\", "/").split("/")[-1]
    stem = re.sub(r"\.(blp|png|jpg|jpeg|webp)$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[^a-z0-9]+", "_", stem.lower())
    return stem.strip("_")
```

Add `import re` at the top. Rewrite the no-`local_path` branch of `icon_for` so that when `_find_local_icon` misses it tries the remote slug before the placeholder:

```python
        slug = _asset_slug((icon or label).split("\\")[-1])
        asset_id = f"icon:{slug or _asset_slug(label) or 'missing'}"
        if asset_id in self._assets:
            return self._assets[asset_id]

        path = self._find_local_icon(slug)
        if path is not None:
            asset = GuideAsset(
                asset_id=asset_id, kind="icon", label=label,
                href=path.name, source="asset_root", missing=False, source_path=str(path),
            )
        else:
            url_slug = _icon_url_slug(icon or "")
            if url_slug:
                asset = GuideAsset(
                    asset_id=asset_id, kind="icon", label=label,
                    href=ASCENSIONDB_ICON_URL_TEMPLATE.format(icon=url_slug),
                    source="ascension_db_remote", missing=False,
                )
            else:
                asset = GuideAsset(
                    asset_id=asset_id, kind="icon", label=label,
                    href=None, source="placeholder", missing=True,
                )
        self._assets[asset_id] = asset
        return asset
```

- [ ] **Step 4: Stop the caller from using the node name as an icon slug**

In `coa_meta/guide_builder.py` change the `icon_for` call (line ~66) so the icon token is a real slug only (drop `or node.name`); the name stays as the label:

```python
            asset = assets.icon_for(
                str((db_row or {}).get("icon") or node.raw.get("icon") or node.raw.get("iconPath") or ""),
                node.name,
                local_path=(db_row or {}).get("icon_asset_path"),
            )
```

- [ ] **Step 5: Renderer emits `<img>` for any non-missing asset**

`_render_icon_content` already emits `<img>` when `href` and not `missing`; confirm it is unchanged and that `_asset_src` passes absolute `https://` hrefs through (it does, via the `startswith(("http://", "https://", ...))` guard). No edit needed unless the guard is missing.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_guide_assets.py tests/test_guide_builder.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add coa_meta/guide_assets.py coa_meta/guide_builder.py tests/test_guide_assets.py
git commit -m "Resolve node icons from AscensionDB CDN instead of abbreviations"
```

---

### Task 2: Spec icons on the index cards

**Files:**
- Modify: `coa_meta/guide_models.py` (`GuideSpec` gains `icon_asset`)
- Modify: `coa_meta/guide_builder.py` (compute the spec icon)
- Modify: `coa_meta/guide_rendering.py` (`_render_spec_card`, new `_render_spec_icon`, CSS)
- Test: `tests/test_guide_rendering.py`

**Interfaces:**
- Consumes: `GuideNode.asset` (Task 1).
- Produces: `GuideSpec.icon_asset: GuideAsset | None = None`; `_render_spec_card` renders `<img>` when present.

- [ ] **Step 1: Failing test**

Add to `tests/test_guide_rendering.py`:

```python
def test_index_spec_cards_render_spec_icon_image():
    html = render_index_html(_site())
    assert 'class="spec-icon"' in html
    assert 'assets/' in html.split('class="spec-icon"', 1)[1][:200]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_guide_rendering.py::test_index_spec_cards_render_spec_icon_image -q`
Expected: FAIL.

- [ ] **Step 3: Add the model field**

In `coa_meta/guide_models.py`, add to `GuideSpec` (after `roles`):

```python
    icon_asset: GuideAsset | None = None
```

- [ ] **Step 4: Compute the spec icon in `guide_builder.py`**

Before constructing `GuideSpec`, pick the first non-missing node asset preferring the spec's own tab:

```python
        spec_icon = next(
            (n.asset for n in guide_nodes if n.tab_name == source_spec_name and not n.asset.missing),
            next((n.asset for n in guide_nodes if not n.asset.missing), None),
        )
```

Pass `icon_asset=spec_icon` into the `GuideSpec(...)` call.

- [ ] **Step 5: Render it**

In `guide_rendering.py`, add a helper and use it in `_render_spec_card`:

```python
def _render_spec_icon(spec: GuideSpec, asset_prefix: str = "assets") -> str:
    asset = getattr(spec, "icon_asset", None)
    if asset and asset.href and not asset.missing:
        src = _asset_src(asset.href, asset_prefix)
        return f'<span class="spec-icon"><img src="{_e(src)}" alt="" loading="lazy"></span>'
    initials = _e("".join(word[:1] for word in spec.class_name.split()[:2]).upper() or spec.class_name[:2].upper())
    return f'<span class="spec-icon spec-icon-mono">{initials}</span>'
```

In `_render_spec_card`, prefix the `<h2>` with the icon:

```python
        f'<h2>{_render_spec_icon(spec)} {_e(spec.class_name)} - {_e(spec.spec_name)}</h2>'
```

Add minimal CSS to `GUIDE_CSS`:

```css
.spec-icon { display: inline-flex; width: 28px; height: 28px; vertical-align: middle; margin-right: 8px; border-radius: 6px; overflow: hidden; }
.spec-icon img { width: 100%; height: 100%; object-fit: cover; }
.spec-icon-mono { align-items: center; justify-content: center; background: rgba(143,92,255,.18); color: var(--text); font-size: 12px; }
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_guide_rendering.py tests/test_guide_builder.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add coa_meta/guide_models.py coa_meta/guide_builder.py coa_meta/guide_rendering.py tests/test_guide_rendering.py
git commit -m "Show spec icons on the guide index cards"
```

---

### Task 3: Select-to-include role filter

**Files:**
- Modify: `coa_meta/guide_rendering.py` (`render_index_html` initial markup; `GUIDE_JS` click handler)
- Test: `tests/test_guide_rendering.py`

**Interfaces:**
- Produces: initial index markup renders `All Roles` as `is-active`/`aria-pressed="true"` and every role button as `aria-pressed="false"`; the JS shows all when the selected set is empty and only-selected otherwise.

- [ ] **Step 1: Failing test**

Add to `tests/test_guide_rendering.py`:

```python
def test_role_filter_defaults_to_all_and_roles_start_unpressed():
    html = render_index_html(_site())
    all_button = html.split('data-role-filter="all"', 1)[1][:120]
    assert 'aria-pressed="true"' in all_button
    melee_button = html.split('data-role-filter="melee_dps"', 1)[1][:120]
    assert 'aria-pressed="false"' in melee_button
    assert 'if (selected.size === 0)' in GUIDE_JS or 'selected.size === 0' in GUIDE_JS
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_guide_rendering.py::test_role_filter_defaults_to_all_and_roles_start_unpressed -q`
Expected: FAIL.

- [ ] **Step 3: Change the initial render**

In `render_index_html`, render role buttons unpressed:

```python
    filters += "".join(
        f'<button class="role-filter" data-role-filter="{_e(role)}" aria-pressed="false">{_e(_label(role))}</button>'
        for role in roles
    )
```

(Leave the `All Roles` button as `is-active`/`aria-pressed="true"`.)

- [ ] **Step 4: Rewrite the JS click handler**

Replace the `document.addEventListener("click", ...)` role-filter block (lines ~116-148) with:

```javascript
  document.addEventListener("click", event => {
    const filter = event.target.closest("[data-role-filter]");
    if (!filter) return;
    const buttons = Array.from(document.querySelectorAll("[data-role-filter]"));
    const roleButtons = buttons.filter(button => button.getAttribute("data-role-filter") !== "all");
    const allButton = buttons.find(button => button.getAttribute("data-role-filter") === "all");
    const selected = new Set(roleButtons.filter(button => button.getAttribute("aria-pressed") === "true").map(button => button.getAttribute("data-role-filter")));
    const clicked = filter.getAttribute("data-role-filter");
    if (clicked === "all") selected.clear();
    else if (selected.has(clicked)) selected.delete(clicked);
    else selected.add(clicked);
    const showAll = selected.size === 0;
    roleButtons.forEach(button => {
      const active = selected.has(button.getAttribute("data-role-filter"));
      button.setAttribute("aria-pressed", String(active));
      button.classList.toggle("is-active", active);
    });
    if (allButton) {
      allButton.setAttribute("aria-pressed", String(showAll));
      allButton.classList.toggle("is-active", showAll);
    }
    document.querySelectorAll("[data-role]").forEach(card => {
      const roles = (card.getAttribute("data-role") || "").split(/\\s+/).filter(Boolean);
      card.hidden = showAll ? false : !roles.some(role => selected.has(role));
    });
    document.querySelectorAll("[data-role-section]").forEach(section => {
      section.hidden = showAll ? false : !selected.has(section.getAttribute("data-role-section"));
    });
  });
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_guide_rendering.py -q`
Expected: PASS (including `test_index_groups_specs_by_role_and_supports_multi_role_filters`, since the `All Roles` button keeps `aria-pressed="true"`).

- [ ] **Step 6: Commit**

```bash
git add coa_meta/guide_rendering.py tests/test_guide_rendering.py
git commit -m "Make Find Your Guide select-to-include with an All Roles default"
```

---

### Task 4: Header GitHub link, footer, and disclaimer copy

**Files:**
- Modify: `coa_meta/guide_rendering.py` (constants, `FRONT_PAGE_DISCLAIMER`, `_render_header`, `_render_footer`, insert into `render_index_html` and `render_spec_html`, CSS)
- Test: `tests/test_guide_rendering.py`

**Interfaces:**
- Produces: `_render_header() -> str` and `_render_footer(site) -> str` fragments used by both index and spec pages.

- [ ] **Step 1: Failing tests**

Update the disclaimer assertion in `test_render_index_html_uses_player_facing_guide_shell` (line 82) to:

```python
    assert "Further accuracy tuning through combat logs/simming" in html
    assert "db.ascension.gg" not in html
```

Add:

```python
def test_pages_include_github_header_and_footer():
    site = _site()
    index_html = render_index_html(site)
    spec = next(item for item in site.specs if item.spec_name == "Damage")
    spec_html = render_spec_html(site, spec)
    for html in (index_html, spec_html):
        assert "https://github.com/plowsters/coa_meta_analyzer" in html
        assert "https://github.com/plowsters/coa_meta_analyzer/issues" in html
        assert "© 2026 CoA Meta Analyzer" in html
        assert "Not affiliated with or endorsed by Project Ascension" in html
        assert 'aria-label="View source on GitHub"' in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_guide_rendering.py::test_pages_include_github_header_and_footer tests/test_guide_rendering.py::test_render_index_html_uses_player_facing_guide_shell -q`
Expected: FAIL.

- [ ] **Step 3: Constants and disclaimer**

At the top of `guide_rendering.py`:

```python
REPO_URL = "https://github.com/plowsters/coa_meta_analyzer"
ISSUES_URL = "https://github.com/plowsters/coa_meta_analyzer/issues"
FRONT_PAGE_DISCLAIMER = (
    "Theorycrafting projections based on CoA Builder and Ascension data. "
    "Further accuracy tuning through combat logs/simming may be added if CoA stays online "
    "and pending CoA compatibility with AscensionLogs."
)
GITHUB_MARK_SVG = (
    '<svg viewBox="0 0 16 16" width="20" height="20" aria-hidden="true" fill="currentColor">'
    '<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 '
    '0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01'
    '1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 '
    '0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 '
    '1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 '
    '3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/>'
    "</svg>"
)
```

- [ ] **Step 4: Header and footer fragments**

```python
def _render_header() -> str:
    return (
        '<header class="site-header">'
        '<a class="site-brand" href="index.html">CoA Meta Guides</a>'
        f'<a class="github-link" href="{REPO_URL}" target="_blank" rel="noopener" '
        f'aria-label="View source on GitHub">{GITHUB_MARK_SVG}</a>'
        "</header>"
    )


def _render_footer(site: GuideSite) -> str:
    generated = _e(getattr(site, "generated_at", "") or "")
    return (
        '<footer class="site-footer">'
        "<p>© 2026 CoA Meta Analyzer · Fan-made theorycraft tool. "
        "Not affiliated with or endorsed by Project Ascension.</p>"
        f'<p><a href="{ISSUES_URL}" target="_blank" rel="noopener">Submit an issue</a> · '
        f'<a href="{REPO_URL}" target="_blank" rel="noopener">Source on GitHub</a>'
        f"{' · Generated ' + generated if generated else ''}</p>"
        "</footer>"
    )
```

Note: header brand links to `index.html`; on spec pages the relative link resolves from `specs/`, so use `../index.html` there. Implement `_render_header(home_href="index.html")` and pass `home_href="../index.html"` from `render_spec_html`; adjust the `href` line accordingly. The GitHub/issues URLs are absolute and need no adjustment.

- [ ] **Step 5: Insert into both pages**

In `render_index_html`, put `{_render_header()}` right after `<main class="site-shell">` and `{_render_footer(site)}` right before `</main>`. In `render_spec_html`, do the same with `_render_header(home_href="../index.html")` and `_render_footer(site)`.

- [ ] **Step 6: CSS**

Add to `GUIDE_CSS`:

```css
.site-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 4px; }
.site-brand { font-weight: 600; color: var(--text); text-decoration: none; }
.github-link { color: var(--muted); display: inline-flex; transition: color .15s ease; }
.github-link:hover { color: var(--fel); }
.site-footer { margin-top: 32px; padding: 18px 4px; border-top: 1px solid rgba(143,92,255,.25); color: var(--muted); font-size: 13px; }
.site-footer a { color: var(--muted); }
.site-footer a:hover { color: var(--fel); }
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_guide_rendering.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add coa_meta/guide_rendering.py tests/test_guide_rendering.py
git commit -m "Add header GitHub link, footer, and updated release disclaimer"
```

---

### Task 5: Remove leveling-path boilerplate reason

**Files:**
- Modify: `coa_meta/guide_rendering.py` (`_render_leveling_path_for_build`)
- Modify: `coa_meta/leveling_path.py` (`_choice_reason` generic fallback)
- Test: `tests/test_guide_rendering.py`

**Interfaces:**
- Produces: rendered leveling path items are `Level N — essence chip — name` with no per-step reason sentence; `_choice_reason` returns `""` for the generic case.

- [ ] **Step 1: Failing test**

Add to `tests/test_guide_rendering.py`:

```python
def test_leveling_path_omits_boilerplate_reason():
    site = _site()
    spec = next(item for item in site.specs if item.spec_name == "Damage")
    html = render_spec_html(site, spec)
    assert "as soon as it is legal" not in html
    assert 'class="muted">Take this' not in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_guide_rendering.py::test_leveling_path_omits_boilerplate_reason -q`
Expected: FAIL (the generic reason currently renders).

- [ ] **Step 3: Drop the reason span from the renderer**

In `_render_leveling_path_for_build`, change the item append to omit `reason`:

```python
        items.append(
            f"<li><strong>Level {_e(level)}</strong> "
            f"<span class=\"chip\">{_e(essence)}</span> "
            f"{_e(name)}</li>"
        )
```

Remove the now-unused `reason = step.get("reason", "")` line.

- [ ] **Step 4: Remove the generic reason at the source**

In `coa_meta/leveling_path.py::_choice_reason`, replace the final `return "Take this selected build node as soon as it is legal."` with:

```python
    return ""
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_guide_rendering.py tests/test_leveling_path.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add coa_meta/guide_rendering.py coa_meta/leveling_path.py tests/test_guide_rendering.py
git commit -m "Remove repeated boilerplate reason from the leveling path"
```

---

### Task 6: Full suite and HTML smoke

- [ ] **Step 1: Run the whole test suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 2: Regenerate the HTML report smoke output**

Run:
```bash
python -m coa_meta meta --class Venomancer --top 1 \
  --entries coa_scraper/dist/coa_entries.jsonl \
  --classes coa_scraper/dist/coa_classes.json \
  --db-tooltips coa_scraper/dist/coa_db_spell_tooltips.jsonl \
  --out reports/meta-m1-12-smoke --format html
```
Expected: writes `index.html` and `specs/*.html`; spot-check that node/spec icons are `<img>` tags, the role filter defaults to All, the header/footer render, and the leveling path has no boilerplate reason.

- [ ] **Step 3: Commit any smoke-output-driven fixes** (only if needed).

## Self-Review

- **Spec coverage:** icons on nodes (Task 1) and spec cards (Task 2); select-to-include filter (Task 3); disclaimer, header GitHub link, footer (Task 4); boilerplate removal (Task 5). All seven M1.12 spec items are covered. The deferred items (essence under-spend, `deferred`-step skips, exclusive nodes, level slider) are intentionally out of scope (M1.15) and have no task here.
- **Placeholder scan:** every code step contains complete code; no TBD/TODO.
- **Type consistency:** `icon_asset` added to `GuideSpec` and read via `getattr` in the renderer; `_render_header(home_href=...)`/`_render_footer(site)` signatures are consistent across index and spec insertion points; `GuideAsset` fields match `guide_models.py`.
