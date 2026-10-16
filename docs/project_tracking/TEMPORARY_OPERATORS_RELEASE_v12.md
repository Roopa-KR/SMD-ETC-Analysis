# Version 12 — Temporary Operator Allocation (reallocation first)

**Date:** 2026-10-13
**Input:** `SMD-main-updated-20261013-v11.zip` (verified against its manifest; 193 tests passed before changes)
**Output:** `SMD-main-updated-20261013-v12.zip`

## What the supervisor can now do

When a truck or work type is at risk, the planner first tries **safe reallocation of existing operators**, exactly as before. Only if that is impossible or not enough does it offer **temporary operators**, in the fewest number needed.

1. **Reallocation first.** The fewest safe, experienced existing operators are searched (unchanged v8 rule: every source truck must stay on time). If reallocation alone meets the safety buffer deadline, temporary operators are **not offered**, and the server refuses them.
2. **Temporary operators when needed.** They are offered when any of these holds:
   - no eligible operator exists;
   - every eligible operator is unsafe to move;
   - safe reallocation is not enough.
3. **Fewest temporaries first.** Among plans with the same number of temporaries, the plan with the fewest reallocations wins, then the one with the most slack.
4. **Temporary Operators panel** (planner, below the staffing requirement) shows:
   - additional operators required in total;
   - existing operators safely available;
   - operators selected for reallocation;
   - temporary operators still required;
   - expected ready time after the proposed allocation;
   - the truck result: meets cutoff and buffer / meets cutoff, buffer not kept / misses pick cutoff.
5. **Controls:**
   - **Use recommended plan** puts the recommended reallocations into the preview and sets the temporary count.
   - **Temporary operators** (0–10) + **Preview** lets the supervisor choose the number.
   - **Allocate Temporary Operators** confirms the temporaries plus any selected reallocations together, after a confirmation dialog.
   - **Clear temporary preview**.
6. **Insufficient numbers.** If the chosen number is too low, the panel shows the remaining gap and the next action. If even the maximum (10) cannot meet the deadline, it says so and points to the departure or loading plan.
7. **Chart rows:**
   - original assignments;
   - after allocation (confirmed), when any exists;
   - after reallocating existing operators;
   - after adding temporary operators.

   Each row is green, yellow or red against the pick cutoff and safety buffer deadline. Temporary rows are marked as using an assumed pace.
8. **Session only.** Reallocated and temporary operators live only in the supervisor's server session. **Reset allocations** (or session expiry or a restart) restores the original assignments. Nothing is written to SQLite, the workbook or the WMS.
9. **Labels.** Existing, reallocated and temporary operators are labelled separately:
   - the operators directory has a Session role column and a row for each temporary operator;
   - the planner lists confirmed reallocated and temporary operators separately;
   - the truck page shows "+N temporary" in the Work types table and "R reallocated + T temporary" in the operator-gap card;
   - the dashboard insight reads "N reallocated · M temporary operators".

## Calculation

```
pick cutoff              = departure − loading time
safety buffer deadline   = pick cutoff − safety buffer                      (unchanged)
temporary pace           = TEMP_OPERATOR_PACE_PCT % × work type per-person rate     (ASSUMPTION)
cautious credit / temp   = min(temporary pace, slowest measured operator pace in that work type)
required cautious rate   = lines ahead ÷ hours to the safety buffer deadline
temporary operators      = ceil((required cautious rate − cautious rate after reallocation)
                                ÷ cautious credit per temporary)            verified by recalculation
```

- **Same rule as any added operator.** A temporary operator is credited exactly as the engine already credits a reallocated one: the point rate rises by the assumed pace, and the cautious rate by at most the slowest measured operator's pace.
- **Status rule unchanged.** Status is still decided by the cautious rate, so green is never shown unless the cautious ready time is at or before the safety buffer deadline.
- **No pace, no estimate.** If a work type has no measured per-person rate, no temporary pace is assumed and the panel explains why.
- **Pace follows each snapshot.** Confirmed temporaries are re-evaluated at every later snapshot using that snapshot's per-person rate.
- **No plan that can't work.** If the truck's slowest area cannot be fixed even with reallocation plus the maximum temporaries, the chart recommends nothing and explains why (v11 rule extended).

**Settings (`.env`):**

| Setting | Default | Meaning |
|---|---|---|
| `TEMP_OPERATOR_PACE_PCT` | 100 | Temporary pace as % of the work type's per-person rate. Precedent: the earlier SMD workbook's synthesized `TEMP_PACE_PCT`. |
| `TEMP_OPERATOR_MAX` | 10 | Most temporaries per work type. Precedent: the earlier workbook's pool of 10. |

