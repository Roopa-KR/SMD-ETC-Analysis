"""v13: environmental conditions — validation, freshness, sensors, analysis gating, and proof that
environmental data (present, missing, invalid or unavailable) never changes ETC, cutoff status,
the ready-time chart or operator allocations.

Replay day 08-Sep-2026, warehouse time America/New_York (EDT, UTC−4). Snapshot 10 = 18:30.
"""
import datetime as dt
import hashlib
import json
import os
import re

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import inspect

import config
from calculations import environment as env
from calculations.environment_analysis import analyse
from calculations.supervisor import build_state, recommend_minimum, preview_state
from models import database as db

SNAP = 10
AS_OF = dt.datetime(2026, 9, 8, 18, 30)
DAY = AS_OF.date()
WORKBOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'INFO', 'historical', 'historical_33_trucks_reference.xlsx')


def local(h, m):
    return env.local_to_utc(dt.datetime(2026, 9, 8, h, m))


def zone_of(conditions, code):
    return next(z for z in conditions['zones'] if z['zone']['zone_code'] == code)


@pytest.fixture(scope='module')
def app_module():
    import app as module
    module.app.config['TESTING'] = True
    return module


@pytest.fixture
def client(app_module, clean_env):
    c = app_module.app.test_client()
    c.get(f'/environment?snapshot={SNAP}')
    with c.session_transaction() as s:
        c.csrf = s['csrf_token']
    return c


@pytest.fixture
def api_token(monkeypatch):
    monkeypatch.setattr(config, 'ENV_INGEST_TOKEN', 'test-token')
    return {'Authorization': 'Bearer test-token'}


# ---------------- storage and zones ----------------
def test_readings_live_in_a_separate_database(clean_env):
    assert config.ENV_DATABASE_URL != config.DATABASE_URL
    assert 'environment_test.db' in config.ENV_DATABASE_URL   # tests never touch data/environment.db
    assert not any(t.startswith('env_') for t in inspect(db.engine).get_table_names())
    assert {'env_zone', 'env_device', 'env_reading', 'env_site_note'} <= set(inspect(clean_env.engine).get_table_names())


def test_zones_are_the_verified_work_types_only(clean_env):
    names = db.load_sources().worktype_names
    zones = clean_env.zones()
    assert [z['zone_code'] for z in zones] == [f'WT{wt}' for wt in sorted(names)]
    assert all(z['source'] == 'M123 work type' for z in zones)
    assert [z['name'] for z in zones] == [f'WT {wt} {names[wt]}' for wt in sorted(names)]


def test_user_added_zone_is_labelled_and_duplicates_refused(clean_env):
    clean_env.add_zone('DOCK', 'Loading dock')
    assert next(z for z in clean_env.zones() if z['zone_code'] == 'DOCK')['source'] == 'user added'
    with pytest.raises(ValueError):
        clean_env.add_zone('DOCK', 'Again')


# ---------------- validation ----------------
def test_normal_manual_reading_is_valid_and_current(clean_env):
    out = env.record_reading('WT2', '26.4', '58', local(18, 10), 'manual', recorded_by='tester')
    assert out == dict(status='stored', quality='valid', note='')
    z = zone_of(env.zone_conditions(AS_OF), 'WT2')
    assert z['freshness'] == 'current' and z['age_minutes'] == 20
    assert z['reading']['data_label'] == 'ACTUAL' and z['reading']['method'] == 'manual'
    assert env.worktype_context(env.zone_conditions(AS_OF), 2)['text'] == '26.4 °C · 58 %RH · 18:10 (current)'


@pytest.mark.parametrize('temperature, humidity, message', [
    (90, 50, 'outside the valid range'), (-41, 50, 'outside the valid range'),
    (25, 101, 'outside 0..100'), (25, -1, 'outside 0..100'),
    ('abc', 50, 'must be a number'), (25, '', 'must be a number'), ('nan', 50, 'finite'),
])
def test_invalid_manual_entries_are_rejected_not_stored(clean_env, temperature, humidity, message):
    with pytest.raises(ValueError, match=message):
        env.record_reading('WT1', temperature, humidity, local(18, 0), 'manual')
    assert clean_env.readings() == []


def test_unknown_zone_and_future_time_are_rejected(clean_env):
    with pytest.raises(ValueError, match='Unknown zone'):
        env.record_reading('NOPE', 25, 50, local(18, 0), 'manual')
    with pytest.raises(ValueError, match='future'):
        env.record_reading('WT1', 25, 50, dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10), 'manual')


