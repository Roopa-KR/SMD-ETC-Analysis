"""Conservative work-order/task/handover workflow for the *synthetic* GiNi demo.

Point weights are recorded separately; no automatic employee blame, approved rework, calibrated standards or factory OEE.
Operational clock events are UTC and are deliberately independent of the fixed
PDF scenario replay. Values from the CTQ guide remain in ctq_rules.json.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from manufacturing.model import UNIT_MAP, WORKER_MAP, ROUTES, CTQ_RULES

ACTIVE = frozenset(('RUNNING', 'PAUSED'))
DECISIONS = frozenset(('ACCEPTED', 'DEFECT_REPORTED'))

class WorkflowError(ValueError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def setup(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS shop_tasks (
          task_id INTEGER PRIMARY KEY AUTOINCREMENT,
          unit_id TEXT NOT NULL, work_order TEXT NOT NULL, worker_id TEXT NOT NULL,
          wc TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('RUNNING','PAUSED','FINISHED')),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, ended_at TEXT,
          CHECK(length(unit_id)>0 AND length(worker_id)>0)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS shop_one_live_task_per_worker
          ON shop_tasks(worker_id) WHERE status IN ('RUNNING','PAUSED');
        CREATE INDEX IF NOT EXISTS shop_tasks_unit ON shop_tasks(unit_id, wc);
        CREATE TABLE IF NOT EXISTS shop_task_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES shop_tasks(task_id),
          event_type TEXT NOT NULL CHECK(event_type IN ('START','PAUSE','RESUME','FINISH')),
          event_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS shop_task_events_order ON shop_task_events(task_id,id);
        CREATE TABLE IF NOT EXISTS shop_handover_checks (
          id INTEGER PRIMARY KEY AUTOINCREMENT, unit_id TEXT NOT NULL,
          from_wc TEXT NOT NULL, to_wc TEXT NOT NULL, worker_id TEXT NOT NULL,
          outcome TEXT NOT NULL CHECK(outcome IN ('ACCEPTED','DEFECT_REPORTED')),
          note TEXT NOT NULL, recorded_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS shop_handover_unit ON shop_handover_checks(unit_id);
        CREATE TABLE IF NOT EXISTS shop_defects (
          id INTEGER PRIMARY KEY AUTOINCREMENT, unit_id TEXT NOT NULL, wc TEXT NOT NULL,
          reported_by TEXT NOT NULL, detail TEXT NOT NULL,
          source TEXT NOT NULL CHECK(source IN ('TASK_ISSUE','INCOMING_INSPECTION')),
          status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status='OPEN'),
          recorded_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS shop_defects_unit ON shop_defects(unit_id);
        -- A reported defect is not confirmed, nor attributed to a worker.
        -- Approved dispositions and responsibility decisions are not modeled.
    ''')


def start_task(db, worker_id, unit_id, wc, active_unit, now=None, worker_state=None):
    worker = WORKER_MAP.get(worker_id)
    unit = UNIT_MAP.get(unit_id)
    if not worker or not unit:
        raise WorkflowError('Select a known worker and a known physical unit.')
    if unit['order'] != active_unit['order']:
        raise WorkflowError('The unit must belong to the selected work order.')
    if wc not in ROUTES[unit['type']] or wc != active_unit['wc']:
        raise WorkflowError('The selected work center is not this unit’s current stage.')
    if wc not in worker['skills']:
        raise WorkflowError('Worker lacks the demonstration qualification for this work center.')
    if (worker_state or worker['state']) == 'Absent':
        raise WorkflowError('An absent worker cannot start a task.')
    if active_unit['status'] in ('Complete','Scrapped','Hold','Proposed replacement','Approved replacement','Inspection pending'):
        raise WorkflowError('This unit is completed, held, scrapped or not yet available to work.')
    if db.execute('SELECT 1 FROM shop_tasks WHERE worker_id=? AND status IN (\'RUNNING\',\'PAUSED\')', (worker_id,)).fetchone():
        raise WorkflowError('This worker already has an open task. Pause does not release the assignment.')
    if db.execute('SELECT 1 FROM shop_defects WHERE unit_id=? AND status=\'OPEN\'', (unit_id,)).fetchone():
        raise WorkflowError('This unit has an unresolved defect report; task start is blocked pending review.')
    now = now or timestamp()
    cur=db.execute('''INSERT INTO shop_tasks(unit_id,work_order,worker_id,wc,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?)''',(unit_id,unit['order'],worker_id,wc,'RUNNING',now,now))
    task_id=cur.lastrowid
    db.execute('INSERT INTO shop_task_events(task_id,event_type,event_at) VALUES(?,?,?)',(task_id,'START',now))
    return task_id


def transition(db, task_id, action, now=None):
    expected={'PAUSE':('RUNNING','PAUSED'),'RESUME':('PAUSED','RUNNING'),
              'FINISH':('RUNNING','FINISHED')}
    if action not in expected:
        raise WorkflowError('Unsupported task action.')
    row=db.execute('SELECT * FROM shop_tasks WHERE task_id=?',(task_id,)).fetchone()
    if not row:
        raise WorkflowError('Task was not found.')
    prior, target=expected[action]
    if row['status']!=prior:
        raise WorkflowError(f'{action.title()} is not allowed while task is {row["status"].lower()}.')
    now=now or timestamp()
    if datetime.fromisoformat(now)<datetime.fromisoformat(row['updated_at']):
        raise WorkflowError('Event time cannot precede the previous task event.')
    db.execute('UPDATE shop_tasks SET status=?, updated_at=?, ended_at=? WHERE task_id=?',
               (target,now,now if action=='FINISH' else None,task_id))
    db.execute('INSERT INTO shop_task_events(task_id,event_type,event_at) VALUES(?,?,?)',(task_id,action,now))
    return target


def elapsed_seconds(events, now=None):
    """Active work only; paused time is excluded, with no unbounded negative intervals."""
    current=None; seconds=0.0
    now=datetime.fromisoformat(now) if isinstance(now,str) else (now or datetime.now(timezone.utc))
    for ev in events:
        name=ev['event_type']; t=datetime.fromisoformat(ev['event_at'])
        if name in ('START','RESUME'):
            if current is not None: raise WorkflowError('Consecutive start/resume events are invalid.')
            current=t
        elif name in ('PAUSE','FINISH'):
            if current is None: raise WorkflowError('Cannot pause/finish without an active timer.')
            seconds+=max(0.0,(t-current).total_seconds()); current=None
        else: raise WorkflowError('Unknown timer event.')
    if current is not None:seconds+=max(0.0,(now-current).total_seconds())
    return round(seconds)


def record_handover(db, unit_id, to_wc, worker_id, outcome, note, now=None):
    unit=UNIT_MAP.get(unit_id)
    worker=WORKER_MAP.get(worker_id)
    if not unit or not worker:raise WorkflowError('Unknown unit or worker.')
    route=ROUTES[unit['type']]
    if to_wc not in route or route.index(to_wc)==0:
        raise WorkflowError('Incoming inspection requires a downstream receiving work center.')
    if to_wc not in worker['skills']:
        raise WorkflowError('Worker lacks the demo receiving-stage qualification.')
    if outcome not in DECISIONS:raise WorkflowError('Choose All Good or Report Defect.')
    note=(note or '').strip()
    if outcome=='DEFECT_REPORTED' and len(note)<5:
        raise WorkflowError('Describe the observed defect before submitting a report.')
    if len(note)>1200:raise WorkflowError('The note is too long.')
    # Only inspect after the unit has actually arrived (or completed) at this stage.
    # Cannot infer a receiving acceptance from a proposed replacement or scrapped unit.
    from_wc=route[route.index(to_wc)-1]
    now=now or timestamp()
    db.execute('''INSERT INTO shop_handover_checks(unit_id,from_wc,to_wc,worker_id,outcome,note,recorded_at)
        VALUES(?,?,?,?,?,?,?)''',(unit_id,from_wc,to_wc,worker_id,outcome,note,now))
    if outcome=='DEFECT_REPORTED':
        db.execute('''INSERT INTO shop_defects(unit_id,wc,reported_by,detail,source,recorded_at)
          VALUES(?,?,?,?,?,?)''',(unit_id,to_wc,worker_id,note,'INCOMING_INSPECTION',now))
    return from_wc


def report_issue(db,unit_id,wc,worker_id,note,now=None):
    if unit_id not in UNIT_MAP or wc not in ROUTES[UNIT_MAP[unit_id]['type']]:
        raise WorkflowError('Choose a valid unit and its work center.')
    if worker_id not in WORKER_MAP:raise WorkflowError('Unknown operator.')
    if wc not in WORKER_MAP[worker_id]['skills']:
        raise WorkflowError('Worker lacks the demo qualification for this reporting station.')
    note=(note or '').strip()
    if len(note)<5 or len(note)>1200:raise WorkflowError('Provide a 5–1200 character description.')
    db.execute('INSERT INTO shop_defects(unit_id,wc,reported_by,detail,source,recorded_at) VALUES(?,?,?,?,?,?)',
               (unit_id,wc,worker_id,note,'TASK_ISSUE',now or timestamp()))


def work_order_overview(units, results):
    """Current fixture counts, never invent operation pass/certification from stage position."""
    orders={}
    verified=defaultdict(set)
    checks=defaultdict(set)
    for row in results:
        checks[row['unit_id']].add(row['check_id'])
        if row['verdict']=='PASS':verified[row['unit_id']].add(row['check_id'])
    bywc=defaultdict(set)
    for rule in CTQ_RULES:bywc[rule['wc']].add(rule['check_id'])
    for u in units:
        if u['status']=='Proposed replacement':continue
        group=orders.setdefault(u['order'],{'id':u['order'],'type':u['type'],'quantity':0,'units':[], 'stages':[]})
        group['units'].append(u);group['quantity']+=1
    for wo in orders.values():
        route=ROUTES[wo['type']]
        for i,wc in enumerate(route):
            # Stage traversal is inferred from the current demo fixture; this is not
            # treated as an authenticated quality gate acceptance.
            arrived=sum(route.index(u['wc'])>=i for u in wo['units'])
            left=sum((route.index(u['wc'])>i or (i==len(route)-1 and u['status']=='Complete'))
                     for u in wo['units'] if u['status']!='Scrapped')
            checked=sum(bool(bywc[wc]) and bywc[wc].issubset(verified[u['id']]) for u in wo['units'])
            wo['stages'].append({'wc':wc,'arrived':arrived,'moved_past':left,'ctq_verified':checked,
                                 'total':wo['quantity'],'checks':len(bywc[wc])})
        wo['complete']=sum(u['status']=='Complete' for u in wo['units'])
        wo['scrapped']=sum(u['status']=='Scrapped' for u in wo['units'])
    return sorted(orders.values(),key=lambda x:x['id'])


def apply_active_defect_holds(units, open_ids):
    """Overlay recorded open shop-floor reports without mutating synthetic source fixtures.

    A reported defect is a temporary quality hold, NOT scrap or an attributed fault.
    """
    affected=set(open_ids)
    copied=[dict(u) for u in units]
    for unit in copied:
        if unit['id'] in affected and unit['status'] not in (
            'Scrapped','Complete','Proposed replacement','Approved replacement'):
            unit['status']='Hold'
    return copied
