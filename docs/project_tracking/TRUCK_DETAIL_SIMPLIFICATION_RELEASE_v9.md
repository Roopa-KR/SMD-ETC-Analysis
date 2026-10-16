# Version 9 — Truck Detail Chart Simplification & Dynamic Operator Gap

**Date:** 2026-10-12
**Source:** `SMD-main-updated-20261012-v8.zip`
**Scope:** Presentation and display adaptation only. Original warehouse formulas, per-truck load overrides, fixed 10-minute safety buffer, 10-truck workbook, operator safety checks, and session-only allocations remain unchanged.

## Implemented

1. Removed three truck-detail UI plots **completely**, including their Plotly rendering code:
   - Open lines and slack over the day (`burn-chart`)
   - Lines picked per 15 min (this truck) (`through-chart`)
   - Pickers logged in per area (`pickers-chart`)
   Their SQL/workbook inputs and calculation functions remain unchanged; existing dashboard analytics are not removed.
2. The **When each area finishes vs the pick cutoff** graph shows only (a) conservative area ready time, (b) a shaded fixed safety-buffer window from *departure − loading − 10 minutes* to *departure − loading* and its required-ready boundary, and (c) projected conservative ready time after adding operators. It uses two Plotly scatter traces and an annotation/shape overlay for the safety buffer, **not a third fake numeric series**. No historic throughput, staffing, uncertainty envelope or slack trend is drawn in this graph. A missing/unmeasurable projection stays missing rather than appearing successful.
3. **Operator Gap (Legacy Baseline)** now reports `recommend_minimum()`'s exact remaining minimum feasible operator count for the relevant truck/worktype at the selected snapshot. The metric is not the number of pickers already assigned. It shows the pace/lines/available-hours calculation explanation. A feasible recommendation displays the projected result in the graph; an unavailable plan displays **Not feasible** (never zero). For more than one at-risk area, the card displays **By area** and individual minima, never adds potentially overlapping operator sets. The existing per-worktype table also consumes this exact recommendation.
4. **Temporary selection behavior:** Any pending supervisor preview for exactly `snapshot:worktype:shipment` supersedes the suggestion in the graph. Its remaining operator gap is recalculated from the selected scenario. The baseline current ready time continues to reflect only **confirmed** temporary session allocations. Previewed candidates never change baseline. On explicit Allocate, source/target state and graph are recalculated. Session reset returns to the original baseline. Candidate eligibility and source safety are validated by existing `preview_state()`; operator movements are never written to SQLite/WMS/workbook.
5. Simplified browser payload to only `{required_ready, physical_cutoff, buffer_minutes, worktypes}`. Removed unused `trends`, `throughput`, `pickers` and unnecessary series from this graph's JSON/JS. The backend `truck_detail()` still computes its historical trend data, preserving other consumers and no changes to ETC logic.

## Modified / created files

- **Modified:** `templates/truck_detail.html`, `static/js/truck_detail.js`, `app.py` (truck-detail display only), and documentation/tracking/index files.
- **Added:** `calculations/truck_detail_view.py` (pure read-only projection adapter), `tests/test_truck_detail_v9.py` (7 new checks), `docs/images/v9-truck-detail-desktop.png`, `docs/images/v9-truck-detail-mobile.png`, this report.
- **Unchanged:** `calculations/supervisor.py`, `calculations/truck.py`, `calculations/etc.py`, original source/engine calculators, `data/workbook.xlsx`, `data/truck_etc.db`, eligibility and session storage, routes and API responses other than truck-detail page chart payload.

## Recorded verification

- `pytest` targeted new UI and historical supervisor/dashboard/route suites: **51 passed**; **82 warnings** including pre-existing Pandas dtype future warnings.
- New tests validate eliminated graph text/IDs, graph series payload with the 10-minute cutoff band, the independent one- and two-operator calculations at default snapshot 10, the matching graph forecast, selection updates without confirmation, explicit allocation changes, session reset, and non-additive multi-area display.
- Default snapshot 10 v8 source: **10 trucks, 2 AT RISK**, with safe minimum recommendations **1** for `SH0908-1034` and **2** for `SH0908-1069`. Unconfirmed plans do not change the risk-count baseline.
- Chromium rendered actual Flask-generated HTML with locally embedded CSS/JS/assets at **1440 × 900** and **390 × 844** (browser direct localhost navigation blocked by environment). **2 chart traces**, **2 buffer shapes**, **0 page JavaScript errors**, **no page-wide horizontal overflow** at these two widths. Screenshots archived under `docs/images/`.
- Python syntax and Node.js JavaScript syntax validated. ZIP file-integrity and SHA-256 manifest to be verified at packaging.
- Test environment Flask libraries were extracted into a **separate test directory** from the earlier project's environment; they are **not included** in this release archive. The normal project `requirements.txt` remains in effect.
- Test suite can update local SQLite truck loading settings. Before ZIP packaging, the database was restored byte-for-byte from the v8 deliverable to avoid carrying over test modifications.

## Caveats

- The active workbook remains synthesized/reference-derived with only one recorded workday. Operator destination pace without measured target evidence is clearly flagged **SYNTHETIC** and is not validated 30-day observed performance.
- A preview or recommendation for one truck/area is **independent** of another proposal that might use the same person. The supervisor engine enforces cumulative source safety and cannot confirm the same operator twice.
- Only selected focused suites and offline browser-render checks were rerun. Full historical Excel-parity suite and live warehouse integrations were not checked in v9.