def test_duplicate_reading_is_stored_once(clean_env):
    assert env.record_reading('WT1', 25, 50, local(18, 0), 'manual')['status'] == 'stored'
    assert env.record_reading('WT1', 25.5, 51, local(18, 0), 'manual')['status'] == 'duplicate'
    assert len(clean_env.readings('WT1')) == 1


def test_large_step_is_suspect_shown_with_warning_and_excluded_from_analysis(clean_env):
    env.record_reading('WT4', 25, 50, local(18, 0), 'manual')
    out = env.record_reading('WT4', 37, 50, local(18, 15), 'manual')
    assert out['quality'] == 'suspect' and '12.0 °C' in out['note']
    c = env.zone_conditions(AS_OF)
    assert zone_of(c, 'WT4')['reading']['quality'] == 'suspect'
    assert any(a['kind'] == 'suspect' for a in c['attention'])
    assert env.worktype_context(c, 4)['status'] == 'current-suspect'
    # the same step after more than 30 minutes is a plausible change, not suspect
    assert env.record_reading('WT4', 25, 50, local(19, 0), 'manual')['quality'] == 'valid'


# ---------------- freshness ----------------
def test_stale_and_missing_readings(clean_env):
    env.record_reading('WT3', 24, 55, local(17, 0), 'manual')
    c = env.zone_conditions(AS_OF)
    assert zone_of(c, 'WT3')['freshness'] == 'stale' and zone_of(c, 'WT3')['age_minutes'] == 90
    assert zone_of(c, 'WT5')['freshness'] == 'missing'
    kinds = {(a['kind'], a['zone']) for a in c['attention']}
    assert ('stale', 'WT 3 Vault') in kinds and ('missing', 'WT 5 Cooler') in kinds
    assert env.worktype_context(c, 5) == dict(status='missing', text='No reading', zone='WT 5 Cooler')


def test_a_reading_after_the_snapshot_time_is_not_used_at_that_snapshot(clean_env):
    env.record_reading('WT1', 25, 50, local(19, 0), 'manual')
    assert zone_of(env.zone_conditions(AS_OF), 'WT1')['freshness'] == 'missing'
    assert zone_of(env.zone_conditions(dt.datetime(2026, 9, 8, 19, 15)), 'WT1')['freshness'] == 'current'


def test_timezone_conversion_and_display():
    assert env.timezone_status()['ok'] and env.timezone_status()['name'] == 'America/New_York'
    assert env.local_to_utc(AS_OF) == dt.datetime(2026, 9, 8, 22, 30, tzinfo=dt.timezone.utc)
    assert env.utc_to_local('2026-09-08T22:20:00+00:00') == dt.datetime(2026, 9, 8, 18, 20)
    assert env.parse_api_time('2026-09-08T18:20:00-04:00') == env.parse_api_time('2026-09-08T22:20:00Z')
    with pytest.raises(ValueError, match='offset'):
        env.parse_api_time('2026-09-08T18:20:00')


# ---------------- sensor API and disconnection ----------------
def test_sensor_api_disabled_without_token(client):
    response = client.post('/api/environment/readings', json={})
    assert response.status_code == 503 and 'disabled' in response.get_json()['error']


def test_sensor_api_authentication_and_body_checks(client, api_token):
    assert client.post('/api/environment/readings', json={}).status_code == 401
    assert client.post('/api/environment/readings', json={}, headers={'Authorization': 'Bearer wrong'}).status_code == 401
    assert client.post('/api/environment/readings', data='not json', headers=api_token).status_code == 400
    many = [dict(device_id='X', temperature_c=1, humidity_pct=1, reading_time='2026-09-08T18:00:00Z')] * 501
    assert client.post('/api/environment/readings', json=many, headers=api_token).status_code == 413


