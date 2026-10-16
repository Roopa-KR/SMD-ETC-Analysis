# Decisions

## DEC-001 — Track every new change as an auditable project task
- **When:** 2026-10-10
- **Decision:** Maintain task log, change log, decision register, issue/solution register and per-file package manifest inside the project.
- **Why:** The user wants a clear record of all work and updated, self-contained ZIPs after each response.
- **Effect:** Every project update must preserve prior logs and append a new version entry.

## DEC-002 — Preserve baseline logic and data for the tracking-only request
- **When:** 2026-10-10
- **Decision:** Do not adjust business calculations, UI, Excel or SQLite without a specific modification request.
- **Why:** Setting up tracking should not introduce unrelated behavioral changes.
- **Effect:** First package contains documentation/tooling additions only.

## DEC-003 — Package project files, omit duplicate generated virtual environments
- **When:** 2026-10-10
- **Decision:** Include Python source, templates, assets, workbook, SQLite, existing documentation, Git metadata and supplied `.env` configuration. Exclude `.venv/`, `.venv-1/`, Python bytecode/test caches, swap files.
- **Why:** The two duplicate Windows environments account for most archive size and are platform-specific; dependencies can be restored from `requirements.txt`.
- **Security:** `.env` and Git history are included to retain supplied context; inspect for secrets and private URLs before forwarding this ZIP to others.

## DEC-004 — Maintain honest verification history
- **When:** 2026-10-10
- **Decision:** Distinguish tests run for each package from prior review claims and from source documentation's reports.
- **Why:** Prevent unverified pass counts from being reported as newly run.

## DEC-005 — No unattended/background project edits
- **When:** 2026-10-10
- **Decision:** Update project records and deliver new archive while actively responding to a user request, not as a background process.
- **Why:** There is no persistent unattended project-edit process in this chat.

## DEC-006 — Defer implementation until explicit business clarification
- **When:** 2026-10-10; version v2.
- **Decision:** Perform evidence-based review, log precise questions, preserve all behavior and data; do not implement any unapproved cutoff, synthetic pace, eligibility, preview or allocation rules.
- **Why:** New requirements explicitly prohibit assuming formulas/policies; current automatic reallocation and uncertain synthetic evidence conflict with supervisor-confirmed allocation.
- **Status:** Approved process decision, **not** approval of any proposed business choice.

## DEC-007 — Clearly separate measured, generated, simulated, and confirmed state
- **When:** 2026-10-10; version v2.
- **Decision:** In the review and future discussions distinguish observed productivity, simulated experience and moves, calculated projection and potential future user-confirmed allocation.
- **Status:** Documentation policy only; no application change.

## DEC-008 — Confirmed cutoff, loading, safety and conservative policies (v3)
- **Approved requirements:** Fixed extra 10-minute safety margin protecting both destination and source work; 30-minute default loading with per-truck supervisor override persisted through restart; conservative-pass criterion; preserve existing source-safety checks; show unsafe operators, marked rather than hidden.
- **State:** Captured only, not implemented. Effective deadline formula still needs user confirmation.

## DEC-009 — Confirmed operator experience and reallocation behavior (v3)
- **Approved:** All existing simulated experience rows count as eligible demo familiarity with visible provenance; retain team-rate baseline with operator-specific destination rate addition and source subtraction, no duplicate selection; sequential graph previews not allocation; supervisor explicitly clicks Allocate; confirmation affects later snapshots but confirmed allocations must not yet be saved locally; no transfer-time modeling this phase.
- **Pending:** Stable in-memory state behavior when a user refreshes/restarts; pace for familiar operators without measured destination data.

## DEC-010 — Monthly pace must be evidence-backed, not invented (v3)
- **Approved process:** Determine existing-data adequacy first; if insufficient, explain gaps and propose correct calculation.
- **Finding:** Only one data day in current stored source. A genuine monthly rate cannot be established.
- **Non-decision:** Monthly window, confidence/sample sufficiency thresholds and synthetic fallback are not yet approved.

## DEC-011 — Individual assignment risk presentation (v3)
- **Approved goal:** Flag at the individual assignment/picking-task level, not only truck or worktype.
- **Missing policy:** Whether risk should inherit shipment–worktype risk or require an independent sequencing/deadline ETC; user confirmation required.


## Decisions confirmed for v4 — 2026-10-10

