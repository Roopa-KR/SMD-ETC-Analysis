"""v12: Temporary Operator Allocation — reallocation first, temporaries only for the remaining gap.

Every scenario is a genuine calculation on the 10-truck demo (v14 data: SH0908-1034 and SH0908-1069
depart 20:30 and carry late add-on OTC orders). Extra deadline pressure comes only from the existing
per-truck loading-time setting (a supervisor input); no status is forced.

    S1 safe reallocation is enough             s10 18:30 SH0908-1034 WT2 OTC        default loading (30)
    S2 no eligible operator                    s12 19:00 SH0908-1057 WT5 Cooler     default loading
    S2b no eligible operator, truck still held s11 18:45 SH0908-1034 WT6 Cases      loading 85 (WT2 holds it back)
    S3 eligible operators, all unsafe          s9  18:15 SH0908-1069 WT1 Prescr.    loading 110
    S4 some reallocation + temporaries         s9  18:15 SH0908-1057 WT1 Prescr.    loading 90 (1003: 100)
    S5 temporaries cannot be enough (> max 10) s10 18:30 SH0908-1034 WT2 OTC        loading 102
    S6 meets cutoff, not the buffer            s10 SH0908-1034 WT2, loading 100, 3 reallocated + 7 temporaries
    S7 meets cutoff and buffer                 the same with 8 temporaries
    S8 two trucks compete for lhall            s9 18:15 SH0908-1057 (90) and SH0908-1003 (100), WT1
"""
import hashlib
import json
import re

import pytest
from sqlalchemy import inspect

from calculations.ready_comparison import ready_time_comparison
from calculations.supervisor import build_state, candidates, preview_state
from calculations.temporary import temporary_requirement
from models import database as db

T1034, T1069, T1057, T1003 = 'SH0908-1034', 'SH0908-1069', 'SH0908-1057', 'SH0908-1003'
S4_LOADING = {T1057: 90, T1003: 100}
THREE = ['dclements', 'ekim', 'jmccraw']


def state(n, loading, moves=(), temps=()):
    src = db.load_sources()
    return src, build_state(src, db.worktype_context(n), db.trucks_at(n), n, loading, list(moves),
                            temporaries=list(temps))


def requirement(n, ship, wt, loading, selected=(), count=None, moves=(), temps=()):
    src, st = state(n, loading, moves, temps)
    return temporary_requirement(src, st, wt, ship, list(selected), count), src, st


def chart(n, ship, loading, previews=None, temp_previews=None, moves=(), temps=()):
    src, original = state(n, loading)
    _, current = state(n, loading, moves, temps)
    result = ready_time_comparison(src, original, current, ship, n, previews or {}, temp_previews or {})
    return {s['key']: s for s in result['scenarios']}, result


# ---------- S1: reallocation is enough, temporaries not offered ----------
def test_s1_safe_reallocation_is_enough_so_no_temporaries():
    q, _, _ = requirement(10, T1034, 2, {})
    assert q['needed'] and not q['allowed']
    assert q['realloc_possible'] and q['realloc_operators'] == ['dclements']
    assert q['temps_required'] == 0 and q['plan'] == {'realloc': ['dclements'], 'temps': 0, 'possible': True}
    assert 'Temporary operators are not needed' in q['reason']
    rows, _ = chart(10, T1034, {})
    assert rows['before']['band'] == 'yellow'
    assert rows['recommended']['band'] == 'green' and 'temporary' not in rows


# ---------- S2: no eligible operator ----------
def test_s2_no_eligible_operator_requires_temporaries():
    q, src, st = requirement(12, T1057, 5, {})
    assert candidates(src, st, 5) == []
    assert q['allowed'] and q['safe_available_count'] == 0 and q['plan'] == {'realloc': [], 'temps': 1, 'possible': True}
    assert q['total_required'] == 1 and q['temps_required'] == 1 and q['band'] == 'green'
    assert 'No experienced existing operator' in q['reason']
    rows, _ = chart(12, T1057, {})
    assert rows['before']['band'] == 'unknown' and 'recommended' not in rows
    assert rows['temporary']['temporary'] == 1 and rows['temporary']['reallocated'] == 0
    assert rows['temporary']['band'] == 'green'


