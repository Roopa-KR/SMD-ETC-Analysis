# Package verification summary — v3

- **Package:** `truck-etc-app-updated-20261010-v3.zip`
- **Recorded:** 2026-10-10 12:28 IST
- **Input:** `truck-etc-app-updated-20261010-v2.zip`
- **Scope:** Clarification capture, read-only per-worker one-day pace feasibility audit, and complete running change/issue/decision logs.
- **Added:** 3 documentation/data-audit files (`OPERATOR_PACE_DATA_AUDIT_v3.md`, `OPERATOR_PACE_SINGLE_DAY_v3.csv`, `CONFIRMED_REQUIREMENTS_AND_OPEN_DECISIONS_v3.md`).
- **Changed:** Existing audit/index/tracking documentation and generated SHA-256 manifest.
- **Application / tests / templates / workbook / SQLite edited:** NONE.
- **Data evidence:** SQLite `src_ti102c` 1,163 completed lines, 1 distinct transaction date (2026-09-08); `src_lm005s1` 282 snapshot rows / 18 snapshots / 12 workers; 14 final-snapshot person-worktype labor combinations; 12 with completed lines; 625 assignment IDs with complete line/order links; 15 simulated familiarity rows.
- **Data caveat:** Single-day rate is an observed statistic of the supplied replay, not a verified monthly productivity measure; labor snapshots are cumulative.
- **New feature tests:** NONE; functionality unchanged, so do not imply user requirements implemented.
- **Pending clarifications:** See `CONFIRMED_REQUIREMENTS_AND_OPEN_DECISIONS_v3.md`, questions A–E.
- **Package validation:** ZIP CRC and SHA-256 manifest tested at build stage; application/data file hashes compared to v2.
- **Privacy:** `.env` and `.git` retained from supplied user project; do not distribute externally without review.

## v4 release — 2026-10-10

- Deliverable: `truck-etc-app-updated-20261010-v4.zip` with original replay workbook/database, updated source/UI/test suite and complete accumulated v1–v4 audit history.
- New workflow: fixed 10-minute safety buffer, 30-minute default loading with persisted per-truck overrides, experienced candidate ranking including UNSAFE, explicitly labeled synthetic pace, interactive cumulative conservative preview, explicit Allocate to temporary per-supervisor server RAM, inherited at-risk assignment list, refreshed dashboard/worktype/truck statuses. No live WMS allocation and no workbook changes.
- 33 focused tests passed in the final selected run; full pytest suite did not finish before timeout. No complete-suite pass claim.
- Data caveat: available source rows cover one day, not the 30 days necessary for reliable monthly productivity.
- Manifest is generated inside ZIP using `scripts/package_project.py` and verifies every included file's SHA-256.
- Risk: supplied private `.env` and `.git` included per original package policy; avoid distributing publicly.

## Version v5 package — 2026-10-10 13:26 IST

- **File:** `truck-etc-app-updated-20261010-v5.zip`; baseline v4 archive; includes v1–v5 accumulated logs, actual source/data and supplied UI reference screenshot.
- **Requested outcome:** reference-inspired responsive enterprise UI using existing Truck ETC/LMS values, functional search/snapshot/status filtering, sorting, CSV export, operational insights and new operator listing, without replacing warehouse business formulas.
- **Added/modified files:** full inventory in `DASHBOARD_REDESIGN_RELEASE_v5.md` and SHA manifest in ZIP.
- **Functional coverage:** dashboard, operator list, planner, truck/operator detail, CSV export return HTTP 200; 33 focused tests pass; screenshot-based desktop/offline-render visual review; desktop/mobile no overflow; mobile sidebar open/close tested; 1024px tablet breakpoint fixed.
- **Source invariant:** `data/workbook.xlsx` and `data/truck_etc.db` unchanged relative to v4. No persisted operator allocations added.
- **Important caveats:** full historical parity suite not rerun; browser local HTTP navigation sandbox-blocked; Bootstrap/icon CSS still CDN-dependent; `.env` and supplied Git history included per package policy, therefore treat this archive as private.
- **Archive integrity:** ZIP CRC and full SHA-256 manifest checked by `scripts/package_project.py`.

## Version 6 — 2026-10-11

