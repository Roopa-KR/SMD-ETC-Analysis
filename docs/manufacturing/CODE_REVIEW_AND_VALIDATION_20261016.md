# GiNi Manufacturing — code review and validation (16 October 2026)

**Scope:** Reviewed the active Flask manufacturing entrypoint (`app.py`), deterministic fixtures and quality logic, ten UI templates, client-side manufacturing JavaScript/CSS, SQLite persistence, tests, configuration, and the preserved legacy code boundary. The original truck-specific engine and historical SMD test suite were examined for dependency/integration boundaries, but **were not rewritten or exhaustively validated** as part of the active manufacturing app. This is still a **synthetic proof of concept**, not validated Siemens Energy software.

## Findings and corrections

| Severity | Finding | Resolution |
| --- | --- | --- |
| High | Scrap and staffing events appeared in what-if scenarios where they never occurred; the normal scenario could show TANK-0018 scrapped. | Scenario-specific event filtering and unit states; `known_at` replay checks. |
| High | Replay could show future work completion or actions before they were known. | Coarse opening WIP view (three waiting at WC2, seven at WC1) and filtered future actions. Earlier replay is deliberately coarse because unit-by-unit historical timestamps do not exist. |
| High | Persistent inspection hold/scrap modified forecast quantity, but the previous reference completion time looked unchanged and authoritative. | Mark completion time **“Recalc needed”** after additional holds/scraps; retain reference scenario wait as illustration, never invent a recalculated ETA. |
| Medium | Local station backlog counted queued units twice (`queue` + same units in `active_count`); staff and crew details could disagree. | Compute queued and active counts separately from displayed units; represent scheduled transfer start and return windows consistently in both WC1/WC4 and worker pages. |
| Medium | Transfer check used static staffing and did not reject workers already engaged or transferred. | Validate scenario-specific available status, source minimum safe crew, qualification, and double-booking; allow relief worker only from the demonstrated available time. |
| Medium | CSV exported all units even with UI filters selected. | Shared filtering/sorting helper is used for UI and export; export link forwards current filters. |
| Medium | Navigating between pages lost the chosen scenario and replay time. | Propagate active GET parameters through generated internal links. |
| Medium | CTQ evidence accepted files with only matching magic bytes; rejected submissions could leave orphan uploads. | Require Pillow image parsing and format match; validate all inputs/evidence before writing the image. Uploaded filenames are random and extension-restricted. |
| Medium | Browser-side required-image validation parsed the first hint in the form rather than the actual evidence rule, so conditional `required` rarely activated. | Use explicit workbook-derived `data-required-yes/no` attributes; server-side evidence validation remains authoritative. |
| Medium | Inspection audit did not preserve evidence references or expose reading history. | Backward-compatible SQLite audit-column migration, retained historical evidence until reset, recent change history on unit passports, and guarded evidence retrieval. |
| Low | SQLite connections were not explicitly closed after `with sqlite3.connect(...)`. | Centralized context-managed commit/rollback/close and busy timeout. |
| Low | Read-only TANK-0018 and invalid-stage forms appeared editable in some scenarios. | Lock reference unit; disable inspection form when it is not an eligible current stage. |
| Low | Fixed “upstream constraint” text also appeared for normal runs and recovery labels assumed only one unit at risk. | Conditional explanatory text and calculated shortfall label. |

**Preserved business rules:** First-stage tank failure is permanent scrap; later failure stays on hold; incomplete/missing CTQ checks cannot be assumed passed; numeric descriptive tolerances require an inspector's recorded rationale; replacement gets a new physical identity; the reference recovery scenario requires a qualified operator transfer and material-backed new tank. Actual Siemens approval of the underlying production/quality rules is still required.

## Executed checks (not inferred)

| Check | Observed result |
| --- | --- |
| Focused manufacturing logic + edge tests | **44 passed** (`tests/test_mfg_logic.py`) |
| Strict Jinja2 render of all ten manufacturing templates with fixture context | **1 passed** (`tests/test_mfg_render.py`) |
| SQLite schema DDL/key smoke | **1 passed** (`tests/test_mfg_schema.py`) |
| Integration test file (`tests/test_manufacturing_routes.py`) | **1 module skipped** because Flask is not installed in this environment |
| Combined test command | **46 passed, 1 skipped** |
| `python -m compileall -q app.py manufacturing tests` | **Passed** syntax compilation |
| `node --check static/js/manufacturing.js` | **Passed** JavaScript syntax |
| Workbook → CTQ JSON mapping | **24 rows, 312 compared fields, 0 differences** (checked with `artifact_tool`; source evidence flags marked `X` mapped to booleans) |
| Whole original legacy `pytest` run | **Blocked** at `tests/test_app.py` startup: `ModuleNotFoundError: No module named 'flask'` |
| Flask server startup, real HTTP/API POST, live browser/mobile workflow | **NOT RUN** — local Flask unavailable; installation attempted and failed due network/DNS restriction |

The integration tests are included for execution on a machine where `requirements-dev.txt` has been installed. The fact that the files compile or isolated templates render is **not** evidence that browser interactions, SQLite mutations, or production deployment work end to end.

## Remaining issues / customer-demo blockers

1. **Critical: run Flask integration tests and browser acceptance tests in the target development environment.** On a computer with network access, install `requirements-dev.txt`, then run the full targeted test command below, launch Flask, and test all interactive screens with actual form submissions.
2. A complete event-based manufacturing scheduling/ETC engine does **not** exist. Reference scenario finish times and WC2 waits are PDF fixtures; a new hold invalidates the ETA. There is no validated dynamic reforecast of shared station capacity, the whole downstream route, and all affected orders.
3. The active manufacturing UI does not expose all original truck-based SMD legacy dashboards, productivity/allocation capabilities, and historical workbooks. The original code, templates, and dependencies remain available as a regression reference; integrating appropriate reusable functionality requires a separate scoped migration.
4. The app has no production authentication, RBAC, evidence-access authorization, audit-retention policy, enterprise integration, or plant-calibrated operational data. **Run locally against synthetic data only**; do not expose on a public or customer network.
5. Source CTQs lack many exact drawings/nominals, mandatory-check definitions and official authorization rules. Conservative gate transitions and WC5–WC8 independent routing remain synthetic assumptions, not Siemens production policy.
6. Early replay before 10:55 cannot show correct minute-level individual tank operations because historical timestamps were not provided. Coarse opening WIP is displayed instead of inventing individual completion times.
7. Client-facing accessibility, responsive layout, UI screenshot comparisons and performance/load testing could not be completed without a running browser-connected server.

## Commands (Windows PowerShell, from ZIP's `GiNi_Manufacturing_App` folder)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q tests/test_mfg_logic.py tests/test_mfg_render.py tests/test_mfg_schema.py tests/test_manufacturing_routes.py
.\.venv\Scripts\python.exe app.py
```

Visit `http://127.0.0.1:5006/`. The main screens are `/`, `/units`, `/work-centers`, `/workers`, `/quality`, `/recovery`. Use the **Reset synthetic scenario data** button after testing data mutations. Never use this demo with real sensitive client production/inspection records.

**Readiness: not yet customer-demo certified.** Route integration and deployment on the customer's environment remain mandatory, and a general-purpose ETC/recovery solver remains unimplemented.
