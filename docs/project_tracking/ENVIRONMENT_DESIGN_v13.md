# Environmental Conditions & Workforce Planning — design (v13, written before implementation)

**Date:** 2026-10-13 · **Baseline:** v12 (206 tests passing) · **Status:** design recorded first, then implemented as described in `ENVIRONMENT_RELEASE_v13.md`.

## What exists today (inspected)

- **Zones in source data.** `LM005S1.ZONEID` is empty in the active extract. TI102 `SRCLOC` holds bin codes, not named zones. The only verified work areas are the six M123/M123T work types: Prescription, OTC, Vault, Cage, Cooler, Cases.
- **No environmental data.** No temperature, humidity or break records exist anywhere in the workbook, SQLite cache or code.
- **Pace data.** LM005S1 sessions give logged time; TI102C gives pick times. Breaks are not recorded; v11 infers waiting only from gaps between picks.
- **Storage.** `data/truck_etc.db` is a rebuildable cache. Whole tables are dropped and rebuilt when the workbook changes, so it is not a safe place for user-entered readings.
- **Users.** The app has no authentication or roles (open gap H-13 since v1).

## Design decisions

1. **Separate database.** Environmental readings go in `data/environment.db`, never in the WMS/LMS source tables or the rebuildable cache (`ENV_DATABASE_URL`). Cache rebuilds can never delete readings, and readings can never overwrite operator, workload or transaction data.
2. **Zones.**
   - Seeded automatically from the M123 work types, labelled *source = M123 work type*.
   - Supervisors may add other zones (for example a dock area), labelled *user added*.
   - No zone is invented.
3. **Collection methods.** Each reading records one of:
   - `manual`: entered by a person in the web app;
   - `sensor`: received through the ingestion API from a registered device;
   - `synthetic`: demo data, created only by the explicit "Load synthetic demo readings" action, always labelled and removable.
4. **Data labels.**
   - Manual and sensor readings are **ACTUAL** (as entered or measured, unverified against a reference instrument).
   - Demo readings are **SYNTHETIC**.
   - Analysis outputs are **CALCULATED** or **EXPERIMENTAL**.
   - Synthetic readings are never used as evidence in the productivity analysis.
5. **Time.**
   - Stored as UTC ISO 8601.
   - Displayed and compared in warehouse local time (`WAREHOUSE_TIMEZONE`, default America/New_York, matching the documented South Carolina operation; to be confirmed).
   - Manual entries are local time.
   - API timestamps must carry a UTC offset or `Z`.
   - The replay compares against the selected snapshot time ("as-of"); live operation would use the current time.
6. **Quality.** Each reading gets one status:
   - `valid`;
   - `suspect`: a step of more than `ENV_MAX_STEP_C` (10 °C) or `ENV_MAX_STEP_RH` (30 %RH) within 30 min of the zone's previous reading; shown with a warning, excluded from analysis;
   - `invalid`: outside the physical limits (temperature −40…85 °C, the DHT22/AM2302 operating range; RH 0…100 %), or a non-numeric value. Manual entries outside the limits are rejected with a message. Sensor values outside them are stored as `invalid` so a faulty device is visible, and never displayed as a condition.
7. **Freshness** (relative to the as-of time):
   - `current`: the latest valid reading is no older than `ENV_STALE_MINUTES` (60);
   - `stale`: it is older;
   - `missing`: there is no reading at or before the as-of time.

   A registered device with no reading for more than `ENV_DEVICE_SILENT_MINUTES` (30) is listed as **sensor requires attention**.
8. **Duplicates.** The same zone, timestamp, method and device is accepted once; repeats are reported as duplicates and not stored. This makes sensor retries safe. Future timestamps more than 5 minutes ahead are rejected.
9. **ETC integration: context only.**
   - The latest reading and its status appear beside the work type on the truck page and in the planner, labelled "context only — not used in ETC".
   - **No environmental adjustment is implemented (Phase 4).** The baseline ETC, ready time, cutoff status and operator allocations are unchanged whether readings exist, are missing or are invalid.
   - The dashboard shows "Environment-adjusted ETC: not available (no validated, approved method)".
