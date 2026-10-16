# v2 — Cutoff management and operator reallocation requirements review

**Status:** Requirements analysis only. **All proposed business-logic and UI changes are BLOCKED pending explicit supervisor/business clarification.**
**Date:** 2026-10-10
**Base artifact:** `truck-etc-app-updated-20261010-v1.zip` (NOT the original 128 MB source upload).

## Evidence inspected

- `calculations/etc.py` (19–58): existing team rate and ETC; team point rate = completed lines / labor hours × resources.
- `calculations/truck.py` (66–115, 123–234): pick cutoff = departure minus workbook `LOADING_MINUTES`; priority lines ahead; point/conservative truck risk.
- `calculations/uncertainty.py` (20–100): empirical operator pace = past completed lines / recorded labor hours, conservative sensitivity bounds.
- `calculations/reallocation.py` (37–107, 129–370): cross-training evidence, automatic iterative selection, source safety, destination/source rate arithmetic, precomputed simulated moves.
- `calculations/excel_io.py` (53–100): configuration and `OPERATOR_EXPERIENCE` loaded from Excel; default no experience if absent.
- `calculations/engine.py` (27–34): reallocation runs eagerly during every workbook computation, before a supervisor action.
- `models/models.py`, `models/database.py`: calculated results and reallocation moves persisted as precomputed simulation outputs; no confirmed staff assignment lifecycle.
- `app.py` (62–125), `templates/dashboard.html`, `templates/truck_detail.html`, `static/js/truck_detail.js`: GET-only dashboard/detail/profile; post-simulation chart, but no selectable candidate graph updates, loading-time control, confirmation endpoint or Allocate button.
- `PROJECT_HANDOVER_CURRENT_STATUS.txt`, `README.md` and current tracking logs (existing behavior, assumptions and historical limitations).
- SQLite `data/truck_etc.db` opened **read-only**: 594 truck rows, 3,564 worktype rows; 15 simulated familiarity entries for 12 operators; 3 automatically calculated moves involving 2 distinct operators.

## Requirement-level findings

| Requirement | Existing behavior | Missing/contradictory behavior | Status |
|---|---|---|---|
| 1. Minimum cutoff buffer | Pick cutoff directly precedes loading; source safety requires meeting cutoff, not a distinct margin | No 10-min margin; fixed-vs-configurable undecided; whether margin applies to all cutoffs/source work requires confirmation | BLOCKED Q1 |
| 2. Synthetic per-operator pace | Observed positive per-operator pace by worktype already calculated; 15 familiarities are **simulated**, not measured | Proposed synthesized per-worktype rate when absent requires documented generation/calibration rule; must label provenance | BLOCKED Q3, Q4 |
| 3. Supervisor-configured loading time | Workbook `TRUCK_CONFIG.LOADING_MINUTES`; pick cutoff = departure - minutes (30 currently documented); dashboard text hardcodes 30 | No UI-controlled loading time nor agreed scope, persistence and recalculation effects | BLOCKED Q2 |
| 4. Flag at-risk work | Worktype, truck point and conservative statuses exist | Buffer not included; worktype vs individual task granularity not decided | BLOCKED Q1, Q8 |
| 5. Eligible by experience, rank by pace | Actual historical completions or explicitly simulated matrix; current engine requires active operator, different WT, source safety, valid pace; sorting favors safety/priority, not simply fastest | Whether simulated experience qualifies, whether to show candidates who fail source safety, destination-specific pace ordering | BLOCKED Q3, Q5 |
| 6. Single operator preview | Static computed before/after chart marker exists | No interaction to preview selected operator or recompute chosen scenario | BLOCKED Q4, Q6, Q9 |
| 7. Sequential preview | Engine automatically tests multiple distinct moves per snapshot and subtracts source/adds destination contributions | No supervisor-driven sequential selection; reconcile summed operator pace to team rate and avoid duplicate selection/assignment | BLOCKED Q6, Q7 |
| 8. Explicit Allocate | `reallocation_move` stores automatically accepted *hypothetical* engine moves | No confirm endpoint, transaction/audit, persistent applied allocation or future-snapshot handling; cannot currently allocate in a WMS | BLOCKED Q7, Q9 |
| 9. Accuracy policy | Most provenance tagged; Excel reference parity tests exist | Need business decisions before altering golden baseline; current data still contains synthetic timetables/cross-training | COMPLIED FOR THIS REVIEW |

## Questions — business owner to answer prior to implementation

**Q1 — Safety buffer.** Should the starting 10-minute buffer be fixed in code or editable by the supervisor? Confirm whether the effective picking deadline is the existing pick cutoff **minus** this extra margin and whether the same margin must protect *source* worktypes when a picker is removed.

