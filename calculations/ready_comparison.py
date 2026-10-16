"""Truck ready time before vs after adding operators (v10 supervisor chart).

Read-only presentation adapter. Every number comes from the existing conservative
supervisor engine, so the chart always agrees with dashboard, truck and planner statuses:

* ``build_state``      - original assignments (no session moves) and confirmed session moves
* ``preview_state``    - sequential selected/recommended moves with cumulative source safety
* ``recommend_minimum``- minimum feasible set of safe, experienced operators per work type
* ``truck_projection`` - every open work type of the truck (a move can also slow a source
                          work type that this truck needs)

Deadlines (Excel serial days):
    pick cutoff            = departure - loading time (per-truck override, else configured default)
    safety buffer deadline = pick cutoff - configured safety buffer

Projected ready time = the truck's conservative (cautious) ready time: the latest of its open
work types, each = snapshot time + lines ahead / conservative team rate.  ETC = ready - now.

Colour bands (never green unless the buffer is kept):
    green   ready <= safety buffer deadline
    yellow  safety buffer deadline < ready <= pick cutoff
    red     ready > pick cutoff
    unknown no measurable ready time (a required work type has no pick rate)
"""
from __future__ import annotations

from calculations.bands import BANDS, COLORS, band, clock, iso  # noqa: F401 (re-exported)
from calculations.supervisor import (add_temporaries, preview_state, recommend_minimum,
                                     shipment_rates, truck_projection)
from calculations.temporary import minimum_mix, temps_needed
from calculations.truck import le


def duration_text(minutes) -> str | None:
    if minutes is None:
        return None
    whole = max(0, int(round(minutes)))
    return f"{whole // 60}h {whole % 60:02d}m" if whole >= 60 else f"{whole} min"


def _signed(minutes: float) -> int:
    """Whole minutes, rounded half away from zero (Excel ROUND), as used for slack elsewhere."""
    return int(abs(minutes) + 0.5) * (1 if minutes >= 0 else -1)


def gap_text(ready, deadline) -> tuple[bool, str]:
    """(on time?, '12 min early' / '3 min late' / '<1 min late' / 'on the deadline').

    The direction comes from the exact times (same EPS rule as the colour bands), so a ready time
    20 seconds after a deadline reads '<1 min late', never '0 min early'.
    """
    on_time = le(ready, deadline)
    minutes = abs(deadline - ready) * 1440
    whole = int(minutes + 0.5)
    if minutes < 1e-6:
        return True, 'on the deadline'
    if whole == 0:
        return on_time, '<1 min early' if on_time else '<1 min late'
    return on_time, f"{whole} min {'early' if on_time else 'late'}"


def relation_text(colour: str, ready, buffer_deadline, cutoff) -> str:
    """Plain-language position of the ready time against both deadlines."""
    if colour == 'unknown' or ready is None:
        return 'Ready time cannot be estimated'
    _, vs_buffer = gap_text(ready, buffer_deadline)
    _, vs_cutoff = gap_text(ready, cutoff)
    if colour == 'green':
        return f"{vs_buffer.replace('early', 'before')} the buffer deadline".replace('on the deadline the', 'exactly at the')
    if colour == 'yellow':
        return (f"{vs_buffer.replace('late', 'into')} the safety buffer · "
                f"{vs_cutoff.replace('early', 'before')} the pick cutoff").replace('on the deadline the', 'exactly at the')
    return f"{vs_cutoff.replace('late', 'after')} the pick cutoff"


def short_relation(colour: str, ready, buffer_deadline, cutoff) -> str:
    """Compact label printed next to the chart marker."""
    if colour == 'unknown' or ready is None:
        return 'no pick rate'
    if colour == 'green':
        return gap_text(ready, buffer_deadline)[1].replace('early', 'before buffer deadline').replace(
            'on the deadline', 'at the buffer deadline')
    if colour == 'yellow':
        return gap_text(ready, buffer_deadline)[1].replace('late', 'into buffer')
    return gap_text(ready, cutoff)[1].replace('late', 'after cutoff')


def _truck(state, shipment):
    return next(t for t in state['trucks'] if t['shipment'] == shipment)