def test_sensor_readings_validated_per_item(client, api_token, clean_env):
    clean_env.register_device('ESP32-TEST-01', 'WT2', 'test device')
    body = [
        dict(device_id='ESP32-TEST-01', temperature_c=26.4, humidity_pct=58, reading_time='2026-09-08T18:20:00-04:00'),
        dict(device_id='ESP32-TEST-01', temperature_c=26.4, humidity_pct=58, reading_time='2026-09-08T18:20:00-04:00'),
        dict(device_id='UNKNOWN', temperature_c=26, humidity_pct=50, reading_time='2026-09-08T18:20:00-04:00'),
        dict(device_id='ESP32-TEST-01', temperature_c=26, humidity_pct=50, reading_time='2026-09-08T18:21:00'),
        'not an object',
    ]
    result = client.post('/api/environment/readings', json=body, headers=api_token).get_json()
    assert [r['status'] for r in result['results']] == ['stored', 'duplicate', 'rejected', 'rejected', 'rejected']
    assert result['stored'] == 1
    stored = clean_env.readings('WT2')[0]
    assert stored['reading_utc'] == '2026-09-08T22:20:00+00:00' and stored['method'] == 'sensor'
    assert stored['device_key'] == 'ESP32-TEST-01' and stored['data_label'] == 'ACTUAL'
    c = env.zone_conditions(AS_OF)
    assert zone_of(c, 'WT2')['local_time'] == '08-Sep 18:20'
    assert c['devices'][0]['status'] == 'ok'


def test_out_of_range_sensor_value_is_stored_invalid_and_flagged(client, api_token, clean_env):
    clean_env.register_device('ESP32-TEST-02', 'WT6')
    env.ingest(dict(device_id='ESP32-TEST-02', temperature_c=27, humidity_pct=50, reading_time='2026-09-08T18:20:00-04:00'))
    out = env.ingest(dict(device_id='ESP32-TEST-02', temperature_c=999, humidity_pct=50,
                          reading_time='2026-09-08T18:25:00-04:00'))
    assert out[0]['status'] == 'stored' and out[0]['quality'] == 'invalid'
    c = env.zone_conditions(AS_OF)
    z = zone_of(c, 'WT6')
    assert z['reading']['temperature_c'] == 27       # the invalid value is never shown as the condition
    assert z['latest_invalid'] is not None
    assert {a['kind'] for a in c['attention']} >= {'invalid', 'sensor'}
    assert c['devices'][0]['status'] == 'attention'
    assert env.ingest(dict(device_id='ESP32-TEST-02', temperature_c=None, humidity_pct=50,
                           reading_time='2026-09-08T18:26:00-04:00'))[0]['quality'] == 'invalid'


def test_sensor_disconnection_is_detected(clean_env):
    clean_env.register_device('ESP32-TEST-03', 'WT1')
    env.ingest(dict(device_id='ESP32-TEST-03', temperature_c=25, humidity_pct=50, reading_time='2026-09-08T17:50:00-04:00'))
    c = env.zone_conditions(AS_OF)       # 40 min silent > 30 min limit, reading still "current" (≤ 60)
    device = c['devices'][0]
    assert device['status'] == 'attention' and 'silent for 40 min' in device['note']
    assert zone_of(c, 'WT1')['freshness'] == 'current'
    assert any(a['kind'] == 'sensor' for a in c['attention'])
    # never reported at all
    clean_env.register_device('ESP32-TEST-04', 'WT3')
    assert env.zone_conditions(AS_OF)['devices'][1]['status'] in ('attention', 'not yet active')


# ---------------- synthetic demo set ----------------
def test_synthetic_demo_is_labelled_covers_every_status_and_is_deletable(clean_env):
    stored = env.load_synthetic(DAY)
    assert stored > 0 and env.load_synthetic(DAY) == 0              # idempotent (duplicates ignored)
    c = env.zone_conditions(AS_OF)
    assert {z['freshness'] for z in c['zones']} == {'current', 'stale', 'missing'}
    assert {a['kind'] for a in c['attention']} == {'missing', 'stale', 'suspect', 'invalid', 'sensor'}
    assert all(r['data_label'] == 'SYNTHETIC' for r in clean_env.readings())
    assert c['synthetic_present']
    assert clean_env.device(env.SYNTHETIC_DEVICE)['data_label'] == 'SYNTHETIC'
    assert clean_env.delete_synthetic() == stored + 1                  # + the invalid sensor value
    assert clean_env.readings() == [] and clean_env.device(env.SYNTHETIC_DEVICE) is None


def test_synthetic_readings_are_never_evidence(clean_env):
    env.load_synthetic(DAY)
    result = analyse(db.load_sources().tc, db.load_sources().worktype_names)
    assert result['checks'][0]['value'] == 0 and not result['sufficient'] and result['results'] == []


