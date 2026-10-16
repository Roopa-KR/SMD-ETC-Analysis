"""New buffered-deadline, experience, manual preview and session-only confirmation checks."""
import pytest

from calculations.supervisor import (DEFAULT_LOADING_MINUTES, SAFETY_BUFFER_MINUTES,
                                     assignment_risks, build_state, candidates, preview_state)


def snapshot_state(snapshot=10, loading=None, moves=()):
    from models import database as db
    src = db.load_sources()
    return src, build_state(src, db.worktype_context(snapshot), db.trucks_at(snapshot),
                            snapshot, loading or {}, moves)


def test_fixed_buffer_default_and_per_truck_override():
    src, state = snapshot_state()
    assert SAFETY_BUFFER_MINUTES == 10 and DEFAULT_LOADING_MINUTES == 30
    assert all(abs((v['departure']-v['deadline'])*1440-40) < 1e-5 for v in state['trucks'])
    ship = state['trucks'][0]['shipment']
    _, changed = snapshot_state(10,{ship:45})
    target = next(t for t in changed['trucks'] if t['shipment'] == ship)
    assert target['loading_minutes'] == 45
    assert abs((target['departure']-target['deadline'])*1440-55)<1e-5
    assert target['deadline'] != next(t for t in state['trucks'] if t['shipment'] == ship)['deadline']


def test_monthly_coverage_label_is_not_faked():
    src, state = snapshot_state()
    assert state['pace_info']['observed_days'] == 1
    assert state['pace_info']['monthly_qualified'] is False
    assert 'NOT reliable monthly' in state['pace_info']['label']
    assert len(state['stats']) >= 12


def test_all_familiar_candidates_visible_and_sorted_unsafe_flagged():
    src, state = snapshot_state()
    cs = candidates(src, state, 2)
    assert len(cs) >= 5
    assert any(not c['safe'] for c in cs)
    assert any(c['safe'] for c in cs)
    safe = [c['pace'] for c in cs if c['safe'] and c['pace'] is not None]
    assert safe == sorted(safe, reverse=True)
    for candidate in cs:
        assert ('SIMULATED' in candidate['experience'] or 'observed' in candidate['experience'])
        assert candidate['source'] != 2
    assert not any(x['operator']=='jmccraw' for x in candidates(src, state, 6))  # current source


def test_preview_does_not_modify_immutable_baseline_and_enforces_safety():
    src, state = snapshot_state()
    before = {w: dict(v) for w,v in state['rates'].items()}
    safe = next(c for c in candidates(src,state,2) if c['safe'])
    viewed = preview_state(src,state,2,[safe['operator']])
    assert viewed['steps'] and viewed['selected']==[safe['operator']]
    assert viewed['rate_after']['resources'] == before[2]['resources']+1
    assert viewed['rate_after']['rate'] > before[2]['rate']
    assert state['rates'] == before
    unsafe = next(c for c in candidates(src,state,2) if not c['safe'])
    with pytest.raises(ValueError, match='no longer safe/eligible'):
        preview_state(src,state,2,[unsafe['operator']])
    with pytest.raises(ValueError, match='twice'):
        preview_state(src,state,2,[safe['operator'],safe['operator']])


def test_confirmation_applies_on_future_snapshots_not_before():
    src, state = snapshot_state()
    c = next(c for c in candidates(src,state,2) if c['safe'])
    move = {'operator':c['operator'],'source':c['source'],'dest':2,
            'destination_pace':c['pace'],'start_snapshot':10}
    assert snapshot_state(9,{},[move])[1]['applied'] == []
    after = snapshot_state(10,{},[move])[1]
    assert len(after['applied']) == 1
    assert after['rates'][2]['resources'] == state['rates'][2]['resources']+1
    later = snapshot_state(11,{},[move])[1]
    # Guard: if a worker has left/changed source in a subsequent snapshot,
    # a scenario must not silently create an imaginary active picker.
    assert move['operator'] in ([x['operator'] for x in later['applied']] + later['skipped'])


def test_assignment_flags_match_parent_worktype():
    src, state = snapshot_state()
    flags = assignment_risks(src,state)
    assert flags
    by_key = {(r['shipment'],r['worktype']):r['status'] for r in state['rows']}
    assert all(f['status']==by_key[(f['shipment'],f['worktype'])] for f in flags)
    assert len({f['assignment'] for f in flags}) > 10


def test_preview_and_explicit_allocation_are_separate_client_steps():
    from app import app, supervisor_scenario
    from models import database as db
    app.testing = True
    c = app.test_client()
    assert c.get('/planner?snapshot=10&worktype=2&shipment=SH0908-1034').status_code == 200
    with c.session_transaction() as s: token = s['csrf_token']
    payload=dict(snapshot=10,worktype=2,shipment='SH0908-1034',csrf_token=token)
    assert c.post('/planner',data=dict(payload,action='add',operator='jmccraw')).status_code==302
    with c.session_transaction() as s:
        assert 'confirmed_moves' not in s and 'preview' not in s  # cookie has no allocations
        key=s['scenario_id']
    from app import _SCENARIOS
    assert _SCENARIOS[key]['confirmed_moves'] == []
    assert _SCENARIOS[key]['preview']['10:2:SH0908-1034']==['jmccraw']
    assert c.post('/planner',data=dict(payload,action='allocate',scenario_version=0)).status_code==302
    assert len(_SCENARIOS[key]['confirmed_moves'])==1
    assert _SCENARIOS[key]['confirmed_moves'][0]['shipment'] == 'SH0908-1034'
    assert not _SCENARIOS[key]['preview'].get('10:2:SH0908-1034')
    assert c.get('/planner?snapshot=11&worktype=2').status_code == 200
    # Confirmed allocation was NOT written to a new staffing/approval table.
    from sqlalchemy import inspect
    assert 'confirmed_allocation' not in inspect(db.engine).get_table_names()
    assert c.post('/planner',data=dict(payload,action='reset_scenario')).status_code==302
    assert not _SCENARIOS[key]['confirmed_moves']


def test_loading_override_database_persistence_and_csrf():
    from app import app
    from models import database as db
    c = app.test_client()
    c.get('/planner?snapshot=10&worktype=2')
    with c.session_transaction() as s: token=s['csrf_token']
    p=dict(snapshot=10,worktype=2,action='loading',shipment='SH0908-1034',minutes=48)
    assert c.post('/planner', data=dict(p,csrf_token='BAD')).status_code==400
    prior = db.get_loading_overrides().get('SH0908-1034')
    try:
        assert c.post('/planner',data=dict(p,csrf_token=token)).status_code==302
        assert db.get_loading_overrides()['SH0908-1034']==48
        # A second client gets the saved per-truck setting, not the first's session.
        assert 'value="48"' in app.test_client().get(
            '/planner?snapshot=10&worktype=2&shipment=SH0908-1034').get_data(as_text=True)
    finally:
        db.set_loading_override('SH0908-1034',prior)
    assert 'SH0908-1981' not in db.get_loading_overrides()
