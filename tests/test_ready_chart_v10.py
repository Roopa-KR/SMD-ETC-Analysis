"""v10: truck ready time before vs after adding operators (green / yellow / red / blue ETC).

Checks the colour rules, the deadline formulas, agreement with the existing conservative
engine, source-area recalculation, and green/yellow/red outcomes both before and after
adding operators. v11: the corrected demo has no at-risk truck at 18:30, so red/yellow cases use
genuine deadline pressure from the per-truck loading-time setting (conftest.py). v14: SH0908-1034 is
yellow (At Risk) at 18:30 without any override; red = Pick Cutoff Passed.
"""
import json
import re

import pytest

from calculations.ready_comparison import band, ready_time_comparison
from calculations.supervisor import build_state, preview_state, truck_projection
from models import database as db
from conftest import INFEASIBLE_LOADING, ONE_OPERATOR_LOADING, TWO_OPERATOR_LOADING

RED_TRUCK, TWO_OP_TRUCK, GREEN_TRUCK = 'SH0908-1034', 'SH0908-1069', 'SH0908-1012'
MINUTE = 1 / 1440


def states(snapshot, loading=None, moves=(), buffer=None):
    src = db.load_sources()
    args = (src, db.worktype_context(snapshot), db.trucks_at(snapshot), snapshot, loading or {})
    original = build_state(*args, [], buffer_minutes=buffer)
    current = build_state(*args, list(moves), buffer_minutes=buffer)
    return src, original, current


def compare(snapshot, truck, loading=None, moves=(), previews=None, buffer=None):
    src, original, current = states(snapshot, loading, moves, buffer)
    return ready_time_comparison(src, original, current, truck, snapshot, previews or {}), current


def by_key(chart, key):
    return next((s for s in chart['scenarios'] if s['key'] == key), None)


# ---------- colour rule boundaries ----------
@pytest.mark.parametrize('ready,expected', [
    (100.0 - 20 * MINUTE, 'green'),     # well before the buffer deadline
    (100.0 - 10 * MINUTE, 'green'),     # exactly at the buffer deadline
    (100.0 - 5 * MINUTE, 'yellow'),     # inside the buffer
    (100.0, 'yellow'),                  # exactly at the pick cutoff
    (100.0 + 1 * MINUTE, 'red'),        # after the pick cutoff
    (None, 'unknown'),                  # no pick rate: never green
])
def test_band_boundaries(ready, expected):
    assert band(ready, 100.0 - 10 * MINUTE, 100.0) == expected


# ---------- deadline formulas use configured values, not constants ----------
def test_cutoff_and_buffer_deadline_follow_configured_loading_and_buffer():
    chart, state = compare(10, RED_TRUCK, loading={RED_TRUCK: 45}, buffer=15)
    truck = next(t for t in state['trucks'] if t['shipment'] == RED_TRUCK)
    assert abs((truck['departure'] - truck['cutoff']) * 1440 - 45) < 1e-6
    assert abs((truck['cutoff'] - truck['deadline']) * 1440 - 15) < 1e-6
    assert chart['loading_minutes'] == 45 and chart['buffer_minutes'] == 15
    assert chart['cutoff_text'] == '19:45' and chart['buffer_deadline_text'] == '19:30'


def test_default_loading_comes_from_workbook_config():
    _, _, state = states(10)
    assert state['default_loading_minutes'] == int(db.load_sources().config['LOADING_MINUTES']) == 30


# ---------- before = original assignments, and agrees with app statuses everywhere ----------
def test_before_scenario_matches_engine_status_for_every_truck_and_snapshot():
    checked = 0
    for snap in db.snapshots():
        src, original, current = states(snap.snapshot_no)
        for truck in original['trucks']:
            chart = ready_time_comparison(src, original, current, truck['shipment'], snap.snapshot_no, {})
            before = by_key(chart, 'before')
            if truck['status'] == 'ALL PICKED':
                assert before['all_picked']
                continue
            assert before['ready'] == truck['conservative_ready']
            if truck['status'] == 'ON TIME':
                assert before['band'] == 'green'
            elif truck['status'] == 'NO RATE':
                assert before['band'] == 'unknown'
            elif truck['status'] == 'AT RISK':
                assert before['band'] == 'yellow'
            elif truck['conservative_ready'] is None:   # cutoff passed by the clock with no pick rate left
                assert truck['status'] == 'PICK CUTOFF PASSED' and before['band'] == 'unknown'
            else:   # PICK CUTOFF PASSED is never green
                assert before['band'] in ('yellow', 'red')
            checked += 1
    assert checked > 30


def test_green_never_shown_when_buffer_is_violated():
    for snap in db.snapshots():
        src, original, current = states(snap.snapshot_no)
        for truck in current['trucks']:
            chart = ready_time_comparison(src, original, current, truck['shipment'], snap.snapshot_no, {})
            for s in chart['scenarios']:
                if s['ready'] is None:
                    assert s['band'] in ('unknown', 'green') and (s['band'] == 'unknown' or s['all_picked'])
                    continue
                assert (s['band'] == 'green') == (s['ready'] <= truck['deadline'] + 1e-9)
                assert (s['band'] == 'red') == (s['ready'] > truck['cutoff'] + 1e-9)
                assert s['etc_minutes'] == pytest.approx((s['ready'] - current['now']) * 1440, abs=0.06)