def test_delete_keeps_actual_readings(clean_env):
    env.record_reading('WT5', 4, 60, local(18, 0), 'manual')
    env.load_synthetic(DAY)
    clean_env.delete_synthetic()
    assert [r['zone_code'] for r in clean_env.readings()] == ['WT5']


# ---------------- analysis gating ----------------
def _fake(days, spread, effect):
    rng = np.random.default_rng(1)
    picks, environment = [], []
    for d in range(days):
        for h in range(8, 16):
            hour = pd.Timestamp(2026, 7, 1 + d, h)
            temperature = 24 + spread * rng.random()
            environment.append(dict(worktype=1, hour=hour, temperature_c=temperature, humidity_pct=50 + rng.random(),
                                    readings=4))
            lines = max(1, int(40 + effect * (temperature - 24) + rng.normal(0, 1)))
            serial = (hour - pd.Timestamp(1899, 12, 30)) / pd.Timedelta(days=1)
            for i in range(lines):
                picks.append(dict(WORKTYPE=1, MOVED_TO_C_AT=serial + i / 100000, RESOURCENAME=f'p{i % 2}'))
    return pd.DataFrame(picks), pd.DataFrame(environment)


def test_analysis_reports_only_with_sufficient_evidence_and_never_claims_cause():
    picks, environment = _fake(days=6, spread=8, effect=-2)
    result = analyse(picks, {1: 'Prescription'}, environment)
    assert result['sufficient'] and len(result['results']) == 2
    temperature = result['results'][0]
    assert temperature['rho'] < 0 and temperature['ci_high'] < 0
    assert 'NOT evidence of cause' in temperature['conclusion']


@pytest.mark.parametrize('days, spread, failing', [(4, 8, 'Distinct days'), (6, 1, 'Temperature spread')])
def test_analysis_withholds_results_when_evidence_is_thin(days, spread, failing):
    picks, environment = _fake(days=days, spread=spread, effect=-2)
    result = analyse(picks, {1: 'Prescription'}, environment)
    assert not result['sufficient'] and result['results'] == []
    assert [c['item'] for c in result['checks'] if not c['ok']][0].startswith(failing)
    assert 'Insufficient evidence' in result['summary']


def test_replay_productivity_is_a_summary_not_a_trend():
    result = analyse(db.load_sources().tc, db.load_sources().worktype_names, pd.DataFrame(
        columns=['worktype', 'hour', 'temperature_c', 'humidity_pct', 'readings']))
    assert result['productivity_days'] == 1 and not result['productivity_is_trend']
    assert {p['worktype'] for p in result['productivity_table']} <= set(db.load_sources().worktype_names)


# ---------------- ETC, cutoff and allocation are unchanged ----------------
def _calculation_fingerprint(loading_minutes):
    src = db.load_sources()
    out = {}
    for snap in (6, 10, 11):
        state = build_state(src, db.worktype_context(snap), db.trucks_at(snap), snap,
                            {'SH0908-1034': loading_minutes}, [])
        out[snap] = dict(
            trucks=[(t['shipment'], t['status'], t['deadline'], t['slack_minutes']) for t in state['trucks']],
            rows=[(r['shipment'], r['worktype'], r['status'], r['point_ready'], r['conservative_ready'], r['rate'])
                  for r in state['rows']],
            recommendation=recommend_minimum(src, state, 2, 'SH0908-1034'),
            preview=preview_state(src, state, 2, [], shipment='SH0908-1034')['rates'])
    return json.dumps(out, default=str, sort_keys=True)


def test_etc_status_and_allocations_identical_with_missing_valid_and_invalid_readings(clean_env, api_token):
    empty = _calculation_fingerprint(110)
    env.load_synthetic(DAY)                                            # current, stale, suspect, invalid, missing
    env.record_reading('WT2', 40, 90, local(18, 20), 'manual')          # hot, humid area of the at-risk truck
    clean_env.register_device('ESP32-TEST-05', 'WT1')
    env.ingest(dict(device_id='ESP32-TEST-05', temperature_c=-80, humidity_pct=50, reading_time='2026-09-08T18:25:00Z'))
    assert _calculation_fingerprint(110) == empty


