# M1.12 Public-Release UI Quick Fixes Design

## Purpose

M1.12 makes the guide site presentable as a public GitHub Pages resource by fixing a set of visible
UI/UX defects. It is deliberately scoped to presentation and static content only: no engine, data,
legality, scoring, or simulation changes. Correctness bugs that require engine changes (essence
under-spend, leveling-path level skips, mutually exclusive nodes) are explicitly deferred to M1.15.

Because M1.13 will re-skin the site from a Claude Design fel/void redesign, M1.12 is implemented as
**durable behavior and content** — icon resolution logic, role-filter semantics, disclaimer/footer
copy, and the repository link — so the redesign inherits the wiring and only restyles it.

## Current State

- **Icons:** `guide_rendering.py::_render_icon_content` (line ~699) falls back to
  `node.name[:2].upper()` two-letter abbreviations. The DB `icon` slug (e.g. `trade_engineering`)
  is already threaded into `guide_assets.py::GuideAssetCatalog.icon_for` via
  `guide_builder.py` (line ~66), but `icon_for` only resolves against a local `asset_root`; with no
  local icon files present it returns `missing=True`, forcing the abbreviation fallback.
- **Spec cards:** `guide_rendering.py::_render_spec_card` (line ~282) renders no icon.
- **Role filter:** `render_index_html` (lines ~231–235) renders every role button as
  `is-active`/`aria-pressed="true"` (all selected), and the click handler (lines ~117–148) works by
  *deselecting* unwanted roles.
- **Disclaimer:** `guide_rendering.py::FRONT_PAGE_DISCLAIMER` (line ~10) references db.ascension.gg
  and uses outdated wording.
- **Header/footer:** the index uses a `<section class="hero">` with no header bar and no footer;
  there is no link to the GitHub repository.
- **Leveling path:** `_render_leveling_path_for_build` (line ~651) renders a boilerplate `reason`
  line (line ~667). The generic fallback reason is
  `leveling_path.py::_choice_reason` → "Take this selected build node as soon as it is legal."
  (line ~373). It also silently skips `deferred` steps (line ~658).

## Scope

M1.12 includes:

- Real spell/talent icons on node cards, hotlinked from AscensionDB by icon slug.
- Spec icons on the main index cards.
- A select-to-include role filter with an "All Roles" default.
- Updated front-page disclaimer copy.
- A header bar with a light-gray GitHub repository link (top-right) on index and spec pages.
- A footer on all pages with copyright, non-affiliation notice, issue-submission link, repository
  link, and builder data-capture date.
- Removal of the repeated boilerplate reason text from the leveling path.
- Test updates that assert the new intended behavior.

M1.12 does not include (deferred to M1.15):

- Making builds spend the full AE/TE budget.
- Making the leveling path render every level 10–60 with a concrete pick (removing `deferred`
  skips at the source).
- Mutually exclusive shared-node handling.
- The granular 10–60 level slider.

M1.12 does not include (deferred to M1.13):

- Any visual redesign, theme, or layout change beyond the minimal header/footer structure needed to
  host the GitHub link and footer content.

## Design

### 1. Node icons via AscensionDB hotlink

Add a remote-icon capability to `GuideAssetCatalog`. When an icon slug is present but no local asset
resolves, produce a `GuideAsset` whose `href` is the AscensionDB icon CDN URL for that slug and
`missing=False`, with `source="ascension_db_remote"`. The exact URL pattern
(e.g. `https://db.ascension.gg/static/images/wow/icons/large/{slug}.jpg`) is verified against a live
db.ascension.gg spell page during implementation before it is hardcoded. `_render_icon_content`
already emits an `<img>` when `href` is present and `missing` is false, so the renderer needs only to
stop forcing the abbreviation fallback when a remote href exists. The two-letter abbreviation remains
the final fallback only when no icon slug exists at all.

Rationale: GitHub Pages CSP permits external `<img>`. M1.14/M1.20 can later localize these assets;
M1.12 gets working icons now without redistributing client files.

### 2. Spec icons on the index

