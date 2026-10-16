"""v9 truck-detail simplification, updated for the v10 before/after ready-time chart."""
import json
import re

import pytest

from calculations.supervisor import build_state, recommend_minimum, preview_state
from calculations.truck_detail_view import area_recommendations
from models import database as db
from conftest import ONE_OPERATOR_LOADING, TWO_OPERATOR_LOADING

FIRST = 'SH0908-1034'
SECOND = 'SH0908-1069'


@pytest.fixture
def client():
    from app import app, _SCENARIOS
    app.config['TESTING'] = True
    _SCENARIOS.clear()
    c = app.test_client()
    yield c
    _SCENARIOS.clear()


def chart_from(response, chart_id='ready-chart'):
    """v10: the truck page chart payload is the shared before/after ready-time comparison."""
    html = response.get_data(as_text=True)
    match = re.search(rf'<script id="{chart_id}-data" type="application/json">(.*?)</script>',html,re.S)
    assert match
    return json.loads(match.group(1))


def scenario(chart, key):
    return next((s for s in chart['scenarios'] if s['key']==key), None)


def get_state():
    src=db.load_sources()
    state=build_state(src,db.worktype_context(10),db.trucks_at(10),10,db.get_loading_overrides())
    return src,state


def test_unwanted_visualizations_removed_but_underlying_tables_and_data_remain(client):
    page=client.get(f'/truck/{FIRST}?snapshot=10')
    assert page.status_code==200
    html=page.get_data(as_text=True)
    for name in ('Open lines and slack over the day', 'Lines picked per 15 min (this truck)',
                 'Pickers logged in per area', 'burn-chart', 'through-chart', 'pickers-chart',
                 'When each area finishes vs the pick cutoff', 'wt-chart'):
        assert name not in html
    assert 'Truck ready time: before vs after adding operators' in html  # v10 replacement chart
    assert 'Orders (' in html and 'Work IDs (' in html
    js=client.get('/static/js/ready_chart.js').get_data(as_text=True)
    for id_ in ('burn-chart','through-chart','pickers-chart'):
        assert id_ not in js
    assert client.get('/static/js/truck_detail.js').status_code==404  # replaced by ready_chart.js
    from calculations.detail import _trends
    assert callable(_trends)  # picking facts and historical trend calculations remain in place


def test_chart_payload_has_cutoff_buffer_etc_and_before_after(client, loading_override):
    from datetime import datetime
    green=chart_from(client.get('/truck/SH0908-1012?snapshot=10'))
    assert [s['key'] for s in green['scenarios']]==['before'] and green['scenarios'][0]['band']=='green'
    default=chart_from(client.get(f'/truck/{FIRST}?snapshot=10'))      # v14: At Risk at 18:30 by default
    assert default['buffer_minutes']==10 and default['loading_minutes']==30
    assert [s['key'] for s in default['scenarios']]==['before','recommended']
    assert default['scenarios'][0]['band']=='yellow' and default['scenarios'][1]['band']=='green'
    loading_override(FIRST, TWO_OPERATOR_LOADING)
    chart=chart_from(client.get(f'/truck/{FIRST}?snapshot=10'))
    cutoff=datetime.fromisoformat(chart['cutoff_iso'])
    buffer=datetime.fromisoformat(chart['buffer_deadline_iso'])
    departure=datetime.fromisoformat(chart['departure_iso'])
    assert int((cutoff-buffer).total_seconds())==600                       # buffer deadline = cutoff - 10 min
    assert int((departure-cutoff).total_seconds())==TWO_OPERATOR_LOADING*60  # cutoff = departure - loading
    before,after=scenario(chart,'before'),scenario(chart,'recommended')
    assert before['band']=='red' and before['ready_text']=='19:33' and before['etc_text']=='1h 03m'
    assert after['band']=='green' and after['operators']==['dclements','ekim'] and after['operators_added']==2
    assert chart['colors']=={'green':'#0ca30c','yellow':'#fab219','red':'#d03b3b','unknown':'#98a2b3','etc':'#2563eb'}
    js=client.get('/static/js/ready_chart.js').get_data(as_text=True)
    assert "type: 'bar'" in js and 'Pick cutoff' in js and 'Buffer deadline' in js


@pytest.mark.parametrize('loading,expected,names',[(ONE_OPERATOR_LOADING,1,['dclements']),
                                                   (TWO_OPERATOR_LOADING,2,['dclements','ekim'])])
