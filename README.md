# Truck ETC / SMD — CURRENT ACTIVE VERSION 14 (2026-10-14)

**New in v14 — calculated At Risk scenario and realistic status evolution.** The demo data now contains a documented evening-pressure scenario, so two trucks are **At Risk at the 18:30 starting snapshot** purely from the calculation.

- **Cause (synthetic, labelled `SYNTHETIC v14`).** Late add-on OTC orders for SH0908-1034 and SH0908-1069 (released 18:20 and 18:49), a 20:30 carrier appointment (pick cutoff 20:00, buffer deadline 19:50), and WT2 picking re-simulated with the same operators and measured paces. lhall's recorded 19:13 logout halves WT2 capacity. Built by `scripts/build_pressure_scenario_v14.py` from the frozen v13 workbook.
- **Statuses evolve from the numbers.** 18:30–19:00 **At Risk** (ready 19:51–19:57) → 19:15 **Pick Cutoff Passed** (one picker left, ready 20:42) → 20:30 departs with one line left behind. The other eight trucks are unchanged.
- **New status rule wording.** PICK CUTOFF PASSED = cutoff reached with lines open *or* conservative ready after the pick cutoff; AT RISK = after the buffer deadline but not after the cutoff. Bands: green / yellow / red.
- **Allocation replay.** A confirmed allocation is replayed at later snapshots: the destination gains the moved operator's credited pace × hours worked; the **source area gets back** the moved operator's later picks that the remaining operators could not cover. With dclements moved at 18:30 both trucks are On Time, then All Picked at 19:30 and 19:45, and depart complete. A too-late or too-small allocation stays At Risk or Pick Cutoff Passed. **All Picked is never set by the allocation itself.**
- **Status history** on the truck page lists every snapshot with its calculated reason; changes are highlighted.

Details: [`PRESSURE_SCENARIO_RELEASE_v14.md`](docs/project_tracking/PRESSURE_SCENARIO_RELEASE_v14.md). Full suite: **263 passed**. The v11 note "the default snapshot has no at-risk truck" is superseded.

## Version 13 (2026-10-13)

**New in v13 — Environmental Conditions & Workforce Planning (context only).** A new **Environment** page records temperature and relative humidity by work area and shows how fresh and reliable each reading is.

- **Manual entry first.** Readings are validated: range, suspect jumps, duplicates, future times. Zones are the six M123 work types plus any zone a supervisor adds.
- **Where it shows.** Latest °C / %RH appear on the dashboard, beside each work type on the truck page, and in the planner's at-risk pickups.
- **Sensor-ready API.** `POST /api/environment/readings` with a bearer token, plus a device registry and silent-sensor detection. Software only: **no hardware has been bought, installed or tested.**
- **Experimental analysis.** Association analysis runs only when the evidence is sufficient. It currently reports insufficient evidence.
- **Hydration and heat-safety information,** with client-editable site notes.
- **Never changes the numbers.** ETC, ready time, cutoff status and allocations are unchanged. **No environment-adjusted ETC exists** until one is validated and approved (Phase 4).
- **Separate storage.** Readings live in `data/environment.db`, created on first run and never mixed with WMS/LMS data. Settings use `ENV_*` keys in `.env`.

Details: [`ENVIRONMENT_RELEASE_v13.md`](docs/project_tracking/ENVIRONMENT_RELEASE_v13.md) · hardware and costs: [`ENVIRONMENT_HARDWARE_PROPOSAL_v13.md`](docs/project_tracking/ENVIRONMENT_HARDWARE_PROPOSAL_v13.md) · status, client questions and gaps: [`PROJECT_STATUS_v13.md`](docs/project_tracking/PROJECT_STATUS_v13.md). Full suite: **246 passed**.

## Version 12 (2026-10-13)

**New in v12 — Temporary Operator Allocation.** When a truck is at risk, the planner first reallocates safe, experienced existing operators. Only if that is impossible or not enough does it offer the **fewest temporary operators** needed.

