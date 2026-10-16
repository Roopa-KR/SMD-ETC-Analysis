# Current Status and Source Comparison — v7 (2026-10-12)

## Scope and source hierarchy
- User-uploaded current source: `SMD-main.zip` (the authoritative starting point for this audit).
- Reference comparison: `truck-etc-app-updated-20261011-v6.zip` from the prior conversation.
- This is an **analysis-only code review**. No Flask routes, Jinja templates, CSS/JS, database models, formulas or application behavior were intentionally modified for v7.
- Generated a clean SQLite cache using the uploaded workbook and existing `calculations.engine.run`, `models.database.rebuild`, `models.database.store_sources`; does **not** include any user-confirmed scenario allocations. The uploaded source ZIP omitted the database file; it normally rebuilds automatically on first Flask startup.

## Summary of actual differences from v6
Seven existing files were modified in the uploaded SMD-main source and one new file was added:
- `app.py`: scenario decisions written to SQLite; `at-risk-pickups` and `eligible-operators` snapshot APIs; scenario versioning; new rendered planner sections.
- `calculations/supervisor.py`: `eligible_candidates()` creates strict observed-target-work eligibility list while retaining simulated experience in `candidates()` for advisory previews.
- `models/database.py`: CRUD for persisted scenario moves and scenario versions, with reset/reverse status.
- `models/models.py`: new `scenario_allocation` SQLAlchemy table with a unique `(scenario_id, operator)` constraint.
- `templates/planner.html`: strict available list, labelled simulated advisory section, pickup risk display, scenario review and persisted allocation text.
- `static/js/planner.js`: minor change in browser-side behavior.
- `docs/TRUCK_ETC_APPLICATION_GUIDE.md`: new documentation content.
- **NEW** `tests/test_pickup_risk_feature.py`: strict eligibility and two API tests.
- All other common non-Git source files, including the golden `data/workbook.xlsx`, were byte-identical to v6. The uploaded source ZIP intentionally or incidentally omitted v6's `.git` directory and `data/truck_etc.db`. v7 does not reintroduce `.git`; it includes a freshly regenerated SQLite cache instead.

## Functional status (source inspection only, except where identified)
- Exists in code: dashboard, operator directory/profile, truck details, workforce planner, status cards, charts, export and search, responsive shared UI from v6.
- Exists in calculations: fixed 10-minute buffer, default 30-minute loading and persistent truck overrides, trailing-30-day pace calculation (only one real recorded day in supplied data), conservative risk, cumulative preview, source safety, inherited assignment-level risk.
- Added but not HTTP-verified in this environment: `/api/snapshots/<id>/at-risk-pickups` (grouped truck/worktype rows, not one JSON row per picking assignment); `/api/snapshots/<id>/worktypes/<worktype>/eligible-operators`.
- No live WMS integration or operational confirmation is implemented. Historical inputs include synthetic truck cutoffs/docks and simulated cross-training assumptions.
- The regenerated SQLite data contains 18 snapshots and 33 trucks at snapshot 10. Source code and workbook remain unchanged.

