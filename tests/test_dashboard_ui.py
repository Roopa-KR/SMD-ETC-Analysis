"""v5 SaaS dashboard view: factual data, functional links, unchanged operational rules."""
import csv
import io
import json
import re
from html import unescape

import pytest


@pytest.fixture(scope='module')
def client():
    from app import app
    return app.test_client()


def _json_script(html, name):
    match = re.search(r'<script type="application/json" id="' + name + r'">(.*?)</script>',
                      html, re.DOTALL)
    assert match, f'Expected JSON chart data {name}'
    return json.loads(match.group(1))


def test_dashboard_contains_all_real_risk_metrics_and_charts(client):
    from models import database as db
    from calculations.dashboard_view import display_trucks, summary
    from calculations.supervisor import build_state
    resp = client.get('/?snapshot=10')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    for marker in ('Total trucks', 'On-time trucks', 'At-risk trucks', 'Critical / delayed',
                   'Truck readiness trend', 'Picking activity', 'On-time completion share',
                   'Operational insights', 'Truck performance', 'Workforce allocation',
                   '10-minute safety buffer', 'id="truck-table"', 'id="risk-trend-chart"'):
        assert marker.casefold() in html.casefold(), marker
    snap=10
    inputs=db.load_sources()
    state=build_state(inputs,db.worktype_context(snap),db.trucks_at(snap),snap,db.get_loading_overrides(),[])
    expected=summary(display_trucks(db.trucks_at(snap),state))
    actual=_json_script(html,'analytics-data')
    assert actual['metrics']==expected
    assert actual['trend'][-1]['snapshot']==snap
    assert actual['trend'][-1]['healthy']==expected['healthy']
    assert all(p['snapshot']<=snap for p in actual['trend'])
    assert expected['total']==10


def test_snapshot_filter_recalculates_metrics_and_trend(client):
    first=_json_script(client.get('/?snapshot=6').get_data(as_text=True),'analytics-data')
    second=_json_script(client.get('/?snapshot=10').get_data(as_text=True),'analytics-data')
    assert len(first['trend'])==6 and len(second['trend'])==10
    assert first['metrics']['healthy']!=second['metrics']['healthy']
    assert second['trend'][0]['completed'] is None  # first snapshot is a baseline
    assert all(x['completed'] is None or x['completed']>=0 for x in second['trend'])


def test_search_and_risk_filter_and_csv_reflect_same_shipments(client):
    html=client.get('/?snapshot=10&q=SH0908-1034').get_data(as_text=True)
    assert '1 / 10 trucks' in html
    assert 'SH0908-1034' in html
    csv_resp=client.get('/export/trucks.csv?snapshot=10&q=SH0908-1034')
    assert csv_resp.status_code==200
    assert 'attachment' in csv_resp.headers['Content-Disposition']
    rows=list(csv.DictReader(io.StringIO(csv_resp.get_data(as_text=True))))
    assert len(rows)==1 and rows[0]['shipment_id']=='SH0908-1034'
    risk_csv=client.get('/export/trucks.csv?snapshot=10&risk=risk')
    risk_rows=list(csv.DictReader(io.StringIO(risk_csv.get_data(as_text=True))))
    assert all(r['risk_category']=='risk' for r in risk_rows)
    assert len(risk_rows)==_json_script(client.get('/?snapshot=10').get_data(as_text=True),'analytics-data')['metrics']['risk']
    assert client.get('/export/trucks.csv?snapshot=999').status_code==404


def test_operator_directory_has_working_existing_profile_links(client):
    html=client.get('/operators?snapshot=10').get_data(as_text=True)
    assert 'Operator directory' in html and 'Observed' in html
    assert '/operator/hgroff?snapshot=10' in html
    assert client.get('/operator/hgroff?snapshot=10').status_code==200
    assert client.get('/operators?snapshot=99').status_code==404


def test_navigation_is_functional_and_preserves_planner(client):
    for path in ('/?snapshot=10','/operators?snapshot=10', '/planner?snapshot=10',
                 '/truck/SH0908-1034?snapshot=10', '/operator/hgroff?snapshot=10'):
        html=client.get(path).get_data(as_text=True)
        assert 'id="app-sidebar"' in html
        assert 'id="sidebar-toggle"' in html
        assert '/?snapshot=10#truck-performance' in html
        assert '/?snapshot=10#risk-trend' in html
        assert '/planner?snapshot=10#loading-settings' in html
        assert '/operators?snapshot=10' in html
    for asset in ('/static/css/style.css','/static/js/dashboard.js',
                  '/static/js/shell.js','/static/vendor/plotly.min.js'):
        response=client.get(asset)
        assert response.status_code==200 and len(response.data)>100
