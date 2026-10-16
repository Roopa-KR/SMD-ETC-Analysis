# Confirmed requirements and open business decisions — v3 (2026-10-10)

**State:** User clarifications have been recorded. No application business-rule changes applied because the remaining questions below directly affect deadline and per-assignment ETC accuracy.

## Confirmed by user in this turn

| Ref | Agreed rule | Implementation state |
|---|---|---|
| C1 | Minimum safety buffer is **fixed at 10 minutes**. Source worktype must remain safe after removal using the same safety margin. | Not implemented |
| C2 | Default loading is **30 minutes**; supervisor can override for an individual truck; overrides must survive app restart. | Not implemented |
| C3 | Existing synthetic `OPERATOR_EXPERIENCE` records count for demo experience eligibility; distinguish the assumed skill from observed completions. | Existing simulations; UI to update |
| C4 | Base operator pace on **monthly individual performance**, after verifying data adequacy; recommend method and gaps if unavailable. | Audit completed; monthly data not present |
| C5 | Show familiar but source-unsafe operators with **UNSAFE** status, not hidden. Retain existing source-safety checks. | Not implemented |
| C6 | Preserve team baseline; preview subtracts selected operator's source pace and adds their destination pace. **Conservative** estimate must pass the deadline. No double counting. | Not implemented |
| C7 | Confirmed allocation affects **subsequent snapshots**; **do not store confirmed allocation locally yet**. | Needs transient-state clarification |
| C8 | Flag **individual work assignments/picking tasks**, not only truck–worktype rows. | Needs assignment-level timing policy |
| C9 | Ignore transfer/handover time for this phase; no new travel-time policy. | No new transfer-time model |
| C10 | Supervisor selects eligible operators one by one and sees original vs sequential projected finish in the graph; **Allocate** must be explicit and never inferred from selection. | Not implemented |

## Existing formulas & precise open questions

**A. Effective deadline definition:** Existing `PICK_CUTOFF = DEPARTURE - LOADING_MINUTES`. Is your intended pass deadline **`DEPARTURE - per-truck LOADING_MINUTES - fixed 10-minute safety buffer`**, preserving `PICK_CUTOFF` as a separate unbuffered displayed milestone? Example: 17:00 departure, 30-minute loading, 10-minute margin -> effective *pick completion planning deadline* 16:20, unbuffered loading cutoff 16:30. Confirm this exact interpretation; do not silently implement.

**B. Monthly period & data:** Should “monthly” mean **trailing 30 calendar days** or **previous completed calendar month**? Are additional daily transaction/time exports available? If not, is it acceptable to use **single-day demo observed pace**, clearly labeled and not called monthly, until the full dataset arrives?

**C. Unmeasured destination pace:** Simulated experience qualifies an operator for visibility, but experience alone provides no measured pace in the new worktype. Should we preserve the current *labeled synthetic fallback* `MIN(actual source pace, destination average per-person rate)` for preview ranking where monthly target pace is unavailable, or leave the pace/preview **UNKNOWN** until an approved alternative or real target history is available? An operator with no defensible pace can remain visible, marked “pace unavailable”. Do not assert a synthetic value is actual monthly productivity.

**D. Individual task risk:** There are **625 assignment IDs** in `src_line_map` and complete links from lines to orders, but no explicit *per-assignment execution order* or assignment-specific deadline in current source records. Is it acceptable to **inherit the connected shipment–worktype conservative readiness result** for each assignment/line (a risk indicator, not a separately predicted line completion timestamp), or do you expect an independent task-level ETC? For independent ETC, supply/define the assignment processing sequence and its cutoff (inherited shipment cutoff or separate SLA).

**E. Post-confirmation state:** With **no local saved confirmed allocation** and no WMS integration, should allocations be **session/server-memory-only** (lost on application restart), yet automatically affect the selected and subsequent snapshots in that running scenario? Clarify if different supervisors should see the same temporary scenario or only their own session. The durable *per-truck loading override* is distinct and can still be saved in app configuration.

## Key technical risk to address once approved

The current engine calls `apply_reallocation` eagerly for every snapshot, automatically recording hypothetical moves in `reallocation_move`; this **must not** be treated as a committed allocation. UI previews and confirmed (non-persistent) in-memory scenarios need explicit states to prevent accidental silent allocation. Assignment-specific ETC is currently absent; truck–worktype ETC uses `LINES_AHEAD` from earlier/equal cutoff trucks. Existing rate arithmetic is incremental relative to the team baseline and is not an identity decomposition of all operator rates.

**Change hold:** Only tracking/docs and a read-only pace audit CSV are added to this package. No modified app logic, UI, workbook, SQLite, automated tests or historical result outputs.
