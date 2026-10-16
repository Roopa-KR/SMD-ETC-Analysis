"""Environmental conditions by zone (v13): validation, quality, freshness and sensor status.

CONTEXT ONLY. Nothing in this module changes ETC, ready time, cutoff status or operator allocation;
see calculations/environment_analysis.py for the (experimental, sufficiency-gated) analysis.

Quality of a reading
    invalid  temperature outside ENV_TEMP_MIN_C..ENV_TEMP_MAX_C (default −40..85 °C, the DHT22/AM2302
             operating range) or RH outside 0..100 %, or not a number. Manual entries are rejected;
             sensor values are stored as invalid (so the device shows as needing attention) and are
             never displayed as a condition or used in analysis.
    suspect  a step larger than ENV_MAX_STEP_C / ENV_MAX_STEP_RH within 30 min of the zone's previous
             reading. Shown with a warning; excluded from analysis.
    valid    otherwise.
Freshness of a zone at the as-of time (the selected replay snapshot; "now" in live use)
    current  latest valid/suspect reading at or before as-of is ≤ ENV_STALE_MINUTES old
    stale    older than that
    missing  no reading at or before as-of
A registered device with no reading for more than ENV_DEVICE_SILENT_MINUTES before as-of, or whose
latest reading is invalid, "requires attention".
"""
from __future__ import annotations

import datetime as dt
import math

import config
from models import environment as store

FUTURE_TOLERANCE = dt.timedelta(minutes=5)
STEP_WINDOW = dt.timedelta(minutes=30)
METHOD_LABELS = {'manual': 'Manual entry', 'sensor': 'Sensor', 'synthetic': 'SYNTHETIC demo'}


# ---------- time ----------
def _zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(config.WAREHOUSE_TIMEZONE), True
    except Exception:  # tz database missing (install tzdata on Windows) or unknown name
        return dt.timezone.utc, False


def timezone_status() -> dict:
    tz, ok = _zone()
    return dict(name=config.WAREHOUSE_TIMEZONE if ok else 'UTC', ok=ok,
                note='' if ok else ('Time-zone data unavailable: times shown in UTC. Install the tzdata '
                                    'package (requirements.txt) or check WAREHOUSE_TIMEZONE.'))


def local_to_utc(local_naive: dt.datetime) -> dt.datetime:
    tz, _ = _zone()
    return local_naive.replace(tzinfo=tz).astimezone(dt.timezone.utc)


def utc_to_local(value) -> dt.datetime:
    tz, _ = _zone()
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    return value.astimezone(tz).replace(tzinfo=None)


