# Truck ETC — v4 supervisor cutoff and reallocation implementation

**Date:** 2026-10-10. **Source:** v3 auditable project ZIP. **Business decisions:** confirmed in the current user conversation. **Scope:** demo/simulation, not live WMS staffing deployment.

## Confirmed and implemented rules

| Rule | Implementation | Evidence / exception |
|---|---|---|
| Fixed minimum safety buffer | `calculations/supervisor.py`, `SAFETY_BUFFER_MINUTES = 10`; conservative pass deadline = shipment departure − per-truck loading − 10 minutes | Applies to destination AND every open source-truck worktype row after a proposed removal. Physical loading cutoff and buffered planning deadline are shown separately in supervisor planner. |
| Truck-specific loading time | `models/database.py` table `truck_loading_override`, app POST `action=loading` | 30-minute default. Per-truck whole-minute override stored in SQLite, survives server restart. Set 30 to remove override. Basic nonnegative/≤24-hour technical validation, not an added warehouse eligibility rule. |
| Prior 30 calendar days | `calculations/supervisor.py::_active_snapshot` | Trailing 30 calendar-day window inclusive of snapshot day. Pace = unique completed `TI102C` lines / nonduplicated `LM005S1` recorded hours, grouped by operator/worktype. Labor time is de-duplicated by employee, worktype, evidence calendar day and segment start, retaining largest snapshot-reported duration. This is a practical method for the currently supplied replay, NOT a proven monthly methodology for future LMS exports without a stable segment ID. |
| Missing monthly data | Explicit label in planner | Only 2026-09-08 is available; single-day observed rates **must not** be described as actual monthly pace. Data upload of 30 daily operator-completion and labor records required for robust monthly validation. |
| Worktype experience | Actual completed work OR existing simulated `OPERATOR_EXPERIENCE` record | No experience = excluded. Synthetic records are visibly marked `SIMULATED`. Destination experience alone is not automatically a measured pace. |
| No destination history | Original approved fallback `min(actual source pace, observed destination per-person team rate)` | Visibly marked `SYNTHETIC` and never represented as observed target performance. Unknown basis yields pace unavailable/UNSAFE. |
| Candidate order and safety | Ranked descending by target-worktype individual pace. Familiar but unsafe operators remain visible with red UNSAFE label | Existing source-safety principle preserved. Cumulative simultaneous removals revalidated at each step. Confirmed scenario cannot double-use one active operator. |
| Interactive what-if | `/planner` POST `add` / `remove` / `clear` plus updated Plotly plot | Original vs conservative ready time after EACH increment. Preview makes no confirmed allocation, staffing database update, or workbook change. |
| Explicit Allocate | POST `allocate`, CSRF-checked and server-side revalidated | Stores only ephemeral in-memory scenario keyed to supervisor session, not in browser cookies, workbook, SQLite result tables or a WMS. `reset_scenario` clears moves. |
| Subsequent snapshots | In-memory move is projected at its starting and later snapshots | **Safety guard:** if operator is no longer active in the original source worktype, cannot be measured or source would become unsafe at later snapshot, that move is skipped and explicitly reported. Historical source records are not rewritten. |
| Assignment-level risk | Join open `TI102` lines to `OB_LINE_MAP` assignment, order and effective shipment | Assignment inherits the matching truck/worktype risk and explanation; no fabricated per-assignment completion sequence or independent ETC. |
| No transfer time | Zero travel/handover delay | Explicitly out of scope per user, not an inferred performance estimate. |

## New UI and existing data preservation

- Dashboard status, ETC and deadline at the chosen snapshot are computed using the active supervisor scenario; original SQLite workbook-replay results remain available to the historic engine and parity tests.
- Truck details reflect scenario deadline, conservative status and updated worktype readiness; the automatic legacy suggested-moves table is not shown as an allocation. Physical picking, orders, completed-work history, operator profiles and charts sourced from the original workbook remain read-only historical data, not simulated future work execution.
- Operator profile no longer labels workbook-generated automatic suggestions as confirmed allocations.
- Current-session planner graph is the authoritative sequential before/after reallocation preview. Dashboard/truck historical trend graphs still use past workbook snapshots; they are **not** a reforecast of past execution under changed staffing. An end-to-end post-allocation labor-event/WMS simulation is not implemented.
- The persistent SQLite contains an older `reallocation_move` **baseline simulation** table for workbook fidelity. It is not used as a confirmed-allocation log. Never interpret it as supervisor-approved action.

## Accuracy and operational caveats

1. **Synthetic data:** Qualification and many truck timings are demo assumptions. Historic data covers only one day, not 30; monthly pace requires multi-day exports, reliable segment IDs and verified productive-time definitions.
2. **Statistical conservatism:** The existing empirical lower envelope is not a confidence interval. Incrementally subtracting operator pace from team rate is a user-approved scenario approximation, not independent measurement of actual team collaboration.
3. **Session lifetime:** In-memory scenario is scoped to one supervisor browser session and this Python process. App restart clears moves. Multi-process worker deployments do not share in-memory scenarios; add centralized ephemeral state only after explicit future authorization.
4. **No auth/integration:** No supervisor login or live WMS execution. Do not treat button action as warehouse fulfillment. Flask developer debug mode remains from the supplied app; disable for real deployments.
5. **Loading overrides:** Per-truck values persist in the local SQLite file, as explicitly requested. They do not change the source workbook and could require migration when changing SQLite instances.
6. **No transfer delay:** Intentionally ignored this phase.
7. **Older documentation:** `PROJECT_HANDOVER_CURRENT_STATUS.txt`, old app manual, and prior screenshots describe earlier baseline behavior; this v4 release note supersedes them for the new workflow.

## Files changed

- **Added:** `calculations/supervisor.py`, `templates/planner.html`, `tests/test_supervisor.py`, this release note.
- **Modified:** `app.py`, `models/database.py`, `templates/base.html`, `templates/dashboard.html`, `templates/truck_detail.html`, `tests/test_app.py`, `README.md`, `PROJECT_ACTIVITY_INDEX.md`, `docs/TRUCK_ETC_APPLICATION_GUIDE.md`, and change tracking records.
- **SQLite:** `data/truck_etc.db` includes the new table `truck_loading_override`. The table currently contains zero overrides; no confirmed operator allocation rows were created.
- **Unmodified:** Excel workbooks, stored input/source tables, original automated engine (`calculations/{etc,truck,uncertainty,reallocation,engine}.py`), and baseline tests for engine parity.

## Verification completed

- `PYTHONPATH=/mnt/data/truck-etc-test-deps:$PWD pytest -q tests/test_app.py tests/test_supervisor.py tests/test_truck.py tests/test_etc.py tests/test_reallocation.py tests/test_uncertainty_reallocation.py --disable-warnings --maxfail=3` **33 passed**.
- Web client opened dashboard, `/planner`, existing truck detail, operator detail. Preview before confirmation contained no confirmed allocation; clicking Allocate added a temporary scenario and subsequent snapshot rendered. A second candidate was rejected when cumulative source safety failed.
- A full `pytest -q` was attempted and stopped by execution timeout before completion; **full-suite pass is NOT claimed**.
- Release ZIP integrity and per-file SHA-256 manifest generated and checked at packaging time.
