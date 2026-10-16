"""Manufacturing demo reference data and deterministic, explicitly synthetic scenario logic.

CTQ criteria in ctq_rules.json come directly from the supplied workbook.
Everything else below is demo data, with narrative values from GiNi Production Flow & Recovery.
This is NOT a calibrated discrete-event factory prediction engine.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

CTQ_RULES = json.loads((Path(__file__).parent / 'data' / 'ctq_rules.json').read_text(encoding='utf-8'))

CENTERS = [
 {'id':'WC1','name':'Pre-Assembly','type':'Tank','flow':'Tank route','planned':5,'present':4,'min_crew':3,'cycle':50,'status':'Short-staffed','equipment':'Fixtures FX-01 / FX-02','queue':1,'color':'amber'},
 {'id':'WC2','name':'Assembly','type':'Tank','flow':'Tank route','planned':4,'present':4,'min_crew':4,'cycle':30,'status':'Waiting for work','equipment':'Assembly lift AL-1','queue':0,'color':'amber'},
 {'id':'WC3','name':'Painting + cure','type':'Tank','flow':'Tank route','planned':2,'present':2,'min_crew':2,'cycle':40,'status':'On schedule','equipment':'Paint booth PB-1','queue':1,'color':'teal'},
 {'id':'WC4','name':'Markings','type':'Tank','flow':'Tank route','planned':2,'present':2,'min_crew':1,'cycle':10,'status':'On schedule','equipment':'Marking station MK-1','queue':0,'color':'teal'},
 {'id':'WC5','name':'Cover assembly','type':'Cover','flow':'Cover stream','planned':3,'present':3,'min_crew':2,'cycle':35,'status':'On schedule','equipment':'Cover jig CJ-1','queue':2,'color':'teal'},
 {'id':'WC6','name':'Cover painting','type':'Cover','flow':'Cover stream','planned':2,'present':2,'min_crew':1,'cycle':28,'status':'In progress','equipment':'Cover booth CB-1','queue':1,'color':'teal'},
 {'id':'WC7','name':'Accessory painting','type':'Accessories','flow':'Accessory stream','planned':2,'present':2,'min_crew':1,'cycle':25,'status':'In progress','equipment':'Coating booth AB-1','queue':2,'color':'teal'},
 {'id':'WC8','name':'Accessory markings','type':'Accessories','flow':'Accessory stream','planned':2,'present':2,'min_crew':1,'cycle':12,'status':'On schedule','equipment':'Marking table AM-1','queue':1,'color':'teal'},
]
CENTER_MAP = {w['id']:w for w in CENTERS}
ROUTES = {'Tank':['WC1','WC2','WC3','WC4'], 'Cover':['WC5','WC6'], 'Accessories':['WC7','WC8']}

WORKERS = [
 {'id':'W-001','name':'Sana Patel','home':'WC1','skills':['WC1'],'state':'Working','unit':'TANK-0019','since':'06:00'},
 {'id':'W-002','name':'Dev Shah','home':'WC1','skills':['WC1'],'state':'Working','unit':'TANK-0019','since':'06:00'},
 {'id':'W-003','name':'Meera Das','home':'WC1','skills':['WC1'],'state':'Working','unit':'TANK-0019','since':'06:00'},
 {'id':'W-004','name':'Kiran Rao','home':'WC1','skills':['WC1'],'state':'Working','unit':'TANK-0019','since':'06:00'},
 {'id':'W-005','name':'Ravi Kumar','home':'WC1','skills':['WC1'],'state':'Absent','unit':None,'since':None},
 {'id':'W-006','name':'Priya Nair','home':'WC2','skills':['WC2','WC1'],'state':'Waiting','unit':None,'since':'09:55'},
 {'id':'W-007','name':'Tom Wilson','home':'WC2','skills':['WC2'],'state':'Waiting','unit':None,'since':'09:55'},
 {'id':'W-008','name':'Lin Chen','home':'WC2','skills':['WC2'],'state':'Waiting','unit':None,'since':'09:55'},
 {'id':'W-009','name':'Ahmed Ali','home':'WC2','skills':['WC2'],'state':'Waiting','unit':None,'since':'09:55'},
 {'id':'W-010','name':'Nina Roy','home':'WC3','skills':['WC3'],'state':'Working','unit':'TANK-0017','since':'08:00'},
 {'id':'W-011','name':'Joel Moss','home':'WC3','skills':['WC3'],'state':'Working','unit':'TANK-0017','since':'08:00'},
 {'id':'W-012','name':'Arun Mehta','home':'WC4','skills':['WC4','WC1'],'state':'Waiting','unit':None,'since':'08:00'},
 {'id':'W-013','name':'Beth Ward','home':'WC4','skills':['WC4'],'state':'Waiting','unit':None,'since':'08:00'},
 {'id':'W-014','name':'Tara Singh','home':'WC5','skills':['WC5'],'state':'Working','unit':'COVER-1002','since':'06:00'},
 {'id':'W-015','name':'Oscar Lee','home':'WC5','skills':['WC5'],'state':'Working','unit':'COVER-1002','since':'06:00'},
 {'id':'W-016','name':'Evan Price','home':'WC5','skills':['WC5'],'state':'Working','unit':'COVER-1002','since':'06:00'},
 {'id':'W-017','name':'Isha Bose','home':'WC6','skills':['WC6'],'state':'Working','unit':'COVER-1001','since':'06:00'},
 {'id':'W-018','name':'Marc Silva','home':'WC6','skills':['WC6'],'state':'Working','unit':'COVER-1001','since':'06:00'},
 {'id':'W-019','name':'Ava Grant','home':'WC7','skills':['WC7'],'state':'Working','unit':'ACC-2002','since':'06:00'},
 {'id':'W-020','name':'Leo Park','home':'WC7','skills':['WC7'],'state':'Working','unit':'ACC-2002','since':'06:00'},
 {'id':'W-021','name':'Mina Tan','home':'WC8','skills':['WC8'],'state':'Working','unit':'ACC-2001','since':'06:00'},
 {'id':'W-022','name':'Eric Reed','home':'WC8','skills':['WC8'],'state':'Working','unit':'ACC-2001','since':'06:00'},
 {'id':'W-023','name':'Nora Finch','home':'Relief','skills':['WC1'],'state':'Available from 12:30','unit':None,'since':None},
]
WORKER_MAP = {w['id']:w for w in WORKERS}

SCENARIOS = {
 'normal':{'name':'Normal shift','short':'No disruption','good':10,'finish':'12:45','wait':15,'severity':'success','description':'All planned crew present and every tank passes the first gate.'},
 'absence':{'name':'WC1 absence','short':'One qualified worker absent','good':10,'finish':'13:55','wait':85,'severity':'warning','description':'WC1 drops from five qualified workers to four. The order still finishes on time.'},
 'scrap':{'name':'First-stage scrap','short':'One tank permanently scrapped','good':9,'finish':'12:45','wait':45,'severity':'danger','description':'TANK-0018 fails its first-stage inspection and cannot re-enter production.'},
 'combined':{'name':'Combined disruption','short':'Absence + permanent scrap','good':9,'finish':'13:55','wait':115,'severity':'danger','description':'WC1 is short-staffed and TANK-0018 is scrapped. The order is short one good tank.'},
 'replacement':{'name':'Replacement only','short':'Replacement without labor transfer','good':9,'finish':'14:45','wait':135,'severity':'danger','description':'Replacement starts too late at understaffed WC1; tenth unit finishes after the due time.'},
 'relief':{'name':'Replacement + relief','short':'Relief available from 12:30','good':9,'finish':'14:37','wait':127,'severity':'danger','description':'Relief worker arrives too late to protect the 14:30 deadline.'},
 'recovered':{'name':'Approved recovery','short':'Arun transfer + TANK-0021','good':10,'finish':'14:21','wait':111,'severity':'success','description':'A qualified transfer from WC4 to WC1 and one material-backed replacement recover the order.'},
 'actual':{'name':'Illustrative actual replay','short':'20-minute handover instead of 15','good':10,'finish':'14:22','wait':112,'severity':'success','description':'Replay uses a 20-minute handover. Not observed Siemens factory performance.'},
}
SCENARIO_ORDER = ['normal','absence','scrap','combined','replacement','relief','recovered','actual']

# Event_time and known_at are separate. No view may expose an event before known_at.
EVENTS = [
 {'id':'EV-100','unit':None,'event_time':'06:05','known_at':'06:05','type':'absence','title':'Ravi absence confirmed','text':'WC1 crew is 4 of 5. Minimum crew is still met.','wc':'WC1'},
 {'id':'EV-101','unit':'TANK-0018','event_time':'09:20','known_at':'09:20','type':'work','title':'WC1 pre-assembly started','text':'Crew Sana, Dev, Meera, Kiran','wc':'WC1'},
 {'id':'EV-102','unit':'TANK-0018','event_time':'10:40','known_at':'10:48','type':'scrap','title':'TANK-0018 failed first-stage gate','text':'Illustrative shell length 1,207 mm vs demo limit 1,195–1,205 mm; SCRAP, permanent.','wc':'WC1'},
 {'id':'EV-103','unit':None,'event_time':'09:55','known_at':'09:55','type':'waiting','title':'WC2 queue depleted','text':'Assembly crew available; upstream approved tank supply is limiting.','wc':'WC2'},
 {'id':'EV-104','unit':'TANK-0021','event_time':'10:55','known_at':'10:55','type':'proposed','title':'Replacement feasibility assessed','text':'One spare kit, lot ML-0415. The unit has not been manufactured.','wc':'WC1'},
]

UNITS = []
for n in range(11,21):
 name=f'TANK-{n:04d}'
 if n <= 16: wc,status,pct='WC4','Complete',100
 elif n == 17: wc,status,pct='WC3','Curing',74
 elif n == 18: wc,status,pct='WC1','Scrapped',14
 elif n == 19: wc,status,pct='WC1','In progress',22
 else: wc,status,pct='WC1','Queued',0
 UNITS.append({'id':name,'type':'Tank','order':'ORD-1042','wc':wc,'status':status,'progress':pct,'lot':'ML-0412','due':'14:30','replacement_for':None,'source':'Synthetic PDF scenario'})
UNITS.append({'id':'TANK-0021','type':'Tank','order':'ORD-1042','wc':'WC1','status':'Proposed replacement','progress':0,'lot':'ML-0415','due':'14:30','replacement_for':'TANK-0018','source':'Synthetic PDF scenario'})
for n,wc,status,pct in [(1001,'WC6','In progress',67),(1002,'WC5','In progress',37),(1003,'WC5','Queued',0),(1004,'WC6','Complete',100)]:
 UNITS.append({'id':f'COVER-{n}','type':'Cover','order':'COV-2007','wc':wc,'status':status,'progress':pct,'lot':f'CV-{n}','due':'15:00','replacement_for':None,'source':'Additional synthetic data'})
for n,wc,status,pct in [(2001,'WC8','In progress',80),(2002,'WC7','In progress',45),(2003,'WC7','Queued',0),(2004,'WC8','Complete',100)]:
 UNITS.append({'id':f'ACC-{n}','type':'Accessories','order':'ACC-3008','wc':wc,'status':status,'progress':pct,'lot':f'AX-{n}','due':'15:30','replacement_for':None,'source':'Additional synthetic data'})
UNIT_MAP = {u['id']:u for u in UNITS}

ABSENCE_SCENARIOS = frozenset(('absence', 'combined', 'replacement', 'relief', 'recovered', 'actual'))
SCRAP_SCENARIOS = frozenset(('scrap', 'combined', 'replacement', 'relief', 'recovered', 'actual'))
REPLACEMENT_SCENARIOS = frozenset(('replacement', 'relief', 'recovered', 'actual'))


def visible_events(asof='10:55', scenario='combined'):
 """Only show events recorded by the replay time AND belonging to this scenario."""
 def applicable(event):
  if event['known_at'] > asof:
   return False
  if event['type'] == 'absence':
   return scenario in ABSENCE_SCENARIOS
  if event['type'] == 'scrap':
   return scenario in SCRAP_SCENARIOS
  if event['type'] == 'waiting':
   return scenario in ABSENCE_SCENARIOS
  if event['type'] == 'proposed':
   return scenario in REPLACEMENT_SCENARIOS and asof >= '10:55'
  return True
 return sorted((e for e in EVENTS if applicable(e)), key=lambda e: e['known_at'], reverse=True)

def unit_view(unit, asof='10:55', overrides=None, recovery=False, scenario='combined'):
 """Display a scenario-consistent fixture, never a future quality decision.

 Earlier replay slots deliberately show coarse, not minute-by-minute, production
 states because unit-level historical timings are not present in the source.
 """
 u=dict(unit)
 if asof < '10:55' and u['type']=='Tank' and unit['id']!='TANK-0021':
  # At shift opening three tanks are approved at WC2 and seven start at WC1.
  # The PDF contains no intermediate tank-level snapshots before 10:55.
  n=int(u['id'][-4:])
  if n<=13: u.update(status='Queued',wc='WC2',progress=0)
  else: u.update(status='Queued',wc='WC1',progress=0)
 if unit['id']=='TANK-0018':
  if scenario not in SCRAP_SCENARIOS or asof < '10:48':
   u.update(status='In progress' if asof>='09:20' else 'Queued', progress=14 if asof>='09:20' else 0, wc='WC1')
 if unit['id']=='TANK-0021':
  u['status']='Approved replacement' if recovery and asof>='10:55' else 'Proposed replacement'
 # User-entered demo results represent the active 10:55+ scenario, never past replay.
 if asof >= '10:55' and overrides and u['id'] in overrides and u['id']!='TANK-0018':
  u.update({k:overrides[u['id']][k] for k in ('status','wc','progress')})
 return u

def ordered_ctqs(wc):
 return [c for c in CTQ_RULES if c['wc']==wc]

def centers_with_counts(units, scenario='combined', asof='10:55', recovery=False):
 """Local capacity and queues from visible units; no queued-unit double counting."""
 waiting=Counter(u['wc'] for u in units if u['status'] in ('Queued','Approved replacement'))
 active=Counter(u['wc'] for u in units if u['status'] in ('In progress','Curing','At inspection','Inspection pending','Hold','Ready for next stage'))
 out=[]
 for c in CENTERS:
  row=dict(c)
  row['queue']=waiting[c['id']]
  row['active_count']=active[c['id']]
  row['checks']=len(ordered_ctqs(c['id']))
  absence=scenario in ABSENCE_SCENARIOS and asof>='06:05'
  if c['id']=='WC1':
   row['present']=4 if absence else 5
   row['status']='Short-staffed' if absence else 'On schedule'
   row['color']='amber' if absence else 'teal'
   joined='11:15' if scenario=='actual' else '11:10'
   returned='12:52' if scenario=='actual' else '12:51'
   if scenario in ('recovered','actual') and joined <= asof < returned:
    row['present']=5;row['status']='Staffing restored by transfer';row['color']='teal'
  if c['id']=='WC2':
   starvation=scenario in ABSENCE_SCENARIOS and '09:55'<=asof<'11:35'
   row['status']='Waiting for input' if starvation else 'On schedule'
   row['color']='amber' if starvation else 'teal'
   # The three approved tanks at 06:00 are represented by TANK-0011–0013.
   # Never add an independent background count to those same units.
   if starvation: row['queue']=0
  if c['id']=='WC4' and scenario in ('recovered','actual'):
   joined='11:15' if scenario=='actual' else '11:10'
   returned='12:52' if scenario=='actual' else '12:51'
   if joined<=asof<returned:
    row['present']=1;row['status']='Qualified worker transferred';row['color']='amber'
  if row['id']=='WC1':
   row['cycle']=40 if row['present']>=5 else 50 if row['present']==4 else 67 if row['present']==3 else 0
  if row['id']=='WC4':
   row['cycle']=10 if row['present']>=2 else 20 if row['present']==1 else 0
  row['demo_units_per_hour']=round(60/row['cycle'],2) if row['cycle'] and row['present']>=row['min_crew'] else 0
  row['demo_local_backlog_minutes']=(row['queue']+row['active_count'])*row['cycle'] if row['demo_units_per_hour'] else None
  out.append(row)
 return out

def verify_candidate(worker_id, scenario='combined', asof='10:55'):
 """Validate skill, availability and both station crews at the requested time."""
 if worker_id not in WORKER_MAP:return {'feasible':False,'reason':'Unknown worker'}
 w=WORKER_MAP[worker_id]
 if 'WC1' not in w['skills']:return {'feasible':False,'reason':'Not qualified for WC1'}
 current=next(p for p in workers_for_scenario(scenario,asof) if p['id']==worker_id)
 state=current['state']
 if state=='Absent':return {'feasible':False,'reason':'Worker is absent'}
 if state=='Transferred to WC1':return {'feasible':False,'reason':'Already assigned to WC1; cannot double-book'}
 if state.startswith('Available from') and asof<'12:30':return {'feasible':False,'reason':'Not available until 12:30'}
 if state not in ('Waiting','Present') and not (state.startswith('Available from') and asof>='12:30'):
  return {'feasible':False,'reason':f'Worker is {state.lower()}; cannot move an occupied worker without a release'}
 home=CENTER_MAP.get(w['home'])
 # Source crew numbers must be from the same scenario snapshot, not the static fixture.
 crew=next((c for c in centers_with_counts([],scenario,asof) if c['id']==w['home']),None)
 if crew and crew['present']-1<crew['min_crew']:
  return {'feasible':False,'reason':f"{w['home']} would have {crew['present']-1} people, below minimum {crew['min_crew']}; source station cannot continue"}
 return {'feasible':True,'reason':f"Qualified and available; {w['home']} keeps its minimum crew. Demo transit + handover: {15 if worker_id=='W-012' else 10} min.", 'source_crew_before':crew['present'] if crew else None, 'source_crew_after':crew['present']-1 if crew else None}

def workers_for_scenario(scenario='combined',asof='10:55'):
 """Scenario-aware observed states; missing scans never imply idle."""
 people=[dict(w) for w in WORKERS]
 for w in people:
  if w['id']=='W-005' and (scenario not in ABSENCE_SCENARIOS or asof<'06:05'):
   w['state']='Present';w['unit']='TANK-0019'
  if w['id'] in ('W-006','W-007','W-008','W-009'):
   starvation=scenario in ABSENCE_SCENARIOS and '09:55'<=asof<'11:35'
   if not starvation:
    w['state']='Working';w['unit']='TANK-0016'
  if w['id']=='W-012' and scenario in ('recovered','actual'):
   joined='11:15' if scenario=='actual' else '11:10'
   returned='12:52' if scenario=='actual' else '12:51'
   if joined<=asof<returned:
    w['state']='Transferred to WC1';w['unit']='TANK-0020'
   elif asof>=returned:
    w['state']='Back at WC4';w['unit']=None
 return people
