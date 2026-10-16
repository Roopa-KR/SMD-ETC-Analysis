# Issues, resolutions, and outstanding work

All statuses reflect the delivered version, not a claim that suggested future fixes are implemented.

| ID | Severity | Status | Issue | Solution / next action |
|---|---|---|---|---|
| PACK-001 | Low | Resolved in v1 | Initial user ZIP bundles two duplicate virtual environments, producing a very large archive. | Excluded `.venv/` and `.venv-1/` from delivery package; use `pip install -r requirements.txt` to restore. Original source ZIP retained. |
| PROC-001 | Medium | Resolved in v1 | No chat-specific, durable log of each requested task and file change. | Added versioned task, change, decision, issue records and SHA-256 manifest. |
| APP-001 | High | Open | No operational live WMS/LMS integration and no user authentication. | Define integration/security requirements and implement behind tests before production use. |
| DATA-001 | High | Open | Truck departures/cutoffs and some dock data are synthesized for replay. | Replace with verified operational schedule and loading rules when available. |
| PLAN-001 | High | Open | Operator skill/familiarity assumptions are partly simulated, not verified live qualifications. | Import approved qualification/cross-training records before acting on moves. |
| PLAN-002 | High | Open | Reallocation simulation does not model transfer/setup time or agreed minimum safety buffer for source work. | Add configurable transfer/setup time and source margin; regression-test scenarios. |
| PLAN-003 | Medium | Open | Suggested moves do not persist staffing changes or execute them in the warehouse. | Keep advisory, or design validated action and audit workflow if implementation is requested. |
| DATA-002 | Medium | Open | Actual staging/loading progress is not part of ETC readiness. | Add observed staging/loading dependencies once real feeds exist. |
| APP-002 | Medium | Open | Timezone assumptions and some hardcoded UI wording need review. | Confirm warehouse-local timezone and standardize date/time display; audit UI strings. |
| TEST-001 | Medium | Unverified | Earlier review's full test run timed out; source handover reports 119 passing tests. | Run complete suite with suitable environment and capture actual results before declaring full green. |
| SEC-001 | Medium | Open consideration | Supplied local `.env` and Git metadata may contain context unsuitable for sharing externally. | Treat package as private; inspect secrets/remote URLs and prepare sanitized distribution archive for external recipients. |

## Issue lifecycle

Each future issue should include discovery date, reproduction/evidence, impacted files, severity, status, implemented solution (if any), verification, and package version. Never mark an app issue resolved just because a solution has been proposed.

## New blockers found during v2 requirements review (2026-10-10)

| ID | Severity | Status | Evidence / issue | Proposed resolution (NOT implemented) |
|---|---|---|---|---|
| REQ-001 | High | BLOCKED | No safety buffer is included in pick cutoff/source safety decisions. | Confirm fixed/configurable + target/source scope (Q1); then implement and regression-test. |
| REQ-002 | High | BLOCKED | Loading time only comes from Excel `TRUCK_CONFIG`, no supervisor edit UI; dashboard hardcodes 30 min. | Confirm user edit scope/persistence/replay behavior (Q2). |
| REQ-003 | High | BLOCKED | Existing familiarity table contains 15 entries, all simulated; individual pace synthesized for familiar but unmeasured worktypes needs an approved basis. | Decide evidence and synthesis methodology (Q3–Q4). |
| REQ-004 | High | BLOCKED | Automatic reallocation uses source-safety/priority sorting, not an independently ranked, selectable pace list. | Confirm candidate display vs eligible-to-move criteria (Q5). |
| REQ-005 | High | BLOCKED | Preview graph is static; current engine automatically creates accepted move scenarios without confirmation. | Build what-if selection and independent confirmation only after Q6–Q7. |
| REQ-006 | High | BLOCKED | Team rate is not strictly the sum of individual rates; potential mismatch on incremental simulation and source subtraction. | Approve reconciliation and conservative-pass policy before combining synthetic/observed paces (Q6). |
| REQ-007 | High | BLOCKED | No persisted, auditable confirmed allocations or external WMS writeback; no cross-snapshot action semantics. | Define confirmation scope and assignment lifecycle (Q7). |
| REQ-008 | Medium | BLOCKED | At-risk `task` could mean per-truck-worktype or individual line/work assignment; task-specific deadlines absent. | Decide risk granularity/data links (Q8). |
| REQ-009 | High | BLOCKED | No travel/setup time in move calculation; source cutoffs have no separate configurable safety margin. | Specify delay and source-risk rule before simulation/confirmation (Q1, Q9). |