- **Temporary Operators panel** shows required totals, operators safely available, operators selected, temporaries still required, expected ready time and the cutoff/buffer result.
- **Controls:** Use recommended plan, choose a count, Preview, then **Allocate Temporary Operators**.
- **Chart** compares original / after reallocation / after temporary operators, each green, yellow or red.
- **Session only:** everything is temporary and Reset restores the original assignments.
- **Settings:** temporary pace is an assumption set in `.env` (`TEMP_OPERATOR_PACE_PCT=100`, `TEMP_OPERATOR_MAX=10`).

Details: [`docs/project_tracking/TEMPORARY_OPERATORS_RELEASE_v12.md`](docs/project_tracking/TEMPORARY_OPERATORS_RELEASE_v12.md). Full suite: **206 passed**.

## Version 11 (2026-10-13)

**New in v11 — consistent, justified At Risk status.**

- **Planning pace = lines ÷ picking time.** A gap over 10 minutes between picks counts as waiting. Set this in `.env` with `PACE_BASIS` and `PACE_GAP_CAP_MINUTES`; `PACE_BASIS=logged_time` reproduces the Excel equation.
- **Demo labor time corrected.** It is scaled per work type to the share of picked lines kept (`scripts/rescale_demo_labor.py`).
- **Effect:** the one-snapshot false At Risk at 18:30 is gone. Every status at every snapshot is recalculated and justified, and the default snapshot had no at-risk truck (superseded by the v14 pressure scenario).

Details: [`docs/project_tracking/STATUS_CONSISTENCY_RELEASE_v11.md`](docs/project_tracking/STATUS_CONSISTENCY_RELEASE_v11.md). Full suite: **193 passed**.

## Version 10 (2026-10-12)

**New in v10 — truck ready time before vs after adding operators.** The truck detail page and the Workforce allocation page share one chart and table showing:

- the projected ready time with the original operators;
- after confirmed allocations;
- after the operators currently selected, or the minimum recommended operators;
- the blue ETC bar, the pick cutoff and the safety buffer deadline.

Markers are **green** (ready by the safety buffer deadline), **yellow** (before the pick cutoff but inside the buffer) or **red** (after the pick cutoff). Each marker carries its exact time, a status word and minutes early/late.

Rules: pick cutoff = departure − loading time (per-truck override, else workbook `TRUCK_CONFIG.LOADING_MINUTES`); safety buffer deadline = pick cutoff − `SAFETY_BUFFER_MINUTES` (set in `.env`, default 10). Details: [`docs/project_tracking/READY_TIME_CHART_RELEASE_v10.md`](docs/project_tracking/READY_TIME_CHART_RELEASE_v10.md).

**Validation (v10):** full test suite **184 passed** (`python -m pytest -q`, about 2 minutes); Chromium desktop and mobile check of the running app.

---

## Version 8 baseline (still applies unless v10 above says otherwise)

**Active project:** 10-truck SYNTHETIC demonstration, not live SMD operating data. Initial snapshot **10 / 18:30** contains exactly **two calculated AT RISK trucks** (`SH0908-1034`, `SH0908-1069`), plus four `ON TIME` and four `ALL PICKED`. Rates cover **one sample day**, not verified 30-day operator productivity.

**New v8:** precise minimum safe additional operators; experience-based ranked candidates (including explicitly synthetic familiarity); unsafe source moves visibly blocked; source and target conservative readiness charts; 30-minute configurable persistent loading with fixed 10-minute safety margin; explicit Allocate confirmation and strictly **memory-only supervisor-session** workforce scenarios. The original 33-truck workbook is archived in `INFO/historical/` and is *not* active UI data. The old persisted allocation table is removed.

**Definitive release document:** [`docs/project_tracking/IMPLEMENTATION_RELEASE_v8.md`](docs/project_tracking/IMPLEMENTATION_RELEASE_v8.md) — business logic, file modifications, safety checks, test results, limitations and reproduction steps. 44 focused tests passed at v8. (Superseded: the full suite now completes — 184 passed at v10.)

## Getting started

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5006/ or `/planner`. To rebuild results from active workbook run `python -m flask --app app init-db`. Do not run development synthesis script as part of app startup. The HTML interface and Excel-source calculation formulas are preserved.

---

## Earlier project release notes (HISTORICAL, not current source of truth)

