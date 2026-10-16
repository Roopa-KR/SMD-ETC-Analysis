# Version 8 — Ten-truck synthetic cutoff and supervisor allocation release

**Date:** 2026-10-12  
**Status:** Implemented for a controlled, explicitly SYNTHETIC warehouse demonstration. No live WMS connection or production validation is claimed.

## Approved requirements and implemented behavior

- **Active warehouse scenario:** `data/workbook.xlsx` and `data/truck_etc.db` contain exactly **10 trucks**, **129 orders**, **283 pick lines**, 18 replay snapshots and 12 operator names. The unmodified prior 33-truck workbook is retained **only as historical, inactive reference** at `INFO/historical/historical_33_trucks_reference.xlsx`. It is not loaded into active web dashboards, REST APIs, CSV exports, or allocation calculations.
- **Initial conditions:** Snapshot **10 (18:30)**, default in `.env`, produces exactly **two conservatively `AT RISK` trucks**: `SH0908-1034` and `SH0908-1069`; remaining eight: **4 ON TIME + 4 ALL PICKED**. These risk labels are calculated by the pre-existing conservative rate/cutoff engine, not assigned manually. Other snapshots legitimately yield different classifications, including `NO RATE` when evidence is insufficient.
- **Synthesis provenance:** Demo inputs were generated from ten selected shipment/order/line histories from the archived reference. A synthetic 10-minute departure extension was applied to shipment `SH0908-1034`. For worktype 1, recorded `LM005S1` labor segment time was explicitly modeled at **65% of the reference** to calibrate available team rate. Operator and worktype experience include separately labeled synthetic familiarity assumptions. These calibrated/synthesized values **are not live actual operations, and are not a validated 30-day pace**. The workbook contains a `SCENARIO_README` explanation and data source markings.
- **Deadlines:** `required_pick_ready = truck departure − configurable truck-specific loading time (default 30 min) − fixed safety buffer (10 min)`. Overrides are saved in SQLite; they can change dynamically after initialization. **Source-worktype** deadlines use the same buffer.
- **Individual pace:** Measured worktype pace from available completed lines per recorded labor hour where present. Historical scope is just one day; no false 30-day performance claim. Cross-trained workers with no observed destination pace use the previously approved **SYNTHETIC `min(source pace, destination per-person pace)`** fallback and visible evidence label.
- **Ranked experience-first candidates:** Only active workers with observed or explicitly simulated target-worktype experience are included. Safely transferable workers appear first, ranked by destination pace; unsafe experienced workers remain visible as `UNSAFE / unavailable` with a reason, and cannot be selected. Nonexperienced workers excluded.
- **Exact minimal staffing count:** For the chosen target truck/worktype, compute `required team pace = priority lines ahead / hours to buffered deadline`. Exhaustively test 1-person, then 2-person, etc., subsets of currently safe experienced workers until a **source-safe combination** makes the **conservative** target worktype finish by deadline. Only then recommend the minimum **additional operator count**; after selections, recalculate remaining count. If none is feasible, show no feasible recommendation and explain alternative actions. These are *advisory calculations*, not automatic allocations.
- **Two distinct reference cases (evaluated independently, not simultaneously):** Truck `SH0908-1034`, WT2, needs **one** additional feasible worker (`dclements`). Truck `SH0908-1069`, WT2, needs **two** (`dclements`, `jmccraw`). The same worker cannot be sent to both trucks at once; once a scenario move is confirmed, the planner recasts subsequent recommendations for remaining eligible staff.
- **Graph and source safety:** Chart shows original and each successive simulated conservative target ready time compared with the buffered required deadline; source chart compares conservative readiness **before versus after** removal alongside each source worktype's own deadline. Source safety is checked cumulatively at each step. The planner separately shows whether a target **truck** remains at risk due to another worktype. NO RATE does not get reported as safe.
- **Supervisor confirmation:** Selection is a **preview only**. **Allocate** plus confirmation explicitly commits the set of validated moves **atomically to in-process temporary state scoped to one supervisor browser session**, never an allocation SQLite table, workbook, source assignment or WMS. Browser cookie holds only an opaque session ID. Session reset, process restart or eight-hour inactivity clears moves. Confirmed moves start at their selected snapshot and are re-evaluated for later snapshot availability/source safety; skipped moves are flagged. Loading overrides alone are persisted in SQLite as approved.
- **Preview separation:** Each pending preview is scoped to `(snapshot, target worktype, shipment)` so switching trucks does not silently carry the pending selections. The confirmed scenario remains scoped to the session and affects subsequent snapshots when safe.
- **Assignment risk:** Individual assignment rows inherit their parent shipment/worktype risk; this is intentionally **not** an invented task-specific completion order or timing model.
- **Page consistency:** Dashboard, truck detail, planner, operator listing/profile, CSV export, risk and eligibility APIs all use the same active ten-truck scenario and temporary confirmed session moves.

## Source modifications in this release

