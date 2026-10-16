# Truck ETC — Project activity index

**CURRENT PACKAGE:** `SMD-main-updated-20261014-v14.zip` (2026-10-14). v14: calculated At Risk pressure scenario, realistic status evolution, allocation replay with source-area recalculation, status history ([`PRESSURE_SCENARIO_RELEASE_v14.md`](docs/project_tracking/PRESSURE_SCENARIO_RELEASE_v14.md)); 263 tests pass.
**PREVIOUS:** `SMD-main-updated-20261013-v13.zip` (2026-10-13). v13: Environmental Conditions & Workforce Planning, context only ([`ENVIRONMENT_RELEASE_v13.md`](docs/project_tracking/ENVIRONMENT_RELEASE_v13.md), [`PROJECT_STATUS_v13.md`](docs/project_tracking/PROJECT_STATUS_v13.md), [`ENVIRONMENT_HARDWARE_PROPOSAL_v13.md`](docs/project_tracking/ENVIRONMENT_HARDWARE_PROPOSAL_v13.md)); 246 tests pass.
**PREVIOUS:** `SMD-main-updated-20261013-v12.zip` (2026-10-13). v12: Temporary Operator Allocation after safe reallocation ([`TEMPORARY_OPERATORS_RELEASE_v12.md`](docs/project_tracking/TEMPORARY_OPERATORS_RELEASE_v12.md)); 206 tests pass.
**PREVIOUS:** `SMD-main-updated-20261013-v11.zip` (2026-10-13). v11: picking-time planning pace + corrected demo labor time; At Risk status consistent across snapshots ([`STATUS_CONSISTENCY_RELEASE_v11.md`](docs/project_tracking/STATUS_CONSISTENCY_RELEASE_v11.md)); 193 tests pass.
**PREVIOUS:** `SMD-main-updated-20261012-v10.zip` (2026-10-12)
**CURRENT STATE:** Ten-truck synthetic replay; shared before/after truck ready-time chart (green/yellow/red vs pick cutoff and safety buffer, blue ETC) on truck detail and planner; configurable safety buffer; nonpersistent supervisor-session allocations. Full suite 184 passed.
**LATEST RELEASE:** [`docs/project_tracking/READY_TIME_CHART_RELEASE_v10.md`](docs/project_tracking/READY_TIME_CHART_RELEASE_v10.md). Data/workflow baseline: [`IMPLEMENTATION_RELEASE_v8.md`](docs/project_tracking/IMPLEMENTATION_RELEASE_v8.md).

Change tracking: [`TASK_LOG.md`](docs/project_tracking/TASK_LOG.md), [`CHANGELOG.md`](docs/project_tracking/CHANGELOG.md), [`DECISIONS.md`](docs/project_tracking/DECISIONS.md), [`ISSUES_AND_SOLUTIONS.md`](docs/project_tracking/ISSUES_AND_SOLUTIONS.md), [`PACKAGE_SUMMARY.md`](docs/project_tracking/PACKAGE_SUMMARY.md) and generated SHA-256 manifest in `PACKAGE_MANIFEST.csv`.

**Older notes follow for historical continuity only; they do not describe v8's current behavior.**

---

# Truck ETC — project activity index

**Tracking introduced:** 2026-10-10 11:45:36 IST  
**Baseline:** `truck-etc-app.zip` as supplied by the user on 10-Oct-2026  
**Current package:** `truck-etc-app-updated-20261010-v3.zip`

This project maintains an auditable change record in `docs/project_tracking/`:

| File | Use |
|---|---|
| `TASK_LOG.md` | Chronological record of completed work and validation |
| `CHANGELOG.md` | Every addition/edit/deletion to delivered project files |
| `DECISIONS.md` | Important decisions and reasons |
| `ISSUES_AND_SOLUTIONS.md` | Identified issues, statuses, and implemented fixes |
| `PACKAGING_POLICY.md` | Packaging rules, limitations, and next-step instructions |
| `PACKAGE_SUMMARY.md` | Version details and verification summary |
| `PACKAGE_MANIFEST.csv` | Per-file size and SHA-256 for every other packaged file |

**How to continue:** Use the latest ZIP as the source for subsequent work; after any task update the records, implement and verify requested changes, increment the package version, and deliver the ZIP in the same response. Files are not modified automatically between conversations/requests.

Existing documentation, calculation source, Excel workbooks, SQLite data, and Git metadata are preserved as supplied. At baseline, no application behavior or dataset values were modified. The bulky duplicated virtual environments and transient Python/test cache files have been omitted because they are reconstructible from `requirements.txt`.

## Latest task (v2)

- Requirement audit for minimum cutoff buffer, synthetic operator paces, adjustable loading time, risk detection, ranked candidate lists, sequential previews and explicit confirmation.
- **Review:** `docs/project_tracking/CUTOFF_OPERATOR_REALLOCATION_REQUIREMENTS_REVIEW_v2.md`.
- **State:** New feature development blocked on Q1–Q9, **no application logic or data changed**.
- **Validation performed:** 15 relevant existing tests passed; read-only stored-data checks.

## Latest task (v3)