def test_pages_show_identical_etc_with_and_without_readings(client, loading_override):
    loading_override('SH0908-1034', 110)

    def figures():
        risk = client.get(f'/api/snapshots/{SNAP}/at-risk-pickups').get_json()
        csv = client.get(f'/export/trucks.csv?snapshot={SNAP}').get_data(as_text=True)
        truck = client.get(f'/truck/SH0908-1034?snapshot={SNAP}').get_data(as_text=True)
        ready = re.search(r'<script id="[^"]*-data" type="application/json">(.*?)</script>', truck, re.S)
        return risk, csv, ready.group(1) if ready else None

    before = figures()
    client.post('/environment', data=dict(csrf_token=client.csrf, action='load_synthetic', snapshot=SNAP))
    after = figures()
    assert before == after and before[2] is not None
    assert 'Projected to miss pick cutoff' in client.get(f'/environment?snapshot={SNAP}').get_data(as_text=True)


def test_unavailable_environment_data_never_breaks_etc_pages(client, app_module, monkeypatch, loading_override):
    loading_override('SH0908-1034', 110)
    csv_before = client.get(f'/export/trucks.csv?snapshot={SNAP}').get_data(as_text=True)

    def broken(*_args, **_kwargs):
        raise RuntimeError('environment database unreachable')
    monkeypatch.setattr(env, 'zone_conditions', broken)
    dashboard = client.get(f'/?snapshot={SNAP}')
    assert dashboard.status_code == 200 and 'Environmental data is unavailable' in dashboard.get_data(as_text=True)
    truck = client.get(f'/truck/SH0908-1034?snapshot={SNAP}')
    assert truck.status_code == 200 and 'Unavailable' in truck.get_data(as_text=True)
    planner = client.get(f'/planner?snapshot={SNAP}&worktype=2&shipment=SH0908-1034')
    assert planner.status_code == 200 and 'Unavailable' in planner.get_data(as_text=True)
    assert client.get(f'/export/trucks.csv?snapshot={SNAP}').get_data(as_text=True) == csv_before
    assert client.get(f'/environment?snapshot={SNAP}').status_code == 503


def test_source_workbook_and_cache_tables_untouched(clean_env):
    digest = hashlib.sha256(open(WORKBOOK, 'rb').read()).hexdigest()
    tables = sorted(inspect(db.engine).get_table_names())
    env.load_synthetic(DAY)
    env.record_reading('WT1', 25, 50, local(18, 0), 'manual')
    assert hashlib.sha256(open(WORKBOOK, 'rb').read()).hexdigest() == digest
    assert sorted(inspect(db.engine).get_table_names()) == tables


# ---------------- web pages and forms ----------------
def test_environment_page_renders_empty_and_states_context_only(client):
    html = client.get(f'/environment?snapshot={SNAP}').get_data(as_text=True)
    for text in ('Context only.', 'Environment-adjusted ETC', 'Not available', 'No reading', 'Not enough readings for a trend',
                 'Insufficient evidence', 'No hardware has been purchased', 'WBGT', 'not mandatory',
                 'Do not ask operators to keep working in unsafe heat', 'Not yet documented by the client',
                 'API</div>', 'Disabled'):
        assert text in html, text
    assert 'env-temp-chart' not in html                                # no empty chart


def test_environment_page_with_synthetic_data_shows_statuses_and_trends(client):
    client.post('/environment', data=dict(csrf_token=client.csrf, action='load_synthetic', snapshot=SNAP))
    html = client.get(f'/environment?snapshot={SNAP}').get_data(as_text=True)
    assert 'SYNTHETIC demo readings are loaded' in html
    for text in ('Stale', 'Missing', 'Suspect', 'Invalid', 'Requires attention', 'env-temp-chart', 'env-rh-chart'):
        assert text in html, text
    assert '<th>Label</th>' not in html
    assert '<th>Source</th>' not in html
    assert 'Series marked SYNTHETIC in the legend are demo data, not SMD conditions.' not in html
    data = json.loads(re.search(r'id="env-trend-data">(.*?)</script>', html, re.S).group(1))
    assert all(s['synthetic'] for s in data) and len({s['color'] for s in data}) == len(data)
    dashboard = client.get(f'/?snapshot={SNAP}').get_data(as_text=True)
    assert 'Work-area conditions' in dashboard and 'Environment-adjusted ETC: not available' in dashboard
    assert 'data-label-synthetic' not in dashboard
    truck = client.get(f'/truck/SH0908-1034?snapshot={SNAP}').get_data(as_text=True)
    assert 'Area conditions' in truck and '(current · SYNTHETIC)' in truck