def test_s2b_temporaries_fix_the_area_but_the_truck_is_still_held_back_elsewhere():
    q, src, st = requirement(11, T1034, 6, {T1034: 85})
    assert candidates(src, st, 6) == []
    assert q['plan'] == {'realloc': [], 'temps': 3, 'possible': True} and q['target_status'] == 'ON TIME'
    assert q['truck_status'] == 'PICK CUTOFF PASSED' and q['band'] == 'red'          # never shown as success
    assert [b['worktype'] for b in q['blocking']] == [2]
    assert 'still held back by WT 2 OTC' in q['next_action']
    rows, _ = chart(11, T1034, {T1034: 85})
    assert rows['before']['band'] == 'red'
    assert rows['temporary']['band'] == 'green' and rows['temporary']['reallocated'] == 2   # OTC planned too


# ---------- S3: eligible operators exist but every move is unsafe ----------
def test_s3_eligible_but_unsafe_operators_are_not_moved():
    q, src, st = requirement(9, T1069, 1, {T1069: 110})
    listed = candidates(src, st, 1)
    assert listed and not any(c['safe'] for c in listed)          # experienced, but unsafe to move
    assert q['allowed'] and q['plan'] == {'realloc': [], 'temps': 2, 'possible': True} and q['band'] == 'green'
    rows, _ = chart(9, T1069, {T1069: 110})
    assert rows['temporary']['reallocated'] == 0 and rows['temporary']['temporary'] == 2


# ---------- S4: some reallocation, plus temporaries ----------
def test_s4_reallocation_first_then_temporaries_for_the_remaining_gap():
    q, _, _ = requirement(9, T1057, 1, S4_LOADING)
    assert q['allowed'] and q['plan'] == {'realloc': ['lhall'], 'temps': 1, 'possible': True}
    assert q['temps_required'] == 2                       # without moving lhall first
    assert 'Reallocating lhall first would reduce the temporary operators needed to 1' in q['next_action']
    selected, _, _ = requirement(9, T1057, 1, S4_LOADING, selected=['lhall'])
    assert selected['selected_count'] == 1 and selected['temps_required'] == 1 and selected['total_required'] == 2
    assert selected['band'] == 'green' and selected['meets_buffer']
    rows, _ = chart(9, T1057, S4_LOADING)
    assert rows['temporary']['reallocated'] == 1 and rows['temporary']['temporary'] == 1
    assert rows['temporary']['band'] == 'green'


# ---------- S5: temporaries cannot be enough ----------
def test_s5_temporaries_insufficient_shows_gap_and_next_action():
    q, _, _ = requirement(10, T1034, 2, {T1034: 102})
    assert q['allowed'] and not q['temps_possible'] and not q['plan']['possible']
    assert q['plan']['temps'] == 11 and q['total_required'] == 14 and q['remaining_gap'] == 14
    assert 'Even 10 temporary operators cannot meet the deadline' in q['next_action']
    assert q['band'] == 'red' and not q['meets_cutoff']
    rows, result = chart(10, T1034, {T1034: 102})
    assert list(rows) == ['before'] and 'configured maximum is 10' in result['message']
    # a supervisor-chosen count below the requirement is never shown as success
    short, _, _ = requirement(9, T1057, 1, S4_LOADING, selected=['lhall'], count=0)
    assert short['remaining_gap'] == 1 and short['band'] != 'green' and not short['meets_buffer']
    assert 'Add 1 more temporary operator' in short['next_action']


# ---------- S6 / S7: buffer kept or not ----------
def test_s6_meets_cutoff_but_not_buffer_is_yellow_never_green():
    q, _, _ = requirement(10, T1034, 2, {T1034: 100}, selected=THREE, count=7)
    assert q['band'] == 'yellow' and q['meets_cutoff'] and not q['meets_buffer'] and q['remaining_gap'] == 1
    rows, result = chart(10, T1034, {T1034: 100}, previews={f'10:2:{T1034}': THREE},
                         temp_previews={f'10:2:{T1034}': 7})
    assert rows['temporary']['band'] == 'yellow' and rows['temporary']['temporary'] == 7
    assert 'still does not meet the safety buffer deadline' in result['message']


def test_s7_meets_cutoff_and_buffer_is_green():
    q, _, _ = requirement(10, T1034, 2, {T1034: 100}, selected=THREE, count=8)
    assert q['band'] == 'green' and q['meets_cutoff'] and q['meets_buffer'] and q['remaining_gap'] == 0
    rows, _ = chart(10, T1034, {T1034: 100}, previews={f'10:2:{T1034}': THREE},
                    temp_previews={f'10:2:{T1034}': 8})
    assert rows['temporary']['band'] == 'green'


