# Change log

## v1 — 2026-10-10 — Initial tracking and delivery package

**Added**
- `PROJECT_ACTIVITY_INDEX.md` (root entry point to change management)
- `docs/project_tracking/TASK_LOG.md` (work completed and validation)
- `docs/project_tracking/CHANGELOG.md` (file-by-file change history)
- `docs/project_tracking/DECISIONS.md` (decision history)
- `docs/project_tracking/ISSUES_AND_SOLUTIONS.md` (open issues and resolved issues)
- `docs/project_tracking/PACKAGING_POLICY.md` (rules for future packages)
- `docs/project_tracking/PACKAGE_SUMMARY.md` (build and validation overview)
- `docs/project_tracking/PACKAGE_MANIFEST.csv` (file inventory and SHA-256)
- `scripts/package_project.py` (reproducible project ZIP creation)

**Unchanged**
- All application code, SQL/SQLite data, workbook data, Jinja templates, static resources, project README, original handover, historical docs, and Git object history included in the archive.

**Omitted from delivery package only**
- Windows virtual environments (`.venv/`, `.venv-1/`) and temporary generated files. The original user ZIP is not altered.

**Behavioral changes:** None.  
**Database migrations:** None.  
**Excel data modifications:** None.

For each subsequent iteration append date, task ID, files edited/created/deleted, behavior impact, test outcome and package version.

## v2 — 2026-10-10 — Requirements and ambiguity analysis only

**Added**
- `docs/project_tracking/CUTOFF_OPERATOR_REALLOCATION_REQUIREMENTS_REVIEW_v2.md` — requirement-by-requirement code audit, precise questions, verified data/test facts.

**Modified**
- `PROJECT_ACTIVITY_INDEX.md` — point to v2 package and review.
- `docs/project_tracking/TASK_LOG.md` — add TASK-20261010-002.
- `docs/project_tracking/CHANGELOG.md` — this version.
- `docs/project_tracking/DECISIONS.md` — document intentional implementation hold.
- `docs/project_tracking/ISSUES_AND_SOLUTIONS.md` — add unimplemented requirements/blockers.
- `docs/project_tracking/PACKAGE_SUMMARY.md` — new package-specific verification.
- `docs/project_tracking/PACKAGE_MANIFEST.csv` — regenerated checksums inside ZIP.

**Application code, tests, templates, scripts, workbook and SQLite changed:** None.
**New features implemented:** None; awaiting business answers.

## v3 — 2026-10-10 — Supervisor decisions and monthly-pace adequacy audit

**Added:** `docs/project_tracking/OPERATOR_PACE_DATA_AUDIT_v3.md`, `docs/project_tracking/OPERATOR_PACE_SINGLE_DAY_v3.csv`, `docs/project_tracking/CONFIRMED_REQUIREMENTS_AND_OPEN_DECISIONS_v3.md`.

**Updated:** `PROJECT_ACTIVITY_INDEX.md`, `docs/project_tracking/TASK_LOG.md`, `CHANGELOG.md`, `DECISIONS.md`, `ISSUES_AND_SOLUTIONS.md`, `PACKAGE_SUMMARY.md`, generated `PACKAGE_MANIFEST.csv`.

**Behavioral changes / application code changes / workbook edits / SQLite edits / implemented features:** NONE. Decisions were documented, pending material clarifications.

**Data/verification:** Read-only SQLite single-day pace audit, CSV totals checked; packaged hashes checked against v2.


## v4 — 2026-10-10 — Approved supervisor scenario workflow