- **D-V4-01:** The fixed safety margin is 10 minutes. Both destination deadline and each source row's conservative safety check use `departure - individual loading - 10 minutes`.
- **D-V4-02:** Loading defaults to 30 minutes. Individual truck override persists in SQLite, separate from any confirmed move.
- **D-V4-03:** Individual operator pace uses a trailing 30-calendar-day ratio of completed lines to de-duplicated recorded hours per operator/worktype. Because data covers only one day, it is labeled observed one-day/available-history evidence, not monthly achieved performance.
- **D-V4-04:** Actual completed destination work or existing explicitly simulated experience qualifies for the list; synthetic fallback is the existing `min(source observed pace, destination team per-person rate)` when target observation is missing. Always identify provenance.
- **D-V4-05:** Familiar unsafe operators remain visible but cannot be selected. Candidates order descending by individual destination pace. Source-safety checks remain mandatory and are cumulative for selected operators.
- **D-V4-06:** Point team rate is preserved as baseline. Selected source pace is subtracted; destination pace added; empirical conservative bound controls pass. Selection is simulation only until explicit Allocate.
- **D-V4-07:** Confirmed allocation is a temporary scenario held in server RAM for the current supervisor's session, never saved to a staffing table/workbook/WMS. It affects later snapshots only while the operator remains present and safety-valid; if not, it is skipped with a warning.
- **D-V4-08:** Assignment/task at-risk flags inherit related shipment/worktype conservative risk; no unsupported individual task ETC.
- **D-V4-09:** No transfer/handover time modeled in this phase, per user direction.

## v5 UI design/metric decisions — 2026-10-10 13:26 IST

- **D-V5-01:** Keep Flask/Jinja, existing CSS/JavaScript and all original business calculation modules; redesign only presentation and read-only view aggregation. Preserve source database/workbook bytes and temp allocation behavior.
- **D-V5-02:** Adopt user-supplied screenshot as design inspiration with #F5F6FA background, white 15px cards, blue #2563EB accent, soft shadows, fixed 236px sidebar, Inter fallback typography; store screenshot in docs for reproducibility.
- **D-V5-03:** Display `On-time completion share` rather than claiming a statistical probability, because the system does not produce a calibrated forecast. Categorize NO RATE as unknown, not as known delay. Gauge segments show actual status counts, no invented probability thresholds.
- **D-V5-04:** Replace unsupported truck-specific assigned-operator numbers with clearly titled `Staffed areas` from existing worktype resource counts, not a fabricated assignment.
- **D-V5-05:** The only available analysis date is the recorded September 8 replay. Topbar displays the actual date plus functional 18-snapshot time selector, not a fictional arbitrary date picker or last-30-days filter.
- **D-V5-06:** Use real cumulative completed-line deltas for interval activity and scenario recalculation at each observed snapshot for the time trend. Do not create forward-prediction events.
- **D-V5-07:** Functional sidebar items link only to implemented endpoints/sections; add a read-only `/operators` directory and export-only `/export/trucks.csv` endpoint. Notification icon links to rule-based insights; avatar is explicitly not authenticated.
- **D-V5-08:** Bundle Plotly JavaScript from available plotly distribution; retain existing Bootstrap 5.3.3 and optional icons/Google Fonts CDN to avoid downgrading UI framework or redistributing fonts.
- **D-V5-09:** Tablet widths 701–1199px show two KPI cards per row, desktop four; mobile 2 columns with stacked charts and scrollable table.

## v6 UI consistency decisions — 2026-10-11

- **D-V6-01:** Reuse the existing Flask/Jinja/Bootstrap/Plotly framework and existing page endpoints. New macros and CSS establish one light SaaS design for five HTML pages, preserving all data and actions.
- **D-V6-02:** Use the reference's #F5F6FA app background, #2563EB primary accent, white softly rounded cards, table filters, mild elevations, and accessible responsive navigation across pages.
- **D-V6-03:** Vendor Bootstrap 5.3.6 CSS/JS (patch update from 5.3.3) and keep existing local Plotly; retain optional external Bootstrap Icons/Inter with native SVG for critical brand/mobile-menu affordances.
- **D-V6-04:** Do not change multi-truck risk calculation to fix ambiguous preview status. Explain clearly that the graph shows the earliest-deadline truck but the worktype status evaluates all open trucks.
- **D-V6-05:** Restore any test-induced SQLite changes to match baseline v5 before packaging. Presentation-only changes should not mutate the user's source data.


## DEC-012 — Preserve uploaded state and defer conflict resolution (v7, 2026-10-12)