Both are **assumptions to be confirmed by SMD**.

## Scenario validation (genuine calculations; pressure only via per-truck loading time)

| # | Scenario | Case | Result |
|---|---|---|---|
| 1 | Safe reallocation is enough | 18:30 SH0908-1034 OTC, loading 100 | dclements; temporaries not offered (server refuses) |
| 2 | No eligible operator | 18:45 SH0908-1034 Cases, loading 110 | no candidates → 3 temporaries, green |
| 3 | Eligible but unsafe | 18:15 SH0908-1069 Prescription, loading 140 | 3 experienced, all unsafe → 2 temporaries, green |
| 4 | Some reallocation + temporaries | 18:45 SH0908-1069 Prescription, loading 110 | dclements + 1 temporary, green (2 temporaries without dclements) |
| 5 | Temporaries insufficient | 18:30 SH0908-1034 OTC, loading 130 | needs 3 reallocated + 11 temporaries > max 10 → no plan, explained |
| 5b | Supervisor count too low | scenario 4 with 0 temporaries | remaining gap 1, yellow |
| 6 | Meets cutoff, not buffer | scenario 2 with 2 temporaries | yellow, "Add 1 more" |
| 7 | Meets cutoff and buffer | scenario 2 with 3 temporaries | green |
| 8 | Trucks compete | 18:15 SH0908-1057 (90) and SH0908-1003 (100), Prescription | both want lhall. After 1057's plan is confirmed, lhall is no longer offered to 1003, whose plan drops from lhall + 6 to 5 temporaries (the shared Prescription area already gained capacity) |

Also seen in the data: at 19:00, SH0908-1057's Cooler line has nobody logged in and no experienced operator. One temporary operator at Cooler's measured rate makes the truck green. The "unknown" explanation for the original row is kept.

## Files

| Change | File |
|---|---|
| Added | `calculations/temporary.py`, `calculations/bands.py`, `tests/test_temporary_operators_v12.py` (13 tests), this report, `docs/images/v12-*.png` |
| Modified | `calculations/supervisor.py` (`temporary_pace`, `add_temporaries`, `build_state(..., temporaries=)`); `calculations/ready_comparison.py` (reallocation pass + temporary pass; new chart rows; counts per row); `calculations/truck_detail_view.py` (gap card); `calculations/dashboard_view.py` (insight); `app.py` (session `confirmed_temps` / `temp_preview`; actions `temp_plan`, `temp_set`, `temp_clear`, `allocate_temps`; reset; temporaries in every recalculation); `config.py`, `.env`; `templates/planner.html`, `operators.html`, `components/ready_chart.html`; `static/js/ready_chart.js`, `planner.js`; `static/css/style.css`; `tests/test_ready_chart_v10.py` (3 tests updated for the new rule); README and tracking documents |
| Unchanged | Workbook, SQLite contents, Excel-equation engine, picking-time pace, deadlines, source safety rule, reallocation search |

## Business rule change (recorded)

The v4–v11 rule was "existing headcount only; never create or imply temporary labour". It is **superseded by the user's explicit v12 request**. Temporary operators are now allowed only after reallocation, only in the calculated minimum number, only on supervisor confirmation, and only for the session.

## Verification

- **Full test suite: 206 passed** (193 previous + 13 new; 3 v10 chart tests updated for the new rule).
- **Chromium walk-through** against the running app (1440 px and 390 px), with no page errors and no horizontal overflow:
  1. recommended plan;
  2. Use recommended plan;
  3. Allocate Temporary Operators (the truck stays yellow because OTC still holds it back, and the chart shows the next step);
  4. session list and operators directory;
  5. 2-of-3 temporaries showing yellow.
- **No persistence:** workbook hash unchanged after allocation; no allocation table in SQLite; a second session does not see the first session's temporaries.

## Known limits

- **Assumed pace.** Temporary-operator pace and the maximum of 10 are assumptions; SMD should confirm them, along with onboarding and walking time, which is still not modelled.
- **Per-work-type panel.** The panel plans one work type at a time. The chart and statuses plan the whole truck, and the panel names any other area still holding the truck back.
- **Search limit.** The exhaustive search covers up to 10 safe candidates per work type. That is adequate for this 12-person roster; a large warehouse would need a bounded solver.
- **Logged hours below picking hours (from v11).** On the operators page some logged hours are lower than picking hours. v11 scaled demo labor time to the share of lines kept, but pick timestamps are real. This is a demo-data artefact, not a calculation error.