Add an icon to `GuideSpec` (guide_models.py) resolved through the same catalog from the spec's
specialization/signature spell icon (the CoA specialization spell where available, otherwise a
representative selected node's icon). `_render_spec_card` renders it in the card header. Fall back to
a class-initial monogram when no icon resolves. The spec-icon source is chosen in `guide_builder.py`
where spec results are assembled.

### 3. Select-to-include role filter

Change both the initial render and the click handler:

- **Initial render:** "All Roles" is `is-active`/`aria-pressed="true"`; individual role buttons are
  inactive/`aria-pressed="false"`. All cards and role sections are visible.
- **Click a role:** deactivate "All", activate the clicked role, and show only the cards/sections
  whose roles are in the selected set. Additional role clicks add to the set (multi-select).
- **Click "All":** clear the selected role set and show everything.
- **Deselect the last active role:** revert to the "All Roles" state (everything visible).

The visibility rule for cards (`data-role`) and sections (`data-role-section`) is: visible if the
selected set is empty/"All", otherwise visible if it intersects the selected set.

### 4. Disclaimer copy

Replace `FRONT_PAGE_DISCLAIMER` with:

> Theorycrafting projections based on CoA Builder and Ascension data. Further accuracy tuning through
> combat logs/simming may be added if CoA stays online and pending CoA compatibility with
> AscensionLogs.

### 5. Header GitHub link

Introduce a shared header fragment used by both `render_index_html` and `render_spec_html`. It
contains the site title on the left and a light-gray inline GitHub mark on the right linking to
`https://github.com/plowsters/coa_meta_analyzer` (`rel="noopener"`, `target="_blank"`,
`aria-label="View source on GitHub"`). The GitHub mark is inline SVG (no external asset). Hover
brightens from the muted gray to the theme foreground.

### 6. Footer

Introduce a shared footer fragment used by all pages containing:

- `© 2026 CoA Meta Analyzer`
- Non-affiliation notice: "Fan-made theorycraft tool. Not affiliated with or endorsed by Project
  Ascension."
- "Submit an issue" → `https://github.com/plowsters/coa_meta_analyzer/issues`
- "Source on GitHub" → the repository URL
- Builder data-capture date, read from report provenance when available.

### 7. Remove leveling-path boilerplate

Stop rendering the per-step `reason` sentence in `_render_leveling_path_for_build` (drop the
`<span class="muted">{reason}</span>`). The leveling path becomes a clean ordered list of
`Level N — essence chip — node name (with icon)`. Remove the generic fallback string from
`leveling_path.py::_choice_reason` at its source. The `reason` field may remain in the JSON as
optional metadata but is no longer displayed as boilerplate. The `deferred`-step skip stays as-is for
M1.12 and is fixed in M1.15.

## Testing

- Icon resolution: given a node with a DB icon slug and no local asset, the rendered node contains an
  `<img>` with the expected AscensionDB URL, not a two-letter abbreviation. Given a node with no
  slug, the abbreviation fallback is retained.
- Role filter: assert the initial "All Roles"-active markup, and (via the documented visibility rule)
  that selecting a single role hides non-matching sections and that clicking "All" restores them.
- Disclaimer: assert the new copy renders and the db.ascension.gg reference is gone.
- Header/footer: assert the GitHub link, issues link, copyright, and non-affiliation notice render on
  index and spec pages.
- Leveling path: assert the boilerplate reason string no longer appears in rendered output.
- Per the M1.14 test-audit principle, verify these tests assert the new *intended* behavior rather
  than snapshotting current output.

## Exit Criteria

- Node and spec cards display icons; two-letter abbreviations appear only when no icon slug exists.
- The role filter defaults to "All Roles" and works by inclusion.
- The new disclaimer copy is live and no db.ascension.gg reference remains on the front page.
- Every page shows the header GitHub link and the footer with copyright, non-affiliation notice, and
  issues link.
- The leveling path no longer prints the repeated boilerplate reason.
- Full test suite passes and the HTML report smoke command regenerates index and spec pages.
