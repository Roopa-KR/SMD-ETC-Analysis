# v6 — Consistent SaaS design across every application page

**Date:** 2026-10-11 (IST)  
**Source:** `truck-etc-app-updated-20261010-v5.zip`  
**Requested:** Apply the visual language, navigation, styling, charts, tables and interactions from the v5 reference-inspired dashboard consistently across the entire Truck ETC / LMS web app.

## Scope and routes

The app has **five HTML page routes** (plus an export endpoint); all five use the shared `templates/base.html` sidebar and topbar. For each page:

| Page | Route | v6 interface work |
| --- | --- | --- |
| Dashboard | `/` | Preserved existing reference-inspired layout and visualizations; unified shared Bootstrap styling and navigation icon fallback |
| Truck detail | `/truck/<shipment_id>` | Matching page intro, real scenario-status badge, top action buttons, snapshot/deadline chips, seven KPI cards, explanation panels, soft white cards, consistent scrollable tables and tabs, redesigned Plotly chart palette |
| Operator directory | `/operators` | Shared page intro/action, neutral provenance notice, consistent table container, functional client-side operator/worktype search, active operator navigation |
| Operator profile | `/operator/<operator_name>` | Shared intro/action, four styled KPI cards, provenance notice, worktype familiarity, eligibility and assignment tables, structured workload panel, readable histories |
| Workforce allocation | `/planner` | Shared intro, compact filter strip, loading-time editor, readable pace-ranked candidate table with functional search, original/projected/required comparison, refined projection chart, clear confirmation and session-state panels, flagged assignments and all-truck table |

The existing `/export/trucks.csv` route is not an HTML page and was retained untouched.

## Exact file changes

**Added**
- `templates/components/ui.html`: reusable `intro`, `panel`, and `metric` presentation macros.
- `static/js/planner.js`: browser-only forecast drawing, truck selector, operator filter and explicit confirmation dialog. All input numbers come from the existing Flask context.
- `static/vendor/bootstrap.min.css`, `bootstrap.bundle.min.js`, `BOOTSTRAP_LICENSE.txt`: locally bundled **Bootstrap 5.3.6**, a patch-level update of the v5 Bootstrap 5.3.3 CDN source.
- `tests/test_design_system_v6.py`: page-shell, component, link, form-action and static-asset regression cases.
- `docs/project_tracking/UI_CONSISTENCY_RELEASE_v6.md`: this report.
- `docs/images/v6-{planner,truck,operator}-desktop.png`: diagnostic headless-browser render previews. Bootstrap icon/font CDN unavailable during isolated render; decorative icons may be absent there but responsive layout is representative.

**Modified**
- `templates/base.html`: active navigation context on truck drill-down; local Bootstrap CSS/JS; built-in SVG for the brand, mobile open and mobile close icons.
- `templates/planner.html`: restyled all sections, preserved form names/CSRF and `plot` data, clarified that overall target-worktype status spans more trucks than the earliest-deadline truck graphed.
- `templates/truck_detail.html`: new page header, status/deadline context, themed KPI cards, styled tables/graphs/tab panels and links; preserved chart payload and all original operational data.
- `templates/operator_detail.html`: restyled KPI, provenance, workload and eligibility sections; replaced fragile `history.back()` with existing directory link.
- `templates/operators.html`: matching directory header, consistent cards/tables, functional in-page search.
- `static/css/style.css`: append v6 shared design tokens, typography, surfaces, controls, informative banners, KPI grids, dense but legible tables, breakpoints and empty states. Existing dashboard selectors preserved.
- `static/js/truck_detail.js`: restyle four Plotly visualizations, render worktype readiness values as actual timestamps instead of a mixed numeric/date bar, add clear buffered cutoff marker; no arithmetic/inputs changed.
- `static/js/shell.js`: add directory filter; retain global search shortcut, snapshot navigation and mobile drawer.
- `README.md`, `PROJECT_ACTIVITY_INDEX.md`, and project-tracking logs (task, change, decisions, issues, package summary, checksums).

**Unchanged:** `app.py`, all `calculations/*.py`, `models/*.py`, `data/workbook.xlsx`, and (after restoring the test-mutated working copy) the exact original v5 `data/truck_etc.db`. No database migration, API response change, formula change, or staffing allocation write is included.

## Design decisions

1. Continue Flask + Jinja + Bootstrap 5 + Plotly, rather than introducing React or replacing page routes.
2. Use light-gray #F5F6FA canvas, white 15px-radius cards, #2563EB primary, subtle shadows and muted semantic warning/success colors.
3. Keep every pre-existing page's data and working actions; standardize presentation through shared macros/CSS rather than replicating static sample widgets.
4. Bundle Bootstrap CSS/JS locally for offline shell behavior. Leave Bootstrap Icons and optional Inter font as CDN dependencies; system-font fallback remains functional.
5. The planner's overall conservative status includes **all open trucks** of the selected worktype, whereas the existing graph displays the **earliest-deadline truck**. Display a clear explanation rather than changing or inventing business rules.
6. Native inline SVG symbols for menu open/close and logo remain visible even without external icon fonts.

## Verification

- **42/42 focused pytest tests passed:** `tests/test_design_system_v6.py`, `tests/test_dashboard_ui.py`, `tests/test_app.py`, `tests/test_supervisor.py`, `tests/test_etc.py`, and `tests/test_truck.py`.
- Headless Chromium browser visually rendered actual Flask-generated markup with local CSS/JS and bundled Plotly for **five pages at 1440px desktop, 1024px tablet, and 390px mobile** (15 page/view combinations).
- In the above 15 checks: **no JavaScript exceptions, no page-level horizontal overflow**. Shared active sidebar links, four truck-detail charts, planner chart, operator directory filtering, candidate search, Bootstrap tab switching and mobile drawer transitions were exercised.
- JavaScript and all template routes were also tested via Flask test client (HTTP 200) and local Bootstrap/JS asset routes (HTTP 200).
- Original v5 workbook and SQLite hashes are compared before delivery, and the ZIP CRC and SHA-256 manifest are validated.

**Verification caveat:** Direct headless Chromium navigation to `127.0.0.1` is restricted by this environment, so browser visuals are generated from the real Flask route HTML using isolated `set_content()` plus the same local CSS/JS. They are not a fully served browser network smoke test. The **full** historic pytest suite exceeded the execution limit and was **not** marked passed. Existing pandas FutureWarnings remain; no formula changes were made to silence them.

## Operational limitations preserved

- No live WMS integration or real authentication; supervisor allocations remain temporary server-memory scenarios.
- Historical data spans only one day, so the 30-day pace source is not true monthly coverage.
- Bootstrap Icons and optional Inter use external font/style resources. Core layout, Bootstrap controls, built-in SVG mobile drawer, Plotly charts and search function with local assets.
- The planner's selected earliest truck finish may precede its deadline even when overall worktype status remains AT RISK because another truck in that worktype misses its deadline. This is now explained alongside the chart, not recalculated.

## Local run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. Browse dashboard, Trucks → truck detail, Operators → profile and Workforce allocation with the shared header, filters and navigation.
