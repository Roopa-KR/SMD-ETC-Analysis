# Low-cost environmental monitoring: proposed hardware and indicative costs (v13)

**Date:** 2026-10-13 · **Status:** PROPOSAL ONLY. Nothing has been purchased, installed or tested on hardware. No budget is assumed. Every figure below needs client approval.

Prices are online list prices checked on 2026-10-13. They are **indicative component prices**, not quotes or installed costs. They exclude tax, shipping, import duty and currency movements. Lines marked *estimate* are not sourced prices.

## 1. Recommended path

| Step | What | Hardware cost |
|---|---|---|
| **Phase 1 (now)** | Supervisors record readings in the web app (Environment → Record a reading), using a thermo-hygrometer the site already has, or one the client approves. | None if a meter exists |
| **Pilot (Phase 3, after approval)** | 1–2 zones with an ESP32 node on existing Wi-Fi. Compare with a reference instrument for 2–4 weeks before any wider roll-out. | ~ $44 per zone + reference instrument |
| **Roll-out** | Only the zones the client confirms, only if the pilot shows reliable readings and coverage. | Per-zone cost × zones confirmed |

The software side is ready for this path: device registry, a token-protected ingestion API, validation, duplicate handling and silent-sensor detection, all tested with simulated API calls (see `ENVIRONMENT_RELEASE_v13.md`). **Device firmware has not been written or tested.**

## 2. Sensor choice: is DHT22 / AM2302 appropriate?

| Sensor | Indicative price | Accuracy (vendor) | Notes |
|---|---|---|---|
| AM2302 (wired DHT22) | $15.00 | ±0.5 °C; 2–5 %RH; −40…80 °C | Requested reference option. **Discontinued at Adafruit**, which recommends the AM2301B instead. Slow single-wire protocol; one reading every 2 s at most. Clones of mixed quality are common. |
| **AM2301B (wired, enclosed AHT20)** | **$7.95** | typ. ±0.3 °C, ±2 %RH (20–80 %RH, 20–60 °C) | **Recommended default.** Same form factor as the wired DHT22, cheaper, I²C, comes in its own vented housing on a cable. |
| SHT41 breakout (Sensirion) | $5.95 | typ. ±0.2 °C, ±1.8 %RH | Best accuracy for the price. Bare board, so it needs a vented housing. Good choice for the reference-comparison pilot. |

All three are adequate for **trend and context** monitoring. None measures heat stress (see section 6).

## 3. Per-zone bill of materials (Wi-Fi, mains-USB powered)

| Category | Item | Indicative price | Source / basis |
|---|---|---|---|
| Controller | Adafruit HUZZAH32 ESP32 Feather, assembled headers | $20.95 | Adafruit 3405 |
| Sensor | AM2301B wired enclosed AHT20 | $7.95 | Adafruit 5181 |
| Power | 5 V 1 A USB wall adapter | $5.95 | SparkFun TOL-11456 |
| Power | Micro-USB cable, 1–2 m | ~ $3 | *estimate* |
| Enclosure | Hammond 1591XXMSBK ABS box 85 × 56 × 25 mm, IP54 (controller only; the sensor hangs outside on its cable so air reaches it) | £2.71 ex VAT (≈ $3.60) | Rapid Electronics; USD conversion approximate |
| Mounting | Screws, cable ties, adhesive cable clips, label | ~ $2 | *estimate* |
| **Components per zone** | | **≈ $43.50** | |

**Six zones** (one per M123 work type, a working assumption until the client confirms the zone list): **≈ $261** in components (6 × $43.45 = $260.70).

## 4. Connectivity: only where Wi-Fi does not reach

Existing Wi-Fi is preferred and costs nothing extra if it covers the zones and IT allows IoT devices on it. Wi-Fi coverage has **not** been verified. Cold rooms, vaults and metal racking often weaken signals.

| Situation | Option | Indicative extra cost |
|---|---|---|
| Good Wi-Fi, IoT devices allowed | Existing network (a separate SSID or VLAN if IT requires) | $0 hardware; IT time |
| Wi-Fi weak in one zone, nearby zone has coverage | ESP-NOW: the node sends to a gateway ESP32 placed in Wi-Fi range, which forwards to the API | +1 gateway board ≈ $21 (one gateway can serve several nodes) |
| No Wi-Fi allowed, wired network available | Olimex ESP32-POE-ISO (Ethernet with isolated PoE power) instead of the Feather and USB adapter | €24.95 per node; needs a PoE switch port or injector (*not priced*) and a cable run |
| No network at all | Manual entry stays the method | $0 |

## 5. Installation, calibration and maintenance

