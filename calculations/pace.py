"""Picking pace for planning (v11): lines per hour of PICKING time, not of logged-in time.

Why: logged-in time includes waiting while an area has no released work. An operator logged in
for hours with little to pick looked slow (e.g. 4.4 lines/h) although they picked at 17-26
lines/h whenever work existed. The cautious team rate (headcount x slowest pace) then forecast
a new burst of work to take hours; it was cleared in minutes, so an At Risk status appeared for
one snapshot and vanished at the next (v10 investigation).

Picking time of one operator in one work type on one day, up to snapshot time T
(times are Excel serial days; ``cap`` = PACE_GAP_CAP_MINUTES, default 10):

    lead     = min(first pick - start of the session that contains it, cap)   (cap if unknown)
    between  = sum over consecutive picks of min(gap, cap)
    trailing = min(T - last pick, cap)   only while the operator is still logged in to that area
    picking hours = (lead + between + trailing) x 24

A gap longer than ``cap`` counts as ``cap`` minutes of picking and the rest as waiting.

    operator pace     = picked lines / picking hours
    per-person rate   = area picked lines / area picking hours
    team rate         = per-person rate x operators logged in to the area (WIPIND = 'Y')
    cautious rate     = min(team rate, operators logged in x slowest operator pace)

The Excel-equation engine (calculations/etc.py, truck.py, uncertainty.py) is unchanged and remains
the logged-time reference; ``PACE_BASIS = logged_time`` reproduces it in the planning layer.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

try:
    from config import PACE_BASIS, PACE_GAP_CAP_MINUTES
except ImportError:  # pragma: no cover - calculations used outside the Flask project
    PACE_BASIS, PACE_GAP_CAP_MINUTES = 'picking_time', 10

EPS = 1e-9


def picking_hours(picks, session_starts, now=None, still_active=False, cap_minutes=None) -> float:
    """Picking hours for one operator / work type / day from sorted pick times (serial days)."""
    if not picks:
        return 0.0
    cap = (PACE_GAP_CAP_MINUTES if cap_minutes is None else cap_minutes) / 1440
    picks = sorted(picks)
    starts = [s for s in session_starts if s is not None and s <= picks[0] + EPS]
    lead = min(picks[0] - max(starts), cap) if starts else cap
    between = sum(min(b - a, cap) for a, b in zip(picks, picks[1:]))
    trailing = min(max(now - picks[-1], 0.0), cap) if still_active and now is not None else 0.0
    return (max(lead, 0.0) + between + trailing) * 24


def basis_label(basis=None, cap_minutes=None) -> str:
    basis = basis or PACE_BASIS
    cap = PACE_GAP_CAP_MINUTES if cap_minutes is None else cap_minutes
    if basis == 'logged_time':
        return 'Pace = lines ÷ logged-in hours (Excel equation)'
    return f'Pace = lines ÷ picking time (a gap over {cap} min between picks counts as waiting)'


def operator_stats(inp, snapshot_time, current_rows, history, picks, people, basis=None, cap_minutes=None):
    """Per (operator, work type): lines, logged hours, picking hours and pace on the chosen basis.

    ``current_rows``: LM005S1 rows of the selected snapshot (today's sessions up to T);
    ``history``: LM005S1 rows in the trailing window (today = selected snapshot only), with EVIDENCE_DAY;
    ``picks``: TI102C rows in the window picked by T; ``people``: {operator: active work type}.
    """
    basis = basis or PACE_BASIS
    if len(history):
        dedup = history.groupby(['RESOURCENAME', 'WORKTYPE', 'EVIDENCE_DAY', 'STARTDATETIME'],
                                dropna=False).TOTALTIMEINSEC.max()
        logged = {(str(n), int(w)): float(v) for (n, w), v in (dedup.groupby(level=[0, 1]).sum() / 3600).items()}
    else:
        logged = {}
    starts = defaultdict(list)
    for r in history.itertuples():
        starts[(str(r.RESOURCENAME), int(r.WORKTYPE), int(float(r.EVIDENCE_DAY)))].append(float(r.STARTDATETIME))
    picking = defaultdict(float)
    lines = defaultdict(int)
    today = int(snapshot_time)
    for (name, wt, day), group in picks.groupby(['RESOURCENAME', 'WORKTYPE', 'TRANSACTIONDATE']):
        key = (str(name), int(wt))
        times = [float(v) for v in group.MOVED_TO_C_AT]
        is_today = int(float(day)) == today
        picking[key] += picking_hours(times, starts.get((key[0], key[1], int(float(day))), []),
                                      now=snapshot_time if is_today else None,
                                      still_active=is_today and people.get(key[0]) == key[1],
                                      cap_minutes=cap_minutes)
        lines[key] += len(times)
    stats = {}
    for key in set(logged) | set(lines):
        n = lines.get(key, 0)
        logged_h = logged.get(key, 0.0)
        pick_h = picking.get(key, 0.0)
        hours = logged_h if basis == 'logged_time' else pick_h
        stats[key] = dict(hours=hours, logged_hours=logged_h, picking_hours=pick_h, lines=n,
                          pace=n / hours if hours > 0 and n > 0 else None, basis=basis, window_days=30)
    return stats


def area_rates(stats, resources: dict[int, int]):
    """Per work type per-person, team and cautious rates from picking-time operator stats."""
    out = {}
    for wt, heads in resources.items():
        own = [s for (name, w), s in stats.items() if w == wt]
        lines = sum(s['lines'] for s in own)
        hours = sum(s['hours'] for s in own)
        per_person = lines / hours if lines > 0 and hours > 0 else None
        team = per_person * heads if per_person and heads > 0 else None
        paces = [s['pace'] for s in own if s['pace']]
        low = min([team] + [heads * p for p in paces]) if team else None
        out[wt] = dict(rate=team, low=low, resources=int(heads), per_person=per_person)
    return out