10. **Analysis (Phase 2): association only.**
    - Pairs valid ACTUAL readings with picking pace for the same work area and hour.
    - Reports a correlation with a bootstrap interval only when there are at least `ENV_MIN_PAIRED_HOURS` (30) paired hours across at least `ENV_MIN_DAYS` (5) days and a temperature spread of at least 3 °C.
    - Otherwise it lists what is missing.
    - Always labelled EXPERIMENTAL and "association, not causation". Never fed into ETC.
11. **Access.**
    - Manual entry and device registration need the form token, plus an optional entry key (`ENV_ENTRY_KEY`) when set.
    - The sensor API needs a bearer token (`ENV_INGEST_TOKEN`); the API is disabled when the token is empty, which is the default.
    - Real user authentication remains a production gap.
12. **Heat and hydration section.**
    - Informational only, citing official guidance.
    - Readings are not a heat-stress assessment: it recommends WBGT measurement or a qualified occupational-health assessment where needed.
    - Never suggests working through unsafe heat to meet a cutoff.
    - The client can record their own hydration stations, break policy and procedures as free text (stored as client-entered site notes).

## Proposed tables (`data/environment.db`)

| Table | Columns | Notes |
|---|---|---|
| `env_zone` | `zone_code` PK, `name`, `worktype` (nullable), `source` (`M123 work type` / `user added`), `active`, `created_utc` | Work-type zones seeded from the cached M123 names |
| `env_device` | `device_id` PK, `zone_code`, `description`, `data_label` (`ACTUAL`; `SYNTHETIC` only for the demo device), `registered_utc`, `last_seen_utc` | Readings from an unregistered device are rejected per item (status `rejected`) |
| `env_reading` | `id` PK, `zone_code`, `temperature_c`, `humidity_pct`, `reading_utc`, `received_utc`, `method`, `device_key` (`''` for manual), `recorded_by`, `quality`, `quality_note`, `data_label`; UNIQUE(`zone_code`, `reading_utc`, `method`, `device_key`) | Never written into WMS/LMS tables |
| `env_site_note` | `topic` PK (`hydration_stations`, `break_policy`, `procedures`), `text`, `updated_utc`, `updated_by` | Client-documented information only |

## Proposed endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/environment?snapshot=n` | Zone conditions, entry form, devices, trends, analysis, heat & hydration |
| POST | `/environment` | Form actions: `reading`, `zone`, `device`, `note`, `load_synthetic`, `delete_synthetic` (form token + optional entry key) |
| POST | `/api/environment/readings` | Sensor ingestion: JSON `{device_id, temperature_c, humidity_pct, reading_time}` or a list (max 500); bearer token; returns per-reading result (stored / duplicate / invalid / rejected) |
| GET | `/api/environment/zones?snapshot=n` | Latest condition and freshness per zone (read-only) |

## Proposed configuration (`.env`)

`ENV_DATABASE_URL`, `WAREHOUSE_TIMEZONE`, `ENV_STALE_MINUTES=60`, `ENV_DEVICE_SILENT_MINUTES=30`, `ENV_TEMP_MIN_C=-40`, `ENV_TEMP_MAX_C=85`, `ENV_MAX_STEP_C=10`, `ENV_MAX_STEP_RH=30`, `ENV_INGEST_TOKEN=` (empty = API off), `ENV_ENTRY_KEY=` (empty = no key), `ENV_MIN_PAIRED_HOURS=30`, `ENV_MIN_DAYS=5`.

The thresholds are prototype defaults to be confirmed with the client. They are not business rules.

## Phases

| Phase | Scope in v13 |
|---|---|
| 1 Low-cost prototype | **Implemented**: manual entry, zones, validation, freshness, dashboard summary, environment page |
| 2 Productivity analysis | **Implemented as a sufficiency-gated, experimental analysis**. With today's data it reports insufficient data, which is correct |
| 3 Sensor integration | **Software side implemented and tested with simulated API calls**: device registry, token-protected ingestion, disconnection detection. **No hardware purchased, installed or tested.** Hardware proposal in `ENVIRONMENT_HARDWARE_PROPOSAL_v13.md` |
| 4 Validated ETC adjustment | **Not implemented by design.** Requires evidence and approval; see the proposal in `ENVIRONMENT_RELEASE_v13.md` |