- **Decision:** Treat the new `SMD-main.zip` as the authoritative source snapshot for a current-status *audit*, not as implicit permission to replace the user's previously approved business decisions.
- **Rationale:** The source now persists advisory allocations in SQLite and changes eligibility/unsafe visibility in conflict with previously confirmed instructions. Such rules must be clarified before changing production logic.
- **Action:** No application logic changes in v7. Record discrepancies clearly and obtain confirmation before implementing fixes. A missing derived SQLite cache may be rebuilt from the unmodified workbook for a complete runnable package, with no fabricated allocations.


## DEC-v8-001 — Active ten-truck demo and inactive source history
- **Date:** 2026-10-12.
- **Decision:** Exactly 10 trucks in ACTIVE workbook, database and all UI/API/CSV calculations, exactly 2 risk labels calculated at default snapshot10. Archive (do not activate) prior 33-truck workbook for reproducibility and historical tests.
- **Reason:** Meet explicit demonstration-count requirement while preserving lineage and avoiding manually forced status values.

## DEC-v8-002 — Explicitly synthesized capacity and cutoff calibration
- **Date:** 2026-10-12.
- **Decision:** Select ten route/order histories; label replay synthetic; extend departure of 1034 by ten minutes and model WT1 labor effort at 65% of reference to construct distinct 1-operator/2-operator feasibility cases.
- **Reason:** Produce naturally computed risk counts and staffing scenarios through existing conservative math. Never present this as measured real operational history or 30-day performance.

## DEC-v8-003 — Minimum **safe feasible** operator count, no arbitrary target
- **Date:** 2026-10-12.
- **Decision:** Exhaustively evaluate qualified active candidate subsets from size one upward, validating cumulative conservative source and target deadlines and remaining truck worktypes. Surface nonfeasibility rather than inventing headcount.
- **Reason:** A raw rate shortfall alone does not prove that an operator can be safely transferred.

## DEC-v8-004 — Temporary server-session allocations only
- **Date:** 2026-10-12.
- **Decision:** Remove v7 SQLite-confirmed advisory allocation model/table. Only per-truck loading overrides may persist. Preview moves remain `(snapshot, worktype, shipment)` scoped; explicit Allocate atomically updates ephemeral in-process session state, reset/expiry/restart restores source assignments.
- **Reason:** Follow user's explicit choice and prevent the inconsistent v7 persistence and reversed-record uniqueness failures.

## DEC-v8-005 — Transparent limitations
- **Date:** 2026-10-12.
- **Decision:** Mark synthetic experience/pace; inherited individual assignment risk only, no invented task ordering; no live warehouse assignments, no transfer time. Full historical suite timeouts and browser test gaps remain open.
- **Reason:** A believable demo must not overstate what is measured or verified.


## 2026-10-12 — v9 truck-detail chart decisions
- Display conservative (not optimistic point) ready time because the conservative result drives the risk status.
- Show safety margin as a **shaded time interval** between buffered required-ready and physical pick cutoff, not as another numeric ETA series.
- Show preview-selected operators when there is an active unconfirmed selection; otherwise show the independently calculated minimum feasible proposed combination. Confirmed session allocation changes baseline, not preview.
- For multi-area risk, never sum independent recommendations that may reuse the same candidate; instead disclose each worktype minimum separately.
- Preserve all underlying replay data, formulas, 10-truck scenario and original SQLite state. No change to live WMS / persistent assignment behavior.


## 2026-10-12 — v10 ready-time chart decisions
- **Projected ready = the conservative truck ready time** (latest open work type at the cautious rate), because that value drives every existing status. Green therefore equals the existing ON TIME status. Yellow and red split the existing AT RISK by whether the pick cutoff itself is met.
- **"Before" always means the original assignments.** After Allocate, a separate "After allocation (confirmed)" row appears, so the supervisor can see the effect of what was confirmed.
- **"After" uses the supervisor's selection when one exists; otherwise the minimum recommended operators.** Moves are applied cumulatively across the truck's work types, so one operator is never counted twice and source safety sees earlier moves.
- **One truck-level chart replaces the per-area chart.** The question is whether the truck is ready; per-area figures stay in the Work types table.
- **Safety buffer is configuration** (`SAFETY_BUFFER_MINUTES` in `.env`), not a code constant. The default loading time comes from the workbook. The value 10 and 30 minute defaults are unchanged.
- **Status is never carried by colour alone:** every marker and table row also shows a status word, and the table repeats all values.