def _scenario(key, title, subtitle, state, rates, shipment, operators=(), confirmed=False,
              projection_note='', reallocated=0, temporary=0, tick_note=''):
    truck = _truck(state, shipment)
    projection = truck_projection(state, rates, shipment)
    now = state['now']
    rows = projection['rows']
    if not rows:
        ready = None
    elif projection['status'] == 'NO RATE' or any(r['conservative_ready'] is None for r in rows):
        ready = None
    else:
        ready = max(r['conservative_ready'] for r in rows)
    point = ([r['point_ready'] for r in rows] if rows else [])
    point_ready = max(point) if point and all(p is not None for p in point) else None
    colour = band(ready, truck['deadline'], truck['cutoff']) if rows else 'green'
    early_buffer = _signed((truck['deadline'] - ready) * 1440) if ready is not None else None
    early_cutoff = _signed((truck['cutoff'] - ready) * 1440) if ready is not None else None
    etc_minutes = (ready - now) * 1440 if ready is not None else None
    bottleneck = None
    if ready is not None:
        worst = max(rows, key=lambda r: r['conservative_ready'])
        bottleneck = f"WT {worst['worktype']} {state['names'].get(worst['worktype'], '')}".strip()
    elif rows:
        missing = [r for r in rows if r['conservative_ready'] is None]
        if missing:
            bottleneck = (f"WT {missing[0]['worktype']} "
                          f"{state['names'].get(missing[0]['worktype'], '')} (no rate)").strip()
    return dict(key=key, title=title, subtitle=subtitle, confirmed=confirmed,
                operators=list(operators), operators_added=reallocated + temporary,
                reallocated=reallocated, temporary=temporary, tick_note=tick_note,
                ready=ready, ready_iso=iso(ready), ready_text=clock(ready),
                point_ready_text=clock(point_ready),
                etc_minutes=round(etc_minutes, 1) if etc_minutes is not None else None,
                etc_text=duration_text(etc_minutes),
                band=colour, band_label=BANDS[colour]['label'], band_meaning=BANDS[colour]['meaning'],
                minutes_before_buffer=early_buffer, minutes_before_cutoff=early_cutoff,
                vs_buffer=gap_text(ready, truck['deadline']) if ready is not None else None,
                vs_cutoff=gap_text(ready, truck['cutoff']) if ready is not None else None,
                relation=(relation_text(colour, ready, truck['deadline'], truck['cutoff'])
                          if rows else 'All released lines picked'),
                relation_short=(short_relation(colour, ready, truck['deadline'], truck['cutoff'])
                                if rows else 'All picked'),
                bottleneck=bottleneck, all_picked=not rows, note=projection_note,
                areas=[dict(worktype=r['worktype'], name=state['names'].get(r['worktype'], ''),
                            ready_text=clock(r['conservative_ready']),
                            band=band(r['conservative_ready'], truck['deadline'], truck['cutoff']))
                       for r in rows])


def _apply_preview(result, worktype, rates, applied, steps, names):
    rates.clear()
    rates.update({w: r.copy() for w, r in result['rates'].items()})
    for step in result['steps']:
        applied.append(dict(operator=step['operator'], source=step['source'], dest=worktype))
        steps.append(dict(operator=step['operator'], source=step['source'],
                          source_name=names.get(step['source'], ''), dest=worktype,
                          dest_name=names.get(worktype, ''), pace=step['pace'],
                          evidence=step['evidence'], experience=step['experience'],
                          source_status_after=step['source_after']['status'],
                          source_ready_after=clock(step['source_after']['finish']),
                          source_deadline=clock(step['source_after']['deadline'])))