| Category | What | Indicative cost |
|---|---|---|
| Installation & mounting | About 0.5–1 hour per zone. Mount at working height, away from doors, heaters, dock openings, lights and direct airflow. Mains socket needed nearby. | Labour rate **not known**; client to supply |
| Calibration (low cost) | Two-point check: side-by-side comparison with a reference instrument, plus a saturated-salt check (about 75 %RH over table salt) for humidity. Record each sensor's offset. | Salt and sealed container: a few dollars (*estimate*) |
| Reference instrument | Extech HT30 heat-stress WBGT meter (air temperature, RH and WBGT). Doubles as the heat-stress instrument in section 6. Confirm it has a calibration certificate if it is used as the reference. | $219 (listed sold out at the time of checking) |
| Maintenance | Monthly: check readings against the reference instrument and clean dust. Replace a sensor whose offset exceeds the agreed tolerance. | ~ 10 min per zone per month; a spare sensor ≈ $8 |
| Software integration | Ingestion API, validation, dashboard and tests: **done in v13**. Still to do: device firmware (read sensor → POST JSON every N minutes, with retry) and IT network setup. | Developer time, to be estimated after the pilot scope is agreed |

### Indicative total (six zones, Wi-Fi available)

| Item | Indicative cost |
|---|---|
| Six-zone component kit | ≈ $261 |
| Spare sensor and controller | ≈ $29 |
| Reference / WBGT instrument (optional, but recommended if heat safety is a goal) | $219 |
| **Hardware subtotal** | **≈ $510** |
| Installation labour, IT setup, firmware development | Not priced; client to confirm |

## 6. Heat-safety measurement is a separate question

Temperature and humidity show conditions and trends. They do **not** measure occupational heat stress, which also depends on radiant heat, air movement, workload and clothing. OSHA recommends on-site WBGT measurement. If heat safety is a goal, the client should use a WBGT meter or a qualified occupational-health assessment. The ESP32 nodes are not a substitute.

## 7. Zone-specific notes

- **Cooler (WT 5).** Pharmaceutical cold storage usually already has a validated, alarmed temperature-monitoring system. Do not duplicate it or treat this low-cost sensor as compliant monitoring. Ask whether existing readings can be shared instead. Moving between cold and warm areas causes condensation, so use a sealed controller box and a vented sensor.
- **Vault (WT 3) and Cage (WT 4).** Security rules may prohibit wireless devices, new cables or contractor access. Confirm before planning a node there.
- **Dock and loading areas.** These are not M123 work types. Add them as user-defined zones only if the client wants them.

## 8. Questions for the client before any recommendation is final

1. **Goal.** Is the aim productivity analysis, heat-safety monitoring, or both? This decides between temperature/RH sensors and WBGT assessment.
2. **Zones.** Which areas should be monitored, and are the six M123 work types the right zones? Are there sub-areas or docks?
3. **Existing equipment.** Is temperature or humidity already monitored (cold chain, BMS/HVAC, data loggers)? Can that data be shared through an export or API?
4. **Wi-Fi.** Is coverage reliable in each zone, including the cooler and vault? Can IoT devices join, on which SSID or VLAN? Is a site survey available?
5. **Power and mounting.** Are mains sockets available near each mounting point? Are there rules on drilling, cable runs or mounting on racking?
6. **Measurement frequency.** For example every 5, 15 or 60 minutes, and during which shifts. Manual entry needs a realistic frequency, such as hourly.
7. **Budget and approval.** Who approves spending, what is the ceiling, and is a 1–2 zone pilot acceptable first?
8. **Calibration.** Is there an approved reference instrument with a certificate, and what tolerance is acceptable (for example ±0.5 °C, ±3 %RH)?
9. **Installation and maintenance.** Who installs (facilities, an electrician, IT) and who checks the sensors monthly?
10. **Data and access.** Who may enter readings manually, and should a sign-in replace the shared entry key? How long should readings be kept?
11. **Policies.** What are the existing hydration stations, break policy and heat procedures, so they can be documented in the app?

## Sources

- [Adafruit HUZZAH32 ESP32 Feather (3405)](https://www.adafruit.com/product/3405)
- [Adafruit AM2302 wired DHT22 (393), discontinued](https://www.adafruit.com/product/393)
- [Adafruit AM2301B wired enclosed AHT20 (5181)](https://adafruit.com/product/5181)
- [Adafruit Sensirion SHT41 (5776)](https://www.adafruit.com/product/5776)
- [SparkFun USB wall charger 5 V 1 A](https://www.sparkfun.com/usb-wall-charger-5v-1a-black.html)
- [Rapid Electronics Hammond 1591XX ABS enclosures](https://rapidonline.com/hammond-1591xx-series-general-purpose-abs-enclosures-black-519028)
- [Olimex ESP32-POE-ISO](https://www.olimex.com/Products/IoT/ESP32/ESP32-POE-ISO/open-source-hardware)
- [Extech HT30 WBGT meter (TruTech Tools)](https://www.trutechtools.com/EXTECH-HT30)
- [OSHA heat hazard recognition (WBGT)](https://www.osha.gov/heat-exposure/hazards)
