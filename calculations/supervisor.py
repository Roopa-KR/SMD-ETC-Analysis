"""Supervisor allocation scenario calculations; historical workbook results remain untouched.

All durations use Excel serial-day timestamps. Every deadline includes the configured safety
buffer (SAFETY_BUFFER_MINUTES, default 10); per-truck loading minutes are persistent, but
allocations are NOT.
Conservative rates preserve the existing empirical lower-envelope logic.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from math import isfinite

import pandas as pd

from calculations.excel_io import serial_to_datetime
from calculations.pace import PACE_BASIS, area_rates, basis_label, operator_stats
from calculations.reallocation import _simulated_familiarity
from calculations.truck import EPS, le

try:  # configured in .env (SAFETY_BUFFER_MINUTES); 10 when the app config is not importable
    from config import SAFETY_BUFFER_MINUTES
except ImportError:  # pragma: no cover - calculations used outside the Flask project
    SAFETY_BUFFER_MINUTES = 10
try:  # v12 temporary operators (see calculations/temporary.py)
    from config import TEMP_OPERATOR_MAX, TEMP_OPERATOR_PACE_PCT
except ImportError:  # pragma: no cover
    TEMP_OPERATOR_PACE_PCT, TEMP_OPERATOR_MAX = 100, 10
# Fallback only. The configured default is the workbook's TRUCK_CONFIG.LOADING_MINUTES,
# read from inp.config by build_state(); per-truck overrides take precedence.
DEFAULT_LOADING_MINUTES = 30


def default_loading_minutes(inp) -> int:
    value = getattr(inp, 'config', {}).get('LOADING_MINUTES')
    try:
        return int(float(value)) if value is not None else DEFAULT_LOADING_MINUTES
    except (TypeError, ValueError):
        return DEFAULT_LOADING_MINUTES


def _positive(value):
    try:
        x = float(value)
        return x if isfinite(x) and x > 0 else None
    except (ValueError, TypeError):
        return None


def _time(serial):
    return serial_to_datetime(float(serial)) if serial is not None else None


CUTOFF_PASSED = 'PICK CUTOFF PASSED'
RISK_STATUSES = ('AT RISK', CUTOFF_PASSED, 'NO RATE')


def _level(ready, deadline, now, open_lines, cutoff=None):
    """Status of open work against the safety-buffer deadline and the pick cutoff (v14).

    ALL PICKED          no open lines
    PICK CUTOFF PASSED  the pick cutoff has passed with lines open, or the conservative ready time
                        is later than the pick cutoff (the truck cannot be ready in time at this pace)
    NO RATE             no measured pace, so no ready time
    AT RISK             ready after the safety-buffer deadline but not after the pick cutoff
    ON TIME             ready by the safety-buffer deadline
    ``cutoff`` None (legacy callers): the deadline is used as the cutoff.
    """
    cutoff = deadline if cutoff is None else cutoff
    if open_lines == 0:
        return 'ALL PICKED'
    if now >= cutoff - EPS or (ready is not None and ready > cutoff + EPS):
        return CUTOFF_PASSED
    if ready is None:
        return 'NO RATE'
    return 'ON TIME' if le(ready, deadline) else 'AT RISK'


def _single_row_result(row, point, low, now):
    """Same ETC calculation as the existing engine, re-evaluated at buffered deadline and pick cutoff."""
    if row['open'] == 0:
        return dict(point_ready=None, conservative_ready=None, status='ALL PICKED',
                    point_status='ALL PICKED', point_etc=None, conservative_etc=None)
    point_etc = row['ahead'] / point / 24 if point and point > 0 else None
    conservative_etc = row['ahead'] / low / 24 if low and low > 0 else None
    ready = now + point_etc if point_etc is not None else None
    late = now + conservative_etc if conservative_etc is not None else None
    cutoff = row.get('physical_cutoff')
    return dict(point_ready=ready, conservative_ready=late,
                status=_level(late, row['deadline'], now, row['open'], cutoff),
                point_status=_level(ready, row['deadline'], now, row['open'], cutoff),
                point_etc=point_etc, conservative_etc=conservative_etc)


def _active_snapshot(inp, snapshot, basis=None):
    """Current active operators plus trailing-30-day operator pace (v11: picking-time basis).

    LM005S1 repeats *cumulative* time in consecutive snapshots: use the maximum
    recorded duration per distinct operator/worktype/day/segment start, never SUM
    all 18 snapshot copies. Current day's evidence stops at the selected snapshot.
    Pace basis: calculations/pace.py (PACE_BASIS 'picking_time' or 'logged_time').
    """
    t = float(inp.snapshots.loc[inp.snapshots.SNAPSHOT_NO == snapshot, 'T'].iloc[0])
    lm = inp.lm[inp.lm.SNAPSHOT_NO == snapshot]
    active = lm[lm.WIPIND == 'Y'].sort_values('STARTDATETIME').drop_duplicates('RESOURCENAME', keep='last')
    people = {str(r.RESOURCENAME): int(r.WORKTYPE) for r in active.itertuples()}
    end = int(t)                 # serial-day calendar date
    start = end - 29            # current day + preceding 29 calendar days
    # SQLite's cached LM005S1 omits TRANSACTIONDATE. Use the stored segment-start
    # calendar day in that case, not a fabricated month of records.
    day = (pd.to_numeric(inp.lm['TRANSACTIONDATE'], errors='coerce')
           if 'TRANSACTIONDATE' in inp.lm else
           pd.to_numeric(inp.lm['STARTDATETIME'], errors='coerce').floordiv(1))
    history = inp.lm[(day >= start) & (day <= end) &
                     ((day < end) | (inp.lm.SNAPSHOT_NO == snapshot))].copy()
    history['EVIDENCE_DAY'] = day.loc[history.index]
    done = inp.tc[(inp.tc.TRANSACTIONDATE >= start) & (inp.tc.TRANSACTIONDATE <= end)
                  & (inp.tc.MOVED_TO_C_AT <= t + EPS)]
    stats = operator_stats(inp, t, lm, history, done, people, basis=basis)
    return t, people, stats


def pace_window_info(inp, now, basis=None):
    """Actual calendar-day coverage in the trailing 30-day window, NOT 30 observations by default."""
    end = int(now)
    start = end - 29
    ts = pd.to_numeric(inp.tc['TRANSACTIONDATE'], errors='coerce').dropna()
    dates = {int(float(v)) for v in ts if start <= float(v) <= end}
    unique_days = [serial_to_datetime(float(v)).date().isoformat() for v in sorted(dates)]
    complete = len(unique_days) >= 30
    return dict(days=unique_days, observed_days=len(unique_days), rolling_days=30,
                monthly_qualified=complete,
                basis=basis_label(basis),
                label=('Observed trailing-30-day pace' if complete else
                       f'Observed pace from {len(unique_days)} recorded day(s) in trailing-30-day window; NOT reliable monthly'))


def temporary_pace(baseline, rows, dest, pct=None):
    """Assumed pace of one temporary operator in work type ``dest`` (SYNTHESIZED ASSUMPTION).

    pace     = pct % x the work type's measured per-person rate at this snapshot
    cautious = min(pace, slowest measured operator pace in the work type), i.e. exactly how the
               conservative rate already credits any added operator (_add_destination).
    None when the work type has no measured per-person rate (fail closed: no estimate).
    """
    pct = TEMP_OPERATOR_PACE_PCT if pct is None else pct
    dest = int(dest)
    per_person = _positive((baseline.get(dest) or {}).get('per_person'))
    floor = min((r.get('empirical_low', float('inf')) for r in rows if r['worktype'] == dest),
                default=float('inf'))
    pace = per_person * pct / 100 if per_person else None
    cautious = (min(pace, floor) if isfinite(floor) else pace) if pace else None
    return dict(pace=pace, cautious=cautious, per_person=per_person, pct=pct,
                slowest=floor if isfinite(floor) else None)


def add_temporaries(rates, rows, dest, count, pace):
    """Return a copy of ``rates`` with ``count`` temporary operators added to work type ``dest``."""
    out = {w: r.copy() for w, r in rates.items()}
    for _ in range(int(count)):
        _add_destination(out[int(dest)], int(dest), pace, rows)
    return out


def _snapshot_times(inp):
    return {int(r.SNAPSHOT_NO): float(r.T) for r in inp.snapshots.itertuples()}


def _logged_in_area(inp, snapshot_no, name):
    """Work type the operator was logged in to (WIPIND = Y) at a snapshot, or None."""
    lm = inp.lm[(inp.lm.SNAPSHOT_NO == snapshot_no) & (inp.lm.RESOURCENAME == name) & (inp.lm.WIPIND == 'Y')]
    return int(lm.sort_values('STARTDATETIME').WORKTYPE.iloc[-1]) if len(lm) else None


def _heads(inp, snapshot_no, area, excluding=()):
    lm = inp.lm[(inp.lm.SNAPSHOT_NO == snapshot_no) & (inp.lm.WIPIND == 'Y')]
    latest = lm.sort_values('STARTDATETIME').drop_duplicates('RESOURCENAME', keep='last')
    return int(((latest.WORKTYPE == area) & ~latest.RESOURCENAME.isin(list(excluding))).sum())


def _line_owners(inp, now):
    """TI102ID -> (truck the line belongs to at time ``now``, release time)."""
    lines = inp.line_map[['TI102ID', 'WHORDERID']].merge(
        inp.orders[['WHORDERID', 'SHIPMENTID', 'ORIGINAL_SHIPMENTID', 'MOVED_AT', 'RELEASE_TIME']],
        on='WHORDERID', how='left')
    moved = pd.to_numeric(lines.MOVED_AT, errors='coerce').fillna(1e9)
    ship = lines.SHIPMENTID.where(now >= moved - EPS, lines.ORIGINAL_SHIPMENTID)
    return dict(zip(lines.TI102ID.astype('int64'), ship))


def scenario_progress(inp, snapshot, now, rows, baseline, committed=(), temporaries=()):
    """v14 scenario replay: what a confirmed allocation changes at LATER snapshots of the replay.

    The replay's open lines are history, recorded without the allocation. For every snapshot after the
    allocation was confirmed (start_snapshot), open lines are adjusted, conservatively, by:

      destination gain  = cautious pace x hours the added operator was logged in since the allocation
                          (cautious pace = min(destination pace, slowest measured pace in that area),
                          the same credit the ETC gives an added operator; temporaries: count x
                          cautious temporary pace x hours). The gained lines are taken from the
                          destination's open lines in priority order (earliest deadline first).
      source loss       = lines the moved operator actually picked in any other area after the
                          allocation, MINUS the spare capacity of the operators who stayed there
                          (their slowest pace x heads x hours - what they actually picked); the rest
                          is treated as still open, lowest priority first.

    No status is set here: the adjusted open lines go through the normal ETC and status rules, so a
    truck shows ALL PICKED only when its adjusted open lines reach zero. Mutates ``rows`` (open,
    history_open, scenario_picked, scenario_reopened) and returns explanation lines.
    """
    times = _snapshot_times(inp)
    if snapshot not in times:
        return []
    notes, gains = [], defaultdict(float)
    index = {(r['shipment'], r['worktype']): r for r in rows}
    for r in rows:
        r.setdefault('history_open', r['open'])
        r.setdefault('scenario_picked', 0)
        r.setdefault('scenario_reopened', 0)

    def floor(area):
        return min((r.get('empirical_low', float('inf')) for r in rows if r['worktype'] == area),
                   default=float('inf'))

    reopen = defaultdict(list)
    for move in committed:
        s0 = int(move['start_snapshot'])
        if snapshot <= s0 or s0 not in times:
            continue
        name, dest = move['operator'], int(move['dest'])
        pace = _positive(move.get('destination_pace'))
        if pace is None:
            continue
        slowest = floor(dest)
        credit = min(pace, slowest) if isfinite(slowest) else pace
        hours = 0.0
        for k in range(s0, snapshot):
            if k + 1 not in times:
                continue
            area = _logged_in_area(inp, k, name)
            if area is not None and area != dest:
                hours += (times[k + 1] - times[k]) * 24
        gains[dest] += credit * hours
        notes.append(f"{name}: {credit:.1f} lines/h credited in WT {dest} for {hours:.2f} h since "
                     f"{serial_to_datetime(times[s0]):%H:%M} = {credit * hours:.1f} lines")
        picks = inp.tc[(inp.tc.RESOURCENAME == name) & (inp.tc.MOVED_TO_C_AT > times[s0] + EPS)
                       & (inp.tc.MOVED_TO_C_AT <= now + EPS) & (inp.tc.WORKTYPE != dest)]
        for p in picks.itertuples():
            reopen[int(p.WORKTYPE)].append((name, int(p.TI102ID), float(p.MOVED_TO_C_AT), s0))
    for alloc in temporaries:
        s0 = int(alloc['start_snapshot'])
        if snapshot <= s0 or s0 not in times:
            continue
        dest = int(alloc['dest'])
        assumed = temporary_pace(baseline, rows, dest, alloc.get('pace_pct'))
        if not assumed['cautious']:
            continue
        hours = (now - times[s0]) * 24
        lines = int(alloc['count']) * assumed['cautious'] * hours
        gains[dest] += lines
        notes.append(f"{alloc['count']} temporary operator(s): {assumed['cautious']:.1f} lines/h each in "
                     f"WT {dest} for {hours:.2f} h = {lines:.1f} lines")
    owners = _line_owners(inp, now) if reopen else {}
    for area, picked in reopen.items():
        movers = {n for n, *_ in picked}
        t0 = min(times[s0] for *_, s0 in picked)
        others = inp.tc[(inp.tc.WORKTYPE == area) & (inp.tc.MOVED_TO_C_AT > t0 + EPS)
                        & (inp.tc.MOVED_TO_C_AT <= now + EPS) & ~inp.tc.RESOURCENAME.isin(list(movers))]
        slowest = floor(area)
        capacity = 0.0
        if isfinite(slowest):
            for k, t in sorted(times.items()):
                if t + EPS < t0 or t >= now - EPS or k + 1 not in times:
                    continue
                capacity += slowest * _heads(inp, k, area, movers) * (times[k + 1] - t) * 24
        spare = max(0, int(capacity - len(others)))
        backlog = max(0, len(picked) - spare)
        priority = sorted(picked, key=lambda p: (index.get((owners.get(p[1]), area), {}).get('deadline', 9e9), p[2]))
        for name, line_id, _, _ in priority[len(priority) - backlog:] if backlog else []:
            row = index.get((owners.get(line_id), area))
            if row is not None:
                row['open'] += 1
                row['scenario_reopened'] += 1
        notes.append(f"WT {area}: {len(picked)} line(s) picked by {', '.join(sorted(movers))} after the move; "
                     f"remaining operators had spare capacity for {spare}; {backlog} treated as still open")
    for dest, gained in gains.items():
        remaining = int(gained + 1e-9)
        for row in sorted((r for r in rows if r['worktype'] == dest and r['open'] > 0),
                          key=lambda r: (r['deadline'], r['shipment'])):
            take = min(row['open'], remaining)
            row['open'] -= take
            row['scenario_picked'] += take
            remaining -= take
            if remaining <= 0:
                break
    return notes


def build_state(inp, base_worktypes, trucks, snapshot, loading_overrides, committed=(),
                buffer_minutes=None, pace_basis=None, temporaries=()):
    """Recalculate all truck/worktype cutoffs and snapshot staffing as a temporary scenario.

    Existing team rate is authoritative. Committed moves subtract the person's source
    pace and add destination pace, once per operator; no baseline results are mutated.

    pick cutoff (physical_cutoff) = departure - loading time (per-truck override, else configured default)
    safety buffer deadline (deadline) = pick cutoff - configured safety buffer
    """
    basis = pace_basis or PACE_BASIS
    now, active, stats = _active_snapshot(inp, int(snapshot), basis)
    names = inp.worktype_names
    buffer = SAFETY_BUFFER_MINUTES if buffer_minutes is None else int(buffer_minutes)
    default_load = default_loading_minutes(inp)
    by_ship = {t.shipment_id: t for t in trucks}
    deadlines = {}
    for shipment_id, truck in by_ship.items():
        load = int(loading_overrides.get(shipment_id, default_load))
        departure = (truck.departure - pd.Timestamp('1899-12-30')).total_seconds() / 86400
        deadlines[shipment_id] = dict(departure=departure, loading_minutes=load,
                                      physical_cutoff=departure-load/1440,
                                      deadline=departure-(load+buffer)/1440)
    if basis == 'logged_time':   # Excel-equation rates exactly as stored by the engine
        baseline = {int(w): dict(rate=_positive(rows[0]['ACTUALRATELINES']),
                                 low=_positive(rows[0]['RATE_LOW']),
                                 resources=int(rows[0]['RESOURCES']),
                                 per_person=_positive(rows[0]['PER_PERSON_RATE']))
                    for w, rows in ((wt, [r for r in base_worktypes if int(r['WORKTYPE']) == wt])
                                    for wt in sorted(set(int(r['WORKTYPE']) for r in base_worktypes)))}
    else:   # v11 default: same structure, picking-time pace (calculations/pace.py)
        heads = {int(r['WORKTYPE']): int(r['RESOURCES']) for r in base_worktypes}
        baseline = area_rates(stats, heads)
    rows = []
    for r in base_worktypes:
        ship, wt = r['SHIPMENTID'], int(r['WORKTYPE'])
        rows.append(dict(shipment=ship, worktype=wt, name=names.get(wt, f'WT {wt}'),
                         open=int(r['OPEN_LINES']), ahead=0, deadline=deadlines[ship]['deadline'],
                         loading_minutes=deadlines[ship]['loading_minutes'],
                         physical_cutoff=deadlines[ship]['physical_cutoff'],
                         resources=baseline[wt]['resources']))
    # Observed per-operator pace floor for the existing conservative envelope.
    for row in rows:
        measured = [d["pace"] for (name, wt), d in stats.items()
                    if wt == row["worktype"] and _positive(d.get("pace"))]
        row["empirical_low"] = min(measured) if measured else float("inf")
    # v14: confirmed allocations change the open lines of LATER snapshots (scenario replay).
    scenario_notes = scenario_progress(inp, int(snapshot), now, rows, baseline, committed, temporaries)
    # All trucks with earlier OR EQUAL planned cutoff count as work ahead.
    open_index = {(r['shipment'], r['worktype']): r['open'] for r in rows}
    for row in rows:
        row['ahead'] = sum(open_index.get((s, row['worktype']), 0) for s, d in deadlines.items()
                           if le(d['deadline'], row['deadline']))
    committed_applied = []
    skipped = []
    rates = {w: v.copy() for w, v in baseline.items()}
    used = set()
    for move in sorted(committed, key=lambda m: int(m['start_snapshot'])):
        name, source, dest = move['operator'], int(move['source']), int(move['dest'])
        if snapshot < int(move['start_snapshot']):
            continue
        # The operator works in ``dest`` from the confirmed snapshot on. At a later snapshot the replay
        # may show them logged out (shift over: no contribution) or in another area than the original
        # source (history without the move): their pace is then taken from that area instead.
        current = active.get(name)
        if name in used or current is None or current == dest:
            skipped.append(name)
            continue
        source = current
        # pace removed from the area they are recorded in now; if they have no picks there yet
        # (just arrived in the replay), their measured pace in the original source area is used
        src = (_positive(stats.get((name, source), {}).get('pace'))
               or _positive(stats.get((name, int(move['source'])), {}).get('pace')))
        dst = _positive(move.get('destination_pace'))
        if src is None or dst is None:
            skipped.append(name)
            continue
        # The measured source pace can change in later snapshots. Destination pace
        # is the explicitly accepted (possibly synthetic) scenario contribution.
        outcome = _adjust_source(rates, rows, source, src, name, now)
        if outcome is None:
            skipped.append(name)
            continue
        rates[source] = outcome
        _add_destination(rates[dest], dest, dst, rows)
        committed_applied.append(move)
        used.add(name)
    # v12: confirmed temporary operators (session only), added after confirmed reallocations.
    # Their pace is re-evaluated at every snapshot from that snapshot's per-person rate.
    temporaries_applied, temporaries_skipped = [], []
    for alloc in sorted(temporaries, key=lambda a: int(a['start_snapshot'])):
        if snapshot < int(alloc['start_snapshot']):
            continue
        dest, count = int(alloc['dest']), int(alloc['count'])
        assumed = temporary_pace(baseline, rows, dest, alloc.get('pace_pct'))
        if count <= 0 or not assumed['pace']:
            temporaries_skipped.append(alloc)
            continue
        for _ in range(count):
            _add_destination(rates[dest], dest, assumed['pace'], rows)
        temporaries_applied.append(dict(alloc, pace=assumed['pace'], cautious_pace=assumed['cautious']))
    for row in rows:
        row.update(_single_row_result(row, rates[row['worktype']]['rate'],
                                      rates[row['worktype']]['low'], now))
        row.update(rate=rates[row['worktype']]['rate'], low_rate=rates[row['worktype']]['low'],
                   resources=rates[row['worktype']]['resources'])
    truck_view = []
    for ship, truck in by_ship.items():
        ours = [r for r in rows if r['shipment'] == ship]
        active_rows = [r for r in ours if r['open']]
        scenario_open = sum(r['open'] for r in ours)
        history_open = sum(r.get('history_open', r['open']) for r in ours)
        passed = now >= deadlines[ship]['physical_cutoff'] - EPS
        status = ('ALL PICKED' if not active_rows else
                  CUTOFF_PASSED if passed or any(r['status'] == CUTOFF_PASSED for r in active_rows) else
                  'NO RATE' if any(r['conservative_ready'] is None for r in active_rows) else
                  'AT RISK' if any(r['status'] != 'ON TIME' for r in active_rows) else 'ON TIME')
        late_rows = [r for r in active_rows if r['conservative_ready'] is not None]
        finish = max((r['conservative_ready'] for r in late_rows), default=None) if status != 'NO RATE' else None
        truck_view.append(dict(shipment=ship, status=status, snapshot=int(snapshot),
                               departure=deadlines[ship]['departure'],
                               loading_minutes=deadlines[ship]['loading_minutes'], buffer_minutes=buffer,
                               cutoff=deadlines[ship]['physical_cutoff'], deadline=deadlines[ship]['deadline'],
                               conservative_ready=finish, open_lines=scenario_open,
                               history_open_lines=history_open,
                               scenario_adjusted=scenario_open != history_open,
                               cutoff_reached=passed,
                               bottleneck=(max(late_rows, key=lambda r: r['conservative_ready'])['worktype']
                                           if late_rows else None),
                               slack_minutes=(round((deadlines[ship]['deadline']-finish)*1440, 1)
                                              if finish is not None else None)))
    return dict(snapshot=int(snapshot), now=now, active=active, stats=stats,
                baseline=baseline, rates=rates, rows=rows, trucks=truck_view,
                names=names, applied=committed_applied, skipped=skipped,
                temporaries_applied=temporaries_applied, temporaries_skipped=temporaries_skipped,
                scenario_notes=scenario_notes,
                buffer_minutes=buffer, default_loading_minutes=default_load, pace_basis=basis,
                pace_info=pace_window_info(inp, now, basis))


def _source_safe(rows, source, point, low, now):
    for row in rows:
        if row['worktype'] == source and row['open']:
            if _single_row_result(row, point, low, now)['status'] != 'ON TIME':
                return False
    return True


def _adjust_source(rates, rows, source, pace, name, now):
    """Preserve existing conservative envelope and source-work safety checks."""
    original = rates[source]
    new = original.copy()
    new['resources'] -= 1
    has_open = any(r['worktype'] == source and r['open'] for r in rows)
    if original['rate'] is None or new['resources'] < 0:
        return None
    # Subtract operator's source productivity even when this source has zero
    # currently open lines. Preserve the resource/rate conservation invariant.
    new['rate'] = max(0., original['rate'] - pace)
    floor = original['low'] / original['resources'] if original['low'] and original['resources'] else None
    new['low'] = min(new['rate'], new['resources']*floor) if floor else None
    if has_open:
        if not new['rate'] or new['rate'] <= 0 or not new['low'] or new['low'] <= 0:
            return None
        if not _source_safe(rows, source, new['rate'], new['low'], now):
            return None
    return new


def _add_destination(rate, dest, pace, rows):
    empirical_floor = min((r.get('empirical_low', float('inf')) for r in rows
                           if r['worktype'] == dest), default=float('inf'))
    low_pace = min(pace, empirical_floor) if isfinite(empirical_floor) else pace
    rate['rate'] = (rate['rate'] or 0)+pace
    rate['low'] = (rate['low'] or 0)+low_pace
    rate['resources'] += 1


def candidates(inp, state, destination, preview=()):
    """Experience-first; ranks even UNSAFE familiar operators by individual destination pace."""
    dest = int(destination)
    now = state['now']
    rates = {w: r.copy() for w, r in state['rates'].items()}
    used = {m['operator'] for m in state['applied']}
    result = []
    simulated = _simulated_familiarity(inp)
    for name, source in sorted(state['active'].items()):
        if source == dest or name in used:
            continue
        actual = state['stats'].get((name, dest), {})
        src = state['stats'].get((name, source), {})
        if _positive(actual.get('pace')):
            pace, evidence = float(actual['pace']), state['pace_info']['label']+' (target worktype)'
            experience = f"{actual['lines']} observed completed lines"
        elif simulated.get((name, dest)):
            per_person = state['baseline'][dest]['per_person']
            src_pace = _positive(src.get('pace'))
            pace = min(src_pace, per_person) if src_pace and per_person else None
            evidence = 'SYNTHETIC: min(observed source pace, destination team per-person rate)'
            experience = f"SIMULATED experience: {simulated[(name, dest)]}"
        else:
            continue  # No documented experience: never eligible for display.
        source_pace = _positive(src.get('pace'))
        safe = source_pace is not None and pace is not None and _adjust_source(
            rates, state['rows'], source, source_pace, name, now) is not None
        reason = ('Source work remains conservatively on time' if safe else
                  'UNSAFE: removing this operator breaches source cutoff, or pace evidence is unavailable')
        if name in preview:
            safe = True  # already accepted earlier in this sequential preview
            reason = 'Already included in the validated preview'
        result.append(dict(operator=name, source=source, dest=dest, pace=pace,
                           source_pace=source_pace, experience=experience, evidence=evidence,
                           safe=safe, reason=reason, selected=name in preview,
                           availability=('Active — transferable' if safe else 'Active — not transferable'),
                           source_open_lines=sum(r['open'] for r in state['rows'] if r['worktype']==source)))
    return sorted(result, key=lambda x: (not x['safe'], x['pace'] is None, -(x['pace'] or 0), x['operator']))


def eligible_candidates(inp, state, destination, preview=()):
    """Return all *experienced* operators, including synthetic familiarity and unsafe moves.

    The original source-safety check is authoritative. Unavailable/unsafe workers stay
    visible for supervisor diagnosis but can never be selected or confirmed.
    """
    ranked = candidates(inp, state, destination, preview)
    return dict(eligible=[r for r in ranked if r['safe']],
                unsafe=[r for r in ranked if not r['safe']],
                all_experienced=ranked,
                excluded=[dict(operator=name,reason='No target worktype experience')
                          for name,src in state['active'].items()
                          if src!=int(destination) and name not in {r['operator'] for r in ranked}])


def truck_projection(state, rates, shipment):
    """Always evaluate ALL open worktypes before declaring a truck safe."""
    rows = [r for r in state['rows'] if r['shipment'] == shipment and r['open']]
    if not rows:
        return dict(status='ALL PICKED', finish=None, deadline=next(
            (t['deadline'] for t in state['trucks'] if t['shipment']==shipment), None), rows=[])
    ev = [dict(worktype=r['worktype'], deadline=r['deadline'],
               **_single_row_result(r, rates[r['worktype']]['rate'], rates[r['worktype']]['low'], state['now']))
          for r in rows]
    status = (CUTOFF_PASSED if any(v['status']==CUTOFF_PASSED for v in ev) else
              'NO RATE' if any(v['status']=='NO RATE' for v in ev) else
              'AT RISK' if any(v['status']!='ON TIME' for v in ev) else 'ON TIME')
    ready_times = [v['conservative_ready'] for v in ev if v['conservative_ready'] is not None]
    finish = max(ready_times) if status != 'NO RATE' and ready_times else None
    return dict(status=status, finish=finish, deadline=rows[0]['deadline'], rows=ev)


def recommend_minimum(inp, state, destination, shipment, selected=()):
    """Exact minimum feasible further operators from the active trained roster.

    Test every smaller subset against *conservative* target and source cutoffs.
    Fail closed (no fabricated recommendation) if no subset can meet the deadline.
    Limited to the actual finite active workforce, never generates operators.
    """
    from itertools import combinations
    dest=int(destination)
    target=next((r for r in state['rows'] if r['shipment']==shipment and r['worktype']==dest and r['open']),None)
    if target is None:
        return dict(required=0, additional=0, operators=[], possible=True,
                    rate_needed=0, rate_available=0, rate_gap=0,
                    explanation='No open lines in this worktype for this truck.')
    now=state['now']
    hours=max(0.,(target['deadline']-now)*24)
    pace_needed=target['ahead']/hours if hours>0 else None
    try:
        current=preview_state(inp,state,dest,list(selected),shipment=shipment)
    except ValueError as e:
        return dict(required=None,additional=None,operators=[],possible=False,
                    rate_needed=pace_needed,rate_available=None,rate_gap=None,explanation=str(e))
    low=current['rates'][dest]['low'] or 0
    gap=max(0.,pace_needed-low) if pace_needed is not None else None
    evaluation=truck_projection(state,current['rates'],shipment)
    target_status=next((r['status'] for r in evaluation['rows'] if r['worktype']==dest),'ALL PICKED')
    explanation=(f"{target['ahead']} priority lines ÷ {hours:.2f} available hours = "
                 f"{pace_needed:.1f} conservative lines/hour required; "
                 f"current rate {low:.1f}; shortfall {gap:.1f} lines/hour." if pace_needed is not None else
                 'Buffered picking deadline has passed; staffing cannot recover this already missed cutoff.')
    if target_status=='ON TIME':
        return dict(required=0,additional=0,operators=[],possible=True,rate_needed=pace_needed,
                    rate_available=low,rate_gap=gap,truck_status=evaluation['status'],explanation=explanation)
    if hours<=0:
        return dict(required=None,additional=None,operators=[],possible=False,rate_needed=None,
                    rate_available=low,rate_gap=None,truck_status=evaluation['status'],explanation=explanation)
    available=[c for c in candidates(inp,state,dest,selected)
               if c['operator'] not in selected and c['safe'] and c['pace']]
    # Lowest count wins. Among equally sized safe combinations prefer maximum proven
    # conservative slack, followed by the higher sum of destination pace.
    for n in range(1,len(available)+1):
        passing=[]
        for group in combinations(available,n):
            names=list(selected)+[c['operator'] for c in group]
            try:
                trial=preview_state(inp,state,dest,names,shipment=shipment)
            except ValueError:
                continue
            ship_ev=truck_projection(state,trial['rates'],shipment)
            target_ev=next((r for r in ship_ev['rows'] if r['worktype']==dest),None)
            if target_ev and target_ev['status']=='ON TIME':
                slack=(target_ev['deadline']-target_ev['conservative_ready'])*1440
                passing.append((slack,sum(c['pace'] for c in group),[c['operator'] for c in group],ship_ev))
        if passing:
            _,_,chosen,ship_ev=max(passing,key=lambda v:(v[0],v[1]))
            return dict(required=n,additional=n,operators=chosen,possible=True,rate_needed=pace_needed,
                        rate_available=low,rate_gap=gap,truck_status=ship_ev['status'],explanation=explanation)
    return dict(required=None,additional=None,operators=[],possible=False,rate_needed=pace_needed,
                rate_available=low,rate_gap=gap,truck_status=evaluation['status'],
                explanation=explanation+' No combination of currently safe, experienced operators can close the gap. '
                            'Review another worktype, staffing availability, or a legitimate departure/loading adjustment.')


def preview_state(inp, state, destination, selected, shipment=None):
    """Recalculate selected moves sequentially; this pure preview never writes to disk."""
    dest = int(destination)
    rates = {w: r.copy() for w, r in state['rates'].items()}
    baseline = [r for r in state['rows'] if r['worktype'] == dest and r['open']]
    steps = []
    used = set()
    target_rows = [r for r in baseline if r['shipment']==shipment] if shipment else baseline
    for name in selected:
        if name in used:
            raise ValueError('An operator cannot be selected twice.')
        # Re-evaluate source safety against *cumulative* simulated moves.
        temp = dict(state, rates=rates)
        choices = {x['operator']: x for x in candidates(inp, temp, dest)}
        chosen = choices.get(name)
        if chosen is None or not chosen['safe'] or chosen['pace'] is None:
            raise ValueError(f'{name} is no longer safe/eligible for this move.')
        source = chosen['source']
        source_rows = [r for r in state['rows'] if r['worktype'] == source and r['open']]
        source_before = priority_result(source_rows, rates[source], state['now'])
        adjusted = _adjust_source(rates, state['rows'], source, chosen['source_pace'], name, state['now'])
        if adjusted is None:
            raise ValueError(f'{name} fails conservative source-safety check.')
        rates[source] = adjusted
        _add_destination(rates[dest], dest, chosen['pace'], state['rows'])
        used.add(name)
        steps.append(dict(**chosen, projected=priority_result(target_rows, rates[dest], state['now']),
                          target_truck=truck_projection(state, rates, shipment) if shipment else None,
                          source_before=source_before,
                          source_after=priority_result(source_rows, rates[source], state['now'])))
    return dict(steps=steps, original=priority_result(target_rows, state['rates'][dest], state['now']),
                projected=priority_result(target_rows, rates[dest], state['now']),
                truck_before=truck_projection(state, state['rates'], shipment) if shipment else None,
                truck_after=truck_projection(state, rates, shipment) if shipment else None,
                aggregate_before=_aggregate_result(state['rows'], state['rates'], state['now']),
                aggregate_after=_aggregate_result(state['rows'], rates, state['now']),
                rate_after=rates[dest], rates=rates, selected=list(selected))


def _aggregate_result(rows, rates, now):
    """Scenario-wide work-type risk count and sum of conservative minutes late."""
    evaluated = [_single_row_result(row, rates[row['worktype']]['rate'], rates[row['worktype']]['low'], now)
                 for row in rows if row['open']]
    late = [ev for ev in evaluated if ev['status'] in ('AT RISK', CUTOFF_PASSED)]
    delay = sum(max(0, (ev['conservative_ready'] - row['deadline']) * 1440)
                for row, ev in zip((r for r in rows if r['open']), evaluated)
                if ev['conservative_ready'] is not None)
    return dict(open_worktypes=len(evaluated), at_risk=len(late), on_time=sum(ev['status'] == 'ON TIME' for ev in evaluated),
                total_delay_minutes=round(delay, 1))


def priority_result(rows, team, now):
    if not rows:
        return dict(status='ALL PICKED', finish=None, deadline=None, rows=[])
    evaluated = []
    for row in rows:
        ev = _single_row_result(row, team['rate'], team['low'], now)
        evaluated.append(dict(shipment=row['shipment'], ahead=row['ahead'], open=row['open'],
                              status=ev['status'], finish=ev['conservative_ready'],
                              point_finish=ev['point_ready'], deadline=row['deadline']))
    priority = min(evaluated, key=lambda r: (r['deadline'], r['shipment']))
    return dict(status=('ON TIME' if all(r['status'] == 'ON TIME' for r in evaluated) else
                        CUTOFF_PASSED if any(r['status'] == CUTOFF_PASSED for r in evaluated) else
                        'NO RATE' if any(r['status'] == 'NO RATE' for r in evaluated) else 'AT RISK'),
                finish=priority['finish'], deadline=priority['deadline'], rows=evaluated)


def assignment_risks(inp, state):
    """Assignment flags inherit their shipment-worktype risk. NO independent task ETC."""
    snap = state['snapshot']
    ti = inp.ti[(inp.ti.SNAPSHOT_NO == snap) & (inp.ti.OPENQTY > 0)][['TI102ID', 'WORKTYPE']]
    lm = inp.line_map[['TI102ID','WHORDERID','ASSIGNMENTID']]
    orders = inp.orders[['WHORDERID','SHIPMENTID','ORIGINAL_SHIPMENTID','MOVED_AT']]
    data = ti.merge(lm, on='TI102ID', how='left').merge(orders, on='WHORDERID', how='left')
    data['shipment'] = data.SHIPMENTID.where(data.MOVED_AT.notna() & (data.MOVED_AT <= state['now']+EPS),
                                            data.ORIGINAL_SHIPMENTID)
    risk = {(r['shipment'],r['worktype']):r for r in state['rows']}
    grouped = data.groupby(['shipment','WORKTYPE','ASSIGNMENTID'], dropna=False).size()
    results = []
    for (ship, wt, assignment), count in grouped.items():
        matched = risk.get((ship, int(wt)))
        if not matched:
            continue
        results.append(dict(shipment=ship, worktype=int(wt), assignment=str(assignment),
                            lines=int(count), status=matched['status'],
                            reason=f"Inherits {ship} WT {wt} conservative completion risk; "
                                   f"{matched['ahead']} priority lines ahead; buffered cutoff "
                                   f"{_time(matched['deadline']):%H:%M}",
                            deadline=matched['deadline']))
    return results


def explain_status(state, shipment):
    """One plain sentence explaining a truck's status at this snapshot, from the same numbers (v14)."""
    truck = next((t for t in state['trucks'] if t['shipment'] == shipment), None)
    if truck is None:
        return ''
    clock = lambda v: serial_to_datetime(v).strftime('%H:%M') if v is not None else '—'
    rows = [r for r in state['rows'] if r['shipment'] == shipment]
    open_rows = [r for r in rows if r['open']]
    gained = sum(r.get('scenario_picked', 0) for r in rows)
    reopened = sum(r.get('scenario_reopened', 0) for r in rows)
    extra = ''
    if gained or reopened:
        parts = []
        if gained:
            parts.append(f'{gained} line(s) picked by the allocated capacity')
        if reopened:
            parts.append(f'{reopened} line(s) reopened in the source area')
        extra = ' Scenario: ' + ', '.join(parts) + ' since the allocation.'
    status = truck['status']
    if status == 'ALL PICKED':
        return 'All released lines are picked.' + extra
    if status == CUTOFF_PASSED and truck.get('cutoff_reached'):
        return (f"Pick cutoff {clock(truck['cutoff'])} has passed with {truck['open_lines']} line(s) still open."
                + extra)
    timed = [r for r in open_rows if r.get('conservative_ready') is not None]
    if status == 'NO RATE' or not timed:
        areas = ', '.join(f"WT {r['worktype']}" for r in open_rows if r.get('conservative_ready') is None)
        return f'No measured picking pace for open work in {areas or "an open area"}, so no ready time.' + extra
    b = max(timed, key=lambda r: r['conservative_ready'])
    basis = (f"bottleneck WT {b['worktype']} {b['name']}: {b['ahead']} line(s) ahead ÷ {b['low_rate']:.1f} lines/h "
             f"cautious rate with {b['resources']} picker(s)")
    ready = clock(truck['conservative_ready'])
    if status == CUTOFF_PASSED:
        return (f"Conservative ready {ready} is after the {clock(truck['cutoff'])} pick cutoff ({basis})." + extra)
    if status == 'AT RISK':
        return (f"Conservative ready {ready} is after the {clock(truck['deadline'])} safety-buffer deadline but not "
                f"after the {clock(truck['cutoff'])} pick cutoff ({basis})." + extra)
    return (f"Conservative ready {ready} is within the {clock(truck['deadline'])} safety-buffer deadline "
            f"({truck['slack_minutes']:+.0f} min; {basis})." + extra)