- **ADD** `calculations/supervisor.py`: fixed safety-buffer effective deadlines, per-truck loading override application, refreshed priority lines ahead, conservative truck/worktype/assignment risk, de-duplicated trailing-30-day pace evidence, experience-qualified and pace-ranked candidates, safe cumulative source/destination preview, subsequent snapshot session scenarios.
- **ADD** `templates/planner.html`: per-truck loading editor, sorted candidate list including unsafe statuses, interactive sequential projected-finish graph, explicit Allocate, session reset, at-risk picking assignments and all-truck overview.
- **ADD** `tests/test_supervisor.py`: 9 dedicated tests covering confirmed rules and state separation.
- **CHANGE** `app.py`: supervisor routes, ephemeral server-memory session allocation store with random browser session key, CSRF checks, current scenario dashboard and truck detail status, old automatic suggestions hidden from confirmation views.
- **CHANGE** `models/database.py`: persistent `truck_loading_override` table and validated get/save/reset functions.
- **CHANGE** `templates/base.html`, `templates/dashboard.html`, `templates/truck_detail.html`: planner links, changed cutoff terminology, scenario caveats.
- **CHANGE** `tests/test_app.py`: updated 4 tests whose old workbook-only status and automatic-suggestion UI assertions conflict with explicitly approved new behavior.
- **CHANGE** `README.md`, `docs/TRUCK_ETC_APPLICATION_GUIDE.md`, `PROJECT_ACTIVITY_INDEX.md`, tracked docs. **ADD** `docs/project_tracking/IMPLEMENTATION_RELEASE_v4.md`.
- **DATA** `data/truck_etc.db`: new empty loading override table; **NO allocation rows** or workbook changes.
- **VERIFIED** 33 targeted tests pass; full suite incomplete after timeout. See TASK-20261010-004.

## v5 — 2026-10-10 13:26 IST — premium reference-inspired dashboard redesign

**Added:** `calculations/dashboard_view.py`, `templates/operators.html`, `static/js/shell.js`, `static/vendor/plotly.min.js`, `static/vendor/README.md`, `tests/test_dashboard_ui.py`, `docs/references/dashboard-ui-reference-20261010.png`, `docs/project_tracking/DASHBOARD_REDESIGN_RELEASE_v5.md`.

**Modified:** `app.py`, `templates/base.html`, `templates/dashboard.html`, `templates/planner.html`, `templates/truck_detail.html`, `templates/operator_detail.html`, `static/css/style.css`, `static/js/dashboard.js`, `tests/test_app.py`, `README.md`, `PROJECT_ACTIVITY_INDEX.md`, and all relevant project tracking logs/package summary/manifest. Nonfunctional dark header replaced by functional white SaaS shell; new operator route/read-only CSV route, snapshot-specific trend/throughput/metric UI, functional search/sort/risk filters, mobile navigation. Other page headers updated and linked. Loading/time/ETC/reallocation logic unchanged. Existing source databases/workbooks unchanged.

**Issues corrected:** old table had excessive columns/no search/sort; desktop-only dark layout; no functional operators directory/export; ambiguous prediction probability; no source-safe truck staffing field; charts relied on Plotly CDN; 1024px KPI needed two-column breakpoint; old tests asserted obsolete navbar wording.

**Verification:** 33 targeted tests passed, JS syntax/Python compile; desktop screenshot inspected, 1440/1024/390px DOM responsive checks; ZIP CRC + SHA manifest performed on packaging. Full suite not asserted.

## v6 — 2026-10-11 — Unified dashboard design for every application page

**Added:** `templates/components/ui.html`, `static/js/planner.js`, `static/vendor/bootstrap.min.css`, `static/vendor/bootstrap.bundle.min.js`, `static/vendor/BOOTSTRAP_LICENSE.txt`, `tests/test_design_system_v6.py`, `docs/project_tracking/UI_CONSISTENCY_RELEASE_v6.md`, `docs/images/v6-planner-desktop.png`, `docs/images/v6-truck-desktop.png`, `docs/images/v6-operator-desktop.png`.

**Modified:** `templates/base.html`, `templates/planner.html`, `templates/truck_detail.html`, `templates/operator_detail.html`, `templates/operators.html`, `static/css/style.css`, `static/js/truck_detail.js`, `static/js/shell.js`, `README.md`, `PROJECT_ACTIVITY_INDEX.md`, `docs/project_tracking/{TASK_LOG,CHANGELOG,DECISIONS,ISSUES_AND_SOLUTIONS,PACKAGE_SUMMARY}.md`, and newly generated in-package `PACKAGE_MANIFEST.csv`.

**Unchanged:** Flask routes/server code, calculation engine, formulas, data models, source workbook, baseline delivered SQLite data. No API/database/WMS/allocation behavior changed.