**Q2 — Loading time scope.** Existing rule is `pick cutoff = scheduled departure - LOADING_MINUTES` (currently 30 minutes in workbook). Should the supervisor edit loading time once for all trucks, per truck, or per session/snapshot? Should the setting persist, and should changing it recalculate historical snapshots or only the currently viewed scenario?

**Q3 — Evidence for “experienced”.** Should eligibility recognize both completed-work history *and* the existing explicitly simulated `OPERATOR_EXPERIENCE` records, or only a particular evidence type? Do all levels of simulated familiarity qualify? The current sheet contains 15 planning-assumption entries; none is verified qualification data.

**Q4 — How to synthesize pace.** What exact approved generation/calibration rule should estimate an operator's pace for a familiar worktype **without measured pace**? Do experience levels influence that estimate, and should measured positive pace always override synthetic pace? Please specify whether the generated values are stable per operator/worktype or vary by snapshot.

**Q5 — List vs recommend eligibility.** The current code additionally checks active WIP, not already moved, a different current worktype, measurable source rate and preservation of every source truck at both normal and conservative estimates. Should **all experienced operators** be visible in the ranked list with an explanatory unavailable/unsafe status, while only source-safe operators are selectable? Or should only source-safe candidates be displayed? Should any existing checks change?

**Q6 — Rate calculation and deadline decision.** For selected operators, should the preview retain the existing team rate as a baseline and add each approved operator-specific *destination* contribution while subtracting their *source* pace? The existing team rate is **not** necessarily the sum of the individual measured rates. Should “meets deadline” mean both point and conservative projections pass, as the current engine requires, or the point estimate only?

**Q7 — Confirmed allocation meaning.** On **Allocate**, should the app merely save a confirmed allocation in its local SQLite planning scenario (the application has no WMS writeback), or must it update an external workforce/assignment system? Should the allocation affect only the chosen snapshot, or propagate through subsequent replay snapshots? How should collisions/competing allocations in the same snapshot be resolved?

**Q8 — At-risk scope.** Does “task” mean (a) a truck × worktype group, as the current algorithm models, or (b) each individual work assignment/line? If (b), what is the source of the task-level deadline and assignment-to-operator relationship?

**Q9 — Transfer delay and safeguards.** Is there a required travel/handoff/setup time before a relocated operator can contribute? The current engine assumes an immediate rate transfer and does not include such time. Also confirm whether an allocation must be disallowed if source-work safety fails, even if the target task becomes on time. Which other already-existing safeguards should remain mandatory?

## Known conflicts, constraints and validation

- **Interaction conflict:** eager `apply_reallocation` in engine runs independently of user input; the database calls them `ReallocationMove` and the UI says reallocated/allocated even though no committed WMS staffing change occurred. Distinguish recommendation, preview, and confirmed state without changing current baseline until approved.
- **Formula conflict risk:** ETC team's `ACTUALRATELINES = (TOTALLINES/TOTALTIMEINHRS)*RESOURCES`; subtracting a particular worker's measured source pace need not exactly preserve team-rate decomposition. Synthetic rates require explicit provenance and defensible reconciliation to this calculation.
- **Data provenance:** operator familiarity matrix is entirely tagged `SIMULATED PLANNING ASSUMPTION`; observed operator pace is derived from workbook LM005S1 and completed TI102C data; departure/cutoff schedule is partly synthesized. Neither of these is verified live operations qualification/schedule.
- **Scope conflict:** a new user-confirmed assignment model needs a DB lifecycle and history; current `reallocation_move` is a precomputed scenario table rather than an allocation ledger.
- **Excel parity:** the workbook remains the golden reference for the existing calculation. A new buffer or modified loading default necessarily changes comparison outputs unless versioned separately; don't silently overwrite existing parity references.
- **Observed facts:** SQLite counts query returned 594 truck rows and 3,564 worktype rows (18×33×6), 15 simulated familiarity rows spanning 12 people/5 worktypes, and 3 automatic simulated moves involving 2 people. At snapshots 9, 10, 11, stored planning AT RISK truck counts are 12, 7, and 3 respectively; these reflect old rules only.
- **Tests executed for this review:** `python -m pytest -q tests/test_truck.py tests/test_reallocation.py tests/test_uncertainty_reallocation.py --disable-warnings --maxfail=1` -> **15 passed**. Baseline test success does not validate any unimplemented feature. No code or data modifications made.

## Non-decisions and safe continuation

- **Approved:** Record the review, avoid speculative code edits, and seek the specific decisions above.
- **NOT approved yet:** Whether buffer is fixed, any pace synthesis formula, qualifying simulated experience, display/filter behavior, frontend edit scope, transfer delays, allocation persistence, risk scoring criteria or task granularity.
- **Source code changed:** None.
- **Workbook or SQLite changed:** None.
- **UI modified:** No.
- **Next step:** Receive answers to Q1–Q9; only then design/test code changes against the authorized rules.