def _plan(src, state, shipment, snapshot, previews, temp_previews=None):
    """Reallocation first, then temporary operators only where reallocation cannot close the gap.

    Pass 1 (existing operators): the supervisor's selection for this truck, else the minimum safe
    recommendation per work type (slowest work type first). Where reallocation alone cannot meet
    the safety buffer deadline, the reallocation part of the fewest-temporary-operators plan is used.
    Pass 2 (temporary operators): an explicit supervisor count, else the fewest needed on top of
    pass 1 - only for work types where safe reallocation (selected + further) cannot meet it.
    Moves are cumulative across work types, so one operator is never counted twice.
    """
    temp_previews = temp_previews or {}
    rates = {w: r.copy() for w, r in state['rates'].items()}
    applied = list(state['applied'])
    steps, notes, temps = [], [], []
    names = state['names']
    open_wts = sorted({r['worktype'] for r in state['rows'] if r['shipment'] == shipment and r['open']})
    key = lambda wt: f'{snapshot}:{wt}:{shipment}'
    selections = {wt: list(previews.get(key(wt), [])) for wt in open_wts}
    selections = {wt: ops for wt, ops in selections.items() if ops}
    explicit = {wt: int(temp_previews[key(wt)]) for wt in open_wts if key(wt) in temp_previews}

    def cumulative():
        return dict(state, rates=rates, applied=applied)

    def pending(current):
        return [r for r in truck_projection(cumulative(), current, shipment)['rows']
                if r['conservative_ready'] is None or not le(r['conservative_ready'], r['deadline'])]

    kind = 'selected' if (selections or explicit) else 'recommended'
    if selections:
        for wt, operators in sorted(selections.items()):
            try:
                result = preview_state(src, cumulative(), wt, operators, shipment=shipment)
            except ValueError as error:
                notes.append(f"WT {wt} {names.get(wt, '')}: selection no longer valid ({error})")
                continue
            _apply_preview(result, wt, rates, applied, steps, names)
    elif kind == 'recommended':
        tried = set()
        for _ in open_wts:
            rows = [r for r in pending(rates) if r['worktype'] not in tried]
            if not rows:
                break
            target = max(rows, key=lambda r: (r['conservative_ready'] is None, r['conservative_ready'] or 0))
            wt = target['worktype']
            tried.add(wt)
            recommendation = recommend_minimum(src, cumulative(), wt, shipment)
            chosen = recommendation['operators'] if recommendation['possible'] else None
            if chosen is None:   # v12: reallocation part of the fewest-temporary-operators plan
                best, _ = minimum_mix(src, cumulative(), wt, shipment)
                if not best or not best['possible']:
                    reason = (best['need']['reason'] if best else
                              temps_needed(cumulative(), rates, wt, shipment)['reason'])
                    notes.append(f"WT {wt} {names.get(wt, '')}: safe reallocation plus temporary operators "
                                 f"cannot meet the safety buffer deadline ({reason})")
                    # The truck is ready only when its slowest area is: a plan that cannot fix that
                    # area cannot make the truck on time, so nothing is recommended (v11 rule).
                    return kind, [], {w: r.copy() for w, r in state['rates'].items()}, [], \
                        {w: r.copy() for w, r in state['rates'].items()}, notes
                chosen = best['realloc']
            if chosen:
                try:
                    result = preview_state(src, cumulative(), wt, chosen, shipment=shipment)
                except ValueError as error:  # eligibility changed during evaluation: fail closed
                    notes.append(f"WT {wt} {names.get(wt, '')}: recommendation could not be validated ({error})")
                    continue
                _apply_preview(result, wt, rates, applied, steps, names)
    realloc_rates = {w: r.copy() for w, r in rates.items()}
    # Pass 2: temporary operators.
    for wt in open_wts:
        row = next((r for r in pending(rates) if r['worktype'] == wt), None)
        if wt in explicit:
            count = explicit[wt]
        elif row is None:
            continue
        else:
            selected_here = selections.get(wt, [])
            if recommend_minimum(src, cumulative(), wt, shipment)['possible']:
                notes.append(f"WT {wt} {names.get(wt, '')}: safe reallocation can still meet the deadline; "
                             f"temporary operators not recommended")
                continue
            need = temps_needed(cumulative(), rates, wt, shipment)
            if need['count'] is None or not need['possible']:
                notes.append(f"WT {wt} {names.get(wt, '')}: {need['reason']}")
                if kind == 'recommended':   # cannot fix this area: recommend nothing (see pass 1)
                    return kind, [], {w: r.copy() for w, r in state['rates'].items()}, [], \
                        {w: r.copy() for w, r in state['rates'].items()}, notes
                continue
            count = need['count']
        if count <= 0:
            continue
        need = temps_needed(cumulative(), rates, wt, shipment)
        pace = need['pace']
        if not pace['pace']:
            notes.append(f"WT {wt} {names.get(wt, '')}: {need['reason'] or 'no temporary pace'}")
            continue
        rates = add_temporaries(rates, state['rows'], wt, count, pace['pace'])
        temps.append(dict(worktype=wt, name=names.get(wt, ''), count=count, pace=pace['pace'],
                          cautious_pace=pace['cautious'], pct=pace['pct'],
                          basis='selected' if wt in explicit else 'recommended'))
    return kind, steps, realloc_rates, temps, rates, notes


def _count(n, word):
    return f"{n} {word}{'s' if n != 1 else ''}"


