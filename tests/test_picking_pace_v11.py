"""v11: picking-time pace, corrected demo labor time, and consistent status across snapshots.

Root cause fixed (see docs/project_tracking/STATUS_CONSISTENCY_RELEASE_v11.md): at 18:30 a burst of
20 OTC lines arrived for SH0908-1034 while the cautious rate used a pace measured over logged-in
time that included waiting (mmathis 4.4 lines/h logged vs 17.6 while picking). The truck showed
At Risk for one snapshot only and finished 82 minutes early in reality.

v14 adds a GENUINE risk on top (late add-on OTC orders, earlier 20:30 departures): the tests below
keep the v11 guarantees (no unexplained status change, picking-time pace) and check that the v14
At Risk status is confirmed by the replayed history rather than being a false alarm.
"""
import shutil
import zipfile
from collections import Counter

import pandas as pd
import pytest

from calculations.excel_io import load_inputs
from calculations.pace import picking_hours
from calculations.supervisor import build_state
from models import database as db

MIN = 1 / 1440


def snapshot_state(n, basis=None, loading=None):
    src = db.load_sources()
    return build_state(src, db.worktype_context(n), db.trucks_at(n), n, loading or {}, [], pace_basis=basis)


# ---------- picking time arithmetic ----------
def test_picking_hours_caps_waiting_gaps():
    start = 100.0
    picks = [start + 5 * MIN, start + 7 * MIN, start + 40 * MIN]     # lead 5, gaps 2 and 33 (capped 10)
    assert picking_hours(picks, [start], cap_minutes=10) * 60 == pytest.approx(17)
    # still logged in to the area 20 min after the last pick: +10 (capped) trailing minutes
    assert picking_hours(picks, [start], now=start + 60 * MIN, still_active=True, cap_minutes=10) * 60 == pytest.approx(27)
    # logged out: no trailing time; unknown session start: lead = cap
    assert picking_hours(picks, [], cap_minutes=10) * 60 == pytest.approx(22)
    assert picking_hours([], [start]) == 0


def test_logged_time_basis_reproduces_excel_equation_rates():
    for n in (8, 10, 12):
        state = snapshot_state(n, basis='logged_time')
        stored = {int(r['WORKTYPE']): r for r in db.worktype_context(n)}
        for wt, rates in state['baseline'].items():
            expected = stored[wt]['ACTUALRATELINES']
            if expected is None or pd.isna(expected) or expected <= 0:
                assert rates['rate'] is None
            else:
                assert rates['rate'] == pytest.approx(expected)


def test_picking_time_is_default_and_labelled():
    state = snapshot_state(10)
    assert state['pace_basis'] == 'picking_time'
    assert 'picking time' in state['pace_info']['basis'] and '10 min' in state['pace_info']['basis']
    mm = state['stats'][('mmathis', 2)]
    assert mm['picking_hours'] > 0 and mm['pace'] == pytest.approx(mm['lines'] / mm['picking_hours'])
    assert mm['hours'] == mm['picking_hours'] != mm['logged_hours']


# ---------- the investigated case ----------
def test_v14_at_risk_at_1830_is_confirmed_by_history_not_a_false_alarm():
    state = snapshot_state(10)
    row = next(r for r in state['rows'] if r['shipment'] == 'SH0908-1034' and r['worktype'] == 2)
    truck = next(t for t in state['trucks'] if t['shipment'] == 'SH0908-1034')
    assert truck['status'] == 'AT RISK' and row['status'] == 'AT RISK'
    assert truck['deadline'] < row['conservative_ready'] <= truck['cutoff']     # 19:57: buffer 19:50, cutoff 20:00
    # history: OTC lines of this truck were still open when the 20:00 pick cutoff arrived
    data = load_inputs('data/workbook.xlsx')
    lines = data.line_map.merge(data.orders[['WHORDERID', 'SHIPMENTID']], on='WHORDERID', suffixes=('_map', ''))
    ids = set(lines[(lines.SHIPMENTID == 'SH0908-1034') & (lines.WORKTYPE == 2)].TI102ID)
    picked = data.tc[data.tc.TI102ID.isin(ids)].MOVED_TO_C_AT
    assert len(picked) < len(ids) or picked.max() > truck['cutoff']


