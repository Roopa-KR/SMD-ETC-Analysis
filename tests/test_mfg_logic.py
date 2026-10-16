"""Manufacturing pure-logic smoke/regression suite; runs without optional Flask runtime."""
from pathlib import Path
import ast
import json
import pytest
from jinja2 import Environment, FileSystemLoader
from manufacturing.model import (
    CENTERS, CENTER_MAP, WORKERS, UNITS, ROUTES, CTQ_RULES, SCENARIOS,
    visible_events, verify_candidate, workers_for_scenario, centers_with_counts)
from manufacturing.quality_logic import (
    can_inspect_at_stage, compute_quality_state, evidence_is_valid_image)


@pytest.mark.parametrize('code,ctype,name',[
    ('WC1','Tank','Pre-Assembly'),('WC2','Tank','Assembly'),
    ('WC3','Tank','Painting'),('WC4','Tank','Markings'),
    ('WC5','Cover','assembly'),('WC6','Cover','painting'),
    ('WC7','Accessories','painting'),('WC8','Accessories','markings')])
def test_all_source_work_centers(code,ctype,name):
    assert CENTER_MAP[code]['type']==ctype
    assert name.lower() in CENTER_MAP[code]['name'].lower()


def test_source_check_coverage_and_uniqueness():
    assert len(CTQ_RULES)==24
    assert len({x['check_id'] for x in CTQ_RULES})==24
    assert set(x['source_row'] for x in CTQ_RULES)==set(range(3,27))
    assert {w['id'] for w in CENTERS}=={x['wc'] for x in CTQ_RULES}
    assert {x['answer_type'] for x in CTQ_RULES}=={'Yes/No','Input'}
    assert all(x['source_kind']=='CTQ workbook' for x in CTQ_RULES)


def test_source_CTQ_components_match_routes():
    for check in CTQ_RULES:
        assert check['wc'] in ROUTES[check['component_type']]


def test_scenarios_preserve_reference_results():
    assert (SCENARIOS['normal']['good'],SCENARIOS['normal']['finish'])==(10,'12:45')
    assert (SCENARIOS['absence']['good'],SCENARIOS['absence']['wait'])==(10,85)
    assert (SCENARIOS['combined']['good'],SCENARIOS['combined']['wait'])==(9,115)
    assert (SCENARIOS['replacement']['good'],SCENARIOS['replacement']['finish'])==(9,'14:45')
    assert (SCENARIOS['recovered']['good'],SCENARIOS['recovered']['finish'])==(10,'14:21')
    assert (SCENARIOS['actual']['good'],SCENARIOS['actual']['finish'])==(10,'14:22')


def test_no_future_knowledge_before_recorded_time():
    assert not any(e['id']=='EV-102' for e in visible_events('10:45'))
    assert any(e['id']=='EV-102' for e in visible_events('10:48'))


@pytest.mark.parametrize('worker,feasible', [('W-012',True),('W-006',False),('W-023',False),('W-005',False)])
def test_transfer_source_and_skill_checks(worker,feasible):
    assert verify_candidate(worker)['feasible'] is feasible


def test_scenario_staffing_changes_consistently():
    normal={x['id']:x for x in centers_with_counts(UNITS,'normal')}
    absence={x['id']:x for x in centers_with_counts(UNITS,'absence')}
    recovered={x['id']:x for x in centers_with_counts(UNITS,'recovered','11:40')}
    assert normal['WC1']['present']==5
    assert absence['WC1']['present']==4
    assert absence['WC1']['cycle']==50
    assert recovered['WC1']['present']==5
    assert recovered['WC4']['present']==1
    assert recovered['WC4']['cycle']==20
    assert absence['WC2']['present']==4
    assert absence['WC2']['status']=='Waiting for input'


def test_worker_replay_is_not_static_absence():
    assert any(x['id']=='W-005' and x['state']=='Present' for x in workers_for_scenario('normal'))
    assert any(x['id']=='W-005' and x['state']=='Absent' for x in workers_for_scenario('combined'))
    assert any(x['id']=='W-012' and x['state']=='Transferred to WC1' for x in workers_for_scenario('recovered','11:40'))


def test_no_component_on_wrong_route():
    assert set(ROUTES)=={'Tank','Cover','Accessories'}
    assert all(u['wc'] in ROUTES[u['type']] for u in UNITS)
    assert len({u['id'] for u in UNITS})==len(UNITS)


def test_inspection_cannot_skip_stage():
    unit=next(u for u in UNITS if u['id']=='TANK-0020')
    assert can_inspect_at_stage(unit,unit,'WC1',ROUTES)
    assert not can_inspect_at_stage(unit,unit,'WC2',ROUTES)


def test_first_stage_fail_permanent_scrap():
    unit=next(u for u in UNITS if u['id']=='TANK-0020')
    assert compute_quality_state(unit,unit,'WC1',{'CTQ-003':'FAIL'},ROUTES,CTQ_RULES)[0]=='Scrapped'


def test_later_failure_holds_not_scraps():
    unit=next(u for u in UNITS if u['id']=='TANK-0017')
    result=compute_quality_state(unit,unit,'WC3',{'CTQ-012':'FAIL'},ROUTES,CTQ_RULES)
    assert result[0]=='Hold' and result[1]=='WC3'


def test_missing_check_never_releases_tank():
    unit=next(u for u in UNITS if u['id']=='TANK-0020')
    result=compute_quality_state(unit,unit,'WC1',{'CTQ-003':'PASS'},ROUTES,CTQ_RULES)
    assert result[0]=='Inspection pending'


