# v14 release — calculated At Risk scenario and status evolution (2026-10-14)

**Package:** `SMD-main-updated-20261014-v14.zip` · **Tests:** 263 passed · **Data:** 10-truck SYNTHETIC replay of 08-Sep-2026, warehouse 100, with the v14 pressure scenario (not live SMD data).

## 1. Request

> Synthesize the data so that at least 2 trucks are at risk in the initial scenario. The truck statuses must change realistically across successive snapshots based on the actual calculated values, rather than being fixed or manually assigned.

Requirements and where each is met:

| # | Requirement | How v14 meets it | Evidence |
|---|---|---|---|
| 1 | At least two genuinely At Risk trucks, from calculated workload, pace, staffing, ETC, cutoff and buffer | SH0908-1034 and SH0908-1069 are **AT RISK at 18:30** because the engine's conservative ready time (19:57) is after the 19:50 safety-buffer deadline but before the 20:00 pick cutoff. No status label is stored anywhere. | §3, `test_two_trucks_are_at_risk_at_1830_from_the_calculation`, `test_nothing_is_hardcoded_the_same_trucks_are_on_time_with_more_staff_or_time` |
| 2 | Consistent truck IDs | The same 10 shipment IDs appear at all 18 snapshots; new lines join existing shipments and existing customers. | `test_truck_ids_and_line_counts_are_consistent_across_snapshots` |
| 3 | Logical evolution | Status is recalculated at every snapshot from that snapshot's open lines, logged-in pickers and measured pace. 18:30–19:00 At Risk → 19:15 Pick Cutoff Passed (a picker logs out) → departs 20:30 with one line left behind. | §4.1, `test_status_timeline_without_supervisor_action`, `test_every_status_change_has_a_changed_input` |
| 4 | Reallocation recalculates destination **and source** | A moved operator's real picks in the source area after the move are put back as open work (net of the remaining operators' spare capacity) and that area is re-evaluated. | §5, `test_source_area_loses_the_moved_operators_picks_minus_spare_capacity` |
| 5 | Dashboard, indicators and before/after graphs update right after confirmation | Confirmation stores the allocation in the session; every page is recomputed on the next request (dashboard cards, truck status, planner chart). | `test_confirming_an_allocation_updates_dashboard_truck_planner_and_later_snapshots`, screenshots §7 |
| 6 | No automatic All Picked / Safe | ALL PICKED requires adjusted open lines = 0 at a snapshot. An allocation that is too small or too late stays At Risk / Pick Cutoff Passed. | §4.3, `test_allocation_that_is_not_enough_never_shows_safe` |
| 7 | Consistent data; every change explainable | Every synthesized row is labelled `SYNTHETIC v14`; per-snapshot rows obey release ≤ snapshot < pick; the truck page lists each status with its calculated reason. | `test_synthesized_rows_are_labelled_and_physically_consistent`, `test_generator_is_deterministic_and_reproduces_the_active_workbook`, `test_status_history_table_lists_each_change_with_its_reason` |

## 2. What was synthesized (and why)

The v11–v13 demo had no truck at risk at 18:30. v14 adds one documented cause of pressure, built by `scripts/build_pressure_scenario_v14.py` from the frozen v13 workbook (`INFO/historical/ten_truck_v13_baseline.xlsx`). The script is deterministic (no random numbers) and idempotent.

| Change | Detail | Label |
|---|---|---|
| Late add-on OTC orders | 69001 (15 lines) and 69003 (4 lines) for SH0908-1034; 69002 (10 lines) and 69004 (3 lines) for SH0908-1069; released 18:20 and 18:49. Existing customers of those routes; item, location and quantity copied from existing WT2 lines. | SYNTHETIC v14 |
| Carrier appointment | Both trucks depart 20:30 → pick cutoff 20:00 (30 min loading) → safety-buffer deadline 19:50. | SYNTHETIC v14 |
| WT2 picking after 18:15 | Re-simulated with the same operators, their login sessions and each operator's measured pace (lhall 135 s/line, mmathis 165 s/line), earliest pick cutoff first. Picks before 18:15 are untouched. | SYNTHETIC v14 |
| Labour | lhall's session ends at her **recorded** logout 19:13 (unchanged). mmathis works overtime to 20:25 (recorded logout 19:15). | SYNTHETIC v14 (overtime) |
| Cross-training | None added. | — |