No proposed solution above has been implemented. See `CUTOFF_OPERATOR_REALLOCATION_REQUIREMENTS_REVIEW_v2.md`.

## Updated issue status — v3 (2026-10-10)

- **REQ-001:** 10-minute fixed buffer and source protection **DEFINED**; effective cutoff arithmetic **PENDING confirmation**; not implemented.
- **REQ-002:** 30-minute default + persisted per-truck override **DEFINED**; not implemented.
- **REQ-003:** Existing synthetic familiarity may count as demo eligibility **DEFINED**; true destination-monthly productivity **MISSING**.
- **REQ-004:** Show source-unsafe candidates as UNSAFE; retain safety enforcement **DEFINED**; not implemented.
- **REQ-005:** Single and progressive previews plus explicit Allocate confirmed; no GUI/API code yet.
- **REQ-006:** Incremental source/destination pace arithmetic and conservative pass **DEFINED**; rate reconciliation/edge tests outstanding.
- **REQ-007:** Confirmed moves follow subsequent snapshots but aren't locally stored; **BLOCKED** on memory/session-lifetime semantics.
- **REQ-008:** User wants assignment-level flagging; links support 625 assignments, but their processing order and own deadlines are absent; **BLOCKED** on risk interpretation.
- **REQ-009:** Transfer time explicitly out of scope for this phase; leave existing no-transfer-time behavior unchanged.
- **DATA-003 (High, OPEN):** One day of completion/time data cannot substantiate monthly pace. **Solution proposed, not implemented:** load multi-day daily event and productive-time history and use a denominator-weighted ratio by operator/worktype.
- **DATA-004 (High, OPEN):** Two labor pairs lack target-worktype completions; simulated qualification is not a measured target pace. **Solution proposed, not implemented:** label missing pace and seek approved synthetic fallback/model.
- **DATA-005 (Medium, OPEN):** Cumulative LM005S1 snapshots must not be summed across snapshots or labor hours will be inflated. **Solution in analysis:** use a single final snapshot for the one-day CSV; design monthly aggregation from non-overlapping daily intervals. No production code change.


## Status update — v4 (2026-10-10)

| Issue | Status after v4 | Verified handling / remaining need |
|---|---|---|
| REQ-001, REQ-002 | Implemented / tested | Fixed 10-minute safety buffer; loading override default 30 min persisted in SQLite; source and destination use effective deadlines. |
| REQ-003, REQ-004 | Implemented with data caveat | All experienced operators shown, safe/unsafe label, descending pace; actual vs synthetic provenance shown. Only one day's evidence available. |
| REQ-005, REQ-006 | Implemented / tested | Sequential preview graph, additive/subtractive rate calculations, conservative source checks, explicit Allocate action. No preview writes allocation. |
| REQ-007 | Implemented as temporary scenario | Server-memory allocations affect later snapshots when source/operator validation allows; no confirmed move stored in SQLite. Multi-worker shared session support is not implemented. |
| REQ-008 | Implemented as inherited assignment risk | Matching assignment IDs inherit parent worktype status; per-assignment independent ETC remains unmodeled by agreement. |
| REQ-009 | Intentionally out of scope | No transfer-time estimate, per user direction. |
| DATA-003/DATA-005 | Partially mitigated, data gap remains | Rolling-30-day extraction and deduplication of replay LM005S1 snapshots; cannot validate genuine monthly operator pace from a single day or ensure unique historical labor segments without stable IDs. |
| APP-001 | Open — production blocker | No authenticated supervisor identity or live WMS/LMS integration. Allocate is a scenario only; original app debug mode remains. |
| PLAN-001 | Open — simulated skills | Some experience links are synthetic; no verified training record or true target measured pace. |
| TEST-001 | Partial | 33 selected tests passed, full suite timed out. Full suite is NOT verified green. |
| APP-003 | Open — multiprocessing | Temporary in-memory scenario per Python process is not shared across multi-worker instances. Single-process local demo supported. |
| DATA-006 | Intentional modeling limitation | Historical trend graphs use workbook replay; confirmed what-if assignment staffing doesn't fabricate future pick event streams. |