def parse_api_time(value):
    """ISO 8601 with offset or Z (required for sensors). Returns aware UTC or raises ValueError."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError('reading_time is required (ISO 8601 with UTC offset, e.g. 2026-09-08T18:20:00-04:00)')
    parsed = dt.datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('reading_time must include a UTC offset or Z')
    return parsed.astimezone(dt.timezone.utc)


# ---------- validation ----------
def _number(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field} must be a number')
    if not math.isfinite(number):
        raise ValueError(f'{field} must be a finite number')
    return number


def out_of_range(temperature, humidity) -> str | None:
    if not config.ENV_TEMP_MIN_C <= temperature <= config.ENV_TEMP_MAX_C:
        return (f'temperature {temperature:g} °C outside the valid range '
                f'{config.ENV_TEMP_MIN_C:g}..{config.ENV_TEMP_MAX_C:g} °C')
    if not 0 <= humidity <= 100:
        return f'relative humidity {humidity:g} % outside 0..100 %'
    return None


def assess_step(zone_code, temperature, humidity, reading_utc: dt.datetime, synthetic: bool):
    previous = store.previous_reading(zone_code, store.utc_text(reading_utc), synthetic)
    if not previous or previous['temperature_c'] is None:
        return 'valid', ''
    gap = reading_utc - dt.datetime.fromisoformat(previous['reading_utc'])
    if gap > STEP_WINDOW:
        return 'valid', ''
    dt_c = abs(temperature - previous['temperature_c'])
    dt_rh = abs(humidity - previous['humidity_pct'])
    if dt_c > config.ENV_MAX_STEP_C or dt_rh > config.ENV_MAX_STEP_RH:
        return 'suspect', (f'changed {dt_c:.1f} °C / {dt_rh:.0f} %RH within {int(gap.total_seconds() // 60)} min '
                           f'of the previous reading; check the sensor or entry')
    return 'valid', ''


def record_reading(zone_code, temperature, humidity, reading_utc: dt.datetime, method, device_id='',
                   recorded_by='', now=None, data_label=None):
    """Validate and store one reading. Returns dict(status, quality, note).

    Raises ValueError for manual entries that are invalid (the person can correct them).
    Sensor values outside physical limits are stored as quality 'invalid' (device needs attention).
    """
    now = now or store.now_utc()
    zone_codes = {z['zone_code'] for z in store.zones()}
    if zone_code not in zone_codes:
        raise ValueError(f'Unknown zone {zone_code}')
    if reading_utc > now + FUTURE_TOLERANCE:
        raise ValueError('Reading time is in the future')
    try:
        temperature = _number(temperature, 'Temperature')
        humidity = _number(humidity, 'Relative humidity')
        problem = out_of_range(temperature, humidity)
    except ValueError as error:
        if method != 'sensor':
            raise
        temperature, humidity, problem = None, None, str(error)
    if problem and method != 'sensor':
        raise ValueError(problem[0].upper() + problem[1:])
    data_label = data_label or ('SYNTHETIC' if method == 'synthetic' else 'ACTUAL')
    synthetic = data_label == 'SYNTHETIC'
    if problem:
        quality, note = 'invalid', problem
    else:
        quality, note = assess_step(zone_code, temperature, humidity, reading_utc, synthetic)
    row = dict(zone_code=zone_code, temperature_c=temperature, humidity_pct=humidity,
               reading_utc=store.utc_text(reading_utc), received_utc=store.utc_text(now), method=method,
               device_key=device_id or '', recorded_by=recorded_by or None, quality=quality,
               quality_note=note or None, data_label=data_label)
    status = store.insert_reading(row)
    if device_id and status == 'stored':
        store.touch_device(device_id, row['reading_utc'])
    return dict(status=status, quality=quality, note=note)


def ingest(payload, now=None):
    """Sensor API body: one object or a list (≤ 500) of {device_id, temperature_c, humidity_pct, reading_time}."""
    items = payload if isinstance(payload, list) else [payload]
    if len(items) > 500:
        raise OverflowError('At most 500 readings per request')
    results = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            results.append(dict(index=index, status='rejected', note='each reading must be a JSON object'))
            continue
        device_id = str(item.get('device_id', '')).strip()
        device = store.device(device_id) if device_id else None
        if device is None:
            results.append(dict(index=index, status='rejected', note=f'device {device_id or "(missing)"} is not registered'))
            continue
        try:
            when = parse_api_time(item.get('reading_time'))
            outcome = record_reading(device['zone_code'], item.get('temperature_c'), item.get('humidity_pct'),
                                     when, 'sensor', device_id=device_id, now=now,
                                     data_label=device['data_label'])
        except ValueError as error:
            results.append(dict(index=index, status='rejected', note=str(error)))
            continue
        results.append(dict(index=index, **outcome))
    return results


# ---------- conditions ----------
def _age_minutes(as_of_utc, reading_utc_text):
    return (as_of_utc - dt.datetime.fromisoformat(reading_utc_text)).total_seconds() / 60


def zone_conditions(as_of_local: dt.datetime):
    """Latest condition per active zone at the as-of time (replay snapshot), plus attention items."""
    as_of_utc = local_to_utc(as_of_local)
    until = store.utc_text(as_of_utc)
    out = []
    for zone in store.zones():
        shown = store.readings(zone['zone_code'], until_utc=until, qualities=('valid', 'suspect'), limit=1)
        last_any = store.readings(zone['zone_code'], until_utc=until, limit=1)
        reading = shown[0] if shown else None
        if reading is None:
            freshness, age = 'missing', None
        else:
            age = _age_minutes(as_of_utc, reading['reading_utc'])
            freshness = 'current' if age <= config.ENV_STALE_MINUTES else 'stale'
        latest_invalid = last_any[0] if last_any and last_any[0]['quality'] == 'invalid' else None
        out.append(dict(zone=zone, reading=reading, freshness=freshness,
                        age_minutes=round(age) if age is not None else None,
                        local_time=utc_to_local(reading['reading_utc']).strftime('%d-%b %H:%M') if reading else None,
                        method_label=METHOD_LABELS.get(reading['method'], '') if reading else '',
                        latest_invalid=latest_invalid))
    attention = []
    for c in out:
        name = c['zone']['name']
        if c['freshness'] == 'missing':
            attention.append(dict(kind='missing', zone=name, text=f'{name}: no reading at or before this time.'))
        elif c['freshness'] == 'stale':
            attention.append(dict(kind='stale', zone=name,
                                  text=f"{name}: latest reading is {c['age_minutes']} min old "
                                       f"(stale after {config.ENV_STALE_MINUTES} min)."))
        if c['reading'] and c['reading']['quality'] == 'suspect':
            attention.append(dict(kind='suspect', zone=name, text=f"{name}: latest reading is suspect — "
                                                                  f"{c['reading']['quality_note']}."))
        if c['latest_invalid']:
            attention.append(dict(kind='invalid', zone=name, text=f"{name}: latest received value is invalid — "
                                                                  f"{c['latest_invalid']['quality_note']}."))
    devices = []
    for d in store.devices():
        if dt.datetime.fromisoformat(d['registered_utc']) > as_of_utc and not d['last_seen_utc']:
            status, note = 'not yet active', 'registered after this time'
        else:
            seen = store.readings(until_utc=until, limit=1, device_key=d['device_id'])
            if not seen:
                status, note = 'attention', 'no reading received at or before this time'
            else:
                age = _age_minutes(as_of_utc, seen[0]['reading_utc'])
                if seen[0]['quality'] == 'invalid':
                    status, note = 'attention', f"latest value invalid ({seen[0]['quality_note']})"
                elif age > config.ENV_DEVICE_SILENT_MINUTES:
                    status, note = 'attention', (f'silent for {round(age)} min (limit '
                                                 f'{config.ENV_DEVICE_SILENT_MINUTES} min) — check power or Wi-Fi')
                else:
                    status, note = 'ok', f'last reading {round(age)} min ago'
        devices.append(dict(device=d, status=status, note=note))
        if status == 'attention':
            attention.append(dict(kind='sensor', zone=d['zone_code'],
                                  text=f"Sensor {d['device_id']} ({d['zone_code']}): {note}."))
    return dict(as_of=as_of_local, zones=out, attention=attention, devices=devices,
                synthetic_present=store.has_synthetic())


def worktype_context(conditions, worktype):
    """Context line for a work type (truck page, planner). Never used in calculations."""
    match = next((c for c in conditions['zones'] if c['zone']['worktype'] == int(worktype)), None)
    if match is None:
        return dict(status='no zone', text='No zone mapped to this work type')
    if match['reading'] is None:
        return dict(status='missing', text='No reading', zone=match['zone']['name'])
    r = match['reading']
    label = ' · SYNTHETIC' if r['data_label'] == 'SYNTHETIC' else ''
    quality = ' · suspect' if r['quality'] == 'suspect' else ''
    return dict(status=match['freshness'] + ('-suspect' if quality else ''), zone=match['zone']['name'],
                text=(f"{r['temperature_c']:.1f} °C · {r['humidity_pct']:.0f} %RH · {match['local_time'][-5:]} "
                      f"({match['freshness']}{quality}{label})"))


def trend_series(as_of_local: dt.datetime, hours_back: int = 6):
    """Valid/suspect readings per zone in the window before as-of, for zones with enough readings."""
    as_of_utc = local_to_utc(as_of_local)
    since = store.utc_text(as_of_utc - dt.timedelta(hours=hours_back))
    series = []
    for zone in store.zones():
        rows = sorted(store.readings(zone['zone_code'], until_utc=store.utc_text(as_of_utc), since_utc=since,
                                     qualities=('valid', 'suspect')), key=lambda r: r['reading_utc'])
        if len(rows) >= config.ENV_TREND_MIN_READINGS:
            series.append(dict(zone=zone['name'], synthetic=any(r['data_label'] == 'SYNTHETIC' for r in rows),
                               times=[utc_to_local(r['reading_utc']).strftime('%Y-%m-%d %H:%M') for r in rows],
                               temperature=[r['temperature_c'] for r in rows],
                               humidity=[r['humidity_pct'] for r in rows],
                               suspect=[r['quality'] == 'suspect' for r in rows]))
    return series


# ---------- labelled synthetic demonstration set ----------
SYNTHETIC_DEVICE = 'DEMO-SENSOR-01'


def load_synthetic(day_local: dt.date):
    """Deterministic SYNTHETIC demo readings that exercise every status (current, stale, missing,
    suspect, invalid, silent sensor). Values are a generic pattern, NOT SMD conditions."""
    zones = {z['worktype']: z['zone_code'] for z in store.zones() if z['worktype']}
    if store.device(SYNTHETIC_DEVICE) is None and 6 in zones:
        store.register_device(SYNTHETIC_DEVICE, zones[6], 'SYNTHETIC demo device (not real hardware)', 'SYNTHETIC')
    plan = {1: (16, 0, 20, 30, False), 2: (16, 0, 20, 30, False), 3: (16, 0, 17, 0, False),
            4: (16, 0, 18, 30, True), 6: (16, 0, 18, 0, False)}    # WT5 deliberately left missing
    stored = 0
    for wt, (h0, m0, h1, m1, step_at_end) in plan.items():
        if wt not in zones:
            continue
        t = dt.datetime.combine(day_local, dt.time(h0, m0))
        end = dt.datetime.combine(day_local, dt.time(h1, m1))
        i = 0
        while t <= end:
            temperature = round(24 + 3 * math.sin(i / 5) + wt * 0.3, 1)
            humidity = round(55 + 8 * math.cos(i / 6) - wt, 0)
            if step_at_end and t == end:
                temperature += 12          # demonstrates a 'suspect' step
            method = 'sensor' if wt == 6 else 'synthetic'
            when = local_to_utc(t)
            if wt == 6:
                outcome = record_reading(zones[wt], temperature, humidity, when, 'sensor',
                                         device_id=SYNTHETIC_DEVICE, data_label='SYNTHETIC')
            else:
                outcome = record_reading(zones[wt], temperature, humidity, when, method,
                                         recorded_by='SYNTHETIC demo')
            stored += outcome['status'] == 'stored'
            t += dt.timedelta(minutes=15)
            i += 1
    if 6 in zones:   # one invalid sensor value, then the demo device goes silent
        record_reading(zones[6], 999, 50, local_to_utc(dt.datetime.combine(day_local, dt.time(18, 5))), 'sensor',
                       device_id=SYNTHETIC_DEVICE, data_label='SYNTHETIC')
    return stored