def test_statuses_consistent_across_all_snapshots_and_changes_are_justified():
    previous = None
    timeline = Counter()
    for snap in db.snapshots():
        state = snapshot_state(snap.snapshot_no)
        trucks = {t['shipment']: t for t in state['trucks']}
        rows = {(r['shipment'], r['worktype']): r for r in state['rows']}
        assert len(trucks) == 10
        for ship, t in trucks.items():
            timeline[t['status']] += 1
            if previous and previous['trucks'][ship]['status'] != t['status']:
                before = {k: (r['open'], r['ahead'], r['resources'], r['rate'], r['low_rate'])
                          for k, r in previous['rows'].items() if k[0] == ship}
                after = {k: (r['open'], r['ahead'], r['resources'], r['rate'], r['low_rate'])
                         for k, r in rows.items() if k[0] == ship}
                assert before != after or previous['trucks'][ship]['deadline'] != t['deadline'], \
                    f'{ship} changed status at snapshot {snap.snapshot_no} with no input change'
        previous = dict(trucks=trucks, rows=rows)
    # v14: risk exists (two trucks), and every status change above was backed by changed inputs
    assert timeline['AT RISK'] > 0 and timeline['PICK CUTOFF PASSED'] > 0


def test_every_on_time_forecast_was_met_in_the_replayed_history():
    src = load_inputs('data/workbook.xlsx')        # workbook carries the line -> truck mapping
    picked = src.tc.groupby('TI102ID').MOVED_TO_C_AT.max()
    for snap in db.snapshots():
        state = snapshot_state(snap.snapshot_no)
        open_ids = set(src.ti[(src.ti.SNAPSHOT_NO == snap.snapshot_no) & (src.ti.OPENQTY > 0)].TI102ID)
        for t in state['trucks']:
            if t['status'] != 'ON TIME':
                continue
            ids = set(src.line_map[src.line_map.SHIPMENTID == t['shipment']].TI102ID) & open_ids
            assert picked[list(ids)].max() <= t['deadline'] + 1e-9


# ---------- corrected demo labor time ----------
V13 = 'INFO/historical/ten_truck_v13_baseline.xlsx'     # v11 labour scaling applied; before the v14 scenario


def test_demo_labor_time_scaled_to_share_of_lines_kept():
    demo = load_inputs(V13)
    ref = load_inputs('INFO/historical/historical_33_trucks_reference.xlsx')
    share = demo.tc.groupby('WORKTYPE').size() / ref.tc.groupby('WORKTYPE').size()
    merged = demo.lm.merge(ref.lm[['SNAPSHOT_NO', 'LM005ID', 'TOTALTIMEINSEC']], on=['SNAPSHOT_NO', 'LM005ID'],
                           suffixes=('', '_ref'))
    assert len(merged) == len(demo.lm) == len(ref.lm)
    expected = (merged.TOTALTIMEINSEC_ref * merged.WORKTYPE.map(share)).round()
    assert (merged.TOTALTIMEINSEC == expected).all()
    assert not merged.DATA_TYPE.str.contains('65%').any()
    # v14 keeps the v11 labour time for every session except the documented mmathis overtime
    active = load_inputs('data/workbook.xlsx')
    changed = active.lm[active.lm.DATA_TYPE.str.contains('v14', na=False)]
    assert set(changed.RESOURCENAME) == {'mmathis'}
    same = active.lm[~active.lm.DATA_TYPE.str.contains('v14', na=False)].merge(
        demo.lm[['SNAPSHOT_NO', 'LM005ID', 'TOTALTIMEINSEC']], on=['SNAPSHOT_NO', 'LM005ID'], suffixes=('', '_v13'))
    assert len(same) == len(active.lm) - len(changed) and (same.TOTALTIMEINSEC == same.TOTALTIMEINSEC_v13).all()


def test_rescale_script_is_idempotent_and_only_touches_labor_sheets(tmp_path):
    from scripts.rescale_demo_labor import rescale
    copy = tmp_path / 'workbook.xlsx'
    shutil.copy(V13, copy)
    rescale(copy, 'INFO/historical/historical_33_trucks_reference.xlsx')
    with zipfile.ZipFile(V13) as a, zipfile.ZipFile(copy) as b:
        assert [i.filename for i in a.infolist()] == [i.filename for i in b.infolist()]
        assert all(a.read(n) == b.read(n) for n in a.namelist())