## v5 dashboard redesign issues and outcomes — 2026-10-10 13:26 IST

1. **V5-I01 | Resolved | UI structural gap:** Preexisting dense tabular dashboard/dark navbar lacked requested SaaS hierarchy, modern cards/sidebar and mobile menu. **Solution:** new shared sidebar/topbar, KPI/analytics layout and responsive stylesheet.
2. **V5-I02 | Resolved | Unsupported probability:** Reference gauge requested on-time probability but available model only computes deterministic conservative status. **Solution:** label as actual on-time share, explain denominator and no forecast; segment by observed status counts.
3. **V5-I03 | Resolved | Unsupported operator count:** Truck-specific assigned operator relationship unavailable, and worktype resources may be shared across trucks. **Solution:** use openly labeled staffed/open worktype-area counts instead of implying real assignment.
4. **V5-I04 | Resolved | Broken prospective navigation:** No existing standalone operator-directory route or live report export. **Solution:** implement read-only `/operators` and functional filtered CSV endpoint; sidebar other entries target existing sections/routes only.
5. **V5-I05 | Resolved | Responsive breakpoint:** Initial tablet 1024px DOM used four KPI cards. **Solution:** CSS 701–1199px breakpoint sets two columns. Responsive browser checks confirm no document overflow at desktop/mobile.
6. **V5-I06 | Resolved | Chart dependency:** Existing Plotly 2.35 script required network. **Solution:** package Plotly JavaScript locally and reference the bundled copy on dashboard, planner and detail pages. Other existing CDN resources retained intentionally.
7. **V5-I07 | Resolved | Stale test assumptions:** `tests/test_app.py` asserted deleted dark-navbar wording. **Solution:** update copy-only assertions to validate current design and preserve business checks; add comprehensive dashboard metric/filter/export test suite.
8. **V5-I08 | Open limitation | Browser environment:** Headless Chromium in the sandbox blocks direct local HTTP navigation, so served-page browser automation was not completed. **Mitigation:** verify Flask test client endpoints + headless browser `set_content` for responsive DOM/JS and desktop chart screenshot. Perform served-page E2E on deployment.
9. **V5-I09 | Open known limitation | Replay history:** One day of data, synthesized departures/experience, no arbitrary multi-day date filtering; fixed buffer and scenario state remain as v4. **Mitigation:** explicit provenance and no invented historical data.
10. **V5-I10 | Open production hardening:** Flask debug mode and lack of authentication/live WMS remain outside UI request; CDN Bootstrap/icons require access. **Mitigation:** mark demo-only and avoid representing authenticated profile or AI capabilities.

## v6 issues and solutions — 2026-10-11

1. **Inconsistent styling across interior pages — RESOLVED.** v5 dashboard was visually modern but planner, truck and operator details retained dense legacy panels. Added reusable page/panel/metric macros and a shared CSS visual system; kept original data and forms.
2. **Inconsistent chart semantics and style — IMPROVED.** Truck worktype plot mixed date-string plot axes with millisecond bar lengths. Now renders each existing ready timestamp/slow bound as timestamp markers against the buffered cutoff; other truck charts use a common muted blue/green/amber palette. No ETC formula changed.
3. **Mobile drawer could lose visible icon if icon font CDN unavailable — RESOLVED.** Critical brand and open/close controls are native inline SVG, independent of icon fonts.
4. **Workforce preview label can appear contradictory — DOCUMENTED/MITIGATED.** The earliest truck's plotted finish can meet its own deadline while the overall worktype remains AT RISK due to another truck; added the precise explanation beside preview graph. No undisclosed change to status calculation.
5. **CSS/Bootstrap JS depended on external CDN — RESOLVED FOR BOOTSTRAP.** Included local Bootstrap 5.3.6 CSS and JS. External Bootstrap Icons and optional Inter still require internet; system font fallback is available. **Open:** bundle first-party SVG symbols for all decorative icons if complete offline operation is required.
6. **Full historic test suite exceeds environment time budget — OPEN.** Focused 42 tests pass; full historical set timed out after progress without final result; rerun on developer workstation or CI. pandas FutureWarnings pre-exist and remain untouched.
7. **Test harness modifies stored SQLite during supervisor tests — RESOLVED FOR PACKAGE.** Restored exact baseline v5 database from original archive after tests and verified hashes. Recommended follow-up: isolate test DB in separate temporary path.
8. **Network-restricted browser test — PARTIALLY MITIGATED.** Local server HTTP navigation blocked by browser policy, but Flask test-client responses were rendered in headless Chromium with local CSS/JS across 15 page/viewport combinations with no runtime JS errors/overflow; full served-page browser acceptance still open.


