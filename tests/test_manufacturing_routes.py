"""Real Flask/SQLite integration checks. Skips explicitly if Flask isn't installed.

Run after installing requirements-dev.txt: python -m pytest -q tests/test_manufacturing_routes.py
"""
from io import BytesIO

import pytest
pytest.importorskip('flask', reason='Flask dependency unavailable; route tests require Flask')
from PIL import Image
from app import create_app


@pytest.fixture
def client(tmp_path):
    application=create_app({
        'TESTING':True, 'SECRET_KEY':'integration-test-only',
        'DEMO_DB':str(tmp_path/'demo.sqlite3'),
        'EVIDENCE_DIR':str(tmp_path/'evidence'),
    })
    with application.test_client() as client:
        yield client


def csrf(client):
    response=client.get('/quality/TANK-0020/CTQ-003')
    assert response.status_code==200
    with client.session_transaction() as sess:
        return sess['csrf_token']


@pytest.mark.parametrize('url',[
    '/', '/units', '/units/TANK-0020', '/work-centers',
    '/work-centers/WC1', '/workers', '/workers/W-012',
    '/quality', '/quality/TANK-0020/CTQ-003', '/recovery',
    '/api/snapshot', '/api/units', '/api/tank-performance', '/api/ctq',
    '/exports/units.csv',
])
def test_all_get_routes_render_without_server_error(client,url):
    response=client.get(url)
    assert response.status_code==200, (url,response.data[:500])


def test_replay_hides_future_and_other_scenario_events(client):
    normal=client.get('/api/snapshot?scenario=normal&asof=10:55').json
    assert not any(e['type'] in ('scrap','absence') for e in normal['events'])
    before=client.get('/api/snapshot?scenario=combined&asof=10:45').json
    assert not any(e['type']=='scrap' for e in before['events'])
    after=client.get('/api/snapshot?scenario=combined&asof=10:55').json
    assert any(e['type']=='scrap' for e in after['events'])
    assert after['metrics']['good']==6
    assert (after['metrics']['good']+after['metrics']['open_wip']+after['metrics']['scrapped']
            ==after['metrics']['total_tanks'])


def test_csv_respects_ui_filters(client):
    resp=client.get('/exports/units.csv?type=Cover&status=Queued')
    lines=resp.data.decode('utf-8').splitlines()
    assert resp.status_code==200
    assert len(lines)==2
    assert 'COVER-1003' in lines[1]
    assert not any('TANK-' in line for line in lines)


def test_csrf_blocks_unsafe_post_and_valid_token_works(client):
    assert client.post('/api/recovery/approve',data={'worker_id':'W-012'}).status_code==403
    token=csrf(client)
    approved=client.post('/api/recovery/approve',data={
        'csrf_token':token,'worker_id':'W-012','actor':'Test supervisor'
    })
    assert approved.status_code==302
    snap=client.get('/api/snapshot').json
    assert snap['metrics']['total_tanks']==11
    assert snap['metrics']['on_time_tanks']==10
    reset=client.post('/api/recovery/reset',data={'csrf_token':token})
    assert reset.status_code==302
    assert client.get('/api/snapshot').json['metrics']['total_tanks']==10


def test_numeric_measurement_blocks_missing_fields_and_stage_skips(client):
    token=csrf(client)
    assert client.post('/quality/TANK-0020/CTQ-007',data={
        'csrf_token':token,'value':'1200','manual_verdict':'PASS',
        'note':'Drawing reviewed'}).status_code==409
    assert client.post('/quality/TANK-0020/CTQ-003',data={
        'csrf_token':token,'value':'nan','manual_verdict':'PASS',
        'note':'Drawing reviewed'}).status_code==400
    for check in ['CTQ-003','CTQ-004','CTQ-005','CTQ-006']:
        result=client.post('/quality/TANK-0020/'+check,data={
            'csrf_token':token,'value':'1200','manual_verdict':'PASS',
            'note':'Synthetic inspector checked reference drawing'})
        assert result.status_code==302
    next_stage=next(u for u in client.get('/api/units').json if u['id']=='TANK-0020')
    assert next_stage['wc']=='WC2'
    assert next_stage['status']=='Ready for next stage'
    assert next_stage['progress']==25


