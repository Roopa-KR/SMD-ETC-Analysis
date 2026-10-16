# Version 11 — Consistent At Risk status: corrected demo labor time and picking-time pace

**Date:** 2026-10-13
**Input:** `SMD-main-updated-20261012-v10.zip` · **Output:** `SMD-main-updated-20261013-v11.zip`
**Decision:** the user chose option C, applying both fixes, with a 10-minute gap limit (configurable).

## Reported problem

SH0908-1034 showed **At Risk at 18:30 only**, On Time at 18:15 and 18:45. SH0908-1069 showed At Risk at 18:30 and 18:45 only.

## Investigation (before the fix)

**Ruled out:**
- Truck identity: all 10 shipment IDs are present at all 18 snapshots, and no orders move between trucks.
- Deadlines: no departure changes, so each truck's deadline is constant all day.
- Snapshot data: at every snapshot, the open lines equal exactly the lines released and not yet picked.
- Status carry-over: every snapshot is recalculated from scratch.

**Root cause:** SH0908-1034, OTC (WT2), the truck's slowest area; buffer deadline 20:15.

| Snapshot | Open OTC lines | Lines ahead | Cautious rate | Projected ready | Status |
|---|---|---|---|---|---|
| 18:15 | 2 | 6 | 8.2 lines/h | 18:59 | On Time |
| 18:30 | 20 | 23 | 8.8 lines/h | 21:06 | **At Risk** |
| 18:45 | 7 | 8 | 15.7 lines/h | 19:15 | On Time |

1. **A burst of 20 OTC lines** was released for the truck between 18:15 and 18:30. This was a genuine input change.
2. **Pace counted waiting as picking.** Pace was measured as lines ÷ logged-in hours. mmathis had been logged in 2.94 h with only 13 lines available, so he measured 4.4 lines/h. While actually picking he did 17.6 lines/h. The cautious rate is pickers × slowest pace = 2 × 4.4 = 8.8 lines/h.
3. **The burst was cleared in minutes.** mmathis and lhall picked 13 of the lines between 18:30 and 18:45 (about 26 lines/h each). At 18:45 the work was mostly gone and the status flipped back. The truck actually finished at 18:53, 82 minutes before its deadline.
4. **The demo data amplified it.** The 10-truck demo kept 100% of logged hours (WT1 at 65%) but only 16–49% of the picked lines, so all pick rates were 2–4 times too low.

SH0908-1069 followed the same pattern. At 18:45 its slowest area was Prescription: esica measured 3.0 lines/h logged-in vs 11.2 lines/h while picking. Its lines were picked by 19:34, against a 20:20 deadline.

**Conclusion:** the one-snapshot At Risk was a **false alarm**, not a lost status. Forcing it to persist would have been wrong.

## Fixes

### B — Demo labor time corrected (data)

- Script: `scripts/rescale_demo_labor.py` (development only; idempotent).
- Rule: each LM005S1 session's `TOTALTIMEINSEC` = the real-day (archived reference) value × that work type's share of picked lines kept in the demo.

| Work type | WT1 | WT2 | WT3 | WT4 | WT5 | WT6 |
|---|---|---|---|---|---|---|
| Share of lines kept | 0.192 | 0.306 | 0.304 | 0.207 | 0.387 | 0.318 |

- The WT1 × 0.65 calibration is removed.
- Session start/end times, WIPIND and operators are unchanged.
- The edit is made in the sheet XML. Only `LM005S1` (TOTALTIMEINSEC, TOTALTIMEINMIN, DATA_TYPE, title) and `SCENARIO_README` change; every other sheet is byte-identical.
- Effect: at 18:30, the per-person OTC rate is 29.8 lines/h, against 25.2 on the real day (it was 9.1).

### A — Planning pace on picking time (calculation)

- Module: `calculations/pace.py`, used by `calculations/supervisor.py`. This is the layer behind every status, the planner and the charts.
- Picking time per operator / work type / day:

```
lead      = min(first pick − start of its session, gap limit)
between   = Σ min(gap between consecutive picks, gap limit)
trailing  = min(now − last pick, gap limit)    only while still logged in to that area
```

- Rates:

```
operator pace   = lines ÷ picking hours
per-person rate = area lines ÷ area picking hours
team rate       = per-person × logged-in pickers
cautious rate   = min(team rate, pickers × slowest operator pace)
```

- The structure is unchanged; only the hours are now picking hours.
- Settings in `.env`:
  - `PACE_BASIS=picking_time` (default) or `logged_time`, which reproduces the Excel equation exactly.
  - `PACE_GAP_CAP_MINUTES=10` (allowed 1–120).
- The Excel-equation engine (`etc.py`, `truck.py`, `uncertainty.py`) is **unchanged**. It remains the logged-time reference, and historical Excel parity still passes.

## Results across all 18 snapshots (default settings)

| Truck | 16:15 | 16:30–17:30 | 17:45 | 18:00 | 18:15 | 18:30 | 18:45 | 19:00 | 19:15+ |
|---|---|---|---|---|---|---|---|---|---|
| SH0908-1034 | no rate | no rate | on time | on time | on time | **on time** (19:13 vs 20:15) | on time | on time | on time, then picked |
| SH0908-1069 | no rate | no rate | on time | on time | on time | **on time** | **on time** | on time | picked / on time |

- **No status is At Risk or Cutoff Passed anywhere.** Every truck the model calls On Time actually finished its open lines by its deadline. This is tested at every snapshot.
- **Every status change has a recalculated cause.** Each change between consecutive snapshots coincides with a change in open lines, lines ahead, pickers, rates or the deadline. This is tested.
- **No-rate statuses are genuine.** They mean no picker is logged in to an area that has open work, or no line has been completed yet. The 19:00 case is one Cooler line with nobody logged in to Cooler. A fallback rate is still a business decision.
- **Backtest of the cautious ready time against the actual finish:** median error −3 min, median absolute error 7.5 min. v10 was +2 min and 16 min, with 5 false at-risk rows.

## Related corrections found while validating

- **Recommendation no longer wastes operators.** If a truck's slowest area has no safe fix, operators are no longer recommended into its other areas, because those moves cannot change the truck's ready time. v10 showed "+2 operators" while the ready time stayed red.
- **Minute texts follow the true direction.** A ready time 20 seconds past a deadline now reads "<1 min late" or "<1 min into buffer", never "0 min early".
- **Operator pages show both measures.** The profile and directory now show logged-in time and pace (Excel equation) beside picking time and **planning pace** (used for ETC and allocation). The planner states the pace basis.

## Effect on the demo

The default snapshot (18:30) now has **no at-risk truck**: 6 on time and 4 all picked. That is the correct result for this data. Tests of the allocation features use genuine deadline pressure from the existing per-truck loading-time setting (`tests/conftest.py`):

| Loading time for SH0908-1034 | Pick cutoff | Before | After |
|---|---|---|---|
| 100 min | 19:15 | yellow | green with +1 (dclements) |
| 110 min | 19:05 | red | green with +2 (dclements, ekim) |
| 130 min | 18:45 | red | no safe combination |

## Files

| Change | File |
|---|---|
| Added | `calculations/pace.py`, `scripts/rescale_demo_labor.py`, `tests/test_picking_pace_v11.py` (8 tests), this report, `docs/images/v11-*.png` |
| Modified | `data/workbook.xlsx` (LM005S1 labor time, SCENARIO_README); `data/truck_etc.db` (rebuilt); `calculations/supervisor.py`; `calculations/ready_comparison.py`; `config.py`; `.env`; `app.py`; `templates/operator_detail.html`, `operators.html`, `planner.html`, `components/ready_chart.html`; `static/css/style.css`; tests `conftest.py`, `test_ten_truck_workflow_v8.py`, `test_truck_detail_v9.py`, `test_ready_chart_v10.py`, `test_app.py`; README and tracking documents |
| Unchanged | ETC Excel-equation engine; deadlines (departure − loading − buffer); source safety; minimum-staffing search; session-only allocation |

## Verification

- **Full test suite: 193 passed.**
- **Chromium check** of the dashboard, truck page, operator profile and operators directory against the running app, with no page errors.
- **Historical Excel parity tests** (archived 33-truck workbook) still pass.
