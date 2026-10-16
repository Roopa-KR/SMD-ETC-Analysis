from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from manufacturing.model import *
from manufacturing.quality_logic import *
from manufacturing.shopfloor import work_order_overview
from manufacturing.scoring import POINTS,work_order_score
from collections import Counter
root=Path(__file__).resolve().parents[1]
e=Environment(loader=FileSystemLoader(root/'templates'),undefined=StrictUndefined,autoescape=True)
e.globals.update(url_for=lambda endpoint,**args:'/'+endpoint+'?'+('&'.join(f'{k}={v}' for k,v in args.items())),request=SimpleNamespace(endpoint='dashboard'),get_flashed_messages=lambda **kw:[])
scenario={'id':'combined',**SCENARIOS['combined'],'changed':False}
units=[unit_view(u,'10:55',scenario='combined') for u in UNITS if u['id']!='TANK-0021']
center=centers_with_counts(units,'combined','10:55')
worker=WORKERS[11]
metrics=dict(target=10,good=6,forecast=9,scrapped=1,at_risk=1,open_wip=3,total_tanks=10,on_time_tanks=9,at_risk_tanks=1,total_components=8,absent_workers=1,wc1_qualified=6,inspection_pass=0,inspection_fail=0,inspection_review=0)
ctx=dict(scene=scenario,asof='10:55',centers=center,units=units,workers=WORKERS,alerts=[],events=visible_events('10:55','combined'),approved=None,ctqs=CTQ_RULES,scenario_order=SCENARIO_ORDER,scenarios=SCENARIOS,stats=metrics,center_map=CENTER_MAP,all_centers=CENTERS,routes=ROUTES,demo_banner='Synthetic demonstration',csrf_token='unit-test-token',
    filtered_units=units,search='',type_filter='all',status_filter='all',sort_by='unit',direction='asc',
    unit=units[9],route=ROUTES['Tank'],inspection_results={},inspection_history=[],unit_events=[],is_scrap_scenario=True,
    center=center[0],assigned=WORKERS[:5],center_units=units,checks=ordered_ctqs('WC1'),
    worker=worker,transfer=verify_candidate('W-012'),home=CENTER_MAP['WC4'],
    wc_filter='all',recorded_count=0,
    check=ordered_ctqs('WC1')[0],existing=None,inspection_allowed=True,
    candidates=[{'worker':WORKER_MAP[i],'test':verify_candidate(i)} for i in ('W-012','W-006','W-023')]
)
orders=work_order_overview(units,[])
ctx.update(selected_wc='WC1',selected_worker='W-001',wc_workers=WORKERS[:5],
           selected_unit='TANK-0019',selectable_units=[u for u in units if u['wc']=='WC1'],
           active_task=None,tasks=[],stage_checks=[dict(x,recorded=None) for x in ordered_ctqs('WC1')],
           handovers=[],defects=[],wo_list=orders,selected_wo='ORD-1042',
           selected_order=next(x for x in orders if x['id']=='ORD-1042'),
           operation_tasks=[],incoming=[],audit=[],
           operators=[],finished_tasks=0,active_tasks=0,productive_seconds=0,
           scoring=[{'order':o,'score':work_order_score(completed=False,rework_count=0,origin_fixed_confirmed=False,downstream_confirmed=0),'pending_defects':0} for o in orders],point_rules=POINTS)
files=['dashboard','units','unit_detail','centers','center_detail','workers','worker_detail','quality','inspection','recovery','operator','work_orders','lms']
for filename in files:
 try:
  html=e.get_template('mfg/'+filename+'.html').render(**ctx)
  assert '<!doctype html>' in html
  assert not 'Undefined' in html
  print('PASS',filename,len(html))
 except Exception as ex:
  print('FAIL',filename,type(ex).__name__,ex)
  raise