> **Current project status (2026-10-12):** Please see [`docs/project_tracking/CURRENT_STATUS_AUDIT_v7.md`](docs/project_tracking/CURRENT_STATUS_AUDIT_v7.md). The uploaded SMD-main code adds SQLite-persisted advisory allocations and strict observed-work eligibility; these conflict with some earlier approved requirements. Older v4-v6 sections below are retained as historical release descriptions, not proof of present behavior.

## New in v5 — premium analytics dashboard (2026-10-10)

The home page (`/`) now has a fixed white sidebar, soft-gray SaaS shell, four
scenario-calculated KPI cards, an interactive conservative on-time share trend,
actual 15-minute completed-line activity bars, status-mix gauge, searchable /
sortable truck table, rule-based operational insights, functional CSV export,
and a responsive mobile navigation drawer. The original ETC-to-cutoff chart
remains available in the expanded analytics section. The chart runtime is
bundled locally in `static/vendor/plotly.min.js` (Bootstrap and icon styles
remain CDN-backed). `/operators` is a real read-only operator directory;
all original detail and `/planner` workflows continue to work.

**Accuracy notes:** The status gauge is an observed on-time **share**, not a
probability forecast. No fake AI insight, live staffing assignment, or new ETC
formula is introduced. Deadline = departure − individually configured loading
minutes − fixed 10-minute buffer; the preview/allocate contract from v4 still
applies. The single-day workbook is not a sufficient 30-day operator pace
sample. See `docs/project_tracking/DASHBOARD_REDESIGN_RELEASE_v5.md` for every
file change, metric definition, test, limitation and screenshot provenance.

## New in v4 — buffered supervisor allocation planner (2026-10-10)

Open **`/planner`** from the dark navigation bar. This view provides per-truck loading minutes (30-minute default, saved in SQLite); a fixed 10-minute source/destination cutoff buffer; at-risk individual assignment flags inherited from shipment/worktype; rank-ordered experienced operator candidates including unsafe ones; incremental before/after conservative readiness graph; and explicit **Allocate** confirmation. Allocation is a **temporary server-memory supervisor scenario**, not a WMS instruction or persistent staffing change. The original Excel workbook and the existing baseline engine remain unchanged. Historical charts are not a simulated future picking event stream.

For every operator, pace is calculated from available trailing 30 calendar days of records (de-duplicated labor time and completed lines). The bundled dataset has **only September 8, 2026**, so this rate is labeled observed available-history/single-day and **not** trustworthy monthly productivity. Synthetic target-worktype pace fallback and simulated experience are explicitly flagged. Follow `docs/project_tracking/IMPLEMENTATION_RELEASE_v4.md` for precise rules, verifications, state lifetime and known limitations.

# Truck ETC LMS (SMD) - first local version

Will each truck's work be picked before its pick cutoff? This app recalculates the Truck ETC of the Excel
workbook in Python, stores the results in SQLite and shows them in a Flask dashboard.

The Excel workbook (`data/workbook.xlsx` = SMD_Truck_ETC_RealDay_2026-09-08.xlsx) is the **golden reference**:
the Python engine reproduces every value of its truck sheets (see "Parity").

**Data: a cleaned subset of the real SMD day 08-Sep-2026** (extract SMD-235, warehouse 100): 1,163 items, 625 work
IDs, 421 customer orders, 33 routes = 33 trucks, and 12 pickers with their real login sessions and pick times. Routes
1001, 1075, and 1085 and all their linked records were removed because their picks occurred after the synthesized
cutoffs/departures. Only the truck departures
(last item release + 60 min, rounded up to 15 min = pick cutoff, + 30 min loading) and dock doors are synthesized,
except the explicitly labelled `T07_PICK_CUTOFF_PASSED_LATE` status-coverage scenario. Operator identities and
productivity are actual; cross-training familiarity includes separately labelled simulated planning assumptions.

SMD structure used: route = truck; a customer order is split into one work ID per region (work ID = order number +
2 digits); a region-6 case-pick work ID can hold items of several customers, and every item keeps its own order and
truck, so all truck calculations count items, not work IDs. Waves are not in the extract.