# ---------- before / after colour combinations ----------
def test_yellow_before_green_after_one_recommended_operator():
    chart, _ = compare(10, RED_TRUCK, loading={RED_TRUCK: ONE_OPERATOR_LOADING})
    before, after = by_key(chart, 'before'), by_key(chart, 'recommended')
    assert (before['band'], before['ready_text']) == ('yellow', '19:57')
    assert before['vs_buffer'] == (False, '7 min late') and before['vs_cutoff'] == (True, '3 min early')
    assert (after['band'], after['ready_text'], after['operators']) == ('green', '19:28', ['dclements'])
    assert after['relation_short'] == '22 min before buffer deadline'


def test_red_before_green_after_two_recommended_operators():
    chart, _ = compare(10, RED_TRUCK, loading={RED_TRUCK: TWO_OPERATOR_LOADING})
    before, after = by_key(chart, 'before'), by_key(chart, 'recommended')
    assert before['band'] == 'red' and before['relation_short'] == '13 min after cutoff'
    assert after['band'] == 'green' and after['operators'] == ['dclements', 'ekim']


def test_red_before_yellow_after_one_selected_operator():
    previews = {f'10:2:{RED_TRUCK}': ['dclements']}
    chart, _ = compare(10, RED_TRUCK, loading={RED_TRUCK: TWO_OPERATOR_LOADING}, previews=previews)
    selected = by_key(chart, 'selected')
    assert selected['band'] == 'yellow' and selected['operators_added'] == 1
    assert selected['vs_buffer'] == (False, '2 min late')
    assert selected['vs_cutoff'][0] is True
    assert by_key(chart, 'recommended') is None     # a selection replaces the recommendation


def test_red_stays_red_after_one_selected_operator():
    previews = {f'10:2:{RED_TRUCK}': ['dclements']}
    chart, _ = compare(10, RED_TRUCK, loading={RED_TRUCK: INFEASIBLE_LOADING}, previews=previews)
    selected = by_key(chart, 'selected')
    assert by_key(chart, 'before')['band'] == 'red' and selected['band'] == 'red'
    assert 'after the pick cutoff' in selected['relation']


def test_no_safe_combination_gives_no_recommendation():
    # v12: temporary operators are now considered, but OTC would need 11 (> configured maximum 10),
    # so no plan can make the truck on time and nothing is recommended.
    chart, _ = compare(10, RED_TRUCK, loading={RED_TRUCK: INFEASIBLE_LOADING})
    assert [s['key'] for s in chart['scenarios']] == ['before'] and chart['scenarios'][0]['band'] == 'red'
    assert 'No safe reallocation or temporary-operator plan' in chart['message']
    assert 'configured maximum is 10' in chart['message']


def test_less_than_one_minute_is_never_shown_as_zero_minutes():
    # 100 min loading: reallocation of 3 plus 8 temporary operators ends seconds before 18:40.
    chart, _ = compare(10, RED_TRUCK, loading={RED_TRUCK: 100})
    plan = by_key(chart, 'temporary')
    assert plan['band'] == 'green' and plan['vs_buffer'] == (True, '<1 min early')
    assert (plan['reallocated'], plan['temporary']) == (3, 8)


def test_no_moves_recommended_into_other_areas_when_slowest_area_cannot_be_fixed():
    # v11 fix: SH0908-1069 at 18:45 with 120 min loading: its slowest area (Prescription) has no safe
    # fix, so moving operators into another area would not change its ready time. v10 recommended +2.
    chart, _ = compare(11, TWO_OP_TRUCK, loading={TWO_OP_TRUCK: 120})
    assert by_key(chart, 'recommended') is None
    assert by_key(chart, 'before')['band'] in ('yellow', 'red')
    assert 'WT 1' in chart['message'] and 'cannot meet the safety buffer deadline' in chart['message']


def test_green_before_needs_no_operators():
    chart, _ = compare(10, GREEN_TRUCK)
    assert [s['key'] for s in chart['scenarios']] == ['before']
    assert chart['scenarios'][0]['band'] == 'green'
    assert 'No additional operators needed' in chart['message']


def test_green_after_confirmed_allocation_and_before_kept_original():
    loading = {RED_TRUCK: ONE_OPERATOR_LOADING}
    src, _, base = states(10, loading)
    step = preview_state(src, base, 2, ['dclements'], shipment=RED_TRUCK)['steps'][0]
    move = dict(operator='dclements', source=step['source'], dest=2, start_snapshot=10,
                destination_pace=step['pace'])
    chart, current = compare(10, RED_TRUCK, loading=loading, moves=[move])
    assert by_key(chart, 'before')['band'] == 'yellow'
    confirmed = by_key(chart, 'confirmed')
    assert confirmed['band'] == 'green' and confirmed['confirmed'] and confirmed['operators'] == ['dclements']
    truck = next(t for t in current['trucks'] if t['shipment'] == RED_TRUCK)
    assert confirmed['ready'] == truck['conservative_ready'] and truck['status'] == 'ON TIME'