## User-approved rule compatibility — action required before production
1. **HIGH — Persistence contradicts approved session-only decision.** The 2026-10-10 decision required confirmed moves to affect later snapshots while *not* saving them locally. Uploaded source now stores `ScenarioAllocation` records in SQLite. Must obtain renewed explicit approval or restore session-only storage. Do not remove or migrate customer records implicitly.
2. **HIGH — Experience and unsafe candidate visibility regression.** User approved labelled simulated experience as eligible and unsafe operators displayed, disabled. New strict `eligible_candidates()` drops simulated experience and excludes unsafe operators from the main list (showing only a count), while a separate safe-only advisory list exists for simulations. Reconcile the UI and API rules and verify end-to-end.
3. **HIGH — Reset prevents operator reuse (reproduced).** `reverse_scenario_moves()` changes status to `REVERSED`, but `record_scenario_move()` checks **all** historical scenario rows for the same operator; the unique constraint additionally covers reversed rows. In an isolated test, confirm -> reverse -> confirm same operator yielded `ValueError: This operator is already allocated in the scenario.` Solution requires a reviewed schema/logic change with a safe migration strategy (e.g., move unique constraint to active-only uniqueness where supported, or use a new scenario version/id plus coherent audit handling). No change applied.
4. **MEDIUM — Multi-operator confirmation not fully transactional.** `app.py` calls `record_scenario_move()` independently for each accepted preview step; if a later write fails, earlier writes can persist while the UI reports an error. Implement one database transaction and validate once before commit.
5. **MEDIUM — Persistence/session lifetime is inconsistent.** Secret key is freshly generated on startup, invalidating existing supervisor cookies while SQLite scenario rows survive. If persistence becomes approved, decide how a supervisor would recover their scenario and add authentication before operational use.
6. **MEDIUM — Source documentation is stale.** The original README, earlier v4-v6 logs, and archived `PROJECT_HANDOVER_CURRENT_STATUS.txt` describe memory-only moves, earlier UI stages, or old validation totals. Preserve these as historical documents; this v7 report is the current status record. Later work should align active README and product docs with the approved design.
7. **MEDIUM — Incomplete test coverage.** No Flask package is available in this audit environment, and package install could not access the internet. API/route/browser tests were not run. Full broad pytest batch timed out without a complete result. New 5 focused math/eligibility tests passed; Python/Jinja/JS syntax checked.
8. **LOW — FutureWarning from pandas.** Existing `calculations/truck.py` produces downcasting warnings under current pandas, no behavior change was applied.
9. **DATA LIMITATION — Monthly pace.** Workbook activity covers one date, 2026-09-08; 30-calendar-day pace request is a rolling window *of available evidence*, not a representative month. Label estimates accordingly and collect longer history.

## Validation evidence (new, 2026-10-12)
- Archive integrity: both uploaded `SMD-main.zip` and prior v6 ZIP passed ZIP CRC validation.
- SQLite cache rebuilt from the source workbook in ~4.5 seconds using calculation engine and database storage functions; 18 snapshots, 33 trucks at snapshot 10; `scenario_allocation` table present and empty in delivered archive.
- Focused test set: 5 passed (`test_fixed_buffer_default_and_per_truck_override`, `test_monthly_coverage_label_is_not_faked`, `test_all_familiar_candidates_visible_and_sorted_unsafe_flagged`, `test_assignment_flags_match_parent_worktype`, `test_strict_eligibility_uses_observed_target_work_and_safe_source`).
- An earlier targeted set of three overlapping tests also passed. Avoid summing repeated tests.
- Python AST syntax checked: 34 files; Jinja parse: 7 templates; browser-side JS syntax check (`node --check`) passed.
- A larger non-Flask regression run emitted progress through 96 tests but exceeded its execution timeout before printing a final pass/fail summary. **Not counted as passed.**
- Direct database reproduction on disposable test database: first `record_scenario_move` succeeded; reversing moves removed it from active scenario; attempting to confirm the same operator again failed with a ValueError. The fresh delivered database contains **zero test allocations**.
- This environment lacks Flask; dependency installation failed because the package index was unreachable. Running the actual UI/HTTP routes is not verified in v7. Previous v6 UI test claims remain historical, not retested here.

## Recommendations and change policy
1. Confirm whether user wants to retain or roll back new SQLite persistence, especially since it contradicts explicit business rules.
2. Fix reset/re-allocation and batch atomicity under one agreed persistence design.
3. Restore visibility of source-UNSAFE familiar operators and label simulated experience as previously approved.
4. Add integration tests that exercise scenario reset/reuse, multi-operator failure rollback, API data/status, and initialization without `data/truck_etc.db`.
5. Re-run all route/browser tests in an environment with requirements installed; ensure adequate isolation of test databases.
6. Maintain evidence labels: **observed** warehouse activity, **synthetic** familiarity and cutoffs, **calculated** risk/ETC, and **advisory** confirmed scenario; never represent as live WMS action.

## v7 delivered files
- Preserves all uploaded source, workbook, templates/assets, tests and historical docs.
- New audit and tracker updates: this file, `TASK_LOG.md`, `CHANGELOG.md`, `DECISIONS.md`, `ISSUES_AND_SOLUTIONS.md`, `PACKAGE_SUMMARY.md`, `PROJECT_ACTIVITY_INDEX.md`, `README.md` notice.
- New derived file: `data/truck_etc.db`, generated from existing workbook and code; no user allocation history seeded.
- Updated in-archive SHA-256 manifest, regenerated by `scripts/package_project.py`; verified after ZIP creation.