## Run it in VS Code

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS / Linux: source .venv/bin/activate)
pip install -r requirements.txt
python app.py                   # first start builds data/truck_etc.db from the workbook (~5 s)
```

Open http://127.0.0.1:5006 and pick a snapshot (16:15 ... 20:30; default 18:15).
The database is rebuilt automatically whenever `data/workbook.xlsx` changes.

| Task | Command |
| --- | --- |
| Run all tests (calculations, Excel parity, dashboard) | `pytest` |
| Rebuild the database after changing the workbook | `flask --app app init-db` |
| Settings | `.env` (workbook path, database URL, default snapshot) |

Bootstrap and Plotly.js load from their CDN, so the browser needs internet access for styling and charts.

## Project layout (only what is used now)

```text
app.py                  Flask app: dashboard and truck routes + `init-db` command
config.py / .env        settings
calculations/
  excel_io.py           reads inputs and the cached Excel results (openpyxl -> pandas)
  etc.py                the ETC equation per snapshot x work type (ETC_CALC)
  truck.py              truck ETC per work type and per truck (TRUCK_WT_ETC, TRUCK_ETC)
  uncertainty.py        empirical observed-pace ranges and conservative planning status
  reallocation.py       qualified existing-operator moves, source-safety checks and after-move ETC
  detail.py             truck drill-down: operators, work types, orders, trends, explanation, alerts
  engine.py             runs the whole calculation
models/
  models.py             SQLAlchemy result tables, including accepted reallocation moves
  database.py           engine / session, rebuild from the calculation, queries