- **Deliverable:** `truck-etc-app-updated-20261011-v6.zip`; baseline v5.
- **Scope:** shared light SaaS design on **every** existing HTML page; no calculation changes. Files and screenshots are indexed by `UI_CONSISTENCY_RELEASE_v6.md`.
- **Validation:** 42 focused tests pass; Chromium isolated HTML rendering of five pages at 1440/1024/390px with no JS errors/page-wide overflow and working navigation, tabs and client-side searches. Browser HTTP direct blocked; full suite timed out.
- **Source preservation:** `data/workbook.xlsx`, `data/truck_etc.db`, `app.py`, and all calculation modules checked byte-for-byte against v5 after restoring test-created SQLite side effects. No WMS/SQLite allocation writes.
- **Archive:** use `scripts/package_project.py`; it creates an in-archive SHA-256 manifest and validates ZIP CRC. Virtual environment/cache folders excluded per packaging policy.


## v7 current-state audit — 2026-10-12

- Input: new user-supplied `SMD-main.zip`, compared with completed v6 package.
- Key result: modern common dashboard sources present; new pickup risk APIs/SQL allocation persistence and strict eligibility changes detected. Confirmed regressions/conflicts and reproduced reset-reuse issue. No behavior fixes made without user approval.
- New status report: `docs/project_tracking/CURRENT_STATUS_AUDIT_v7.md`.
- Data: golden workbook unmodified; included fresh derived SQLite cache (18 snapshots, 33 trucks at snapshot 10), empty advisory scenario table.
- Verified: 5 focused tests; Python 34 files/Jinja 7 templates/JS syntax; ZIP integrity/manifest. Flask unavailable in environment; full suite timed out. Do not misrepresent these as full E2E passes.
- Output: `SMD-main-updated-status-20261012-v7.zip`; includes all user-uploaded files and cumulative tracking history plus audit/update artifacts, excluding transient caches.

## Version v8 — 2026-10-12

- **Input:** `SMD-main-updated-status-20261012-v7.zip`.
- **Output:** `SMD-main-updated-20261012-v8.zip`.
- **Active synthetic data:** 10 trucks, 129 orders, 283 pick lines, 18 snapshots; default snapshot10 = 2 AT RISK (`SH0908-1034`, `SH0908-1069`), 4 ON TIME, 4 ALL PICKED. Old 33-truck source preserved only as inactive historical reference.
- **Scenarios:** Independently calculated minimum safe additional operators = 1 and 2; derived from actual conservative math on synthetic input, never forced labels.
- **Workflow:** Per-worker pace and approved clearly marked synthetic fallback, transferable-vs-unsafe candidates, conservative buffered source/target graphs, explicit Allocate, temporary in-process session moves, reset and subsequent snapshot re-evaluation, per-truck loading overrides in SQLite only.
- **Data origin:** Actively simulated/replay-derived, includes explicit WT1 labor and one departure calibration. Single-day data NOT validated 30-day productivity.
- **Code/doc references:** `IMPLEMENTATION_RELEASE_v8.md`, `TASK_LOG.md`, `CHANGELOG.md`, `DECISIONS.md`, `ISSUES_AND_SOLUTIONS.md`, `scripts/build_ten_truck_demo.py`.
- **Verification:** 44/44 focused tests pass with isolated test dependencies; Python compileall and Node syntax pass; ten active IDs and consistent CSV/API references checked; no allocation SQL table. Historical suite exceeded timeout, live browser acceptance pending.
- **Package:** ZIP CRC and per-file SHA-256 manifest verified on build. `.venv`, `__pycache__`, temporary experiment scripts omitted. The supplied `.env` and Git history may contain private data; treat as private.


## v9 package — 2026-10-12
- **Input:** `SMD-main-updated-20261012-v8.zip`; **Output:** `SMD-main-updated-20261012-v9.zip`.
- **Scope:** Truck-detail UI removals and conservative ready/cutoff/proposed-ready chart, read-only gap adapter, seven new tests. All active synthetic records and SQL source returned to the original v8 bytes.
- **Findings:** 10 total trucks, 2 initial at-risk, independent minimums 1 and 2. The card follows preview-only selections and changes after confirmed temporary allocation/reset. No unsafe or overlapping recommendation is silently recorded as completed.
- **Verification:** 51 focused passes; offline browser-rendered 1440/390px checks, two chart series and no browser exceptions; archive integrity and generated SHA-256 per-file manifest.
- **Report:** `TRUCK_DETAIL_SIMPLIFICATION_RELEASE_v9.md`; screenshots under `docs/images/v9-truck-detail-{desktop,mobile}.png`.


