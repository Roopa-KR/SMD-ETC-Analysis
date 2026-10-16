# Version 10 — Truck ready time: before vs after adding operators

**Date:** 2026-10-12
**Source:** `SMD-main-updated-20261012-v9_1.zip` (byte-identical to the v9 manifest)
**Output:** `SMD-main-updated-20261012-v10.zip`

## What changed for the supervisor

One chart, on both the **truck detail page** and the **Workforce allocation (planner) page**, now answers: *will this truck meet its pick cutoff and safety buffer, now and after adding operators?*

| Element | How it is shown |
|---|---|
| Before allocation | Projected ready time with the original operator assignments (row 1) |
| After allocation (confirmed) | Shown when this session has confirmed moves that affect the truck's work types |
| After adding selected operators | Shown while operators are in the planner preview (not yet allocated) |
| After adding recommended operators | Shown when nothing is selected and the truck is not green: the minimum safe set of experienced operators |
| ETC | Blue bar from "now" to the projected ready time, labelled with the duration |
| Pick cutoff | Solid vertical line, labelled with its time |
| Safety buffer deadline | Dashed vertical line, labelled with its time; the buffer is the shaded yellow band between the two lines |
| Ready time markers | Green / yellow / red circles, labelled with the exact time (24-hour), status word and the distance to the relevant deadline |
| Operators added | In the row label (+N) and the table |

A table under the chart repeats every value (ETC, projected ready, minutes early/late against both deadlines, status, slowest area) and works on narrow screens. A colour key sits between the chart and the table.

## Rules

```
Pick cutoff            = departure − loading time        (per-truck override, else workbook TRUCK_CONFIG.LOADING_MINUTES)
Safety buffer deadline = pick cutoff − safety buffer     (.env SAFETY_BUFFER_MINUTES, default 10)
Projected ready        = latest conservative ready time of the truck's open work types
ETC                    = projected ready − snapshot time

Green   ready ≤ safety buffer deadline
Yellow  safety buffer deadline < ready ≤ pick cutoff
Red     ready > pick cutoff
Unknown no pick rate for a required work type (never green; explained under the table)
```

Colours: green `#0ca30c`, yellow `#fab219`, red `#d03b3b`, ETC blue `#2563eb`. Every marker and table row also carries a status word and icon, so meaning never relies on colour alone.

Green is identical to the existing conservative **ON TIME** status. Yellow and red are both the existing **AT RISK** / **CUTOFF PASSED**, now split by whether the pick cutoff itself is still met.

## Calculation path (no new formulas)

- **Before:** `build_state(..., committed=[])`, so it always uses the original assignments, even after Allocate.
- **Confirmed:** `build_state(..., confirmed session moves)`. This is the same state used by the dashboard and statuses.
- **Selected / recommended:** `preview_state` applied cumulatively across the truck's work types. Each operator's individual pace is added to the destination area and removed from the source area, and every source truck must stay on time. Recommendations come from `recommend_minimum`. Moves are evaluated cumulatively, so one operator is never counted twice.
- **Truck result:** `truck_projection` over **all** the truck's open work types. A move that slows a source area this truck also needs is reflected.

New module: `calculations/ready_comparison.py` (read-only).

## Configuration made explicit

- The safety buffer is now `SAFETY_BUFFER_MINUTES` in `.env` (default 10, allowed 0–240). It was a code constant.
- The default loading time now comes from the workbook (`TRUCK_CONFIG.LOADING_MINUTES`, stored in `src_config`). It was a code constant of 30. Saving the default in the planner removes a truck's override.
- Page texts that said "fixed 10-minute" or "30 minutes" now show the configured values.

## Files

| Change | File |
|---|---|
| Added | `calculations/ready_comparison.py`, `templates/components/ready_chart.html`, `static/js/ready_chart.js`, `tests/test_ready_chart_v10.py`, this report, `docs/images/v10-*.png` |
| Modified | `app.py` (truck and planner routes, `original_state`, `ready_chart`, loading default), `calculations/supervisor.py` (configurable buffer and default loading; state exposes `buffer_minutes`, `default_loading_minutes`), `config.py`, `.env`, `models/database.py` (stores `LOADING_MINUTES`; rebuild when missing; `default_loading_minutes()`; override reset uses the configured default), `templates/truck_detail.html`, `templates/planner.html`, `templates/dashboard.html`, `static/js/planner.js` (old target chart removed, source-impact chart kept), `static/css/style.css`, `tests/test_truck_detail_v9.py`, `tests/test_design_system_v6.py`, `tests/test_dashboard_ui.py`, `data/truck_etc.db` (regenerated cache with `LOADING_MINUTES`) |
| Removed | `static/js/truck_detail.js` (replaced by the shared `ready_chart.js`) and the per-area "When each area finishes" chart. The per-area values remain in the Work types table. |
| Unchanged | `data/workbook.xlsx`, ETC / rate / conservative / source-safety / minimum-staffing formulas, session-only allocation behaviour |

## Planner layout

The planner page now reads top to bottom:

1. At-risk pickups
2. Truck ready time chart
3. Staffing requirement
4. Eligible operators and the review/Allocate panel
5. Loading time and source-area impact, side by side
6. Assignments and fleet table

## Verification

- **Full test suite: 184 passed** (`python -m pytest -q`, about 2 minutes). This includes 21 new v10 tests and the updated v9/v6/dashboard tests.
- **Colour boundaries:** exactly at the buffer deadline is green; exactly at the cutoff is yellow; any later is red; no rate is unknown.
- **Agreement with existing statuses:** checked for every truck at all 18 snapshots. Green appears only when the ready time is at or before the buffer deadline, and red only when it is after the cutoff.
- **Before/after cases tested:**

| Snapshot | Truck | Scenario | Before | After |
|---|---|---|---|---|
| 10 | SH0908-1034 | 1 recommended operator | red | green |
| 10 | SH0908-1069 | 2 recommended operators | red | green |
| 11 | SH0908-1069 | 1 recommended operator | yellow | green |
| 10 | SH0908-1069 | 1 selected operator | red | red |
| 10 | SH0908-1069 | 1 selected operator, 15 min loading | red | yellow |
| 10 | SH0908-1012 | none needed | green | — |
| 12 | SH0908-1057 | none possible | unknown | — |

- **Selection, Allocate and reset:** the chart changes after each selection and after Allocate, and returns to the original after reset (planner and truck pages). The source rate drops by the operator's own pace; the destination rises by the operator's pace.
- **Configured values:** setting `SAFETY_BUFFER_MINUTES=15` moves the SH0908-1034 buffer deadline from 20:15 to 20:10 on the page.
- **Browser check:** Chromium against the running Flask app at 1440 px and 390 px. No JavaScript errors and no horizontal page overflow. The only console errors were the external font/icon CDN, which the sandbox blocks. Screenshots are in `docs/images/v10-*.png`.

## Known limits (unchanged by v10)

- The demo data's pick rates are 2–4 times lower than the real day: it keeps all logged hours but only 16–49% of completed lines. The demo's red trucks therefore look worse than reality would.
- Before about 17:45 most trucks show "Unknown" because nobody is logged in to the area or no line has been completed yet. A fallback rate needs a business decision.
- No transfer or set-up time is modelled for a moved operator.
