"""Focused checks for durable advisory pickup-risk allocations."""

from calculations.supervisor import build_state, eligible_candidates


def _state(snapshot=10):
    from models import database as db
    src = db.load_sources()
    return src, build_state(src, db.worktype_context(snapshot), db.trucks_at(snapshot), snapshot,
                            db.get_loading_overrides())


def test_strict_eligibility_uses_observed_target_work_and_safe_source():
    src, state = _state()
    result = eligible_candidates(src, state, 2)
    assert all(c['pace'] > 0 and c['source_pace'] > 0 and c['safe'] for c in result['eligible'])
    assert any('SYNTHETIC' in c['evidence'] for c in result['all_experienced'])
    assert result['unsafe'] and all(not c['safe'] for c in result['unsafe'])
    assert [c['pace'] for c in result['eligible']] == sorted((c['pace'] for c in result['eligible']), reverse=True)
    assert result['excluded']
    assert all('experience' in x['reason'].lower() for x in result['excluded'])


def test_risk_and_eligibility_apis_are_snapshot_aware():
    from app import app
    client = app.test_client()
    risk = client.get('/api/snapshots/10/at-risk-pickups')
    assert risk.status_code == 200
    payload = risk.get_json()
    assert payload['snapshot'] == 10 and payload['pickups']
    assert {'shipment', 'worktype', 'cutoff', 'estimated_completion', 'risk'} <= set(payload['pickups'][0])
    candidates = client.get('/api/snapshots/10/worktypes/2/eligible-operators')
    assert candidates.status_code == 200
    assert all(row['pace'] > 0 for row in candidates.get_json()['eligible'])
