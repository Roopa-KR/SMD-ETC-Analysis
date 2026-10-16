"""Phase 2: is temperature / humidity ASSOCIATED with picking productivity? (v13, EXPERIMENTAL)

Never used in ETC, ready time, cutoff status or allocation. No penalty is applied anywhere.

Pairs, per work-area zone and clock hour:
    environment   mean of VALID, ACTUAL (manual or sensor) readings in that zone and hour
                  (synthetic and suspect/invalid readings are excluded from evidence)
    productivity  lines picked in that work type and hour ÷ distinct pickers who picked in it
                  ("lines per active picker-hour", from TI102C pick times; ACTUAL replay data)

A result is reported only when the evidence is sufficient:
    paired hours ≥ ENV_MIN_PAIRED_HOURS, distinct days ≥ ENV_MIN_DAYS,
    temperature spread ≥ ENV_MIN_TEMP_SPREAD_C.
Then: Spearman rank correlation with a 95 % bootstrap interval (2,000 resamples, fixed seed) and
the least-squares slope (lines per picker-hour per °C). Association, not causation: shift
pattern, workload mix and staffing change with the time of day just as temperature does.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

import config
from calculations import environment as env
from models import environment as store

UNAVAILABLE_INPUTS = [
    ('Recorded breaks / hydration breaks', 'Not available: LM005S1 has login sessions only, no break records.'),
    ('Truck cutoff outcomes', 'Departures are synthesized in the demo, so cutoff outcomes cannot validate an adjustment.'),
    ('Heat-stress measurement (WBGT)', 'Not collected. Temperature and humidity alone do not measure heat stress.'),
]


def productivity_by_hour(picks: pd.DataFrame, worktype_names: dict) -> pd.DataFrame:
    """Lines per active picker-hour per work type and local clock hour (from TI102C pick times)."""
    if picks.empty:
        return pd.DataFrame(columns=['worktype', 'hour', 'lines', 'pickers', 'lines_per_picker_hour'])
    times = pd.to_datetime(pd.to_numeric(picks['MOVED_TO_C_AT']), unit='D', origin='1899-12-30')
    data = pd.DataFrame(dict(worktype=picks['WORKTYPE'].astype(int).values, hour=times.dt.floor('h').values,
                             picker=picks['RESOURCENAME'].astype(str).values))
    grouped = data.groupby(['worktype', 'hour']).agg(lines=('picker', 'size'), pickers=('picker', 'nunique')).reset_index()
    grouped['lines_per_picker_hour'] = grouped.lines / grouped.pickers
    return grouped


def environment_by_hour() -> pd.DataFrame:
    rows = store.readings(qualities=('valid',), include_synthetic=False)
    if not rows:
        return pd.DataFrame(columns=['worktype', 'hour', 'temperature_c', 'humidity_pct', 'readings'])
    zones = {z['zone_code']: z['worktype'] for z in store.zones(active_only=False)}
    frame = pd.DataFrame(rows)
    frame['worktype'] = frame.zone_code.map(zones)
    frame = frame.dropna(subset=['worktype'])
    frame['hour'] = [pd.Timestamp(env.utc_to_local(t)).floor('h') for t in frame.reading_utc]
    return (frame.groupby([frame.worktype.astype(int), 'hour'])
            .agg(temperature_c=('temperature_c', 'mean'), humidity_pct=('humidity_pct', 'mean'),
                 readings=('id', 'size')).reset_index())


def _spearman(x, y):
    rx, ry = pd.Series(x).rank().values, pd.Series(y).rank().values
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float('nan')
    return float(np.corrcoef(rx, ry)[0, 1])


def associate(paired: pd.DataFrame, variable: str, seed: int = 13):
    x, y = paired[variable].values, paired['lines_per_picker_hour'].values
    rho = _spearman(x, y)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(2000):
        idx = rng.integers(0, len(x), len(x))
        value = _spearman(x[idx], y[idx])
        if np.isfinite(value):
            boot.append(value)
    low, high = (np.percentile(boot, [2.5, 97.5]) if boot else (float('nan'), float('nan')))
    slope = float(np.polyfit(x, y, 1)[0]) if np.std(x) > 0 else float('nan')
    includes_zero = not (low > 0 or high < 0)
    return dict(variable=variable, n=len(x), rho=rho, ci_low=float(low), ci_high=float(high), slope=slope,
                conclusion=('No reliable association detected (95 % interval includes zero).' if includes_zero else
                            'Association observed in this data — NOT evidence of cause; do not adjust ETC from this.'))


def analyse(picks: pd.DataFrame, worktype_names: dict, environment: pd.DataFrame | None = None):
    environment = environment_by_hour() if environment is None else environment
    productivity = productivity_by_hour(picks, worktype_names)
    paired = productivity.merge(environment, on=['worktype', 'hour'], how='inner')
    days = paired.hour.dt.date.nunique() if len(paired) else 0
    spread = float(paired.temperature_c.max() - paired.temperature_c.min()) if len(paired) else 0.0
    checks = [
        dict(item='Valid ACTUAL readings (manual or sensor)', value=int(environment.readings.sum()) if len(environment) else 0,
             required='> 0', ok=bool(len(environment))),
        dict(item='Hours with both readings and picking', value=len(paired),
             required=f'≥ {config.ENV_MIN_PAIRED_HOURS}', ok=len(paired) >= config.ENV_MIN_PAIRED_HOURS),
        dict(item='Distinct days', value=days, required=f'≥ {config.ENV_MIN_DAYS}', ok=days >= config.ENV_MIN_DAYS),
        dict(item='Temperature spread across paired hours', value=f'{spread:.1f} °C',
             required=f'≥ {config.ENV_MIN_TEMP_SPREAD_C:g} °C', ok=spread >= config.ENV_MIN_TEMP_SPREAD_C),
    ]
    sufficient = all(c['ok'] for c in checks)
    productivity_days = productivity.hour.dt.date.nunique() if len(productivity) else 0
    results = [associate(paired, 'temperature_c'), associate(paired, 'humidity_pct')] if sufficient else []
    # Per-work-type summary of the productivity side (CALCULATED from the replay pick times). It is a
    # trend only when it spans ENV_MIN_DAYS days; with one replay day it is a summary, not a trend.
    table = []
    for wt, group in productivity.groupby('worktype') if len(productivity) else []:
        table.append(dict(worktype=int(wt), name=worktype_names.get(int(wt), ''), hours=len(group),
                          lines=int(group.lines.sum()),
                          median=float(group.lines_per_picker_hour.median()),
                          low=float(group.lines_per_picker_hour.min()),
                          high=float(group.lines_per_picker_hour.max())))
    return dict(sufficient=sufficient, checks=checks, results=results, paired_hours=len(paired),
                productivity_table=table,
                productivity_is_trend=productivity_days >= config.ENV_MIN_DAYS,
                productivity_days=productivity_days, productivity_hours=len(productivity),
                unavailable=UNAVAILABLE_INPUTS,
                summary=('EXPERIMENTAL association analysis available below; not used in ETC.' if sufficient else
                         'Insufficient evidence: no conclusion about temperature, humidity and productivity can be '
                         'drawn yet, and no adjustment is applied. ' +
                         f'Picking data covers {productivity_days} day(s); environmental evidence must cover at least '
                         f'{config.ENV_MIN_DAYS} days with {config.ENV_MIN_PAIRED_HOURS}+ paired hours.'))