## 2026-10-13 — v11 decisions (user chose option C)
- **Pace for planning = lines ÷ picking time.** A gap over `PACE_GAP_CAP_MINUTES` (10) between an operator's picks counts as waiting. Logged-in time included waiting while no work was released, which made operators look slow and caused one-snapshot false alarms.
- **The Excel equation stays the reference** in the engine (logged time). The planning layer uses picking time by default; `PACE_BASIS=logged_time` reproduces Excel exactly.
- **Demo labor time is scaled per work type to the share of picked lines kept** (replaces WT1 × 0.65). Real session times, operators and WIPIND are unchanged.
- **Statuses are never forced.** The corrected demo has no at-risk truck at 18:30. Tests and demonstrations create pressure only through real inputs such as the per-truck loading time.
- **Recommendations never move operators into areas that cannot change the truck's ready time.** If the slowest area has no safe fix, nothing is recommended and the reason is shown.


## 2026-10-13 — v12 decisions
- **Supersedes the v4–v11 rule "no temporary labour".** Per the user's explicit request, temporary operators are allowed, but only after safe reallocation is evaluated, only in the calculated minimum, only on supervisor confirmation, and only for the session.
- **Reallocation first, enforced.** Temporaries are not offered (and the server refuses them) when safe reallocation (selected + further) can meet the safety buffer deadline. The recommended plan minimises temporaries, then reallocations.
- **Assumed pace** = `TEMP_OPERATOR_PACE_PCT` (default 100%) × the work type's per-person rate, labelled as a synthesized assumption. Cautious credit = min(that pace, slowest measured operator), the same rule as any added operator. Default and maximum (10) follow the earlier SMD workbook's synthesized temporary-operator settings.
- **One confirmation.** Allocate Temporary Operators confirms the selected reallocations and the temporaries together, because the temporary count was calculated on top of that selection.
- **No partial recommendations.** If no plan (reallocation + maximum temporaries) can make the truck's slowest area on time, the chart recommends nothing and explains; the supervisor can still preview any count manually.
- **Insufficient allocations are allowed but never reported as success.** The flash, chart colour and panel show the remaining gap.


## 2026-10-13 — v13 decisions
- **Separate database for readings** (`data/environment.db`). The results cache is rebuilt from the workbook, and readings must never mix with or overwrite WMS/LMS data.
- **Zones = the six M123 work types** (the only verified work areas), plus labelled user-added zones. No invented zones.
- **Context only.** No environmental input to ETC, ready time, status or allocation. "Environment-adjusted ETC: not available" until Phase 4 evidence and approval. Any future adjustment may only make ETC slower, never faster.
- **Synthetic data only on request.** Loaded by a button, labelled SYNTHETIC, excluded from analysis, deletable.
- **Analysis gated.** Results only with ≥ 30 paired hours, ≥ 5 days and a ≥ 3 °C spread, using valid ACTUAL readings. Always "association, not causation".
- **Recommended sensor:** AM2301B (enclosed AHT20) or SHT41 rather than the discontinued AM2302/DHT22. Existing Wi-Fi first; ESP-NOW gateway or PoE Ethernet only where coverage fails. No purchase without client approval.
- **Heat safety:** temperature/RH is not a heat-stress measure. Recommend WBGT or an occupational-health assessment. Never advise working through unsafe heat to meet a cutoff.


## 2026-10-14 — v14 decisions
- **Pressure from data, not labels.** At Risk comes from added work (late add-on orders) and recorded labour (lhall's 19:13 logout), passed through the unchanged engine. No status is stored or forced.
- **Trucks chosen to avoid collateral risk.** SH0908-1034 and SH0908-1069 are last in WT2 priority, so their extra work does not delay any other truck. An earlier design (SH0908-1012/WT2 and SH0908-1057/WT6 with a break) was rejected because it put other trucks at risk.
- **Separate status for a projected miss.** Conservative ready after the pick cutoff is PICK CUTOFF PASSED (red), not AT RISK, so the transition the client described is visible.
- **Allocation replay is conservative.** Gain uses min(operator pace, slowest area pace) × hours actually logged in; a moved operator's later source picks are reopened unless the remaining operators had spare capacity. All Picked only when adjusted open lines reach 0.
- **No added cross-training.** Recommendations use only the recorded experience table.
- **v13 workbook frozen** in `INFO/historical/` as the generator's input, so the scenario can be rebuilt or reverted.