# ---------- S8: two trucks compete for the same operator ----------
def test_s8_competing_trucks_recalculate_after_one_allocation():
    loading = S4_LOADING
    first, src, st = requirement(9, T1057, 1, loading)
    second, _, _ = requirement(9, T1003, 1, loading)
    assert first['plan'] == {'realloc': ['lhall'], 'temps': 1, 'possible': True}
    assert second['plan'] == {'realloc': ['lhall'], 'temps': 6, 'possible': True}   # same operator wanted
    step = preview_state(src, st, 1, ['lhall'], shipment=T1057)['steps'][0]
    move = dict(operator='lhall', source=step['source'], dest=1, start_snapshot=9, destination_pace=step['pace'])
    temp = dict(id='TEMP-1', dest=1, count=1, start_snapshot=9, shipment=T1057, pace_pct=100)
    after, _, current = requirement(9, T1003, 1, loading, moves=[move], temps=[temp])
    assert 'lhall' not in after['safe_available'] and after['plan']['realloc'] == []
    assert after['plan']['temps'] < second['plan']['temps'] + 1 and after['plan']['possible']
    statuses = {t['shipment']: t['status'] for t in current['trucks']}
    assert statuses[T1057] == 'ON TIME' and statuses[T1003] in ('AT RISK', 'PICK CUTOFF PASSED')
    rows, _ = chart(9, T1003, loading, moves=[move], temps=[temp])
    assert rows['confirmed']['temporary'] == 1 and rows['temporary']['band'] == 'green'


# ---------- engine: confirmed temporaries ----------
def test_confirmed_temporaries_add_assumed_pace_only_from_their_snapshot():
    loading = {}
    _, base = state(12, loading)
    temp = dict(id='TEMP-1', dest=5, count=1, start_snapshot=12, shipment=T1057, pace_pct=100)
    _, with_temps = state(12, loading, temps=[temp])
    pace = with_temps['temporaries_applied'][0]['pace']
    assert pace == pytest.approx(base['baseline'][5]['per_person'])            # 100% of per-person rate
    assert with_temps['rates'][5]['resources'] == base['rates'][5]['resources'] + 1
    assert with_temps['rates'][5]['rate'] == pytest.approx((base['rates'][5]['rate'] or 0) + pace)
    assert next(t for t in with_temps['trucks'] if t['shipment'] == T1057)['status'] == 'ON TIME'
    _, earlier = state(11, loading, temps=[temp])
    assert earlier['temporaries_applied'] == [] and earlier['rates'][5] == state(11, loading)[1]['rates'][5]
    assert base['temporaries_applied'] == []   # original state untouched


# ---------- web workflow ----------
@pytest.fixture
def client():
    from app import app, _SCENARIOS
    app.config['TESTING'] = True
    _SCENARIOS.clear()
    yield app.test_client()
    _SCENARIOS.clear()


def page_chart(html, chart_id='planner-ready-chart'):
    match = re.search(rf'<script id="{chart_id}-data" type="application/json">(.*?)</script>', html, re.S)
    return {s['key']: s for s in json.loads(match.group(1))['scenarios']}


def start(client, snapshot, wt, ship):
    url = f'/planner?snapshot={snapshot}&worktype={wt}&shipment={ship}'
    client.get(url)
    with client.session_transaction() as sess:
        token, key = sess['csrf_token'], sess['scenario_id']
    return url, key, dict(csrf_token=token, snapshot=snapshot, worktype=wt, shipment=ship)


def test_planner_panel_shows_required_counts_and_assumed_pace(client, loading_override):
    loading_override(T1057, 90)
    loading_override(T1003, 100)
    html = client.get(f'/planner?snapshot=9&worktype=1&shipment={T1057}').get_data(as_text=True)
    for text in ('id="temporary-operators"', 'Additional operators required in total',
                 'Existing operators safely available', 'Selected for reallocation',
                 'Temporary operators still required', 'Expected ready after proposed allocation',
                 'SYNTHESIZED ASSUMPTION', 'Allocate Temporary Operators', 'Use recommended plan'):
        assert text in html
    assert re.search(r'data-temp="total">2<', html) and re.search(r'data-temp="required">2<', html)