## v7 current status issues — 2026-10-12

1. **V7-01 HIGH / OPEN — Unexpected SQLite scenario persistence:** `app.py`, `models/database.py`, `models/models.py`; conflicts with 2026-10-10 approved no-local-storage requirement. **Solution proposed, not applied:** clarify desired persistence; keep one consistent design and tests.
2. **V7-02 HIGH / OPEN — Operator eligibility/visibility inconsistency:** `eligible_candidates()` excludes simulated experience and source-unsafe candidates; approved policy allows labelled simulated experience and requires unsafe candidates to remain visible. **Solution proposed, not applied:** single list of experienced operators with provenance and disabled unsafe rows, consistent API/UI.
3. **V7-03 HIGH / REPRODUCED OPEN — Reset-and-reassign blocked:** reversals retain the unique `(scenario_id, operator)` row and preinsert check ignores status. **Solution proposed, not applied:** reviewed schema/transaction migration or scenario rollover allowing reuse while preserving audit history.
4. **V7-04 MEDIUM / OPEN — Allocation batch partial-write risk:** each operator is persisted in its own transaction. **Solution proposed, not applied:** atomic multi-operator write with version and source revalidation.
5. **V7-05 MEDIUM / OPEN — Restart lifecycle inconsistent with persisted decisions:** random signing key invalidates cookie but SQLite rows survive. **Solution proposed, not applied:** confirm lifecycle and implement scenario recovery/authentication if persistence approved.
6. **V7-06 MEDIUM / OPEN — Outdated active and historical documentation:** v4/README descriptions are inaccurate for uploaded code. **Mitigation applied:** add this status audit/README pointer; postpone rewriting older historical releases until target business rules are confirmed.
7. **V7-07 MEDIUM / OPEN — Flask integration and complete regression tests unverified:** Flask absent in container and offline package install fails, broad pytest timed out; selected calculation tests passed. **Solution proposed:** run in fully provisioned CI/test environment with isolated SQLite DB and perform actual route/browser checks.
8. **V7-08 RESOLVED IN PACKAGE — Missing derived SQLite cache:** reconstructed clean database from the supplied, unchanged workbook via existing engine. No synthetic/saved allocation history injected.
9. **V7-09 DATA LIMITATION / OPEN — One recorded day, synthetic experience/departures:** no reliable individual monthly pace or live WMS guarantees; maintain explicit provenance.


## Version 8 issue register — 2026-10-12