**Verified:** 42 focused tests pass; five page renders at 1440, 1024, 390 pixels with no JS exceptions/page-wide overflow; mobile drawer, Bootstrap tabs, candidate search and operator directory filter functional. Full-suite timeout is NOT a pass. See `UI_CONSISTENCY_RELEASE_v6.md` for breakdown and limitations.


## v7 — 2026-10-12 — Uploaded source status audit (analysis-only)

- **New:** `docs/project_tracking/CURRENT_STATUS_AUDIT_v7.md` with v6 comparison, risk findings and validation evidence.
- **Updated documentation:** `docs/project_tracking/TASK_LOG.md`, `CHANGELOG.md`, `DECISIONS.md`, `ISSUES_AND_SOLUTIONS.md`, `PACKAGE_SUMMARY.md`, `PROJECT_ACTIVITY_INDEX.md`, `README.md`; regenerated in-ZIP manifest.
- **Generated derived data:** `data/truck_etc.db` was missing from uploaded `SMD-main.zip` and built fresh from unmodified `data/workbook.xlsx` using the existing engine. No saved scenario allocations included.
- **Important:** The uploaded source itself differs from v6 in seven existing files plus one new test. These were not authored or modified by v7; see exact inventory in `CURRENT_STATUS_AUDIT_v7.md`.
- **Not changed in v7:** Flask routes, calculation formulas, eligibility implementation, database model definitions, HTML UI source, JS, CSS, workbook data, source tests.


## v8 — 2026-10-12 — Ten active synthesized trucks and explicit safe workforce-allocation scenarios

**New:** `scripts/build_ten_truck_demo.py` (artifact_tool synthesizer), inactive `INFO/historical/historical_33_trucks_reference.xlsx`, `tests/test_ten_truck_workflow_v8.py`, `docs/project_tracking/IMPLEMENTATION_RELEASE_v8.md`.

**Modified application/calculations:** `app.py`, `config.py`, `.env`, `calculations/excel_io.py`, `calculations/operator.py`, `calculations/supervisor.py`, `models/models.py`, `models/database.py`. Migrate away from permanent advisory allocation table, preserve loading override table, implement exact safe min-staffing and preview scoping, correct NO RATE treatment, show synthesized data provenance.

**Modified source data:** `data/workbook.xlsx` (only 10 active synthesized trucks, 129 orders, 283 lines), `data/truck_etc.db` (clean rebuilt 18-snapshot corresponding data, no confirmed allocation). Historical 33-truck workbook stored separately and **never part of the active UI query path**.

**Modified UI:** `templates/planner.html`, `static/js/planner.js`, `templates/truck_detail.html`, `templates/operator_detail.html`. Show minimum required, feasibility explanations, candidate availability/ranking, before/after source and destination cutoff charts, explicit allocate/reset, dynamic current scenario.

**Modified tests:** `tests/conftest.py`, `tests/test_data_integrity.py`, `tests/test_app.py`, `tests/test_supervisor.py`, `tests/test_dashboard_ui.py`, `tests/test_design_system_v6.py`, `tests/test_pickup_risk_feature.py`. Archived source used for historical parity fixture; loading override fixture resets to prior value; obsolete 33-truck route expectations updated.

**Documentation:** `README.md`, `PROJECT_ACTIVITY_INDEX.md`, `docs/project_tracking/IMPLEMENTATION_RELEASE_v8.md`, `TASK_LOG.md`, `CHANGELOG.md`, `DECISIONS.md`, `ISSUES_AND_SOLUTIONS.md`, `PACKAGE_SUMMARY.md`, generated SHA-256 manifest. Old documents maintained for history but marked as superseded.

**Not deployed or persisted:** No WMS writes, no confirmed operator allocation in workbook/SQLite. **Removed from release tooling:** temporary local experiment scripts `_explore_synth.py`, `_explore_synth2.py`; synthesis rationale preserved in release document.

**Test results:** 44/44 focused pytest passes; static Python/JS syntax passes. Full historical parity run timed out and browser E2E not executed.


