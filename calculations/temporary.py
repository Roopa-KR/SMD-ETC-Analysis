"""Temporary operators after safe reallocation (v12).

Order of decisions for one truck + work type (the planner's target):

1. Reallocation first. ``recommend_minimum`` searches the fewest safe, experienced existing
   operators. If reallocation alone meets the safety buffer deadline, temporary operators are
   NOT offered.
2. Only when safe reallocation (with the supervisor's current selection, plus any further safe
   reallocation) cannot meet the deadline, the plan with the FEWEST temporary operators is
   searched; among equal temporary counts, the fewest reallocated operators, then the most slack.
3. Temporary operators are credited exactly like any added operator in the conservative
   engine: point rate + pace, cautious rate + min(pace, slowest measured operator pace).

    temporary pace          = TEMP_OPERATOR_PACE_PCT % x work type per-person rate  (ASSUMPTION)
    required cautious rate  = lines ahead / hours left to the safety buffer deadline
    temporary operators     = ceil((required cautious rate - cautious rate after reallocation)
                                    / temporary cautious contribution), verified by recalculation

The safety buffer deadline is departure - loading time - safety buffer (unchanged).
Nothing here writes anywhere: confirmed temporary operators live only in the supervisor session
and are applied by ``build_state(..., temporaries=...)``.
"""
from __future__ import annotations

from itertools import combinations
from math import ceil

from calculations.bands import band, clock
from calculations.supervisor import (TEMP_OPERATOR_MAX, TEMP_OPERATOR_PACE_PCT, _single_row_result,
                                     add_temporaries, candidates, preview_state, recommend_minimum,
                                     temporary_pace, truck_projection)

SEARCH_LIMIT = 10        # exhaustive subset search over at most this many safe candidates


def _target(state, dest, shipment):
    return next((r for r in state['rows'] if r['shipment'] == shipment and r['worktype'] == int(dest)
                 and r['open']), None)


def _row_status(state, rates, row):
    rate = rates[row['worktype']]
    return _single_row_result(row, rate['rate'], rate['low'], state['now'])


def assumed_pace(state, dest):
    info = temporary_pace(state['baseline'], state['rows'], dest)
    info['label'] = (f"{info['pct']}% of the work type's per-person rate"
                     f"{' (' + format(info['per_person'], '.1f') + ' lines/h)' if info['per_person'] else ''}"
                     " — SYNTHESIZED ASSUMPTION, no temporary-staff history")
    return info


def temps_needed(state, rates, dest, shipment, max_count=None):
    """Fewest temporary operators so the target row meets its safety buffer deadline (cautious)."""
    max_count = TEMP_OPERATOR_MAX if max_count is None else max_count
    row = _target(state, dest, shipment)
    pace = assumed_pace(state, dest)
    if row is None:
        return dict(count=0, possible=True, reason='No open lines in this work type for this truck.', pace=pace)
    hours = (row['deadline'] - state['now']) * 24
    if _row_status(state, rates, row)['status'] == 'ON TIME':
        return dict(count=0, possible=True, reason='', pace=pace, hours=hours)
    if hours <= 0:
        return dict(count=None, possible=False, pace=pace, hours=hours,
                    reason='The safety buffer deadline has passed; added staff cannot recover it.')
    if not pace['cautious']:
        return dict(count=None, possible=False, pace=pace, hours=hours,
                    reason='No measured per-person rate in this work type, so a temporary pace cannot be assumed.')
    required = row['ahead'] / hours
    current = rates[int(dest)]['low'] or 0.0
    count = max(0, ceil((required - current) / pace['cautious'] - 1e-9))
    for _ in range(3):  # verify with the real recalculation (guards rounding)
        trial = add_temporaries(rates, state['rows'], dest, count, pace['pace'])
        if _row_status(state, trial, row)['status'] == 'ON TIME':
            break
        count += 1
    return dict(count=count, possible=count <= max_count, pace=pace, hours=hours,
                required_rate=required, current_rate=current,
                reason='' if count <= max_count else
                f'{count} temporary operators would be needed; the configured maximum is {max_count}.')


def minimum_mix(inp, state, dest, shipment, selected=()):
    """Fewest temporary operators, then fewest further reallocations, on top of ``selected``."""
    base = preview_state(inp, state, dest, list(selected), shipment=shipment)
    available = [c for c in candidates(inp, dict(state, rates=base['rates']), dest)
                 if c['operator'] not in selected and c['safe'] and c['pace']][:SEARCH_LIMIT]
    best = None
    for k in range(0, len(available) + 1):
        for group in combinations(available, k):
            names = list(selected) + [c['operator'] for c in group]
            try:
                trial = preview_state(inp, state, dest, names, shipment=shipment)
            except ValueError:
                continue
            need = temps_needed(state, trial['rates'], dest, shipment)
            if need['count'] is None:
                continue
            rates = add_temporaries(trial['rates'], state['rows'], dest, need['count'], need['pace']['pace'] or 0)
            finish = truck_projection(state, rates, shipment)['finish']
            key = (need['count'], k, finish if finish is not None else float('inf'))  # earlier = more slack
            if best is None or key < best['key']:
                best = dict(key=key, realloc=[c['operator'] for c in group], temps=need['count'],
                            possible=need['possible'], need=need)
        if best and best['temps'] == 0:
            break   # reallocation alone meets the deadline at this smallest size
    return best, available


def _with_selection(inp, state, dest, shipment, selected):
    try:
        return preview_state(inp, state, dest, list(selected), shipment=shipment), list(selected)
    except ValueError:
        return preview_state(inp, state, dest, [], shipment=shipment), []


