# GiNi Production Flow & Recovery — manufacturing prototype

**Status: source-aware, synthetic prototype; NOT customer-validated or production-ready.** Updated 16 October 2026 following the revised implementation prompt. This prototype is not an official Siemens Energy system and does not connect to any Siemens Energy ERP, MES, SAP, equipment or identity platform.

## Starting the app in VS Code (Windows / PowerShell)

Open **this folder** (`GiNi_Manufacturing_App`) in VS Code, then run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python app.py
```

Open `http://127.0.0.1:5008/` in your browser. If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r requirements-manufacturing.txt` and `.\.venv\Scripts\python.exe app.py` directly. To run the focused manufacturing and route tests: `python -m pytest -q tests/test_mfg_logic.py tests/test_mfg_render.py tests/test_mfg_schema.py tests/test_manufacturing_routes.py`. Flask route tests need Flask installed; they are skipped in an environment without it.

### Navigation

- `/` — shift overview, **Tank Performance** projection, station flow, risk and alerts
- `/units` — tank/cover/accessory passports, search, filtering, sorting and CSV export
- `/work-centers` — WC1–WC8, staffing, workload and source-specific CTQ lists
- `/workers` — fictional roster and scenario-aware status; person detail views
- `/quality` — 24 source-derived CTQ checks from the workbook
- `/quality/TANK-0020/CTQ-003` — sample dimensional inspection; manually judged against the source reference
- `/recovery` — explore fixed disruption scenarios and source-safe transfer decisions
- `/api/snapshot`, `/api/units`, `/api/tank-performance`, `/api/ctq` — JSON demonstration endpoints

Demo mutations (inspection results, approval and audit history) persist to `data/manufacturing_demo.sqlite3`. **Reset demo scenario** on the recovery page clears all demo changes. The source workbook is in `data/source/EN_Siemens_CTQ_Guide_1.xlsx` and source rows are preserved as `manufacturing/data/ctq_rules.json`.

## Data provenance and limits

The source CTQ guide has two sheets: `CTQ Guide (2)` (24 checks, rows 3–26, across WC1–WC8) and `Sheet1` (work-center reference mapping). Tolerances such as `ISO 2768-1 Grade C` and `-0% / +20%` are **descriptive** here: the source often does not supply an exact nominal, dimension, or target value. Numeric inspections therefore require a reasoned inspector decision and do not automatically claim an engineering acceptance decision. The Yes/No negative-answer interpretation comes from the workbook. Evidence is conditionally required where the workbook marks Yes/No images.

All tanks, people, orders, materials, staffing, cycle times, due times, events, and projections are fictional scenario fixtures. The reference PDF supplies the **illustrative** combined staffing-absence/first-stage-scrap/recovery story, not an approved production process. Only the tank WC1→WC4 provisional route is modeled; WC5→WC6 covers and WC7→WC8 accessories are independent demonstration streams with **no fabricated final join**. WC1 tank scrap is permanent; other failures are held for review in this demonstration. The **all-stage-checks-pass-to-release** rule is a conservative *demo-only* rule requiring client approval before adoption.

**Tank Performance KPI definitions:** Total Tanks = registered original tank identities (10) plus an approved replacement if one exists. On-Time Tanks (projected) = the scenario forecast of good tank-route completions by the ORD-1042 deadline (0–10), not measured on-time performance. At-Risk Tanks (projected) = max(0, 10 − projected on-time tanks); this is an **order-level shortfall**, not a confirmed classification of an individual physical tank. Route complete = synthetic reference count (six at the 10:55 replay) plus newly recorded complete units. All sample ETAs, staffing rates and wait times are concept-scenario figures, not plant-calibrated forecasts. Source-specific actual tank IDs or CTQ completions were not supplied.

## Existing SMD app preservation

The previous original SMD truck calculation packages, historical workbook, templates, older project documentation and `legacy_truck_app.py` were kept as **reference and regression baselines**, not silently changed or represented as migrated manufacturing logic. The previous Flask application routes are **not wired into** the new manufacturing shell; the active `app.py` is a separate source-aware manufacturing implementation. The old SMD regression suite is **not evidence** of manufacturing readiness. Legacy project history lives at `docs/legacy/README_SMD_v14.md` and `docs/project_tracking/`.

## Required validation before customer presentation

Install dependencies in an internet-enabled development machine, start Flask, exercise all GET/POST routes in a browser, check desktop and mobile layouts, run tests for inspection persistence, CSRF, saved evidence, transfer approvals and all regressions, and validate the Siemens-specific open assumptions with the client. **Flask was unavailable in the audit environment and could not be downloaded due to blocked DNS/network access.** The updated offline suite ran **46 passing checks** and skipped the Flask route test module; server startup, browser/API interactions and deployment are not verified. Pure-logic tests and Jinja template checks are not substitutes for integration tests.

See `docs/manufacturing/IMPLEMENTATION_AND_TEST_REPORT.md` for source mapping, architecture, modified-files report, test evidence, gaps and stakeholder decisions.

## Latest code audit

See `docs/manufacturing/CODE_REVIEW_AND_VALIDATION_20261016.md` for the exact defects corrected, executed checks, new integration tests, and remaining customer-demonstration blockers. The application now requires Pillow to validate inspection evidence images; it is included in `requirements-manufacturing.txt`.

## New: operator execution, work orders, LMS and confirmed points (16 October 2026)

The additional source references (`EN_Siemens_CTQ_Guide 1(2).xlsx`, `Mockup ingles html(1).html`, 00:04–04:07 of Rajesh's transcript, and four newly confirmed point weights) informed a cautious shop-floor extension:

- `/operator` — choose WC1–WC8, worker and physical unit; start/pause/resume/finish UTC-clocked task; inspect source CTQs; record an incoming decision or report a defect.
- `/work-orders` — drill from work order to work-center stage and unit, with CTQ/task/receiving/defect history.
- `/lms` — measured task time and activity, work-order flow, exact confirmed points **policy** and visible eligibility/pending evidence. Automatic worker ranking/penalties, unresolved rework dispositions and arbitrary standard times are intentionally disabled.
- `/api/operator/tasks` — raw UTC activity record, labeled synthetic data.

`manufacturing/shopfloor.py` persists operator and handover events in SQLite and prevents double-booking. `manufacturing/scoring.py` encodes confirmed weights (+3, +2, −4, ±1/min) but **will not assign points to workers or settle unconfirmed defect reports**. Source/quality rules in `manufacturing/data/ctq_rules.json` and old routes remain intact. The historical PDF replay and new UTC event timestamps are separate; a new task does not imply that the fixed PDF ETC has dynamically recalculated.

Run focused regression tests with:

```powershell
python -m pytest -q tests/test_mfg_logic.py tests/test_mfg_schema.py tests/test_mfg_render.py tests/test_shopfloor_logic.py tests/test_manufacturing_routes.py
```

For implemented functionality, exact non-goals, 20 open clarification questions, and the test limitations, see `docs/manufacturing/SHOPFLOOR_IMPLEMENTATION_AND_OPEN_QUESTIONS_20261016.md` and `docs/manufacturing/SHOPFLOOR_TEST_REPORT_20261016.md`.