## v9 — 2026-10-12 — Minimal truck ready-time view and calculated operator gap
**Added:** `calculations/truck_detail_view.py`, `tests/test_truck_detail_v9.py`, v9 release report, v9 desktop/mobile browser-rendered screenshots.
**Modified:** `app.py` truck detail payload/card projection adapter, `templates/truck_detail.html` operator-gap card and two-series chart, `static/js/truck_detail.js` chart-only renderer, release metadata and cumulative logs.
**Removed from truck-detail UI only:** three requested history/throughput/picker charts and obsolete JS references. Raw data, historical trend calculations and unrelated dashboard metrics preserved.
**No business-logic change:** risk, ETC, conservative rates, fixed safety margin, exact min-staffing solver, source safety, preview/Allocate session semantics, source workbook and shipped SQLite remain identical to v8.
**Validation:** 51/51 selected checks; offline actual-HTML Chromium desktop/mobile; SHA-256/ZIP CRC on package build. See `TRUCK_DETAIL_SIMPLIFICATION_RELEASE_v9.md`.


## v10 — 2026-10-12 — Truck ready time: before vs after adding operators
**Added:** `calculations/ready_comparison.py` (read-only before/after comparison), `templates/components/ready_chart.html` (shared panel), `static/js/ready_chart.js` (shared renderer), `tests/test_ready_chart_v10.py` (21 tests), `READY_TIME_CHART_RELEASE_v10.md`, `docs/images/v10-*.png`.
**Modified:** `app.py`, `calculations/supervisor.py`, `config.py`, `.env` (`SAFETY_BUFFER_MINUTES=10`), `models/database.py`, `templates/truck_detail.html`, `templates/planner.html`, `templates/dashboard.html`, `static/js/planner.js`, `static/css/style.css`, `tests/test_truck_detail_v9.py`, `tests/test_design_system_v6.py`, `tests/test_dashboard_ui.py`, `data/truck_etc.db` (regenerated: stores `LOADING_MINUTES`), `README.md`, `PROJECT_ACTIVITY_INDEX.md`, `PROJECT_HANDOVER_CURRENT_STATUS.txt`, `docs/TRUCK_ETC_APPLICATION_GUIDE.md` (v10 notice), tracking logs.
**Removed:** `static/js/truck_detail.js` and the per-area "When each area finishes vs the pick cutoff" chart (replaced by the shared truck-level chart; per-area values remain in the Work types table). The planner's old "Conservative completion projection" chart and summary boxes are replaced by the same shared chart; the source-impact chart is kept.
**Unchanged:** `data/workbook.xlsx`; ETC, rate, conservative envelope, source safety and minimum-staffing formulas; session-only allocations.
**Validation:** full suite 184 passed; Chromium 1440 px and 390 px against the running app with no JS errors and no page overflow.


## v11 — 2026-10-13 — Consistent At Risk status: corrected demo labor time + picking-time pace
**Added:** `calculations/pace.py`, `scripts/rescale_demo_labor.py`, `tests/test_picking_pace_v11.py`, `STATUS_CONSISTENCY_RELEASE_v11.md`, `docs/images/v11-*.png`.
**Modified:** `data/workbook.xlsx` (LM005S1 TOTALTIMEINSEC/TOTALTIMEINMIN/DATA_TYPE/title, SCENARIO_README; all other sheets byte-identical), `data/truck_etc.db` (rebuilt), `calculations/supervisor.py` (pace basis; picking-time baseline rates; `pace_basis` in state), `calculations/ready_comparison.py` (stop recommending moves when the slowest area cannot be fixed; exact early/late texts), `config.py` + `.env` (`PACE_BASIS`, `PACE_GAP_CAP_MINUTES`), `app.py` (operator directory/profile planning pace), `templates/operator_detail.html`, `templates/operators.html`, `templates/planner.html`, `templates/components/ready_chart.html`, `static/css/style.css`, tests (`conftest.py` loading-override fixture; `test_ten_truck_workflow_v8.py`, `test_truck_detail_v9.py`, `test_ready_chart_v10.py`, `test_app.py` updated for the corrected data), README and tracking docs.
**Unchanged:** Excel-equation engine (`etc.py`, `truck.py`, `uncertainty.py`, `reallocation.py`), deadlines, source safety, minimum-staffing search, session-only allocations.
**Validation:** full suite 193 passed; Chromium check of dashboard, truck, operator and operators pages.