def temporary_requirement(inp, state, dest, shipment, selected=(), temp_count=None):
    """Planner figures for the Temporary Operators panel (reallocation first, then temporaries)."""
    dest = int(dest)
    row = _target(state, dest, shipment)
    truck = next(t for t in state['trucks'] if t['shipment'] == shipment)
    pace = assumed_pace(state, dest)
    out = dict(shipment=shipment, dest=dest, pace=pace, max_count=TEMP_OPERATOR_MAX,
               pace_pct=TEMP_OPERATOR_PACE_PCT, selected=list(selected), selected_count=len(selected),
               buffer_deadline=truck['deadline'], cutoff=truck['cutoff'])
    if row is None:
        return dict(out, applicable=False, allowed=False, needed=False, total_required=0,
                    safe_available=[], safe_available_count=0, temps_required=0,
                    reason='No open lines in this work type for this truck.')
    base, selected = _with_selection(inp, state, dest, shipment, selected)
    out.update(selected=selected, selected_count=len(selected))
    safe_now = [c['operator'] for c in candidates(inp, dict(state, rates=base['rates']), dest)
                if c['operator'] not in selected and c['safe'] and c['pace']]
    realloc = recommend_minimum(inp, state, dest, shipment, selected)
    with_selection = temps_needed(state, base['rates'], dest, shipment)
    on_time_now = with_selection['count'] == 0
    if on_time_now:
        plan = dict(realloc=[], temps=0, possible=True)
    elif realloc['possible']:
        plan = dict(realloc=realloc['operators'], temps=0, possible=True)
    else:
        best, _ = minimum_mix(inp, state, dest, shipment, selected)
        plan = (dict(realloc=best['realloc'], temps=best['temps'], possible=best['possible'])
                if best else dict(realloc=[], temps=None, possible=False))
    needed = not on_time_now
    allowed = bool(needed and not realloc['possible'] and with_selection['count'] is not None)
    if not needed:
        reason = 'The work type already meets the safety buffer deadline with the current selection.'
    elif realloc['possible']:
        reason = (f"Safe reallocation is enough: reallocate {len(realloc['operators'])} more existing "
                  f"operator(s) ({', '.join(realloc['operators'])}). Temporary operators are not needed.")
    elif with_selection['count'] is None:
        reason = with_selection['reason']
    elif not safe_now and not selected:
        reason = 'No experienced existing operator can be moved safely, so temporary operators are needed.'
    else:
        reason = 'Safe reallocation alone cannot meet the safety buffer deadline; temporary operators are needed.'
    default = with_selection['count'] if allowed and with_selection['possible'] else 0
    count = default if temp_count is None else max(0, int(temp_count))
    proposed_rates = (add_temporaries(base['rates'], state['rows'], dest, count, pace['pace'])
                      if count and pace['pace'] else base['rates'])
    projection = truck_projection(state, proposed_rates, shipment)
    target_ev = next((r for r in projection['rows'] if r['worktype'] == dest), None)
    ready = projection['finish'] if projection['status'] != 'NO RATE' else None
    required_temps = with_selection['count'] if allowed else 0
    remaining = (max(0, with_selection['count'] - count) if allowed and with_selection['count'] is not None
                 else None)
    colour = band(ready, truck['deadline'], truck['cutoff'])
    # other open work types of this truck that still miss the safety buffer deadline
    blocking = [dict(worktype=r['worktype'], name=state['names'].get(r['worktype'], ''), status=r['status'])
                for r in projection['rows'] if r['worktype'] != dest and r['status'] != 'ON TIME']
    if not needed:
        next_action = ''
    elif realloc['possible']:
        next_action = f"Add {', '.join(realloc['operators'])} to the preview, then Allocate Operators."
    elif with_selection['count'] is None:
        next_action = ('Review the departure or loading plan with the shift manager; '
                       'added staff cannot meet this deadline.')
    elif not with_selection['possible']:
        next_action = (f"Even {TEMP_OPERATOR_MAX} temporary operators cannot meet the deadline; review the "
                       'departure or loading plan, or move work to a later truck.')
    elif remaining:
        next_action = f"Add {remaining} more temporary operator(s) to meet the safety buffer deadline."
    elif blocking and target_ev and target_ev['status'] == 'ON TIME':
        next_action = ('This work type meets its deadline, but the truck is still held back by '
                       + ', '.join(f"WT {b['worktype']} {b['name']}" for b in blocking)
                       + '. Plan that work type next.')
    elif plan['temps'] is not None and plan['realloc'] and plan['temps'] < (with_selection['count'] or 0):
        next_action = (f"Reallocating {', '.join(plan['realloc'])} first would reduce the temporary "
                       f"operators needed to {plan['temps']}.")
    else:
        next_action = ''
    return dict(out, applicable=True, allowed=allowed, needed=needed, reason=reason,
                safe_available=safe_now, safe_available_count=len(safe_now),
                realloc_possible=realloc['possible'], realloc_operators=realloc['operators'],
                plan=plan,
                total_required=(len(selected) + len(plan['realloc']) + plan['temps']
                                if plan['temps'] is not None else None),
                temps_required=required_temps, temps_possible=with_selection['possible'],
                temps_without_further_reallocation=with_selection['count'],
                plan_available=bool(allowed and plan['possible'] and plan['temps'] is not None
                                    and (plan['realloc'] or plan['temps'])),
                blocking=blocking,
                temps_reason=with_selection['reason'], required_rate=with_selection.get('required_rate'),
                proposed_count=count, remaining_gap=remaining,
                ready=ready, ready_text=clock(ready), band=colour,
                target_status=target_ev['status'] if target_ev else 'ALL PICKED',
                truck_status=projection['status'],
                meets_cutoff=colour in ('green', 'yellow'), meets_buffer=colour == 'green',
                next_action=next_action)