templates/, static/     Jinja2 + Bootstrap 5 + Plotly.js dashboard
tests/                  pytest: test_etc.py, test_truck.py, test_excel_parity.py, test_detail.py, test_app.py
```

SQLite is reached only through SQLAlchemy (`DATABASE_URL`), so PostgreSQL can replace it later without touching
the calculation code.

## Phase 1 - how the workbook calculates the Truck ETC

**Inputs (workbook sheets)**

| Sheet | Used for |
| --- | --- |
| CONFIG | analysis date, filters (client SMD, warehouse 100, WIPIND Y, status 3), the 18 snapshots |
| LM005S1 | labour segments per snapshot: time, pickers logged in |
| TI102 / TI102C | open lines per snapshot / completed lines with completion time |
| OB_SHIPMENT | trucks: departure, departure change (time it was announced) |
| OB_ORDER, OB_LINE_MAP | order -> truck (with moved orders), pick line -> order |
| TRUCK_CONFIG | LOADING_MINUTES 30 and the observed-evidence-only reallocation rule |
| TRUCK_REALLOCATION | Every at-risk destination, before/after ETC, cutoff, status and no-eligible reason |
| TRUCK_REALLOCATION_MOVES | Accepted moves with source, familiarity, observed pace and source slack evidence |

**Steps (all per snapshot T)**

1. ETC equation per work type (ETC_CALC): TOTALTIMEINHRS = SUM(TOTALTIMEINSEC)/3600; TOTALLINES = completed lines
   (TI102 + TI102C with completion <= T); RESOURCES = distinct pickers with WIPIND Y;
   ACTUALRATELINES = TOTALLINES / TOTALTIMEINHRS x RESOURCES; PER_PERSON_RATE = TOTALLINES / TOTALTIMEINHRS.
2. Truck deadline: departure as known at T (a changed departure applies from DEPARTURE_CHANGED_AT);
   PICK_CUTOFF = departure - LOADING_MINUTES.
3. Per truck and work type (TRUCK_WT_ETC): OPEN_LINES = open TI102 lines of the truck (order's truck as known at T);
   LINES_AHEAD = open lines of that work type on trucks with the same or earlier cutoff; WT_ETC = LINES_AHEAD /
   ACTUALRATELINES; WT_READY_TIME = T + WT_ETC; meets cutoff YES / NO / NO - CUTOFF PASSED / UNKNOWN - NO RATE;
   `WT_STATUS = AT RISK` whenever the calculated ready time exceeds the pick cutoff. OPERATORS_NEEDED =
   ROUNDUP(LINES_AHEAD / (PER_PERSON_RATE x hours to cutoff)), ADDITIONAL = needed - RESOURCES.
4. Per truck (TRUCK_ETC): TRUCK_ETC = largest WT_ETC (BOTTLENECK = that work type; NULL if a needed work type has
   no rate); READY_TIME = T + TRUCK_ETC; SLACK = PICK_CUTOFF - READY_TIME; status (first rule that applies):
   DEPARTED (complete / n lines left behind), NO WORK RELEASED YET, ALL PICKED, PICK CUTOFF PASSED - LATE,
   NO RATE, ON TIME, AT RISK.
5. Uncertainty: for every work type and snapshot, positive operator paces observed by that time form an empirical
   sensitivity envelope. `RATE_LOW/HIGH` encloses both the current team rate and `resources x observed min/max pace`;
   `WT_ETC_LOW/HIGH = LINES_AHEAD / RATE_HIGH/LOW`. Planning status uses the slower bound. This is not a statistical
   confidence interval and does not include unmeasured travel, congestion, breaks, equipment or replenishment delays.
6. Existing-operator reallocation, for point-estimate or uncertainty-driven at-risk work:
   * familiarity comes from either completed TI102C destination lines (actual historical) or the separate
     `OPERATOR_EXPERIENCE` sheet (explicitly labelled **SIMULATED PLANNING ASSUMPTION**);
   * operator pace = that operator's completed lines in the work type / their LM005S1 hours in it by T;
   * destination contribution = actual destination pace when available; otherwise the conservative, data-bounded
     estimate `MIN(actual source pace, actual destination per-person rate)`;
   * destination rate after = team rate before + destination contribution;
   * source rate after = team rate before - operator's observed source pace;
   * source ETC is recalculated for every open source truck at both point and conservative rates, and the move is
     rejected unless every source cutoff remains safe;
   * after every accepted move, source/destination resources, rates, ETC, slack and status are recalculated before
     evaluating another candidate;
   * selection continues until the conservative cutoff is met or no safe familiar operator remains. Allocated count,
     remaining staffing shortfall and the stop reason are retained. Total headcount is unchanged.

The cleaned real day contains no operator with observed completions in more than one work type, so the application
does not misrepresent cross-training as verified history. A separate deterministic simulated familiarity matrix adds
planning qualifications to the 12 existing operators without creating labor, picks, hours, or headcount. Under the
empirical conservative source-safety rule, three moves remain acceptable in the active replay (snapshots 9-11).
Snapshot 6's six-picker OTC gap remains unresolved because no qualified source operator can be proven safe at the
slower observed productivity bound; the UI shows zero allocated, six remaining and the rejection reason.

**Edge cases handled:** no pickers on a work type (NULL rate), cutoff already passed, departed trucks (lines left
behind), departure changed during the day, order moved to another truck, no work released yet, cancelled lines,
missing cross-training evidence, unsafe source removal and an at-risk destination that remains late.

## Parity with Excel

`tests/test_excel_parity.py` compares every value of ETC_CALC, TRUCK_WT_ETC, TRUCK_ETC and TRUCK_REALLOCATION
(all 18 snapshots) with the cached workbook values: all equal.

Times are kept as Excel serial numbers (days) so comparisons match Excel. Two tiny tolerances are needed and
documented in the code:
* time comparisons allow 1e-9 day, because Python's conversion of a time can differ from Excel's stored number in
  the 12th digit (otherwise a ready time exactly on the cutoff can flip from YES to NO);
* ROUNDUP ignores a 1e-9 excess (40 lines / (10 lines/h x 1 h) = 4 people, not 5);
* TEXT(x, "[h]:mm") is reproduced as Excel does it: rounded to the nearest second, then whole minutes.

NO RATE on the real day means that an area with open work has no usable positive observed rate. Usually nobody is
logged in (Cage, Cooler and Vault before about 17:30; Cooler between batches); early in the day a picker can also be
logged in before completing the first line needed to establish a rate. The app distinguishes those explanations and
shows NO RATE exactly as the workbook does (169 of 594 truck-snapshot rows).

Departed status is frozen at the departure event. `LINES_LEFT_AT_DEPARTURE` counts released lines that were not
picked by departure; later picks cannot change a truck from "DEPARTED - ... LEFT BEHIND" to "DEPARTED COMPLETE".

## Phase 4 - truck drill-down

Click a truck on the dashboard (or open `/truck/SH0908-1010?snapshot=6`). The page shows, for that truck at the snapshot:

* KPIs: lines and pieces picked / open, orders complete, ETC and ready time, bottleneck, operators who picked it,
  extra pickers needed and the result after safe existing-operator reallocation.
* **Why this status**: a sentence built from the numbers (slowest area, lines ahead from earlier trucks, pickers, rate,
  ready time vs cutoff, pickers needed, reallocation result or no-eligible reason; or, for a departed truck, when the last line was
  picked and what was left behind).
* At-risk reallocation: eligible candidates, destination operators/rate/ETC/ready time before and after, selected
  operator and source, cutoff, time saved, allocation shortfall and final status. Candidate eligibility still requires
  familiarity evidence and source-safety validation even though those intermediate fields are not separate columns.
* Work types: open / ahead / picked, working-assigned-idle pickers, rates, ETC, ready time, meets cutoff and extra pickers;
  chart of each area's finish against the pick cutoff.
* Operator names in reallocation results link to profiles with actual productivity, labor time, current/previous
  assignments, remaining work, ETC, cutoff status, familiarity provenance and destination-specific reallocation
  eligibility. Unavailable productive-only time is stated, not inferred.
* Trends up to the snapshot: open lines and slack, lines picked per 15 min by area, pickers per area.
* Orders on the truck (customer, regions, work IDs, state) and the truck's work IDs (region, customers, items done /
  open, state, pickers; work IDs holding several customers are marked), and alerts with suggested actions.

The drill-down logic is in `calculations/detail.py` (thresholds at the top: assigned-not-started 10 min, no pick 30 min,
low pace below 60% of the area average after 0.5 h). It reads the source rows that `init-db` stores in SQLite
(`src_*` tables) and the stored engine results; `tests/test_detail.py` checks that its totals match the engine.

## Next phases (not built yet)

Work-type page, Phase 5 what-if planner (move orders, delay departure, ship partial), Phase 6 alerts,
Phase 7 configuration and audit, Phase 8 production evolution.

## v6 — One dashboard design throughout the application (2026-10-11)

The light SaaS layout now applies to all five HTML routes: `/`, `/planner`, `/operators`,
`/truck/<shipment_id>`, and `/operator/<operator_name>`. Navigation, page headings, KPI cards,
forms, alerts, status badges, scrollable tables and charts share one design system. The planner
has an operator-search filter and a clearly labeled earliest-cutoff projection; the operator
directory has real in-page search. The truck readiness visual uses the same muted blue/green/
amber palette as the landing dashboard. Responsive mobile navigation uses native SVG symbols.

Bootstrap CSS/JS and Plotly are included locally under `static/vendor/`; decorative Bootstrap
Icons and the optional Inter font still use CDN resources and fall back to native display when
not available. This v6 note supersedes the earlier README statement that Bootstrap and Plotly
both require CDN access. See `docs/project_tracking/UI_CONSISTENCY_RELEASE_v6.md` for precise
file changes, tests and production limitations. **No warehouse data, stored ETC formulas,
loading policies, or operator allocation logic was changed.**


## Current UI update: v9 (2026-10-12)

Truck Details removes three nonessential historical graphs and shows one simplified area ready-time/cutoff chart (conservative current ready, 10-minute safety window, conservative proposed ready after operator additions). The **Operator Gap (Legacy Baseline)** KPI now shows the smallest *feasible additional* staffing recommendation from the supervisor engine (or **Not feasible**) instead of a stale baseline estimate. Pending supervisor preview affects the unconfirmed projection only; explicit Allocate changes the temporary confirmed session and current readiness. All existing formulas, source safety, dashboard navigation, and 10-truck synthetic data remain intact. See `docs/project_tracking/TRUCK_DETAIL_SIMPLIFICATION_RELEASE_v9.md`.
