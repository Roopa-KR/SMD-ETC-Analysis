# Operator pace data adequacy audit — v3 (2026-10-10)

**Status:** Review and evidence only. No new pace algorithm has been implemented. Application source, Excel and SQLite files remain unchanged.

## Supplied data coverage (SQLite read-only mirror of current app replay)

- `src_ti102c`: **1,163 completed pick-line records**, all on **2026-09-08**, with operator/worktype, processed pieces and completion timestamp. Exactly **one transaction date**, not a month.
- `src_lm005s1`: **282 snapshot-level labor records** across **18 snapshots**, **12 distinct operators**, **6 worktypes**. Records include per-row `TOTALTIMEINSEC`, `SNAPSHOT_NO`, `RESOURCENAME`, `WORKTYPE`, `WIPIND`, `STARTDATETIME`, but no durable month-long history or verified break/productive-time classification.
- Latest snapshot is **2026-09-08 20:30** (snapshot 18). It provides **14 operator–worktype labor pairs**, of which **12 pairs** have completed-line evidence and **2 pairs** have no completed lines recorded for that worktype. Those 12 measured worktype pairs span 12 operators.
- `src_operator_experience`: **15 entries**, all marked **SIMULATED PLANNING ASSUMPTION**. These are approved by the user to count as demo eligibility evidence, **not proof of historical productivity, proficiency, or verified certification**.
- `src_line_map`: **1,163 mapped lines**, **625 distinct `ASSIGNMENTID` values**, 421 distinct orders. Referential match against `src_order` is complete (0 unmapped orders) and all current `src_ti102` / `src_ti102c` lines map to `src_line_map` (0 unmatched rows).
- A second legacy workbook under `INFO/` is named for **2026-09-08**. No full-month operator history is evidenced in the supplied project data or database.

## The computable single-day statistic (not monthly pace)

For an operator *o* and worktype *w* at the last snapshot:

`DAY_OBSERVED_LINES_PER_HOUR(o,w) = count of TI102C completed lines for (o,w) at/before 20:30 / (SUM LM005S1.TOTALTIMEINSEC for (o,w) at snapshot 18 / 3600)`

The CSV `OPERATOR_PACE_SINGLE_DAY_v3.csv` contains all 14 combinations, provenance and the **NO** monthly-availability flag. It is derived from the current SQLite replay without altering the workbook. A value without completed lines is **blank/unknown**, **not automatically 0 productivity**; absence may mean no measurable output for that worktype.

Sample evidence (single replay day only): `ekim`/Prescription = 223 lines / 3.4006 h = **65.58 lines/h**; `amack`/Prescription = 13 / 3.6981 h = **3.52 lines/h**; `lhall`/OTC = 128 / 1.8411 h = **69.52 lines/h**; `tedwards`/Cage = 164 / 1.4053 h = **116.70 lines/h**. These extreme differences require contextual quality checks before inferring month-long performance.

**Cumulative-snapshot trap:** `TOTALTIMEINSEC` reflects time accumulated at successive snapshot cuts. E.g. `amack` has a 60-second labor entry at snapshot 1, increasing through snapshot 16 to 13,313 seconds, and the same final total in snapshots 17 and 18. Summing labor across all snapshots grossly overcounts exposure. Use a non-overlapping transaction-duration history or one correct end-of-period accumulated total per period/segment, deduplicated and reconciled to shift starts/stops. Within snapshot 18 multiple rows for an operator/worktype represent segments; those can be summed for the snapshot, subject to overlap verification.

**Potential contamination:** All demo source values are present in the supplied dataset. They have not been independently validated as real production transactions. “Observed” here means **observed in supplied rows**, not verified operational truth.

## Proposed reliable monthly algorithm (recommendation, NOT approved or implemented)

1. Gather at least the agreed reporting month of *raw* daily completed-pick events and *non-overlapping* operator worktype labor intervals. Join on operator ID, warehouse, worktype and date/interval; include reassignments and avoid double counting archived/live tables.
2. Per operator × worktype × day, compute **completed lines** = count of uniquely completed `TI102ID` at status 3, and **effective labor hours** = sum of validated worktype-active seconds / 3600. Identify breaks, inactive time, training, travel, interruption and duplicate intervals using business-defined codes (do not silently drop time).
3. Monthly `observed_pace(o,w) = SUM(daily completed lines) / SUM(daily productive hours)` **over the same reporting dates**, not the arithmetic average of daily rates. Record numerator, denominator, first/last activity, active days, coverage, completeness/exception flags and data provenance.
4. Track enough daily variation to support a conservative bound. Prefer a documented rolling historical lower percentile or validation-based forecast **only after** choosing a minimum number of valid shifts/lines and a worktype-specific aggregation policy. The current lowest-operator-rate envelope is a **sensitivity bound, not a statistical confidence interval**.
5. For eligible cross-trained workers with **no measured target worktype pace**, retain `pace = UNKNOWN` unless a separately approved *clearly synthetic* transfer-prediction model is selected. Do **not** relabel a synthetic estimate as monthly actual.
6. Separate line pace (lines/h) from pieces pace (pieces/h), adjust for work mix if reliable units and complexity measures exist, and benchmark/review unexpected outliers rather than assuming equal workload complexity.
7. Reconcile team baseline `ACTUALRATELINES = (TOTALLINES / TOTALTIMEINHRS) * RESOURCES` with the sum of individual observed paces: these are **not generally numerically equal**. Preserve the approved existing incremental delta rule for previews and make the source/destination reconciliation traceable; test against negative rates, inactive source staff and duplicate operator selection.

## Additional data needed for monthly accuracy

- Completed TI102C/TI102 historical events for all desired dates, with unique ID, operator, worktype, completed timestamp, warehouse/client, count/pieces and correction/cancellation markers.
- LM005S1/LM005S1H raw activity periods for those dates: operator, worktype, active start/end, reliably defined productive seconds, breaks/inactive intervals and shift boundaries. Avoid additive snapshot copies.
- Worktype qualification/familiarity history (simulated is permitted for **demo eligibility**, but not historical production skill); ideally effective dates/training approval.
- If available: per-assignment difficulty, order/quantity mix, operator reassignment timestamps, blocking/downtime flags, partial picks/shorts, resource overlap checks, and reliable timezone.

## Verification and limitations

- Read-only SQL used; SQLite contents unchanged. CSV was generated with standard-library sqlite3/csv.
- Final-snapshot labor pairs: 14; observed pair completions: 12; total line counts in the CSV: 1,163; distinct operators: 12.
- **Not proven:** Full-month pace, skill equivalence across worktypes, labor/line timestamp alignment in real operations, whether times exclude breaks, or which synthetic destination estimator is acceptable.
- No full workbook re-import/recalculation was performed for this audit. The existing application's `.xlsx` golden reference was left untouched; the source mirror and current code are the evidence base.
