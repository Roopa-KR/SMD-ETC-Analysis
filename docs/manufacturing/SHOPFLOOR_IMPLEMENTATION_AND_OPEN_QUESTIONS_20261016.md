# GiNi manufacturing — operator flow, WO traceability and confirmed points

**Date:** 16 October 2026  
**Release status:** Synthetic development prototype, **not** customer-accepted.

## Exact source scope

- Transcript supplied: 00:04–04:07, then an unrelated closing at 1:00:34; the middle ~56 minutes were not provided. It confirms manufacturing of tanks, WOs for 1/multiple units, tank stage flow, separate cover/accessory WOs as a possible process, inspections at stages, and that one or several workers may work on a tank. It explicitly treats variable worker specialization and kitting as not yet verified.
- `EN_Siemens_CTQ_Guide 1(2).xlsx`: `CTQ Guide (2)` has 24 questions across WC1–WC8; source-bound mapping retained in `manufacturing/data/ctq_rules.json`. The workbook defines Yes/No vs Input, its negative-answer fields, help/requirements and conditional image evidence, but not all numeric nominal limits.
- `Mockup ingles html(1).html`: intended six-stage operator UI, LMS supervision screen and WO three-pane traceability UI. Many sample values, awards and OEE are hardcoded illustrations; the mockup is **not** itself a validated rule engine.
- Existing `GiNi_Production_Flow_Recovery` demonstrator: fixed deterministic PDF scenarios and a conservative CTQ release rule, *independent* of the new real-UTC task sessions. First-stage tank scrap is permanent. Later-stage release/rework disposition is unconfirmed.
- User-confirmed scoring **weights**: +3 / WO no rework; +2 / WO origin defect caught+fixed; −4 / confirmed downstream defect; ±1 point / minute vs target. Attribution, sign/rounding and approval details remain unclear.

## What has now been implemented

| Feature | Behavior | Source / constraint |
|---|---|---|
| Process and station selection | WC1–WC8, mapped to tank, cover or accessory routes | CTQ workbook and reference routes |
| Operator + unit + WO selection | Only known physical units and demo-qualified workers at current station | Transcript; worker eligibility is **synthetic** and conservative |
| Shared-unit labor | Multiple workers may start sessions on one physical unit | Transcript |
| One active assignment per worker | Unique database constraint across RUNNING and PAUSED prevents double-booking | Safety constraint; pause **does not** release assignment |
| Task time events | Persist START/PAUSE/RESUME/FINISH and UTC timestamps; compute active time excluding pauses | Mockup; paused time tracked as separate interval |
| Live timer display | Second-by-second presentation clock; server event history is authoritative | Mockup; not linked to PDF replay |
| CTQ checklist | Station-specific questions with hyperlinks to existing validated evidence-aware form | Workbook |
| Incoming inspection | Log ACCEPTED or DEFECT_REPORTED at downstream current work center; record detector/time and upstream station separately | Mockup; no inferred responsibility |
| Defect reporting | Persistent open issue; affected active unit is held for review; further CTQ progression blocked | Conservative safe implementation; no auto scrap/rework |
| WO control page | Separate family WOs, stage flow, unit passports, recorded CTQ history, task sessions, receipts and issue history | Transcript + mockup; stages from fixture, not verified historic releases |
| LMS | Recorded productive labor, task counts, worker activity, WO quantities and open quality reports | No fabricated OEE or historical benchmarks |
| Points | Exact four confirmed weights encoded in `manufacturing/scoring.py`. Verified WO-level formula available; display eligibility and unsettled reports | No automatic employee blame, awards or deductions without confirmation |
| Regression | Original 10 screens remain; three new screens, 4 new HTTP paths and new persistent tables | Existing legacy code kept intact |

### Important invariants

1. A physical unit belongs to exactly one WO and follows its component-specific demo route; a WO can contain many units.
2. A completed task is **not** evidence of passing a CTQ gate.
3. Missing CTQ input is never a pass; a single passed check never overrides another failed/missing check.
4. A downstream **reported** defect is not automatically a confirmed origin defect or worker fault. No penalty/rework task is generated from a report alone.
5. The new UTC-clocked operator sessions do not alter the PDF's scenario cycle times, due-date forecast or labor assumptions.
6. Work-center historical counts in existing synthetic fixtures cannot certify old quality gates; the WO screen clearly labels that limit.
7. Routes WC5–WC8 stay separate from the tank until a final-assembly/kitting join is confirmed.