def test_manual_form_stores_local_time_and_reports_errors(client, clean_env):
    response = client.post('/environment', data=dict(csrf_token=client.csrf, action='reading', snapshot=SNAP, zone='WT1',
                                                     temperature='25.5', humidity='55', reading_time='2026-09-08T18:15',
                                                     recorded_by='JD'), follow_redirects=True)
    assert 'Reading stored' in response.get_data(as_text=True)
    stored = clean_env.readings('WT1')[0]
    assert stored['reading_utc'] == '2026-09-08T22:15:00+00:00' and stored['recorded_by'] == 'JD'
    response = client.post('/environment', data=dict(csrf_token=client.csrf, action='reading', snapshot=SNAP, zone='WT1',
                                                     temperature='120', humidity='55', reading_time='2026-09-08T18:20'),
                           follow_redirects=True)
    assert 'outside the valid range' in response.get_data(as_text=True) and len(clean_env.readings()) == 1
    duplicate = client.post('/environment', data=dict(csrf_token=client.csrf, action='reading', snapshot=SNAP, zone='WT1',
                                                      temperature='25.5', humidity='55', reading_time='2026-09-08T18:15'),
                            follow_redirects=True)
    assert 'not stored twice' in duplicate.get_data(as_text=True)


def test_forms_require_the_form_token(client, clean_env):
    response = client.post('/environment', data=dict(action='reading', snapshot=SNAP, zone='WT1', temperature='25',
                                                     humidity='50', reading_time='2026-09-08T18:15'))
    assert response.status_code == 400 and clean_env.readings() == []


def test_entry_key_restricts_changes_when_configured(client, clean_env, monkeypatch):
    monkeypatch.setattr(config, 'ENV_ENTRY_KEY', 'secret')
    form = dict(csrf_token=client.csrf, action='reading', snapshot=SNAP, zone='WT1', temperature='25', humidity='50',
                reading_time='2026-09-08T18:15')
    denied = client.post('/environment', data=form, follow_redirects=True).get_data(as_text=True)
    assert 'Entry key required' in denied and clean_env.readings() == []
    client.post('/environment', data=dict(form, entry_key='secret'))
    assert len(clean_env.readings()) == 1
    assert 'name="entry_key"' in client.get(f'/environment?snapshot={SNAP}').get_data(as_text=True)


def test_device_zone_and_site_note_forms(client, clean_env):
    client.post('/environment', data=dict(csrf_token=client.csrf, action='device', snapshot=SNAP, device_id='ESP32-A',
                                          zone='WT2', description='OTC aisle 3'))
    assert clean_env.device('ESP32-A')['zone_code'] == 'WT2'
    again = client.post('/environment', data=dict(csrf_token=client.csrf, action='device', snapshot=SNAP,
                                                  device_id='ESP32-A', zone='WT2'), follow_redirects=True)
    assert 'already registered' in again.get_data(as_text=True)
    client.post('/environment', data=dict(csrf_token=client.csrf, action='zone', snapshot=SNAP, zone_code='dock',
                                          zone_name='Loading dock', worktype=''))
    assert any(z['zone_code'] == 'DOCK' and z['worktype'] is None for z in clean_env.zones())
    client.post('/environment', data=dict(csrf_token=client.csrf, action='note', snapshot=SNAP, topic='break_policy',
                                          text='10 min every 2 h', recorded_by='HSE'))
    assert clean_env.site_notes()['break_policy']['text'] == '10 min every 2 h'
    bad = client.post('/environment', data=dict(csrf_token=client.csrf, action='note', snapshot=SNAP, topic='other',
                                                text='x'), follow_redirects=True)
    assert 'Unknown note topic' in bad.get_data(as_text=True)


def test_zones_api_is_read_only_context(client, clean_env):
    env.record_reading('WT2', 26.4, 58, local(18, 10), 'manual')
    data = client.get(f'/api/environment/zones?snapshot={SNAP}').get_json()
    assert data['used_in_etc'] is False and data['timezone'] == 'America/New_York'
    wt2 = next(z for z in data['zones'] if z['zone'] == 'WT2')
    assert wt2['temperature_c'] == 26.4 and wt2['freshness'] == 'current' and wt2['reading_time_local'] == '08-Sep 18:10'
    assert client.get('/api/environment/zones?snapshot=999').status_code == 404
