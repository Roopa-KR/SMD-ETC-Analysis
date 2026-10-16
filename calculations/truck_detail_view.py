"""Presentation-only projection adapter for the truck-detail page.

Consumes current session state and the already-approved minimum feasible staffing
search. Never changes the calculation engine, baseline workbook or assignments.
"""
from calculations.supervisor import preview_state, recommend_minimum
from calculations.temporary import temporary_requirement


RISK_STATUSES = {'AT RISK', 'CUTOFF PASSED', 'PICK CUTOFF PASSED', 'NO RATE'}


def area_recommendations(source, state, shipment, snapshot, session_previews):
    """Return independently verified area forecasts and an honest operator-gap display.

    A candidate forecast is NOT a confirmed operator allocation. An in-progress
    preview takes priority; without one, show the minimum feasible suggestion.
    Never add per-worktype minimums together: a shared operator can appear in
    more than one independent scenario.
    """
    areas = []
    at_risk = []
    for row in state['rows']:
        if row['shipment'] != shipment or not row['open']:
            continue
        wt = row['worktype']
        key = f'{snapshot}:{wt}:{shipment}'
        selected = list(session_previews.get(key, []))
        preview = None
        if selected:
            try:
                preview = preview_state(source, state, wt, selected, shipment=shipment)
            except ValueError:
                selected = []  # stale preview cannot silently change the scenario
        risk = row['status'] in RISK_STATUSES
        recommendation = (recommend_minimum(source, state, wt, shipment, selected)
                          if risk or selected else None)
        projection_basis = None
        if selected and preview is not None:
            projection_basis = f'Unconfirmed preview: {len(selected)} selected operator(s)'
        elif recommendation and recommendation['possible'] and recommendation['operators']:
            try:
                preview = preview_state(source, state, wt,
                                        recommendation['operators'], shipment=shipment)
                projection_basis = (f'Unconfirmed recommendation: '
                                    f"{len(recommendation['operators'])} operator(s)")
            except ValueError:
                preview = None  # fail closed if eligibility changes during evaluation
        temporary = None
        if recommendation and not recommendation['possible'] and risk:
            # v12: safe reallocation alone cannot meet the deadline -> fewest temporary operators
            temporary = temporary_requirement(source, state, wt, shipment, selected)
        projected = preview['projected'] if preview is not None else None
        entry = dict(worktype=wt, name=row['name'], status=row['status'],
                     current_ready=row['conservative_ready'],
                     projected_ready=projected['finish'] if projected else None,
                     projected_status=projected['status'] if projected else None,
                     projection_basis=projection_basis,
                     selected=selected, recommendation=recommendation, temporary=temporary)
        areas.append(entry)
        if risk:
            at_risk.append(entry)

    if not at_risk:
        gap = dict(display='0', summary='No additional operators required for currently safe areas.',
                   details='', worktype=areas[0]['worktype'] if areas else 2,
                   breakdown=[])
    elif len(at_risk) == 1:
        area = at_risk[0]
        rec = area['recommendation']
        temp = area['temporary']
        mixed = bool(temp and temp['plan']['possible'] and temp['plan']['temps'])
        gap = dict(display=(str(rec['required']) if rec and rec['possible'] else
                            str(len(temp['plan']['realloc']) + temp['plan']['temps']) if mixed else 'Not feasible'),
                   summary=(f"{len(temp['plan']['realloc'])} reallocated + {temp['plan']['temps']} temporary "
                            f"(assumed pace) — safe reallocation alone cannot meet the deadline" if mixed else
                            'Additional operators still required (after unconfirmed selections)'
                            if area['selected'] else 'Minimum additional operators required'),
                   details=(f"{area['name']}: {rec['explanation']}" if rec else
                            'No validated recommendation available.'),
                   worktype=area['worktype'],
                   breakdown=[dict(worktype=area['worktype'], required=rec['required'] if rec else None,
                                   selected=len(area['selected']))])
    else:
        parts = []
        for area in at_risk:
            rec = area['recommendation']
            temp = area['temporary']
            count = (str(rec['required']) if rec and rec['possible'] else
                     f"{len(temp['plan']['realloc'])} reallocated + {temp['plan']['temps']} temporary"
                     if temp and temp['plan']['possible'] and temp['plan']['temps'] else 'not feasible')
            parts.append(f"{area['name']}: {count} further")
        gap = dict(display='By area', summary='Independent minimum per at-risk area; do not add counts.',
                   details=' · '.join(parts),worktype=at_risk[0]['worktype'],
                   breakdown=[dict(worktype=a['worktype'],
                                   required=a['recommendation']['required'],
                                   selected=len(a['selected'])) for a in at_risk])
    return areas, gap