def test_card_and_projection_use_same_minimum_safe_calculation(client,loading_override,loading,expected,names):
    loading_override(FIRST, loading)
    page=client.get(f'/truck/{FIRST}?snapshot=10')
    html=page.get_data(as_text=True)
    assert 'Operator Gap (Legacy Baseline)' in html
    assert f'id="minimum-operator-gap">{expected}<' in html
    assert 'priority lines' in html and 'conservative lines/hour' in html
    src,state=get_state()
    recommendation=recommend_minimum(src,state,2,FIRST)
    assert recommendation['required']==expected and recommendation['operators']==names
    projection=preview_state(src,state,2,names,shipment=FIRST)
    chart=chart_from(page)
    from calculations.excel_io import serial_to_datetime
    iso=lambda v: serial_to_datetime(v).isoformat(timespec='seconds')
    assert scenario(chart,'recommended')['operators']==names
    assert scenario(chart,'recommended')['ready_iso']==iso(projection['truck_after']['finish'])
    assert scenario(chart,'before')['ready_iso']==iso(projection['truck_before']['finish'])


def test_unconfirmed_selection_updates_chart_and_remaining_gap_without_allocating(client, loading_override):
    from app import _SCENARIOS
    loading_override(FIRST, TWO_OPERATOR_LOADING)
    original=chart_from(client.get(f'/truck/{FIRST}?snapshot=10'))
    client.get(f'/planner?snapshot=10&worktype=2&shipment={FIRST}')
    with client.session_transaction() as sess:
        token,key=sess['csrf_token'],sess['scenario_id']
    params=dict(csrf_token=token,snapshot=10,worktype=2,shipment=FIRST)
    posted=client.post('/planner',data=dict(params,action='add',operator='dclements'))
    assert posted.status_code==302
    assert not _SCENARIOS[key]['confirmed_moves']
    page=client.get(f'/truck/{FIRST}?snapshot=10')
    html=page.get_data(as_text=True)
    assert 'id="minimum-operator-gap">1<' in html
    after=chart_from(page)
    assert scenario(after,'before')==scenario(original,'before')          # original assignments unchanged
    selected=scenario(after,'selected')
    assert selected and selected['operators']==['dclements'] and selected['band']=='yellow'
    assert selected['vs_buffer']==[False,'2 min late']
    assert scenario(after,'recommended') is None and scenario(after,'confirmed') is None
    client.post('/planner',data=dict(params,action='add',operator='ekim'))
    final=client.get(f'/truck/{FIRST}?snapshot=10')
    assert 'id="minimum-operator-gap">0<' in final.get_data(as_text=True)
    selected=scenario(chart_from(final),'selected')
    assert selected['band']=='green' and selected['operators_added']==2
    assert not _SCENARIOS[key]['confirmed_moves']
    client.post('/planner',data=dict(params,action='clear'))
    reset=client.get(f'/truck/{FIRST}?snapshot=10')
    assert 'id="minimum-operator-gap">2<' in reset.get_data(as_text=True)
    assert scenario(chart_from(reset),'recommended')['operators_added']==2


def test_session_confirm_updates_current_ready_and_reset_restores_original(client, loading_override):
    from app import _SCENARIOS
    loading_override(FIRST, ONE_OPERATOR_LOADING)
    before=chart_from(client.get(f'/truck/{FIRST}?snapshot=10'))
    client.get(f'/planner?snapshot=10&worktype=2&shipment={FIRST}')
    with client.session_transaction() as sess: token,key=sess['csrf_token'],sess['scenario_id']
    params=dict(csrf_token=token,snapshot=10,worktype=2,shipment=FIRST)
    client.post('/planner',data=dict(params,action='add',operator='dclements'))
    resp=client.post('/planner',data=dict(params,action='allocate',scenario_version=0))
    assert resp.status_code==302
    assert len(_SCENARIOS[key]['confirmed_moves'])==1
    after=chart_from(client.get(f'/truck/{FIRST}?snapshot=10'))
    assert scenario(after,'before')==scenario(before,'before')   # before = original assignments
    confirmed=scenario(after,'confirmed')
    assert confirmed['band']=='green' and confirmed['operators']==['dclements'] and confirmed['confirmed']
    assert scenario(after,'recommended') is None and scenario(after,'selected') is None
    assert 'id="minimum-operator-gap">0<' in client.get(f'/truck/{FIRST}?snapshot=10').get_data(as_text=True)
    client.post('/planner',data=dict(params,action='reset_scenario'))
    restored=chart_from(client.get(f'/truck/{FIRST}?snapshot=10'))
    assert scenario(restored,'confirmed') is None
    assert restored['scenarios'][0]==before['scenarios'][0]
    assert not _SCENARIOS[key]['confirmed_moves']


def test_multiple_worktypes_are_not_double_counted_as_one_truck_requirement(loading_override):
    loading_override(FIRST, TWO_OPERATOR_LOADING)   # WT2 genuinely at risk; WT1 marked at risk below
    src,state=get_state()
    target=next(r for r in state['rows'] if r['shipment']==FIRST and r['worktype']==1)
    # Adapter should never sum independent area minimums into a fictitious joint plan.
    original_status=target['status']
    try:
        target['status']='AT RISK'
        areas,gap=area_recommendations(src,state,FIRST,10,{})
        assert gap['display']=='By area'
        assert 'do not add counts' in gap['summary']
        assert len(gap['breakdown'])==2
    finally:
        target['status']=original_status