Tables rewritten: TI102C, TI102 (per-snapshot rows), LM005S1, OB_ORDER (133 orders), OB_LINE_MAP (315 lines), OB_SHIPMENT (counts and note), SCENARIO_README. The other eight trucks keep their v13 statuses.

## 3. Status rule (unchanged formulas, sharper wording)

- Conservative ETC = lines ahead (earliest pick cutoff first) ÷ cautious rate (logged-in pickers × slowest measured picking pace in the area).
- Pick cutoff = departure − loading time. Safety-buffer deadline = pick cutoff − `SAFETY_BUFFER_MINUTES` (10).
- **ALL PICKED** — no open lines.
- **PICK CUTOFF PASSED** — the snapshot is at or after the pick cutoff with lines open, **or** the conservative ready time is after the pick cutoff. (v13 called the projected case "AT RISK"; v14 separates it so the 19:30-style transition in the request is visible.)
- **AT RISK** — ready after the safety-buffer deadline but not after the pick cutoff.
- **ON TIME** — ready by the safety-buffer deadline.
- **NO RATE** — open lines but no measurable pace yet.
- Colour bands: green On time, yellow At risk, red Pick cutoff passed.

## 4. Timelines (calculated, not assigned)

### 4.1 No action

| Snapshot | SH0908-1034 | SH0908-1069 | Why |
|---|---|---|---|
| 18:15 | ON TIME 19:13 (19 open) | ON TIME 19:13 (17 open) | First add-on order not yet in the snapshot. |
| **18:30** | **AT RISK 19:57 (43)** | **AT RISK 19:57 (32)** | 69001/69002 released 18:20. WT2: 51 lines ahead ÷ 2 pickers. Ready 19:57 > 19:50 buffer, ≤ 20:00 cutoff. |
| 18:45 | AT RISK 19:51 (43) | AT RISK 19:51 (27) | 42 lines ahead ÷ 37.9 lines/h. |
| 19:00 | AT RISK 19:57 (25) | AT RISK 19:57 (20) | 37 lines ahead ÷ 38.3 lines/h (69003/69004 released 18:49). |
| **19:15** | **PICK CUTOFF PASSED 20:42 (25)** | **PICK CUTOFF PASSED 20:42 (4)** | lhall logged out 19:13 (recorded): 1 picker, 19.3 lines/h, ready 20:42 > 20:00. |
| 19:30–19:45 | PICK CUTOFF PASSED 20:36 (18, 13) | PICK CUTOFF PASSED 20:36 (5, 4) | Still projected after the cutoff. |
| 20:00–20:15 | PICK CUTOFF PASSED (7, 3) | PICK CUTOFF PASSED (4, 3) | Cutoff has passed with lines open. |
| 20:30 | DEPARTED – 1 LINE LEFT BEHIND | DEPARTED – 1 LINE LEFT BEHIND | One line per truck was never picked. |

### 4.2 Recommended allocation at 18:30 — dclements (WT3 → WT2)

The planner recommends one operator: **dclements**, experienced in WT2, from WT3 where he has no picks after 18:30 (so nothing is reopened there). Credited at min(his WT2 pace, slowest WT2 pace) = 19.1–19.9 lines/h while logged in.

| Snapshot | SH0908-1034 | SH0908-1069 |
|---|---|---|
| 18:30 | ON TIME 19:28 (43) | ON TIME 19:28 (32) |
| 18:45 | ON TIME 19:25 (39, recorded 43) | ON TIME 19:25 (27) |
| 19:00 | ON TIME 19:29 (16, recorded 25) | ON TIME 19:29 (20) |
| 19:15 | ON TIME 19:36 (11, recorded 25) | ON TIME 19:36 (4) |
| 19:30 | **ALL PICKED** (0, recorded 18) | ON TIME 19:34 (4, recorded 5) |
| 19:45 | ALL PICKED | **ALL PICKED** (0, recorded 4) |
| 20:30 | DEPARTED COMPLETE | DEPARTED COMPLETE |

All Picked appears only at the snapshot where the subtracted lines reach the open count, not at confirmation.

### 4.3 Allocations that are not enough