- Confirmed 10-minute fixed source/target buffer, persisted per-truck 30-minute default loading override, simulated experience eligibility, conservative source safeguards, individual assignment risk goal, sequential previews, explicit allocation and follow-up snapshot effects.
- Audited 2026-09-08 labor/completions: one day only (not monthly), 12 workers, 14 labor worktype combinations with 12 observed completed pairs, and 625 linked assignments.
- **Open questions:** `docs/project_tracking/CONFIRMED_REQUIREMENTS_AND_OPEN_DECISIONS_v3.md` (A–E).
- **Pace calculation and input gaps:** `docs/project_tracking/OPERATOR_PACE_DATA_AUDIT_v3.md` + `OPERATOR_PACE_SINGLE_DAY_v3.csv`.
- **No implementation yet:** User requests confirmation before uncertain business formulas/assignment timing are coded.


## v4 current state — 2026-10-10

**Latest:** `truck-etc-app-updated-20261010-v4.zip`. Approved supervisor planning implementation added. See `docs/project_tracking/IMPLEMENTATION_RELEASE_v4.md` for requirements and evidence, `TASK_LOG.md` entry TASK-20261010-004 for every step, `CHANGELOG.md` for files, `DECISIONS.md` for approved rules, and `ISSUES_AND_SOLUTIONS.md` for open risks. New workflow route: `/planner`. The original workbook is not modified. Confirmed allocations live only in Python process memory keyed by supervisor session; loading overrides persist in SQLite. **33 targeted tests passed; full suite unverified after timeout.**

## Version 5 — premium Truck ETC dashboard (2026-10-10)
- New design delivered on existing Flask stack; no changes to golden workbook/SQLite calculations.
- **Primary review:** `docs/project_tracking/DASHBOARD_REDESIGN_RELEASE_v5.md` (file map, live URLs, KPI semantics, interactions, responsiveness, tests, issues).
- **Reference screenshot:** `docs/references/dashboard-ui-reference-20261010.png`.
- **Verification:** 33 targeted tests; local DOM responsive / desktop chart inspect; direct HTTP browser automation sandbox-blocked.
- **Tracked output:** `truck-etc-app-updated-20261010-v5.zip` with source/data/docs/images/history and internal SHA-256 file manifest.

## Latest release — v6 consistent application-wide UI (2026-10-11)

- **New:** Reference-inspired SaaS design now covers dashboard, workforce planner, truck details, operator directory, and operator profiles, with shared headings, metrics, filters, charts, responsive layouts and functional navigation.
- **Implementation/audit:** `docs/project_tracking/UI_CONSISTENCY_RELEASE_v6.md` lists each file changed, interactions, browser and test checks, preserved source data and remaining issues.
- **Verification:** 42 focused tests passed; 15 page-device visual renders. Full historic suite exceeded execution limit; no full-suite pass claimed.
- **Tracked deliverable:** `truck-etc-app-updated-20261011-v6.zip` with latest source/data/documentation/manifest.


## Current uploaded source review — v7 (2026-10-12)

**Start here:** `docs/project_tracking/CURRENT_STATUS_AUDIT_v7.md` documents the uploaded SMD-main source's actual status, new pickup-risk APIs, differences from v6, failed reset/reassign reproduction, explicit conflicts with approved business rules, and verification limitations. All older handovers are retained as historical artifacts. Version 7 contains the uploaded application's existing code **unchanged**, plus updated audit documents and a clean regenerated SQLite cache.


## v9 (2026-10-12): Clean Truck-Detail cutoff view
- Removed three requested truck-detail plots, keeping calculation/data pipelines intact.
- Replaced chart with conservative current ready, shaded fixed 10-minute safety window and proposed ready after operators; links exact supervisor preview or feasible suggestion.
- Legacy operator-gap KPI now displays exact `recommend_minimum()` additional operators and the calculation reason, never a stale baseline operator count.
- Files, tests and screenshots: `docs/project_tracking/TRUCK_DETAIL_SIMPLIFICATION_RELEASE_v9.md`. 51 focused tests passed; desktop/mobile offline browser checks passed; workbook and SQLite unchanged compared with v8.
- See the latest ZIP and its included SHA-256 manifest for all files.

## v10 (2026-10-12): Truck ready time — before vs after adding operators
- One shared chart and table on truck detail and planner: original assignments, confirmed moves, selected or recommended operators; blue ETC bars; pick cutoff and safety buffer deadline lines; green/yellow/red markers with exact times and minutes early/late.
- Safety buffer configurable (`.env` `SAFETY_BUFFER_MINUTES`); default loading time read from the workbook.
- Full suite 184 passed; Chromium desktop/mobile check. Details: `docs/project_tracking/READY_TIME_CHART_RELEASE_v10.md`.

## v11 (2026-10-13): Consistent At Risk status
- Investigated a truck showing At Risk at one snapshot only. Cause: release burst plus pace measured on logged-in time including waiting, and demo hours not scaled. It was a false alarm, not a tracking bug.
- Fix (user option C): picking-time planning pace (10-minute gap limit, configurable) and corrected demo labor time. No status is forced.
- 193 tests pass. Details: `docs/project_tracking/STATUS_CONSISTENCY_RELEASE_v11.md`.

## v12 (2026-10-13): Temporary Operator Allocation
- Reallocation first. Temporary operators are offered only when no eligible operator exists, all are unsafe to move, or reallocation is insufficient. The fewest temporaries are calculated at an assumed pace (configurable).
- Planner panel, chart rows (original / reallocation / temporary), Allocate Temporary Operators, session-only, Reset; existing / reallocated / temporary labelled.
- 206 tests pass. Details: `docs/project_tracking/TEMPORARY_OPERATORS_RELEASE_v12.md`.