## v12 — 2026-10-13 — Temporary Operator Allocation (reallocation first)
**Added:** `calculations/temporary.py`, `calculations/bands.py`, `tests/test_temporary_operators_v12.py`, `TEMPORARY_OPERATORS_RELEASE_v12.md`, `docs/images/v12-*.png`.
**Modified:** `calculations/supervisor.py`, `calculations/ready_comparison.py`, `calculations/truck_detail_view.py`, `calculations/dashboard_view.py`, `app.py`, `config.py`, `.env` (`TEMP_OPERATOR_PACE_PCT=100`, `TEMP_OPERATOR_MAX=10`), `templates/planner.html`, `templates/operators.html`, `templates/components/ready_chart.html`, `static/js/ready_chart.js`, `static/js/planner.js`, `static/css/style.css`, `tests/test_ready_chart_v10.py` (3 tests updated for the new rule), README and tracking docs.
**Unchanged:** workbook, SQLite contents, Excel-equation engine, picking-time pace, deadlines, source safety, reallocation search.
**Validation:** full suite 206 passed; Chromium walk-through at 1440 px and 390 px.


## v13 — 2026-10-13 — Environmental Conditions & Workforce Planning (context only)
**Added:** `models/environment.py`, `calculations/environment.py`, `calculations/environment_analysis.py`, `templates/environment.html`, `static/js/environment.js`, `tests/test_environment_v13.py`, `ENVIRONMENT_DESIGN_v13.md`, `ENVIRONMENT_RELEASE_v13.md`, `ENVIRONMENT_HARDWARE_PROPOSAL_v13.md`, `PROJECT_STATUS_v13.md`, `docs/images/v13-*.png`.
**Modified:** `app.py` (Environment page and actions, sensor and zones API, context helpers; dashboard card, truck and planner context columns), `config.py` + `.env` (`ENV_*` settings), `requirements.txt` (`tzdata` on Windows), `.gitignore` (`data/environment.db`), `templates/base.html`, `templates/dashboard.html`, `templates/truck_detail.html`, `templates/planner.html`, `static/css/style.css`, `tests/conftest.py` (separate test environment database, `clean_env` fixture), README, guide notice and tracking docs.
**Unchanged:** workbook, `truck_etc.db` contents, ETC engine, pace, deadlines, reallocation and temporary-operator logic.
**Validation:** full suite 246 passed (206 existing + 40 new); Chromium check at 1440 px and 390 px.


## v14 — 2026-10-14 — Calculated At Risk scenario and realistic status evolution
**Added:** `scripts/build_pressure_scenario_v14.py` (deterministic scenario generator), `INFO/historical/ten_truck_v13_baseline.xlsx` (frozen v13 workbook, generator input), `tests/test_pressure_scenario_v14.py`, `PRESSURE_SCENARIO_RELEASE_v14.md`, `docs/images/v14-*.png`.
**Modified (data):** `data/workbook.xlsx` regenerated — late add-on OTC orders 69001–69004 for SH0908-1034 and SH0908-1069 (32 lines), 20:30 departures for those two trucks, WT2 picking after 18:15 re-simulated, mmathis overtime to 20:25, SCENARIO_README notes; all new or changed rows labelled `SYNTHETIC v14`. `data/truck_etc.db` rebuilt from it.
**Modified (code):** `calculations/supervisor.py` (PICK CUTOFF PASSED when conservative ready is after the pick cutoff; scenario replay of confirmed allocations at later snapshots with destination gain and source-area reopening; per-truck explanation), `calculations/dashboard_view.py` (departed status from scenario counts; Pick cutoff passed category; wording), `calculations/truck_detail_view.py`, `calculations/bands.py` (band labels), `app.py` (status history, explanations, risk labels), `templates/truck_detail.html` (pick cutoff, why-now, scenario strip, status history), `templates/dashboard.html`, `templates/planner.html`, `templates/components/ready_chart.html`, `static/css/style.css`.
**Modified (tests):** `tests/conftest.py` and the v8–v13 test files whose anchors depended on v13 data (same behaviour, re-derived values).
**Unchanged:** Excel-equation engine formulas, picking-time pace, deadlines, safety buffer, reallocation search, temporary operators, environment feature.
**Validation:** full suite 263 passed (15 new v14 cases; v8–v13 tests re-derived where the data changed); Chromium walk-through at 1440 px and 390 px.