## Scoring policy and eligibility

| Code | Weight | Only when |
|---|---:|---|
| NO_REWORK_WO | +3 | Whole WO is confirmed complete and rework count is zero |
| ORIGIN_CAUGHT_FIXED_WO | +2 | Origin detection and fix are **confirmed** for the WO (award capped to once per WO) |
| DOWNSTREAM_CONFIRMED_DEFECT | −4 each | Defect is validated as downstream-detected; **per-WO** provisional scope until accountability is confirmed |
| TIME_DIFFERENCE_PER_MINUTE | ±1 / min | Approved target, reliable measured task time, scoring polarity and rounding all configured |

The pure computation includes a **preview** of `target − actual` minutes (positive for earlier completion), without applying it to any ledger or ranking. This is a calculation aid, not a signed-off payout/employee scoring rule. The current data has **no confirmed** downstream defects, no authorized resolution of origin defects, and no approved time targets; reports therefore remain pending. Only a fully completed clean WO could qualify for +3 without additional decisions.

## Clarifications required *before* enabling additional features

1. **Physical units / WO quantities:** Is every tank inspected individually? Is batch sampling allowed? Are there explicit unit IDs, sub-operation quantities or quantity-level bookings?
2. **Tank route:** Confirm the actual station order, release gates and whether partial batches can move independently.
3. **Cover/accessory join:** Are WOs linked in a bill of materials? When does kitting/final assembly occur and what stops assembly if a component is missing?
4. **Worker eligibility:** Are tasks universally flexible or skill/certification-controlled? How are operator qualifications, shift transfers, supervision, and permissions authorized?
5. **Task time:** Should pauses count toward productivity, and which pause reasons count as direct vs indirect labor? How is task time apportioned when several people share one tank?
6. **Standards:** What are the approved target minutes for every size, component, operation, quantity, crew and shift? Does painting cure count as process time but not worker time?
7. **CTQ numbers:** For each numeric check, what blueprint nominal, limits, unit, calibration instrument and revision validate a measurement?
8. **Evidence:** Which checks require images always versus only when answers trigger `Evidence Yes/No`? Are camera capture/device ownership requirements enforced?
9. **Incoming check:** When may a receiving operator accept a unit with missing upstream records? Who may release a hold and what evidence is required?
10. **Rework:** Who approves, creates, assigns, closes or rejects rework? Which failures are permanent scrap versus repairable? How is rework time counted?
11. **Defect origin:** Who confirms the cause and validates links between detection, equipment, material, operator/crew and origin process? When, if ever, is a person accountable?
12. **Points recipient:** Are the four point rules WO-level, crew-level, individual, or a mix? How are shared units or shared defects credited/debited?
13. **Points stacking:** May a WO receive +3 and +2, or are no-rework/origin-rework mutually exclusive? What is the +2 meaning if an origin defect is repaired without a formal rework ticket?
14. **−4 deduction trigger:** Does a downstream *report* trigger it or only a confirmed defect following supervisor review? Can it be reversed after investigation?
15. **±1 time variance:** Is a minute faster always +1 and a minute slower −1? Fractional-minute rounding? Capped score? Target vs actual source? Points per task, unit, station, or WO?
16. **Dashboards:** What exactly are OEE's availability, performance and quality inputs? Which historical date ranges/tank-size models and comparison baselines are approved?
17. **Operational continuity:** What happens to an interrupted task across logout, device loss, shift change or concurrent tablet usage? Which roles can pause another worker's task?
18. **Scenario integration:** What event data and production standards are available to replace the fixed scenario with a real dynamic flow engine?
19. **Access control:** Authentication, supervisor privileges, permissions to inspect, approve, override, score and view personal performance.
20. **Client UI:** Brand/logo authorization and desired production deployment target; the mockup includes third-party remote CSS/JS while this implementation keeps existing local CSS and JS.

## Validation limits

See `SHOPFLOOR_TEST_REPORT_20261016.md`. Dependencies `Flask` and `Pillow` are declared, but Flask is unavailable in this execution environment. Pure Python/SQLite tests, strict Jinja renders and JS syntax checks were executed; actual Flask server startup and route/browser integration still require a machine with dependencies installed.