## v10 package — 2026-10-12
- **Input:** `SMD-main-updated-20261012-v9_1.zip` (byte-identical to the v9 manifest). **Output:** `SMD-main-updated-20261012-v10.zip`.
- **Scope:** A shared before/after truck ready-time chart (green/yellow/red vs pick cutoff and safety buffer deadline, blue ETC) on truck detail and planner; configurable safety buffer; workbook-driven default loading time.
- **Verification:** full pytest suite 184 passed; Chromium desktop and mobile check of the running app; ZIP CRC and per-file SHA-256 manifest at build.
- **Data:** workbook unchanged; SQLite cache regenerated (adds `LOADING_MINUTES` to `src_config`; no loading overrides; no allocations).
- **Report:** `READY_TIME_CHART_RELEASE_v10.md`.


## v11 package — 2026-10-13
- **Input:** `SMD-main-updated-20261012-v10.zip`. **Output:** `SMD-main-updated-20261013-v11.zip`.
- **Scope:** Root-cause investigation of one-snapshot At Risk; demo labor time corrected; picking-time planning pace (configurable gap limit); recommendation and early/late text fixes; operator pages show both paces.
- **Verification:** full suite 193 passed; Chromium page check; workbook change limited to LM005S1 and SCENARIO_README (verified part-by-part).
- **Data:** workbook labor time changed as documented; SQLite cache rebuilt; no loading overrides; no allocations.
- **Report:** `STATUS_CONSISTENCY_RELEASE_v11.md`.


## v12 package — 2026-10-13
- **Input:** `SMD-main-updated-20261013-v11.zip`. **Output:** `SMD-main-updated-20261013-v12.zip`.
- **Scope:** Temporary Operator Allocation after safe reallocation; planner panel, chart rows, session-only confirmation and reset, role labels.
- **Verification:** full suite 206 passed; Chromium walk-through; ZIP CRC and SHA-256 manifest at build.
- **Data:** workbook and SQLite unchanged from v11 (no overrides, no allocations).
- **Report:** `TEMPORARY_OPERATORS_RELEASE_v12.md`.


## v13 package — 2026-10-13
- **Input:** `SMD-main-updated-20261013-v12.zip`. **Output:** `SMD-main-updated-20261013-v13.zip`.
- **Scope:** Environmental Conditions & Workforce Planning (manual entry, validation, sensor-ready API, gated analysis, heat and hydration information, dashboard/truck/planner context). Hardware proposal and client questions.
- **Verification:** full suite 246 passed; Chromium check; ZIP CRC and SHA-256 manifest at build.
- **Data:** workbook and SQLite unchanged from v12 (no overrides, no allocations). `data/environment.db` is not shipped; it is created empty on first run.
- **Reports:** `ENVIRONMENT_RELEASE_v13.md`, `PROJECT_STATUS_v13.md`, `ENVIRONMENT_HARDWARE_PROPOSAL_v13.md`.


## v14 package — 2026-10-14
- **Input:** `SMD-main-updated-20261013-v13.zip`. **Output:** `SMD-main-updated-20261014-v14.zip`.
- **Scope:** Synthetic pressure scenario (two calculated At Risk trucks at 18:30), PICK CUTOFF PASSED for projected misses, allocation replay with source recalculation, truck status history.
- **Verification:** full suite 263 passed; Chromium check; ZIP CRC and SHA-256 manifest at build; suite re-run from the extracted ZIP.
- **Data:** `data/workbook.xlsx` regenerated by `scripts/build_pressure_scenario_v14.py`; `data/truck_etc.db` rebuilt; v13 workbook kept in `INFO/historical/`. `data/environment.db` not shipped.
- **Report:** `PRESSURE_SCENARIO_RELEASE_v14.md`.
