"""Read-only dashboard presentation helpers.

These categorize existing conservative supervisor scenario statuses; they do NOT
change ETC, cutoff, source safety, or warehouse data.
"""
from __future__ import annotations

from types import SimpleNamespace
from calculations.excel_io import serial_to_datetime


def category(status: str | None) -> str:
    """Exhaustive explicit display categories; no inferred probabilistic forecast."""
    status = status or ''
    if status in {'ON TIME', 'ALL PICKED', 'DEPARTED COMPLETE'}:
        return 'healthy'
    if status == 'AT RISK':
        return 'risk'
    if status in {'CUTOFF PASSED', 'PICK CUTOFF PASSED', 'PICK CUTOFF PASSED - LATE'} or (
            status.startswith('DEPARTED') and status != 'DEPARTED COMPLETE'):
        return 'critical'
    return 'unknown'


def departed_status(engine_status, scenario):
    """After departure the engine reports lines left behind from history; a confirmed allocation's
    scenario replay may have picked them (v14), so the count follows the scenario's open lines."""
    if not engine_status.startswith('DEPARTED'):
        return scenario['status']
    if not scenario.get('scenario_adjusted'):
        return engine_status
    left = scenario.get('open_lines', 0)
    return 'DEPARTED COMPLETE' if left == 0 else f'DEPARTED - {left} LINES LEFT BEHIND'


def display_trucks(baseline, state):
    by_ship = {entry['shipment']: entry for entry in state['trucks']}
    output = []
    for original in baseline:
        t = SimpleNamespace(**{key: value for key, value in vars(original).items()
                               if not key.startswith('_')})
        scenario = by_ship[t.shipment_id]
        related = [r for r in state['rows'] if r['shipment'] == t.shipment_id and r['open']]
        status = departed_status(original.status, scenario)
        t.open_lines = scenario.get('open_lines', t.open_lines)
        t.planning_status = status
        t.category = category(status)
        points = [r['point_ready'] for r in related if r['point_ready'] is not None]
        slower = [r['conservative_ready'] for r in related if r['conservative_ready'] is not None]
        complete_points = bool(related) and len(points) == len(related)
        complete_slow = bool(related) and len(slower) == len(related)
        t.etc_hours = ((max(points) - state['now']) * 24 if complete_points else None)
        t.etc_low_hours = t.etc_hours
        t.etc_high_hours = ((max(slower) - state['now']) * 24 if complete_slow else None)
        t.ready_time = serial_to_datetime(max(points)) if complete_points else None
        t.ready_time_late = serial_to_datetime(max(slower)) if complete_slow else None
        t.pick_cutoff = serial_to_datetime(scenario['deadline'])
        t.hours_to_cutoff = (scenario['deadline'] - state['now']) * 24
        t.planning_slack_text = (f"{scenario['slack_minutes']:+.0f} min"
                                 if scenario['slack_minutes'] is not None else '')
        t.uncertainty_changes_risk = False
        t.planning_operator_gap = ''  # the stored operator gap used a different cutoff
        t.bottleneck = (f"{scenario['bottleneck']}" if scenario['bottleneck'] is not None else '')
        t.staffed_areas = sum(1 for r in related if r['resources'] > 0)
        t.open_areas = len(related)
        t.loading_minutes = scenario['loading_minutes']
        output.append(t)
    return output


def summary(trucks):
    total = len(trucks)
    buckets = {k: sum(t.category == k for t in trucks)
               for k in ('healthy', 'risk', 'critical', 'unknown')}
    return dict(total=total, **buckets,
                on_time_pct=round(buckets['healthy'] / total * 100, 1) if total else 0)


def operational_insights(trucks, state, moves):
    """Deterministic factual flags, not AI-generated recommendations."""
    categories = summary(trucks)
    unstaf = {r['worktype'] for r in state['rows'] if r['open'] > 0 and r['resources'] == 0}
    return [
        dict(icon='bi-exclamation-octagon', tone='critical', title=f"{categories['critical']} critical / delayed trucks",
             explanation='Pick cutoff passed or projected to be missed, or departed with unfinished work.', target='#truck-performance',
             category='critical'),
        dict(icon='bi-clock-history', tone='risk', title=f"{categories['risk']} at-risk trucks",
             explanation='Conservative completion is after the safety-buffer deadline but not after the pick cutoff.', target='#truck-performance',
             category='risk'),
        dict(icon='bi-question-circle', tone='unknown', title=f"{categories['unknown']} without confirmed on-time status",
             explanation='Includes missing pace evidence or work that has not released.',
             target='#truck-performance', category='unknown'),
        dict(icon='bi-people', tone='primary', title=f"{len(unstaf)} worktypes have unstaffed open work",
             explanation='At least one outstanding truck needs work in these areas, with zero current resources.',
             target='planner', category=None),
        dict(icon='bi-person-check', tone='primary',
             title=(f"{len(moves)} reallocated · "
                    f"{sum(int(t['count']) for t in state.get('temporaries_applied', []))} temporary operators"),
             explanation='Confirmed supervisor-session allocations; never written to WMS.',
             target='planner', category=None),
    ]