def ready_time_comparison(src, original_state, current_state, shipment, snapshot, previews, temp_previews=None):
    """Chart payload: original assignments, confirmed session allocation, then the proposed plan:
    after reallocating existing operators, and after adding temporary operators (v12)."""
    truck = _truck(current_state, shipment)
    names = current_state['names']
    open_wts = {r['worktype'] for r in current_state['rows'] if r['shipment'] == shipment and r['open']}
    scenarios = [_scenario('before', 'Before allocation', 'Original operator assignments',
                           original_state, original_state['rates'], shipment,
                           tick_note='original operators')]

    confirmed = [m for m in current_state['applied']
                 if ((int(m['dest']) in open_wts and m.get('shipment') in (None, shipment))
                     or int(m['source']) in open_wts)]
    confirmed_temps = [t for t in current_state.get('temporaries_applied', [])
                       if int(t['dest']) in open_wts and t.get('shipment') in (None, shipment)]
    if confirmed or confirmed_temps:
        into = [m['operator'] for m in confirmed
                if int(m['dest']) in open_wts and m.get('shipment') in (None, shipment)]
        out_of = [m['operator'] for m in confirmed if int(m['source']) in open_wts and int(m['dest']) not in open_wts]
        temp_total = sum(int(t['count']) for t in confirmed_temps)
        parts = []
        if into:
            parts.append(f"+{_count(len(into), 'reallocated operator')} ({', '.join(into)})")
        if out_of:
            parts.append(f"−{len(out_of)} moved out of its areas")
        if temp_total:
            parts.append(f"+{_count(temp_total, 'temporary operator')}")
        scenarios.append(_scenario('confirmed', 'After allocation (confirmed)', ' · '.join(parts),
                                   current_state, shipment_rates(current_state, shipment), shipment,
                                   operators=into, confirmed=True, reallocated=len(into), temporary=temp_total,
                                   tick_note=f"confirmed · +{len(into)} reallocated"
                                             + (f" +{temp_total} temporary" if temp_total else '')))

    latest = scenarios[-1]
    plan_kind, steps, realloc_rates, temps, rates, notes = _plan(src, current_state, shipment, snapshot,
                                                                 previews, temp_previews)
    status_word = 'selected, not yet allocated' if plan_kind == 'selected' else 'recommended, not allocated'
    added = [s['operator'] for s in steps]
    if steps:
        title = ('After reallocating selected operators' if plan_kind == 'selected'
                 else 'After reallocating recommended operators')
        subtitle = f"+{_count(len(added), 'existing operator')}: {', '.join(added)} · {status_word}"
        scenarios.append(_scenario(plan_kind, title, subtitle, current_state, realloc_rates, shipment,
                                   operators=added, reallocated=len(added),
                                   projection_note='' if temps else '; '.join(notes),
                                   tick_note=f"not allocated · +{len(added)} reallocated"))
    temp_total = sum(t['count'] for t in temps)
    if temp_total:
        detail = ', '.join(f"{t['count']} to WT {t['worktype']} {t['name']} at {t['pace']:.1f} lines/h" for t in temps)
        subtitle = ((f"+{_count(len(added), 'existing operator')} ({', '.join(added)}) and " if added else '')
                    + f"+{_count(temp_total, 'temporary operator')} ({detail}; assumed pace) · {status_word}")
        scenarios.append(_scenario('temporary', 'After adding temporary operators', subtitle, current_state,
                                   rates, shipment, operators=added, reallocated=len(added),
                                   temporary=temp_total, projection_note='; '.join(notes),
                                   tick_note=f"not allocated · +{len(added)} reallocated +{temp_total} temporary"))
    message = None
    if latest['all_picked']:
        message = 'All released lines for this truck are picked; no operators are needed.'
    elif not steps and not temp_total and latest['band'] == 'green':
        message = 'No additional operators needed: the truck is ready by its safety buffer deadline.'
    elif latest['band'] == 'unknown':
        area = (latest['bottleneck'] or 'a required work type').replace(' (no rate)', '')
        message = (f"Ready time cannot be estimated with the current operators: {area} has no "
                   f"measured pick rate yet (nobody logged in, or no line completed). "
                   + ('The plan below adds operators to that area.' if (steps or temp_total) else
                      ('; '.join(notes) + '.' if notes else '')))
    elif not steps and not temp_total:
        message = ('No safe reallocation or temporary-operator plan can be added. '
                   + ('; '.join(notes) + '.' if notes else 'Review other work types or the departure/loading plan.'))
    final = scenarios[-1]
    if (steps or temp_total) and final['band'] != 'green' and not message:
        message = (f"The proposed allocation still does not meet the safety buffer deadline "
                   f"({final['band_label'].lower()}). " + ('; '.join(notes) + '.' if notes else ''))

    return dict(
        shipment=shipment, snapshot=int(snapshot),
        now_iso=iso(current_state['now']), now_text=clock(current_state['now']),
        departure_iso=iso(truck['departure']), departure_text=clock(truck['departure']),
        cutoff_iso=iso(truck['cutoff']), cutoff_text=clock(truck['cutoff']),
        buffer_deadline_iso=iso(truck['deadline']), buffer_deadline_text=clock(truck['deadline']),
        loading_minutes=truck['loading_minutes'], buffer_minutes=current_state['buffer_minutes'],
        scenarios=scenarios, steps=steps, temporaries=temps, plan_kind=plan_kind if (steps or temp_total) else None,
        message=message, notes=notes, colors=COLORS,
        bands=[dict(key=k, **v) for k, v in BANDS.items() if k != 'unknown'])
