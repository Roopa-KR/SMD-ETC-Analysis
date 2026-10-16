"""Standalone tests for shop-floor and confirmed point values; no Flask required."""
import sqlite3
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from manufacturing.shopfloor import (setup,start_task,transition,elapsed_seconds,
    record_handover,report_issue,work_order_overview,WorkflowError)
from manufacturing.scoring import POINTS, time_variance_preview, work_order_score
from manufacturing.model import UNIT_MAP, UNITS, WORKER_MAP, CTQ_RULES

@pytest.fixture
def db():
    conn=sqlite3.connect(':memory:')
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    setup(conn)
    yield conn
    conn.close()

BASE='2026-10-16T06:00:00+00:00'

def test_task_start_and_persisted_event(db):
    i=start_task(db,'W-001','TANK-0019','WC1',UNIT_MAP['TANK-0019'],now=BASE)
    row=db.execute('SELECT * FROM shop_tasks WHERE task_id=?',(i,)).fetchone()
    assert (row['status'],row['work_order'])==('RUNNING','ORD-1042')
    assert db.execute('SELECT event_type FROM shop_task_events').fetchone()['event_type']=='START'

def test_parallel_workers_same_unit_allowed(db):
    start_task(db,'W-001','TANK-0019','WC1',UNIT_MAP['TANK-0019'],now=BASE)
    start_task(db,'W-002','TANK-0019','WC1',UNIT_MAP['TANK-0019'],now=BASE)
    assert db.execute('SELECT COUNT(*) FROM shop_tasks').fetchone()[0]==2

def test_double_assignment_blocked_even_when_paused(db):
    i=start_task(db,'W-001','TANK-0019','WC1',UNIT_MAP['TANK-0019'],now=BASE)
    transition(db,i,'PAUSE','2026-10-16T06:10:00+00:00')
    with pytest.raises(WorkflowError,match='already has an open task'):
        start_task(db,'W-001','TANK-0020','WC1',UNIT_MAP['TANK-0020'],now=BASE)

def test_allows_next_after_finish(db):
    i=start_task(db,'W-001','TANK-0019','WC1',UNIT_MAP['TANK-0019'],now=BASE)
    transition(db,i,'FINISH','2026-10-16T06:10:00+00:00')
    start_task(db,'W-001','TANK-0020','WC1',UNIT_MAP['TANK-0020'],now='2026-10-16T06:12:00+00:00')
    assert db.execute("SELECT COUNT(*) FROM shop_tasks WHERE status='RUNNING'").fetchone()[0]==1

def test_pause_excluded_resume_counted(db):
    i=start_task(db,'W-001','TANK-0019','WC1',UNIT_MAP['TANK-0019'],now=BASE)
    transition(db,i,'PAUSE','2026-10-16T06:10:00+00:00')
    transition(db,i,'RESUME','2026-10-16T06:25:00+00:00')
    transition(db,i,'FINISH','2026-10-16T06:30:00+00:00')
    assert elapsed_seconds(db.execute('SELECT event_type,event_at FROM shop_task_events ORDER BY id').fetchall())==900

def test_invalid_transition_rejected(db):
    i=start_task(db,'W-001','TANK-0019','WC1',UNIT_MAP['TANK-0019'],now=BASE)
    with pytest.raises(WorkflowError):transition(db,i,'RESUME','2026-10-16T06:03:00+00:00')
    with pytest.raises(WorkflowError):transition(db,i,'FINISH','2026-10-16T05:59:00+00:00')

def test_unskilled_and_absent_blocked(db):
    with pytest.raises(WorkflowError,match='qualification'):
        start_task(db,'W-006','COVER-1002','WC5',UNIT_MAP['COVER-1002'],now=BASE)
    with pytest.raises(WorkflowError,match='absent'):
        start_task(db,'W-005','TANK-0019','WC1',UNIT_MAP['TANK-0019'],now=BASE)
    # In the normal scenario Ravi is explicitly present, not permanently absent.
    start_task(db,'W-005','TANK-0019','WC1',UNIT_MAP['TANK-0019'],worker_state='Present',now=BASE)

def test_wrong_station_and_ended_unit_blocked(db):
    with pytest.raises(WorkflowError,match='current stage'):
        start_task(db,'W-006','TANK-0019','WC2',UNIT_MAP['TANK-0019'],now=BASE)
    with pytest.raises(WorkflowError,match='completed'):
        start_task(db,'W-013','TANK-0011','WC4',UNIT_MAP['TANK-0011'],now=BASE)