# ---------- after = individual pace added to target AND removed from source ----------
def test_after_scenario_recalculates_source_and_target_worktypes():
    src, original, current = states(10, {RED_TRUCK: ONE_OPERATOR_LOADING})
    chart = ready_time_comparison(src, original, current, RED_TRUCK, 10, {})
    step = chart['steps'][0]
    result = preview_state(src, current, 2, ['dclements'], shipment=RED_TRUCK)
    assert result['rates'][2]['rate'] == pytest.approx(current['rates'][2]['rate'] + step['pace'])
    source_pace = current['stats'][('dclements', step['source'])]['pace']
    assert result['rates'][step['source']]['rate'] == pytest.approx(
        max(0, current['rates'][step['source']]['rate'] - source_pace))
    after = by_key(chart, 'recommended')
    assert after['ready'] == truck_projection(current, result['rates'], RED_TRUCK)['finish']
    assert step['source_status_after'] in ('ON TIME', 'ALL PICKED')


def test_unknown_rate_is_never_coloured_and_explained():
    chart, _ = compare(12, 'SH0908-1057')
    before = by_key(chart, 'before')
    assert before['band'] == 'unknown' and before['ready'] is None and before['etc_text'] is None
    assert 'cannot be estimated' in chart['message'] and 'no measured pick rate' in chart['message']
    # v12: nobody on Cooler and no experienced operator -> one temporary operator at Cooler's measured rate
    temporary = by_key(chart, 'temporary')
    assert temporary['temporary'] == 1 and temporary['reallocated'] == 0 and temporary['band'] == 'green'


# ---------- rendered pages ----------
@pytest.fixture
def client():
    from app import app, _SCENARIOS
    app.config['TESTING'] = True
    _SCENARIOS.clear()
    yield app.test_client()
    _SCENARIOS.clear()


def page_chart(html, chart_id):
    match = re.search(rf'<script id="{chart_id}-data" type="application/json">(.*?)</script>', html, re.S)
    assert match
    return json.loads(match.group(1))


def test_truck_and_planner_show_same_comparison_with_labels_and_table(client, loading_override):
    loading_override(RED_TRUCK, TWO_OPERATOR_LOADING)
    truck_html = client.get(f'/truck/{RED_TRUCK}?snapshot=10').get_data(as_text=True)
    planner_html = client.get(f'/planner?snapshot=10&worktype=2&shipment={RED_TRUCK}').get_data(as_text=True)
    truck_chart, planner_chart = page_chart(truck_html, 'ready-chart'), page_chart(planner_html, 'planner-ready-chart')
    assert truck_chart['scenarios'] == planner_chart['scenarios']
    for html in (truck_html, planner_html):
        for text in ('Pick cutoff <strong>19:20</strong>', 'Safety buffer deadline <strong>19:10</strong>',
                     f'= departure − {TWO_OPERATOR_LOADING} min loading', '= cutoff − 10 min buffer',
                     'Green · On time', 'Yellow · At risk', 'Red · Pick cutoff passed', 'Blue · ETC',
                     'data-band="red"', 'data-band="green"', '13 min late', '8 min early', 'ready_chart.js'):
            assert text in html


def test_planner_chart_updates_on_selection_and_allocate(client, loading_override):
    loading_override(RED_TRUCK, TWO_OPERATOR_LOADING)
    url = f'/planner?snapshot=10&worktype=2&shipment={RED_TRUCK}'
    client.get(url)
    with client.session_transaction() as sess:
        token = sess['csrf_token']
    params = dict(csrf_token=token, snapshot=10, worktype=2, shipment=RED_TRUCK)
    client.post('/planner', data=dict(params, action='add', operator='dclements'))
    chart = page_chart(client.get(url).get_data(as_text=True), 'planner-ready-chart')
    assert by_key(chart, 'selected')['band'] == 'yellow'
    client.post('/planner', data=dict(params, action='add', operator='ekim'))
    chart = page_chart(client.get(url).get_data(as_text=True), 'planner-ready-chart')
    assert by_key(chart, 'selected')['band'] == 'green'
    client.post('/planner', data=dict(params, action='allocate', scenario_version=0))
    chart = page_chart(client.get(url).get_data(as_text=True), 'planner-ready-chart')
    assert by_key(chart, 'before')['band'] == 'red'
    assert by_key(chart, 'confirmed')['band'] == 'green' and by_key(chart, 'confirmed')['operators_added'] == 2
    client.post('/planner', data=dict(params, action='reset_scenario'))
    chart = page_chart(client.get(url).get_data(as_text=True), 'planner-ready-chart')
    assert by_key(chart, 'confirmed') is None and by_key(chart, 'recommended')['operators_added'] == 2