| Allocation | Result | Why |
|---|---|---|
| psam (WT1) at 19:00 | 19:00 ON TIME 19:43 → 19:15 **PICK CUTOFF PASSED** 20:32 → 20:15 1034 all picked; 1069 cleared at 20:30 | The planner cannot know lhall will log out at 19:13. When she does, the next snapshot recalculates with the real headcount. |
| dclements at 19:15 | AT RISK 19:58 at 19:15, 19:57 at 19:30 and 19:45 → ALL PICKED at 20:00 | Too late to get inside the buffer; status stays At Risk until the work is actually done. |
| ekim (WT1) at 18:30 | Both trucks ON TIME and cleared by 19:30–19:45, **but** WT1 is re-evaluated: 8 of ekim's later WT1 picks reopened at 19:00 (1 at 19:30), SH0908-1057 shows 2 open (NO RATE) at 19:00 and clears at 19:15 | The cost of moving him is shown, not hidden. dclements is preferred because his source area loses nothing. |

## 5. Scenario replay model (how a confirmed allocation affects later snapshots)

Allocations remain session-only and are never written to the WMS. From the snapshot after confirmation:

1. **Destination gain** = credited pace × hours the moved operator was logged in (any area other than the destination) during each snapshot interval, applied to the destination's open lines earliest-cutoff first. Credited pace = min(operator's destination pace, slowest destination pace). Temporary operators: count × cautious temporary pace × hours.
2. **Source loss** = the moved operator's actual picks in other areas after the confirmation snapshot, minus the spare capacity of the operators who stayed (slowest pace × remaining heads × interval − their own picks). The remainder is reopened on the lowest-priority lines of the source area.
3. Each truck's adjusted open lines then go through the same status rule. A departed truck uses the adjusted count (`DEPARTED COMPLETE` only if it is 0).
4. The truck page shows "recorded N" beside the adjusted count and a scenario note per snapshot.

This is a conservative counterfactual on recorded history: it never invents faster picking than the slowest measured pace in the area.

## 6. Interface changes

- **Dashboard:** new red category "Pick cutoff passed"; critical text and insight explanations reworded; departed trucks use the scenario count.
- **Truck detail:** pick cutoff shown beside the buffer deadline; "Why this status" uses the calculated reason; scenario strip after an allocation; new **Status history** table (snapshot, status, open lines with recorded value, conservative ready, calculated reason; status changes highlighted).
- **Planner:** badges and the ready-time chart legend use the three bands; the at-risk pickups table shows "At risk: ready inside safety buffer" and "Pick cutoff passed".

## 7. Screenshots

| Image | Shows |
|---|---|
| `docs/images/v14-trucks-1830-before.png` | Dashboard at 18:30 with two At Risk trucks |
| `docs/images/v14-status-history-no-action.png` | SH0908-1034 history to 20:00, At Risk → Pick Cutoff Passed at 19:15 |
| `docs/images/v14-why-2000.png` | "Why this status" at 20:00 |
| `docs/images/v14-planner-pickups-1830.png` | Planner at-risk pickups at 18:30 |
| `docs/images/v14-planner-ready-before.png`, `v14-planner-ready-selected.png` | Ready-time chart before and with dclements selected |
| `docs/images/v14-trucks-1830-after.png` | Dashboard immediately after confirming dclements |
| `docs/images/v14-status-history-after-allocation.png` | SH0908-1034 history to 19:30 with the allocation: On Time → All Picked at 19:30 (recorded 18) |

## 8. Tests

New `tests/test_pressure_scenario_v14.py` (14 test functions, 15 cases). v8–v13 tests whose anchors depended on the v13 data were re-derived against the v14 workbook (same assertions about behaviour). Full suite: **263 passed** (about 2 minutes).

## 9. Limitations

- The scenario is synthetic. Departures of 20:30, the add-on orders and mmathis' overtime are invented and labelled; lhall's 19:13 logout is recorded data.
- The planner does not know future shift ends or breaks, so an allocation that looks sufficient (psam at 19:00) can later prove insufficient. The next snapshot shows it.
- Scenario replay uses the moved operator's recorded login time; it does not model transfer time (PLAN-002) or fatigue.
- Source-area reopening assumes the reopened lines are the lowest-priority ones in that area.
- Rerunning the generator overwrites `data/workbook.xlsx`; the v13 workbook is kept at `INFO/historical/ten_truck_v13_baseline.xlsx`.
