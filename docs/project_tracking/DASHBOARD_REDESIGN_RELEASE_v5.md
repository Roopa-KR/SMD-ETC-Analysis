# Version 5 — Truck ETC dashboard redesign

**Date:** 2026-10-10  
**Reference:** `docs/references/dashboard-ui-reference-20261010.png` supplied by user.  
**Baseline:** `truck-etc-app-updated-20261010-v4.zip`.  
**Scope:** Flask/Jinja/HTML/CSS/JavaScript UI, read-only view aggregation,
CSV export and functional operators directory. No ETC/reallocation formula change.

## Why these components were changed

| File | Change and rationale |
|---|---|
| `templates/base.html` | Replaced dark Bootstrap navbar with white fixed sidebar, operational nav, responsive mobile drawer, global truck search, 1-day replay date, snapshot picker, insights shortcut, honest non-authenticated supervisor avatar. Other pages inherit the shell. |
| `templates/dashboard.html` | Reference-inspired heading, four KPI cards, 65/35 analytics composition, area trend, operational activity, segmented on-time share gauge, rules-based insights, searchable/sortable/filterable truck table and preserved original ETC comparison in an expandable section. |
| `static/css/style.css` | SaaS light design tokens, 236px sidebar, blue (#2563EB) accent, 15px cards, subtle shadows, large whitespace, hover/focus states and responsive 4/2/2 KPI layout. Legacy styles remain for older tables. |
| `static/js/dashboard.js` | Plotly area/bar charts from JSON, SVG gauge using the actual status distribution (not fictional thresholds), accessible rows, client-side sorting, clickable truck rows and original ETC chart on expansion. |
| `static/js/shell.js` (added) | Mobile sidebar open/close, Escape/backdrop handling, snapshot navigation, '/' keyboard focus for search. |
| `calculations/dashboard_view.py` (added) | Pure read-only mapping of baseline truck rows and current supervisor scenario to presentation fields, explicit risk classification, factual rules-based insights. No engine modifications. |
| `app.py` | New GET `/operators` and `/export/trucks.csv` endpoints; dashboard snapshot history recomputes conservative scenario state for each observed snapshot; KPI/chart/table all sourced from same state. CSV includes search + risk filters; no new database schema. |
| `templates/operators.html` (added) | Functional operator directory based on existing worker activity and measured available-history pace, linking to existing profiles. |
| `templates/planner.html` | Added loading-settings anchor and appropriate header title. Saved loading-time and allocation controls unchanged. |
| `templates/truck_detail.html` | Applied correct shared header title and local Plotly bundle, no changes to truck or ETC content. |
| `templates/operator_detail.html` | Applied correct shared header title, no changes to operator-calculation content. |
| `static/vendor/plotly.min.js` (added) | Local Plotly bundle prevents a chart-rendering dependency on Plotly CDN. |
| `static/vendor/README.md` (added) | Vendor source/license, remaining CDN requirements, font redistribution avoided. |
| `tests/test_dashboard_ui.py` (added) | Verifies factual KPIs, snapshot trend, search/filter/export, operator routes and asset/navigation links. |
| `tests/test_app.py` | Modernized dark-navbar copy assertions to refer to the new interface while retaining functional smoke checks. |
| `docs/references/dashboard-ui-reference-20261010.png` (added) | Original supplied visual reference retained for future UI iterations. |
| Project tracking and README | Complete v5 audit trail and setup/feature explanation. |

## Metric definitions and non-inventions

- **Total trucks:** number of current truck records (33 on this replay).
- **On-time:** supervisor-scenario `ON TIME`, `ALL PICKED`, or baseline `DEPARTED COMPLETE` (the last category is used only for departed records).
- **At risk:** conservative estimated finish misses `departure - per-truck loading - 10 minute safety`, but deadline has not yet passed.
- **Critical/delayed:** conservative scenario `CUTOFF PASSED` or baseline departed with work left behind. Do not artificially count `NO RATE` as a known delay.
- **Unknown/pending:** no demonstrated rate or work-release evidence. Displayed explicitly rather than classified as on time or critical.
- **On-time share (gauge and trend):** `100 * healthy_count / all_trucks` at each actual recorded snapshot. This is **not** a calibrated probability; no machine-learning prediction has been added. The gauge segments encode actual current status mix, not invented thresholds.
- **Picking activity:** `sum(TI102C pick lines completed by current snapshot) - sum(completed by preceding snapshot)` using cumulative `truck_result.lines_picked` across shipments. First snapshot has no preceding 15-minute interval and is omitted from the bars.
- **Staffed areas in truck table:** count of worktype areas with open work and nonzero team resources, NOT personally assigned operators to that truck. No unsupported truck-specific worker assignment is invented.
- **Trends:** limited to available observed snapshots up to selected time; no forecast or future work stream is fabricated. The active per-supervisor confirmed scenario and persisted per-truck loading overrides are included in re-evaluation.
- **Search:** exact string contains match over shipment ID, current status and bottleneck worktype. Risk filter uses the explicit display categories. Export uses same current snapshot/scenario and filter conditions.
- **Profile avatar:** visual marker of supervisor planning view; NOT an authenticated logged-in user.
- **Insights:** rule-based counts only; no AI/LLM backend or autonomous warehouse action.

## Navigation / responsiveness

All enabled links lead to real Flask routes or real in-page sections. Other than the added `/operators` read-only directory and CSV route, existing routes `/`, `/truck/<shipment_id>`, `/operator/<operator_name>` and `/planner` are preserved. Individual truck details remain accessible via table rows; loading settings are located in the existing planner.

At desktop >=1200px, 4 KPI cards; tablets ~701–1199px, 2 per row; mobile <=700px, 2 per row with stacked analytics cards, full-width table-search and horizontally scrolling truck table. Side navigation collapses below 992px, with usable toggle, backdrop and Escape handling. Respect reduced-motion accessibility settings.

## Tests and verification

- **33/33 passed** in a targeted run:
  `PYTHONPATH=... pytest -q tests/test_app.py tests/test_supervisor.py tests/test_dashboard_ui.py tests/test_etc.py tests/test_truck.py tests/test_reallocation.py --disable-warnings --maxfail=1`
- `node --check static/js/dashboard.js` and `node --check static/js/shell.js`: passed.
- `python -m py_compile app.py calculations/dashboard_view.py`: passed.
- Manual Flask test client: dashboard for multiple snapshots / filtered search, `/operators`, `/planner`, truck/profile details and exported CSV all returned 200.
- Headless Chromium DOM/CSS/JS check on local test HTML: no page JavaScript exceptions in responsive shell checks; 1440px desktop and 390px mobile widths have no document-wide horizontal overflow; mobile drawer open and close functions. 1024px tablet breakpoint adjusted after first review. Desktop Plotly line/activity chart rendering was visually inspected from a local render. The isolated browser environment blocked direct HTTP navigation to `127.0.0.1`, so a genuine served-page end-to-end/browser network test could not be completed in that sandbox; offline DOM rendering from Flask-generated HTML was used as a substitute. Do not mistake this for exhaustive cross-browser validation.
- **Full historical Excel parity suite:** not rerun in this v5 UI-only change; all calculation modules other than new view-only helper were preserved unchanged. Do not claim complete suite passed.
- Original `data/workbook.xlsx` and the preexisting cached SQLite database are preserved; no new schema/data writes in the delivered archive.

## Known limitations

1. Data is a single replay day, so the 30-day operator rate is not reliable monthly evidence. The UI links to the existing provenance and source-safety workflows.
2. CDN Bootstrap CSS/JS, Bootstrap Icons and optional Google Inter font still require internet access; Plotly is now local. Source app already used external Bootstrap.
3. Server starts with Flask debug mode when executing `python app.py`, inherited from v4; not safe as a production deployment without a production web server, authentication and authorization.
4. The existing temporary per-supervisor operator allocations are RAM-only and not shared across app worker processes or persisted. This UI change does not modify that contract.
5. Simulated truck departures and experience assumptions are still demo data, separately labeled in existing docs.
6. Snapshot date selection covers only the data available (one date), not an invented arbitrary date range.