def test_handover_keeps_origin_distinct_from_detection(db):
    record_handover(db,'TANK-0017','WC3','W-010','DEFECT_REPORTED','Incorrect weld surface',now=BASE)
    a=db.execute('SELECT * FROM shop_handover_checks').fetchone()
    d=db.execute('SELECT * FROM shop_defects').fetchone()
    assert (a['from_wc'],a['to_wc'],a['outcome'])==('WC2','WC3','DEFECT_REPORTED')
    assert d['status']=='OPEN' and d['source']=='INCOMING_INSPECTION' and 'fault' not in d.keys()

def test_receiving_inspection_rejects_initial_stage(db):
    with pytest.raises(WorkflowError,match='downstream'):
        record_handover(db,'TANK-0019','WC1','W-001','ACCEPTED','',now=BASE)

def test_defect_requires_narrative_and_qualified_operator(db):
    with pytest.raises(WorkflowError,match='Describe'):
        record_handover(db,'TANK-0017','WC3','W-010','DEFECT_REPORTED','bad',now=BASE)
    with pytest.raises(WorkflowError,match='qualification'):
        report_issue(db,'COVER-1002','WC5','W-001','This is defective',now=BASE)

def test_reports_do_not_assign_fault_or_points(db):
    report_issue(db,'TANK-0019','WC1','W-001','Observed missing hole in fixture',now=BASE)
    row=db.execute('SELECT source,status,detail FROM shop_defects').fetchone()
    assert (row['source'],row['status'])==('TASK_ISSUE','OPEN')

def test_work_orders_three_product_families():
    orders=work_order_overview(UNITS,[])
    assert {o['type'] for o in orders}=={'Tank','Cover','Accessories'}
    tank=next(o for o in orders if o['type']=='Tank')
    assert [x['wc'] for x in tank['stages']]==['WC1','WC2','WC3','WC4']
    assert all(x['checks']>0 for x in tank['stages'])

def test_all_four_points_weights_confirmed():
    assert POINTS=={'NO_REWORK_WO':3,'ORIGIN_CAUGHT_FIXED_WO':2,
                    'DOWNSTREAM_CONFIRMED_DEFECT':-4,'TIME_DIFFERENCE_PER_MINUTE':1}

def test_points_verified_conditions_only():
    assert work_order_score(completed=True,rework_count=0,origin_fixed_confirmed=False,downstream_confirmed=0)['total']==3
    assert work_order_score(completed=False,rework_count=0,origin_fixed_confirmed=True,downstream_confirmed=2)['total']==-6
    assert work_order_score(completed=True,rework_count=1,origin_fixed_confirmed=True,downstream_confirmed=1)['total']==-2

def test_time_variance_is_provisional_not_worker_award():
    assert time_variance_preview(42,45)==Decimal('3')
    assert time_variance_preview(45.5,45)==Decimal('-0.5')
    assert work_order_score(completed=False,rework_count=0,origin_fixed_confirmed=False,downstream_confirmed=0)['time_points'] is None

@pytest.mark.parametrize('actual,target', [('bad',10),(-1,10),(1,0),('NaN',2),(1,'Infinity')])
def test_time_preview_validates_bad_inputs(actual,target):
    with pytest.raises(ValueError):time_variance_preview(actual,target)


def test_open_reports_hold_only_affected_live_units():
    from manufacturing.shopfloor import apply_active_defect_holds
    data=[dict(UNIT_MAP['TANK-0019']),dict(UNIT_MAP['TANK-0020']),dict(UNIT_MAP['TANK-0011'])]
    out=apply_active_defect_holds(data,['TANK-0019','TANK-0011'])
    assert [x['status'] for x in out]==['Hold','Queued','Complete']
    assert UNIT_MAP['TANK-0019']['status']=='In progress'

def test_unconfirmed_downstream_report_does_not_create_auto_score(db):
    record_handover(db,'TANK-0017','WC3','W-010','DEFECT_REPORTED','Defective paint surface',now=BASE)
    report=db.execute('SELECT status FROM shop_defects').fetchone()
    assert report['status']=='OPEN'
    result=work_order_score(completed=False,rework_count=0,origin_fixed_confirmed=False,downstream_confirmed=0)
    assert result['total']==0 and result['worker_allocation'] is None
