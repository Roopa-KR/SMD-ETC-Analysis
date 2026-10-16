"""v8 acceptance tests (updated v14): ten-truck demo, calculated (never forced) risk, session-only allocation.

v14 synthesized late add-on OTC orders, so the default snapshot has two calculated At Risk trucks
(SH0908-1034, SH0908-1069). Stronger pressure comes from the existing per-truck loading-time setting
(see conftest.py)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from sqlalchemy import inspect
import pytest

from calculations.excel_io import load_inputs
from calculations.supervisor import (SAFETY_BUFFER_MINUTES,build_state,candidates,
                                     preview_state,recommend_minimum,truck_projection)
from models import database as db
from conftest import ONE_OPERATOR_LOADING, TWO_OPERATOR_LOADING

FIRST='SH0908-1034'
SECOND='SH0908-1069'


def state(snapshot=10, moves=(), loading=None):
    src=db.load_sources()
    return src,build_state(src,db.worktype_context(snapshot),db.trucks_at(snapshot),
                           snapshot, loading if loading is not None else db.get_loading_overrides(),moves)


@pytest.fixture
def client():
    from app import app,_SCENARIOS
    app.config['TESTING']=True
    _SCENARIOS.clear()
    c=app.test_client()
    yield c
    _SCENARIOS.clear()


def test_only_ten_trucks_in_active_workbook_database_and_all_snapshots():
    data=load_inputs('data/workbook.xlsx')
    assert len(data.shipments)==10
    ids=set(data.shipments.SHIPMENTID)
    assert len(data.orders)==133 and len(data.line_map)==315     # v14: +4 late add-on orders, +32 lines
    assert set(data.orders.SHIPMENTID).issubset(ids)
    assert set(data.orders.ORIGINAL_SHIPMENTID).issubset(ids)
    assert set(data.line_map.SHIPMENTID).issubset(ids)
    assert set(data.ti.TI102ID).issubset(set(data.line_map.TI102ID))
    assert set(data.tc.TI102ID).issubset(set(data.line_map.TI102ID))
    for snap in range(1,19):
        assert {t.shipment_id for t in db.trucks_at(snap)}==ids
    assert 'SH0908-1981' not in ids


def test_default_statuses_are_calculated_and_pressure_creates_genuine_risk():
    src,st=state(loading={})
    assert len(st['trucks'])==10
    statuses=Counter(t['status'] for t in st['trucks'])
    assert statuses=={'ON TIME':4,'ALL PICKED':4,'AT RISK':2}   # v14: two calculated At Risk trucks at 18:30
    assert {t['shipment'] for t in st['trucks'] if t['status']=='AT RISK'}=={FIRST,SECOND}
    for t in st['trucks']:
        assert abs((t['departure']-t['deadline'])*1440-(t['loading_minutes']+SAFETY_BUFFER_MINUTES))<0.01
        if t['status']=='ON TIME':
            assert t['conservative_ready']<=t['deadline']+1e-9
        if t['status']=='AT RISK':
            assert t['deadline']<t['conservative_ready']<=t['cutoff']+1e-9
    _,pressed=state(loading={FIRST:TWO_OPERATOR_LOADING})
    changed={t['shipment']:t['status'] for t in pressed['trucks']}
    assert changed[FIRST]=='PICK CUTOFF PASSED'          # ready 19:33 > pick cutoff 19:20 (projected)
    first=next(t for t in pressed['trucks'] if t['shipment']==FIRST)
    assert first['conservative_ready']>first['cutoff']
    assert any(r['shipment']==FIRST and r['open']>0 and r['conservative_ready']>r['deadline'] for r in pressed['rows'])
    # An earlier FIRST deadline puts FIRST's lines ahead of later trucks that share a work type; every
    # other status change must be explained by more lines ahead, never by anything else.
    before={t['shipment']:t['status'] for t in st['trucks']}
    ahead={(r['shipment'],r['worktype']):r['ahead'] for r in st['rows']}
    for ship,status in changed.items():
        if ship==FIRST or status==before[ship]:
            continue
        assert any(r['shipment']==ship and r['open'] and r['ahead']>ahead[(ship,r['worktype'])]
                   and any(f['shipment']==FIRST and f['worktype']==r['worktype'] and f['open'] for f in pressed['rows'])
                   for r in pressed['rows']), ship


def test_exact_minimum_operators_uses_feasible_combinations():
    for loading,needed,names in [(ONE_OPERATOR_LOADING,1,['dclements']),(TWO_OPERATOR_LOADING,2,['dclements','ekim'])]:
        src,st=state(loading={FIRST:loading})
        result=recommend_minimum(src,st,2,FIRST)
        assert result['required']==needed and result['possible']
        assert result['operators']==names
        assert 'priority lines' in result['explanation']
        projected=preview_state(src,st,2,names,shipment=FIRST)
        assert projected['truck_after']['status']=='ON TIME'
        assert projected['truck_after']['finish']<=projected['truck_after']['deadline']+1e-9
        for step in projected['steps']:
            assert step['safe']
            assert step['source_after']['status'] in ('ON TIME','ALL PICKED')


def test_one_is_insufficient_under_more_pressure_but_enough_under_less():
    src,st=state(loading={FIRST:TWO_OPERATOR_LOADING})
    one=preview_state(src,st,2,['dclements'],shipment=FIRST)
    assert one['truck_after']['status']=='AT RISK'      # 19:12: after the buffer deadline, before the cutoff
    assert recommend_minimum(src,st,2,FIRST,['dclements'])['required']==1
    src,easier=state(loading={FIRST:ONE_OPERATOR_LOADING})
    first=preview_state(src,easier,2,['dclements'],shipment=FIRST)
    assert first['truck_after']['status']=='ON TIME'
    assert recommend_minimum(src,easier,2,FIRST,['dclements'])['required']==0
    assert state(loading={FIRST:TWO_OPERATOR_LOADING})[1]['trucks']==st['trucks']  # preview is pure


def test_unsafe_source_remains_listed_and_cannot_be_previewed():
    src,st=state()
    options=candidates(src,st,2)
    assert any(not c['safe'] for c in options)
    assert any(c['safe'] for c in options)
    assert all('SIMULATED' in c['experience'] or 'observed' in c['experience'] for c in options)
    assert not any(c['operator']=='unknown-worker' for c in options)
    safe=[c for c in options if c['safe']]
    assert [c['pace'] for c in safe]==sorted((c['pace'] for c in safe),reverse=True)
    with pytest.raises(ValueError,match='no longer safe/eligible'):
        preview_state(src,st,2,[next(c['operator'] for c in options if not c['safe'])],shipment=FIRST)


def test_loading_time_and_buffer_affect_deadlines_risk():
    src,original=state()
    sh=FIRST
    _,changed=state(10,loading={sh:45})
    before=next(t for t in original['trucks'] if t['shipment']==sh)
    after=next(t for t in changed['trucks'] if t['shipment']==sh)
    assert SAFETY_BUFFER_MINUTES==10
    assert abs((before['deadline']-after['deadline'])*1440-15)<0.01
    assert abs((after['departure']-after['deadline'])*1440-55)<0.01


def test_session_preview_never_allocates_until_explicit_confirmation(client, loading_override):
    from app import _SCENARIOS
    from sqlalchemy import inspect
    loading_override(FIRST, ONE_OPERATOR_LOADING)
    page=client.get(f'/planner?snapshot=10&worktype=2&shipment={FIRST}')
    assert page.status_code==200 and b'1 more operator' in page.data
    assert b'Unsafe / unavailable' in page.data
    assert b'SYNTHETIC' in page.data
    with client.session_transaction() as sess:
        token,key=sess['csrf_token'],sess['scenario_id']
    fields=dict(csrf_token=token,snapshot=10,worktype=2,shipment=FIRST)
    assert client.post('/planner',data=dict(fields,action='add',operator='dclements')).status_code==302
    assert not _SCENARIOS[key]['confirmed_moves']
    assert _SCENARIOS[key]['preview']=={'10:2:SH0908-1034':['dclements']}
    preview=client.get(f'/planner?snapshot=10&worktype=2&shipment={FIRST}')
    assert preview.status_code==200
    assert b'source-impact-chart' in preview.data
    assert b'No further operator required' in preview.data
    assert client.post('/planner',data=dict(fields,action='allocate',scenario_version=0)).status_code==302
    assert [r['operator'] for r in _SCENARIOS[key]['confirmed_moves']]==['dclements']
    assert not inspect(db.engine).has_table('scenario_allocation')
    assert next(t for t in state(moves=_SCENARIOS[key]['confirmed_moves'])[1]['trucks']
                if t['shipment']==FIRST)['status']=='ON TIME'
    assert client.post('/planner',data=dict(fields,action='reset_scenario')).status_code==302
    assert _SCENARIOS[key]['confirmed_moves']==[]


def test_two_sessions_are_isolated_and_historical_source_unchanged(client):
    from app import _SCENARIOS,app
    client.get('/planner?snapshot=10&worktype=2')
    other=app.test_client()
    other.get('/planner?snapshot=10&worktype=2')
    with client.session_transaction() as s: token,key=s['csrf_token'],s['scenario_id']
    with other.session_transaction() as s: other_key=s['scenario_id']
    assert key!=other_key
    client.post('/planner',data=dict(csrf_token=token,snapshot=10,worktype=2,
                                      shipment=FIRST,action='add',operator='dclements'))
    client.post('/planner',data=dict(csrf_token=token,snapshot=10,worktype=2,
                                      shipment=FIRST,action='allocate',scenario_version=0))
    assert _SCENARIOS[other_key]['confirmed_moves']==[]
    assert db.trucks_at(10)[0].shipment_id in set(db.load_sources().orders.ORIGINAL_SHIPMENTID)


def test_ui_and_export_all_reference_same_ten_trucks(client):
    assert client.get('/').status_code==200
    result=client.get('/export/trucks.csv?snapshot=10')
    assert result.status_code==200
    assert len(result.data.decode().splitlines())==11
    assert b'SH0908-1981' not in result.data
    for endpoint in ['/operators?snapshot=10','/operator/hgroff?snapshot=10',
                     f'/truck/{FIRST}?snapshot=10',f'/truck/{SECOND}?snapshot=10',
                     '/api/snapshots/10/at-risk-pickups',
                     '/api/snapshots/10/worktypes/2/eligible-operators']:
        r=client.get(endpoint)
        assert r.status_code==200,endpoint
    assert client.get('/truck/SH0908-1981?snapshot=10').status_code==404


def test_source_history_explicitly_archived_and_synthesized_rates_labelled():
    assert Path('INFO/historical/historical_33_trucks_reference.xlsx').exists()
    src,st=state()
    assert st['pace_info']['observed_days']==1
    assert not st['pace_info']['monthly_qualified']
    assert 'NOT reliable monthly' in st['pace_info']['label']
    assert any('SIMULATED' in c['experience'] for c in candidates(src,st,2))
