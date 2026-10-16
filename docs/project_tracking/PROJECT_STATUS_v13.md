# Project status — v13 (2026-10-13)

**Package:** `SMD-main-updated-20261013-v13.zip` · **Tests:** 246 passed · **Data:** 10-truck SYNTHETIC replay of 08-Sep-2026, warehouse 100 (not live SMD data)

## 1. What exists (before v13, unchanged)

| Area | Status |
|---|---|
| ETC engine | Excel-equation engine with parity tests. Conservative ETC = lines ahead ÷ cautious rate. Picking-time planning pace (v11). |
| Deadlines | Pick cutoff = departure − loading. Buffered deadline = cutoff − `SAFETY_BUFFER_MINUTES`. Per-truck loading overrides. |
| Pages | Dashboard, truck detail, operators, operator profile, Workforce allocation (planner). |
| Workforce actions | Safe reallocation (v8); before/after ready-time chart (v10); temporary operators after reallocation (v12). All allocations are session-only. |
| Data | Workbook golden reference and a rebuildable SQLite cache. Departures and some dock data are synthesized; operator familiarity is partly simulated. |

## 2. New in v13

| Item | Status | Data label |
|---|---|---|
| Environmental zones (6 M123 work types, plus user-added zones) | Implemented | Zones are verified work types; user zones are labelled |
| Manual temperature and RH entry with validation | Implemented, tested | ACTUAL (as entered) |
| Freshness, quality, attention list, dashboard card, truck and planner context | Implemented, tested | CALCULATED |
| Sensor ingestion API and device registry | Implemented, tested with simulated calls | ACTUAL once real devices post |
| Trend charts (when ≥ 3 readings in 6 h) | Implemented | as source |
| Association analysis | Implemented, gated; currently "insufficient evidence" | EXPERIMENTAL |
| Hydration and heat-safety information; client site notes | Implemented | Guidance cites NIOSH/OSHA; notes are client-documented |
| Synthetic demo readings | Optional button; deletable | SYNTHETIC |
| Hardware proposal and costs | Document only | Indicative prices |

## 3. Synthesized or assumed in v13

- The synthetic demo readings, and the demo device `DEMO-SENSOR-01` (a database record, not hardware).
- Thresholds: stale after 60 min; silent after 30 min; suspect at > 10 °C or > 30 %RH within 30 min; analysis minimums of 30 paired hours, 5 days and a 3 °C spread. These are prototype defaults.
- Warehouse time zone America/New_York.
- Six zones as the working count for the cost estimate.
- Installation, IT and firmware effort are not priced.

## 4. Pending (not done)

- **Hardware (Phase 3).** Nothing purchased, installed or tested. No device firmware. Wi-Fi coverage not surveyed. No reference-instrument comparison.
- **Real readings.** None yet. The analysis cannot conclude anything until ACTUAL readings cover at least 5 days.
- **Environment-adjusted ETC (Phase 4).** Not implemented. Requires evidence, validation against actual outcomes, and approval. See the proposal in `ENVIRONMENT_RELEASE_v13.md` §6.
- **User authentication.** Still open (APP-001). Entry uses a form token plus an optional shared key.
- **Break and hydration records.** Not in the source data (LM005S1 has login sessions only).
- Carried over from earlier versions:
  - synthesized departures and cutoffs (DATA-001);
  - simulated familiarity (PLAN-001);
  - transfer time (PLAN-002);
  - NO RATE fallback;
  - temporary-operator pace assumptions.

## 5. Questions for the client

**Environmental feature**

1. Is the goal productivity analysis, heat-safety monitoring, or both?
2. Which zones should be monitored? Are the six work types right? Are docks or sub-areas needed?
3. Is temperature or humidity already monitored (cold-chain system, BMS/HVAC, loggers)? Can that data be shared?
4. Is Wi-Fi coverage reliable in each zone, including the cooler and vault? May IoT devices join the network, and on which SSID or VLAN?
5. Are mains sockets available at the mounting points? Are there installation restrictions (drilling, racking, security areas, contractor access)?
6. What measurement frequency is wanted, and during which shifts? Who will enter readings during the manual phase?
7. What budget is available, who approves it, and is a 1–2 zone pilot acceptable first?
8. Which reference instrument (with certificate) will be used, and what tolerance is acceptable?
9. Who installs and maintains the devices?
10. What are the existing hydration stations, break policy and heat procedures? Can they be recorded in the app?
11. Should environment entry use individual sign-in rather than a shared key? How long should readings be kept?
12. Confirm the warehouse time zone. Should alert thresholds (stale, silent, suspect) differ by zone?
13. If an adjustment is ever approved: who signs off (operations and HSE), and what evidence period is acceptable?

**Carried over:** real departure and loading schedule; approved qualifications and cross-training; transfer time; fallback rate when no pace is measured; temporary-operator pace and maximum.

## 6. Remaining gaps and risks

| ID | Gap | Effect | Next action |
|---|---|---|---|
| ENV-001 | No real environmental readings | No analysis possible | Start manual entry or a pilot after approval |
| ENV-002 | Heat stress is not measured by temperature/RH | Readings cannot be used for safety decisions | WBGT measurement or occupational-health assessment if heat safety is a goal |
| ENV-003 | No break records | Cannot test the effect on breaks | Ask whether break or hydration events can be recorded |
| ENV-004 | Wi-Fi, power and security unknown | Hardware design not final | Site survey with IT and facilities |
| ENV-005 | Shared entry key only | Weak attribution of manual entries | Add user sign-in (APP-001) |
| ENV-006 | Cooler may have validated monitoring | Risk of duplicate or non-compliant monitoring | Use existing system data if available |