| File | Modification |
|---|---|
| `data/workbook.xlsx` | New clearly labeled 10-truck active synthetic replay |
| `INFO/historical/historical_33_trucks_reference.xlsx` | Added archival, inactive 33-truck reference workbook |
| `data/truck_etc.db` | Rebuilt source records and 18 snapshots from active ten-truck workbook; previous persisted advisory allocations removed |
| `scripts/build_ten_truck_demo.py` | Reproducible workbook synthesis using `artifact_tool`; does not run during Flask execution |
| `calculations/excel_io.py` | Source-data provenance from `SCENARIO_README` |
| `calculations/supervisor.py` | Exact minimum feasible operator set, cumulative source safety, per-shipment conservative projection, visible simulated experience and unsafe candidates, accurate NO RATE handling |
| `calculations/operator.py` | Explicit current synthetic-pace provenance in operator views |
| `models/models.py`, `models/database.py` | Remove persistent advisory allocation model and legacy table, preserve separately persisted loading overrides, refresh source provenance |
| `app.py` | Temporary server session allocations; shipment-isolated previews; planner recommendations, source/target projections, updated dashboard/APIs/export statuses |
| `templates/planner.html`, `static/js/planner.js` | Minimum count, gap, ranked candidate table, source impact visualization, sequential preview, explicit Allocate review and reset |
| `templates/truck_detail.html`, `templates/operator_detail.html` | Dynamic truck recommendation and honest operator pace labels |
| `tests/test_ten_truck_workflow_v8.py` | Ten scenario-specific acceptance tests |
| `tests/test_supervisor.py`, `tests/test_app.py`, `tests/test_dashboard_ui.py`, `tests/test_design_system_v6.py`, `tests/test_pickup_risk_feature.py` | Update obsolete 33-truck assumptions and improve database-loading override test cleanup |
| `tests/conftest.py`, `tests/test_data_integrity.py` | Run historical reference/parity tests against archived 33-truck workbook instead of reinterpreting the synthetic demo |
| `README.md`, `PROJECT_ACTIVITY_INDEX.md`, `docs/project_tracking/*` | Release instructions, provenance, issue, decision, task and manifest documentation |

Temporary scenario exploration scripts (`scripts/_explore_synth.py` and `scripts/_explore_synth2.py`) are excluded from the release; their findings and chosen calibrations are recorded here.

## Verified test evidence

- **44/44 focused pytest cases passed** with Flask dependencies made available from a separate local test environment. Tests cover active shipment/line referential integrity, exactly 2 calculated risks, 1/2-person independent scenarios, source safety, preview versus allocation, supervisor session isolation/reset, future snapshots, loading settings, risk APIs, CSV filtering, Jinja route renders, CSS design contract and source provenance.
- **No persistent allocation table:** tested with SQLite schema introspection after explicit confirmation. Loading override persistence is verified independently and reverted by its test to prevent contaminating other test cases.
- **Data count checks:** every replay snapshot contains exactly 10 active truck IDs; 129 order IDs and 283 pick-line mappings refer to active shipments; deleted/archived truck routes do not return a detail page; filtered CSV has ten data rows.
- **Static syntax:** Python bytecode compilation and `node --check` for changed planner/dashboard/shell JavaScript succeeded.
- **Broader historic parity suite:** **NOT fully verified** in this run; execution exceeded the test time limit with no reported assertion failure in its partial output. Historical parity should be run overnight/in CI in a properly provisioned environment before deployment.
- **Actual Chrome layout/e2e:** not independently rerun for v8. Flask test-client page rendering and UI structure were tested; graphical/browser acceptance should be done locally.

## Remaining limitations and follow-up

1. Demo activity and productivity are **synthetic or reference-derived**; no live WMS transactions, verified individual worktype qualifications, 30-day performance history, travel/setup time, congestion, replenishment, or task-level pick order. Do not use this model for real-world staff moves without data validation.
2. The exhaustive minimum-operator search is safe for the small 12-worker demo but needs a bounded/optimized solver for a large warehouse roster.
3. Temporary scenario memory is one Python process; a multi-worker production web server would require an explicitly temporary, expiring session-store design (not permanent allocation records). No authentication/RBAC is included. Server restart intentionally erases all temporary moves.
4. The initial **exactly-two-risk** invariant is guaranteed only for snapshot 10 with the default 30-minute loading settings and no confirmed moves. A supervisor's persisted override, subsequent snapshot or confirmed scenario legitimately changes the count. Reset overrides to default if reproducing the initial demonstration.
5. Complete historical suite and live-device GUI validation remain outstanding.

## Run and reproducibility

```
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`, choose snapshot 10 and Workforce Allocation. To rebuild the active SQLite cache from the included synthetic workbook: `python -m flask --app app init-db`. **Do not run `scripts/build_ten_truck_demo.py` during normal operation**; it is a development-only data-generation script requiring `artifact_tool` and re-creates the scenario workbook from the inactive archived reference.