| Issue | Severity | Status | Finding and resolution |
|---|---|---|---|
| V8-001 | High | Resolved in demo | Persisted advisory allocations in v7 contradicted temporary session-only requirement and created reversal/reallocation uniqueness failure. Removed persistent model/table; confirmed moves are process-memory scenarios scoped to session, with reset and expiry. |
| V8-002 | High | Resolved in demo | Current source contained 33 trucks / many UI references. Generated active ten-truck workbook and rebuilt SQLite from matching entities; archived old 33-truck workbook separately. Verifies exact two naturally calculated AT RISK at snapshot10. |
| V8-003 | High | Resolved in demo | Fixed or pace-only staffing counts could be infeasible due to donor/source risk. Exact subset search checks conservative target cutoff and every donor worktype after each move; reports infeasibility if no combination passes. |
| V8-004 | High | Resolved | Switching from truck A to B in same worktype could keep pending preview selections. Key previews by snapshot+worktype+shipment, verify at explicit confirmation. |
| V8-005 | Medium | Resolved | Worktype conservative estimate could be `None` (`NO RATE`) and crash max readiness aggregation at early snapshots. `truck_projection` now safely propagates `NO RATE` with `finish=None`. |
| V8-006 | Medium | Resolved | Legacy loading override test left 48-minute shipment override, causing later risk/count tests to fail. Restore original persisted value in fixture cleanup; reverified no overrides remain at delivery. |
| V8-007 | Medium | Controlled demo assumption | Only one day of labor/production observations and 15 simulated familiarity entries; cannot validate 30-day individual pace. Calibrated synthetic replay and per-person fallback conspicuously labeled, never represented as real data. |
| V8-008 | Medium | Open for deployment | Full historical regression suite timed out. Focused v8 and route/UI suites passed 44/44, Python/JS syntax checks passed. Run comprehensive parity suite and live browser/device tests outside time-limited environment. |
| V8-009 | High for production | Open | In-memory scenario state is per Flask process and lacks authentication/RBAC. Suitable for local supervisor demo; production cluster must supply truly temporary expiring shared session store and verified authenticated operator roles. |
| V8-010 | Medium | Open | Cumulative picking order/transfer time and 30-day productivity unavailable; per-assignment risk inherited from worktype, not independent task ETC. No transfer time modeled per user's prior instruction. |
| V8-011 | Medium | Open by design | Exactly two risks guaranteed only for default synthetic snapshot10, default loading overrides and zero temporary staffing moves. Later snapshots and supervisor overrides can legitimately produce different counts; do not force labels. |

**Source safety rule:** Any experienced candidate (including labeled simulated qualifications) can be shown, but unsafe/unavailable candidates cannot be previewed or confirmed. A move is not a success if the truck remains at risk in another worktype. The initial one-operator/two-operator recommendations are independent scenarios and must not be combined without re-evaluation.


## 2026-10-12 — v9 removed noise and legacy gap inconsistency
- **Issue (resolved):** Three legacy detail charts obscured cutoff and workforce actions. **Solution:** Remove only their truck-detail template containers and JS renderers; retain calculators/source data for other consumers.
- **Issue (resolved):** Legacy operator-gap card showed a different baseline count unrelated to safe, individualized minimum recommendations. **Solution:** Read-only display adapter uses `recommend_minimum()` and labels non-feasible results distinctly; shows explanatory lines/hours/rate gap and current assigned picker count separately.
- **Issue (resolved):** Ready-time graph mixed point-ready, conservative uncertainty bound, and automatic historical proposals. **Solution:** Two-series conservative current vs safe after-adding projection; buffered deadline shaded and annotated, with clear temporary status label.
- **Issue (resolved):** Preview selection not represented on the truck detail graph. **Solution:** Read the preview for the exact shipment/worktype/snapshot from server-session state, without confirming it; recompute on request and reset.
- **Issue (known, unchanged):** One-day synthetic workbook cannot prove individual monthly pace; no live WMS integration; full Excel-parity suite and served-HTTP Chromium test not completed in v9.


## 2026-10-12 — v10
- **Issue (resolved):** The truck chart showed per-area times only; there was no truck-level before/after view, no ETC display and no distinction between missing the buffer and missing the cutoff. **Solution:** A shared before/after chart and table with green/yellow/red bands, a blue ETC bar and both deadlines.
- **Issue (resolved):** The 10-minute buffer and 30-minute default loading were code constants, and page texts said "fixed". **Solution:** The buffer is now configured in `.env` and the loading default is read from the workbook; texts show the configured values.
- **Issue (resolved):** Earlier notes said the full suite "timed out". **Solution:** The full suite completes in about 2 minutes: 163 passed at v9, 184 at v10.
- **Issue (open, pre-existing, found during the v9 review):** The operator directory links to profiles at snapshots where the operator has not logged in yet, which returns 404 (43 links across early snapshots). An invalid snapshot number on a truck page silently shows 16:15 data. Not changed in v10.
- **Issue (open, data):** The 10-truck demo keeps 100% of logged hours but only 16–49% of completed lines, so pick rates are 2–4 times too low and the demo's at-risk trucks are an artifact. Most trucks show NO RATE / Unknown before 17:45; a fallback rate needs a business decision.