def test_first_stage_fail_is_immutable_and_decrements_forecast(client):
    token=csrf(client)
    response=client.post('/quality/TANK-0020/CTQ-003',data={
        'csrf_token':token,'value':'1207','manual_verdict':'FAIL',
        'note':'Synthetic drawing limit exceeded'})
    assert response.status_code==302
    data=client.get('/api/snapshot?scenario=combined&asof=10:55').json
    assert data['metrics']['forecast']==8
    assert 'Recalc needed' in data['scenario']['finish']
    assert client.post('/quality/TANK-0020/CTQ-004',data={
        'csrf_token':token,'value':'10','manual_verdict':'PASS',
        'note':'Test'}).status_code==409
    early=client.get('/api/snapshot?scenario=combined&asof=10:45').json
    assert early['metrics']['forecast']==10
    assert early['metrics']['scrapped']==0


def test_required_evidence_rejects_empty_and_retains_audit_history(client):
    token=csrf(client)
    path='/quality/TANK-0017/CTQ-012'
    no_image=client.post(path,data={'csrf_token':token,'value':'Yes'})
    assert no_image.status_code==302
    image=BytesIO()
    Image.new('RGB',(3,3)).save(image,format='PNG')
    image.seek(0)
    with_image=client.post(path,data={
        'csrf_token':token,'value':'Yes',
        'evidence':(image,'test.png')},content_type='multipart/form-data')
    assert with_image.status_code==302
    evidence=client.get('/quality/evidence/TANK-0017/CTQ-012')
    assert evidence.status_code==200
    assert evidence.data.startswith(b'\x89PNG')
    passport=client.get('/units/TANK-0017')
    assert b'Inspection change history' in passport.data
    assert b'Evidence stored' in passport.data


def test_errors_are_not_silently_accepted(client):
    assert client.get('/work-centers/WC999').status_code==404
    assert client.get('/units/NOT-A-UNIT').status_code==404
    assert client.get('/quality/TANK-0020/INVALID').status_code==404
    assert client.get('/quality/evidence/TANK-0020/CTQ-003').status_code==404
    assert client.get('/api/recovery/check/W-INVALID').status_code==404


@pytest.mark.parametrize('url', ['/operator','/work-orders','/lms','/api/operator/tasks'])
def test_new_shopfloor_routes(client,url):
    response=client.get(url)
    assert response.status_code==200,(url,response.data[:500])


def test_operator_task_start_pause_resume_finish_and_double_booking(client):
    token=csrf(client)
    path='/operator/start'
    base={'csrf_token':token,'wc':'WC1','worker_id':'W-001','unit_id':'TANK-0019'}
    assert client.post(path,data={k:v for k,v in base.items() if k!='csrf_token'}).status_code==403
    assert client.post(path,data=base).status_code==302
    payload=client.get('/api/operator/tasks').json['tasks']
    assert payload[0]['status']=='RUNNING'
    task_id=payload[0]['task_id']
    assert client.post(path,data={**base,'unit_id':'TANK-0020'}).status_code==302
    assert len(client.get('/api/operator/tasks').json['tasks'])==1
    assert client.post(f'/operator/tasks/{task_id}/pause',data={'csrf_token':token}).status_code==302
    assert client.get('/api/operator/tasks').json['tasks'][0]['status']=='PAUSED'
    assert client.post(f'/operator/tasks/{task_id}/resume',data={'csrf_token':token}).status_code==302
    assert client.post(f'/operator/tasks/{task_id}/finish',data={'csrf_token':token}).status_code==302
    assert client.get('/api/operator/tasks').json['tasks'][0]['status']=='FINISHED'
    # Task finish alone never marks quality complete or changes any other unit.
    unit=next(u for u in client.get('/api/units').json if u['id']=='TANK-0019')
    assert unit['status']=='In progress'


def test_downstream_defect_holds_only_affected_unit_and_blocks_ctq(client):
    token=csrf(client)
    response=client.post('/operator/incoming',data={
        'csrf_token':token,'unit_id':'TANK-0017','wc':'WC3','worker_id':'W-010',
        'outcome':'DEFECT_REPORTED','note':'Dimensional issue found at receipt'})
    assert response.status_code==302
    units={u['id']:u for u in client.get('/api/units').json}
    assert units['TANK-0017']['status']=='Hold'
    assert units['TANK-0019']['status']=='In progress'
    assert client.post('/quality/TANK-0017/CTQ-012',data={
        'csrf_token':token,'value':'No'}).status_code==409
    html=client.get('/lms').data.decode('utf-8')
    assert 'pending confirmation' in html
    # No automated worker blame or persisted points appear in task JSON.
    assert 'score' not in client.get('/api/operator/tasks').json