def test_temporaries_refused_when_safe_reallocation_is_enough(client, loading_override):
    from app import _SCENARIOS
    url, key, form = start(client, 10, 2, T1034)       # default loading: dclements alone is enough
    assert 'Allocate Temporary Operators' not in client.get(url).get_data(as_text=True)
    client.post('/planner', data=dict(form, action='temp_set', temp_count=1))
    assert _SCENARIOS[key]['temp_preview'] == {}
    assert 'Safe reallocation is enough' in client.get(url).get_data(as_text=True)


def test_recommended_plan_preview_allocate_and_reset_are_session_only(client, loading_override):
    from app import _SCENARIOS
    loading_override(T1057, 90)
    loading_override(T1003, 100)
    workbook = hashlib.sha256(open('data/workbook.xlsx', 'rb').read()).hexdigest()
    url, key, form = start(client, 9, 1, T1057)
    client.post('/planner', data=dict(form, action='temp_plan'))
    assert _SCENARIOS[key]['preview'] == {f'9:1:{T1057}': ['lhall']}
    assert _SCENARIOS[key]['temp_preview'] == {f'9:1:{T1057}': 1}
    rows = page_chart(client.get(url).get_data(as_text=True))
    assert rows['selected']['reallocated'] == 1 and rows['temporary']['temporary'] == 1
    assert rows['temporary']['band'] == 'green' and not _SCENARIOS[key]['confirmed_temps']
    response = client.post('/planner', data=dict(form, action='allocate_temps', scenario_version=0),
                           follow_redirects=True)
    assert 'now meets its safety buffer deadline' in response.get_data(as_text=True)
    memory = _SCENARIOS[key]
    assert [m['operator'] for m in memory['confirmed_moves']] == ['lhall']
    assert [(t['dest'], t['count']) for t in memory['confirmed_temps']] == [(1, 1)]
    assert memory['preview'] == {} and memory['temp_preview'] == {}
    rows = page_chart(client.get(url).get_data(as_text=True))
    assert rows['confirmed']['band'] == 'green' and rows['confirmed']['temporary'] == 1
    assert rows['before']['band'] in ('yellow', 'red')            # original assignments kept
    operators = client.get('/operators?snapshot=9').get_data(as_text=True)
    assert 'role-reallocated' in operators and 'TEMP-1-1' in operators and 'role-temporary' in operators
    truck = client.get(f'/truck/{T1057}?snapshot=9').get_data(as_text=True)
    assert '1 temporary' in truck
    assert not inspect(db.engine).has_table('scenario_allocation')
    assert hashlib.sha256(open('data/workbook.xlsx', 'rb').read()).hexdigest() == workbook
    other = __import__('app').app.test_client()                    # another supervisor session
    assert 'TEMP-1-1' not in other.get('/operators?snapshot=9').get_data(as_text=True)
    client.post('/planner', data=dict(form, action='reset_scenario'))
    assert memory['confirmed_moves'] == [] and memory['confirmed_temps'] == []
    assert 'confirmed' not in page_chart(client.get(url).get_data(as_text=True))


def test_supervisor_count_preview_shows_gap_and_rejects_out_of_range(client, loading_override):
    from app import _SCENARIOS
    loading_override(T1069, 110)
    url, key, form = start(client, 9, 1, T1069)
    client.post('/planner', data=dict(form, action='temp_set', temp_count=1))
    html = client.get(url).get_data(as_text=True)
    assert 'Add 1 more temporary operator' in html and page_chart(html)['temporary']['band'] != 'green'
    client.post('/planner', data=dict(form, action='temp_set', temp_count=99))
    assert _SCENARIOS[key]['temp_preview'] == {f'9:1:{T1069}': 1}  # rejected, unchanged
    client.post('/planner', data=dict(form, action='temp_set', temp_count=2))
    client.post('/planner', data=dict(form, action='allocate_temps', scenario_version=0))
    assert _SCENARIOS[key]['confirmed_temps'][0]['count'] == 2
    assert page_chart(client.get(url).get_data(as_text=True))['confirmed']['band'] == 'green'
    dashboard = client.get('/?snapshot=9').get_data(as_text=True)
    assert '0 reallocated · 2 temporary operators' in dashboard