## 2026-10-13 — v11
- **Issue (resolved):** At Risk appeared for one snapshot only (SH0908-1034 at 18:30; SH0908-1069 at 18:30–18:45). **Root cause:** a release burst combined with a pace measured on logged-in time including waiting, amplified by demo hours not scaled to the lines kept. **Solution:** picking-time pace in the planning layer, and demo labor time scaled to the line share. **Evidence:** no false at-risk at any snapshot; every On Time forecast met; status changes justified by input changes (tests).
- **Issue (resolved):** Demo pick rates 2–4× too low (open since the v9 review). **Solution:** `scripts/rescale_demo_labor.py`.
- **Issue (resolved):** The chart recommended moves into a non-bottleneck area when the bottleneck area could not be fixed. **Solution:** stop at the infeasible slowest area and explain.
- **Issue (resolved):** A ready time seconds past a deadline was shown as "0 min early". **Solution:** direction taken from exact times ("<1 min late").
- **Issue (open, business decision):** NO RATE before about 17:45 and at 19:00 (Cooler unstaffed) is genuine missing evidence; a fallback rate (e.g. M150 standard or historical average) needs SMD approval.
- **Issue (open, unchanged):** Operator profile links 404 at snapshots before the operator logs in; an invalid truck-page snapshot number falls back to 16:15.
- **Note:** The default demo snapshot no longer shows an at-risk truck. To demonstrate the planner, set a longer loading time for one truck (e.g. SH0908-1034: 100 min gives yellow → green with 1 operator), or agree a different synthetic departure.


## 2026-10-13 — v12
- **Feature (done):** Temporary Operator Allocation. See `TEMPORARY_OPERATORS_RELEASE_v12.md`.
- **Issue (resolved during build):** When the slowest area could not be fixed, the first draft added temporaries to other areas that could not help. **Solution:** apply the v11 rule to temporaries and recommend nothing in that case.
- **Issue (resolved during build):** The unknown-rate explanation disappeared when a temporary plan was found for an unstaffed area. **Solution:** always keep the explanation for the original row.
- **Issue (open, business):** Temporary pace (100% of per-person rate), the maximum (10 per work type) and onboarding/walking time are assumptions; SMD to confirm.
- **Issue (open, demo data, from v11):** On the operators page, some logged hours are below picking hours, because v11 scaled labor time to the share of lines kept while pick timestamps are real. Cosmetic; does not affect statuses.
- **Issue (open, unchanged):** Operator profile links 404 before the operator logs in; an invalid truck-page snapshot number falls back to 16:15.


## 2026-10-13 — v13
- **Feature (done):** Environmental Conditions & Workforce Planning, context only. See `ENVIRONMENT_RELEASE_v13.md`.
- **Issue (resolved during build):** Flash messages were not shown on the new page (the base layout does not render them). **Solution:** show them inside the section that was submitted.
- **Issue (resolved during build):** Area-condition text was clipped in the truck table and times wrapped in the dashboard card. **Solution:** wrapping widths.
- **Issue (open):** ENV-001 to ENV-006 (no real readings; temperature/RH is not heat stress; no break records; Wi-Fi, power and security unknown; shared entry key only; cooler may have validated monitoring). See `PROJECT_STATUS_v13.md` §6.
- **Issue (open, unchanged):** APP-001 authentication; DATA-001 synthesized departures; PLAN-001/002.


## 2026-10-14 — v14
- **Feature (done):** Calculated At Risk scenario and status evolution. See `PRESSURE_SCENARIO_RELEASE_v14.md`.
- **Issue (resolved during build):** First scenario design put other trucks at risk. **Solution:** use the two last-priority WT2 trucks with their own later appointment.
- **Issue (resolved during build):** openpyxl wrote times with 16 significant digits (16:45 became 16:44:59.9999). **Solution:** the generator writes floats with `repr`.
- **Issue (resolved during build):** An operator whose recorded history later moved to an area where he had no pace was skipped by the replay. **Solution:** fall back to his pace in the confirmed source area.
- **Issue (open, by design):** The planner cannot see future logouts or breaks; an allocation that looks sufficient can become insufficient (psam at 19:00). The next snapshot shows it.
- **Issue (open):** Scenario replay does not model transfer time (PLAN-002) and assumes the lowest-priority source lines are the ones reopened.
- **Issue (open, unchanged):** APP-001 authentication; DATA-001 synthesized departures; PLAN-001/002; ENV-001 to ENV-006.