def test_unreviewed_numeric_measurement_never_releases():
    unit=next(u for u in UNITS if u['id']=='TANK-0020')
    recorded={f'CTQ-{n:03d}':'PASS' for n in range(3,7)}
    recorded['CTQ-004']='REVIEW'
    assert compute_quality_state(unit,unit,'WC1',recorded,ROUTES,CTQ_RULES)[0]=='Inspection pending'


def test_all_stage_passes_release_only_next_stage():
    unit=next(u for u in UNITS if u['id']=='TANK-0020')
    recorded={f'CTQ-{n:03d}':'PASS' for n in range(3,7)}
    result=compute_quality_state(unit,unit,'WC1',recorded,ROUTES,CTQ_RULES)
    assert result==('Ready for next stage','WC2',25)
    active=dict(unit,status=result[0],wc=result[1],progress=result[2])
    assert not can_inspect_at_stage(unit,active,'WC3',ROUTES)
    assert can_inspect_at_stage(unit,active,'WC2',ROUTES)


def test_completed_stage_only_when_all_pass():
    unit=next(u for u in UNITS if u['id']=='ACC-2001')
    assert compute_quality_state(unit,unit,'WC8',{'CTQ-026':'PASS'},ROUTES,CTQ_RULES)[0]=='Complete'


@pytest.mark.parametrize('content,ext,valid',[
    (b'\x89PNG\r\n\x1a\nxxxx','png',False),
    (b'\xff\xd8\xffthisisthej','jpg',False),
    (b'RIFFabcdWEBPimage','webp',False),
    (b'hello malware','png',False),
    (b'RIFFabcdXXXXimage','webp',False),
    (b'\xff\xd8\xffabc','jpeg',False),
])
def test_image_evidence_magic_bytes(content,ext,valid):
    assert evidence_is_valid_image(content,ext) is valid


def test_python_source_syntax():
    root=Path(__file__).resolve().parents[1]
    for path in (root/'app.py',root/'manufacturing/model.py',root/'manufacturing/quality_logic.py'):
        ast.parse(path.read_text(encoding='utf-8'))


def test_all_manufacturing_templates_parse():
    root=Path(__file__).resolve().parents[1]
    loader=Environment(loader=FileSystemLoader(root/'templates'))
    for template in (root/'templates/mfg').glob('*.html'):
        loader.get_template('mfg/'+template.name)


def test_demo_pages_do_not_show_obsolete_truck_terms():
    root=Path(__file__).resolve().parents[1]
    for template in (root/'templates/mfg').glob('*.html'):
        assert 'truck performance' not in template.read_text().lower()
        assert 'total trucks' not in template.read_text().lower()


@pytest.mark.parametrize('format_name,extension',[('PNG','png'),('JPEG','jpg'),('WEBP','webp')])
def test_complete_image_files_are_accepted(format_name,extension):
    from io import BytesIO
    from PIL import Image
    stream=BytesIO()
    Image.new('RGB',(3,3)).save(stream,format=format_name)
    assert evidence_is_valid_image(stream.getvalue(),extension)
    assert not evidence_is_valid_image(stream.getvalue()[:30],extension)


def test_tank_scrap_does_not_leak_into_normal_scenario():
    from manufacturing.model import unit_view, UNIT_MAP
    u=UNIT_MAP['TANK-0018']
    assert unit_view(u,'10:55',scenario='normal')['status']!='Scrapped'
    assert unit_view(u,'10:55',scenario='combined')['status']=='Scrapped'
    assert unit_view(u,'10:45',scenario='combined')['status']!='Scrapped'


def test_no_wrong_scenario_events_or_future_action_events():
    assert not any(e['type']=='scrap' for e in visible_events('14:30','normal'))
    assert not any(e['type']=='absence' for e in visible_events('14:30','scrap'))
    assert not any(e['type']=='proposed' for e in visible_events('10:45','recovered'))
    assert any(e['type']=='scrap' for e in visible_events('10:55','combined'))


def test_opening_wip_is_at_correct_stations():
    from manufacturing.model import unit_view, UNIT_MAP
    snapshot=[unit_view(u,'06:00',scenario='normal') for u in UNITS if u['type']=='Tank' and u['id']!='TANK-0021']
    assert sum(u['wc']=='WC2' and u['status']=='Queued' for u in snapshot)==3
    assert sum(u['wc']=='WC1' and u['status']=='Queued' for u in snapshot)==7
    assert sum(u['status']=='Complete' for u in snapshot)==0


def test_queue_not_double_counted_in_local_capacity():
    from manufacturing.model import unit_view
    units=[unit_view(u,'10:55',scenario='combined') for u in UNITS if u['id']!='TANK-0021']
    centers={c['id']:c for c in centers_with_counts(units,'combined','10:55')}
    assert centers['WC1']['queue']==1
    assert centers['WC1']['active_count']==1
    assert centers['WC1']['demo_local_backlog_minutes']==100


def test_recovered_worker_returns_to_home_and_cannot_double_book():
    assert next(w for w in workers_for_scenario('recovered','11:40') if w['id']=='W-012')['state']=='Transferred to WC1'
    assert not verify_candidate('W-012','recovered','11:40')['feasible']
    assert next(w for w in workers_for_scenario('recovered','13:00') if w['id']=='W-012')['state']=='Back at WC4'


def test_relief_not_eligible_early_and_available_later():
    assert not verify_candidate('W-023','combined','10:55')['feasible']
    assert verify_candidate('W-023','combined','12:30')['feasible']
