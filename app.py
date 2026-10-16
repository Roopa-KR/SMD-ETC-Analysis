"""GiNi Production Flow & Recovery — source-aware synthetic Flask demonstrator.

Run: python -m pip install -r requirements-manufacturing.txt && python app.py
This does not integrate with Siemens Energy systems. Use synthetic data only.
"""
from __future__ import annotations
import os
import secrets
import sqlite3
from datetime import datetime
from math import isfinite
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
from flask import Flask, abort, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, Response, has_request_context
from manufacturing.model import (
    CENTERS, CENTER_MAP, WORKERS, WORKER_MAP, UNITS, UNIT_MAP, ROUTES, CTQ_RULES,
    SCENARIOS, SCENARIO_ORDER, ABSENCE_SCENARIOS, SCRAP_SCENARIOS, REPLACEMENT_SCENARIOS, visible_events, unit_view, ordered_ctqs,
    centers_with_counts, workers_for_scenario, verify_candidate
)
from manufacturing.quality_logic import compute_quality_state, can_inspect_at_stage, evidence_is_valid_image
from manufacturing.shopfloor import setup as setup_shopfloor, apply_active_defect_holds

ROOT=Path(__file__).resolve().parent
ALLOWED_EVIDENCE={'png','jpg','jpeg','webp'}


def create_app(test_config=None):
    app=Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('GINI_DEMO_SECRET', secrets.token_hex(32)),
        DEMO_DB=str(ROOT/'data'/'manufacturing_demo.sqlite3'),
        EVIDENCE_DIR=str(ROOT/'data'/'evidence'),
        MAX_CONTENT_LENGTH=6*1024*1024)
    if test_config:app.config.update(test_config)
    Path(app.config['DEMO_DB']).parent.mkdir(parents=True,exist_ok=True)

    @contextmanager
    def connect():
        """Always commit/rollback and close; sqlite Connection.__exit__ alone does not close."""
        db=sqlite3.connect(app.config['DEMO_DB'],timeout=8)
        try:
            db.row_factory=sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize_db():
        with connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS inspection_results (
                unit_id TEXT NOT NULL, check_id TEXT NOT NULL, value TEXT NOT NULL,
                verdict TEXT NOT NULL, note TEXT, evidence_filename TEXT,
                inspector TEXT NOT NULL, recorded_at TEXT NOT NULL,
                PRIMARY KEY(unit_id, check_id));
            CREATE TABLE IF NOT EXISTS inspection_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT, unit_id TEXT NOT NULL,
                check_id TEXT NOT NULL, value TEXT NOT NULL, verdict TEXT NOT NULL,
                note TEXT, inspector TEXT NOT NULL, recorded_at TEXT NOT NULL,
                evidence_filename TEXT);
            CREATE TABLE IF NOT EXISTS unit_state (
                unit_id TEXT PRIMARY KEY, status TEXT NOT NULL, wc TEXT NOT NULL, progress INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, action_key TEXT NOT NULL UNIQUE,
                action_type TEXT NOT NULL, actor TEXT NOT NULL, state TEXT NOT NULL,
                proposed_at TEXT NOT NULL, approved_at TEXT, started_at TEXT, completed_at TEXT,
                worker_id TEXT, from_wc TEXT, to_wc TEXT, replacement_id TEXT, note TEXT);
            ''')
            setup_shopfloor(db)
            columns={r[1] for r in db.execute('PRAGMA table_info(inspection_audit)')}
            if 'evidence_filename' not in columns:
                db.execute('ALTER TABLE inspection_audit ADD COLUMN evidence_filename TEXT')
    initialize_db()

    def csrf_token():
        if 'csrf_token' not in session:session['csrf_token']=secrets.token_urlsafe(24)
        return session['csrf_token']

    def csrf_required(fn):
        @wraps(fn)
        def inner(*args,**kwargs):
            token=request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
            if not token or not secrets.compare_digest(token,str(session.get('csrf_token',''))):
                abort(403,'Invalid form security token; reload the page and try again.')
            return fn(*args,**kwargs)
        return inner

    @app.after_request
    def security_headers(resp):
        resp.headers['X-Content-Type-Options']='nosniff'
        resp.headers['X-Frame-Options']='DENY'
        resp.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        resp.headers['Cache-Control']='no-store'
        return resp

    def approved_recovery():
        with connect() as db:return db.execute("SELECT * FROM action_log WHERE action_key='arun_replacement' AND state='approved'").fetchone()

    def overrides():
        with connect() as db:
            return {r['unit_id']:dict(r) for r in db.execute('SELECT * FROM unit_state')}

    def check_results(unit_id=None):
        with connect() as db:
            if unit_id:return {r['check_id']:dict(r) for r in db.execute('SELECT * FROM inspection_results WHERE unit_id=?',(unit_id,))}
            return [dict(r) for r in db.execute('SELECT * FROM inspection_results')]

    def scenarios_state(scenario_id=None, asof=None):
        asof=asof or request.args.get('asof','10:55')
        if (len(asof)!=5 or asof[2]!=':' or not (asof[:2].isdigit() and asof[3:].isdigit())
                or not ('06:00'<=asof<='14:30') or int(asof[3:])>59):
            asof='10:55'
        scene=scenario_id or request.args.get('scenario') or ('recovered' if approved_recovery() else 'combined')
        if scene not in SCENARIOS:scene='combined'
        s=dict(SCENARIOS[scene]);s['id']=scene
        # Scenario choices are what-if hypotheses. Future actions/events cannot be
        # presented as known before their recorded/proposed time.
        if asof<'06:05' and scene in ABSENCE_SCENARIOS:
            for key in ('good','finish','wait'):s[key]=SCENARIOS['normal'][key]
            s['description']='Shift opening: the absence is not known until 06:05.'
        elif asof<'10:48' and scene in SCRAP_SCENARIOS:
            basis='absence' if scene in ABSENCE_SCENARIOS else 'normal'
            for key in ('good','finish','wait'):s[key]=SCENARIOS[basis][key]
            s['description']='At this replay time the 10:40 failure has not yet been entered (known at 10:48).'
        elif asof<'10:55' and scene in REPLACEMENT_SCENARIOS:
            for key in ('good','finish','wait'):s[key]=SCENARIOS['combined'][key]
            s['description']='Recovery is not proposed until 10:55; this is the disruption forecast before that decision.'
        # A separately recorded inspection can invalidate a canned fixture count.
        # Quantity can be bounded, but an ETA requires full rescheduling, NOT a
        # made-up unchanged last-unit completion time.
        changed=overrides() if asof>='10:55' else {}
        damaged=sum(1 for uid,item in changed.items() if uid.startswith('TANK-')
                    and uid!='TANK-0018' and item['status'] in ('Scrapped','Hold'))
        s['good']=max(0,s['good']-damaged)
        s['changed']=bool(damaged)
        if damaged:
            s['finish']='Recalc needed'
            s['description'] += f' {damaged} additionally held/scrapped tank(s) lower the illustrative good-unit count. Stage-by-stage ETA has not been recalculated.'
        return s,asof

    def data_units(asof='10:55',scenario='combined',approved=False):
        ov=overrides() if asof>='10:55' else {}
        # Proposed replacements belong only to branches that actually consider them.
        include_replacement=scenario in REPLACEMENT_SCENARIOS and asof>='10:55'
        is_approved=bool(approved) and scenario in ('recovered','actual')
        units=[unit_view(u,asof,ov,is_approved,scenario) for u in UNITS
                if u['id']!='TANK-0021' or include_replacement]
        if asof>='10:55':
            with connect() as db:
                pending={r['unit_id'] for r in db.execute(
                    "SELECT DISTINCT unit_id FROM shop_defects WHERE status='OPEN'")}
            units=apply_active_defect_holds(units,pending)
        return units

    def context(scene=None,asof=None):
        s,t=scenarios_state(scene,asof)
        rec=approved_recovery()
        with connect() as db:
            open_defect_ids={r['unit_id'] for r in db.execute(
                "SELECT DISTINCT unit_id FROM shop_defects WHERE status='OPEN'")}
        if open_defect_ids and t>='10:55':
            s['changed']=True
            s['finish']='Recalc needed'
            s['description']+=' Open shop-floor defect reports require review; the fixed scenario is not a fresh production forecast.'
        us=data_units(t,s['id'],bool(rec))
        tank=[u for u in us if u['type']=='Tank']
        people=workers_for_scenario(s['id'],t)
        results=check_results() if t>='10:55' else []
        alerts=[]
        if t>='06:05' and s['id'] in ABSENCE_SCENARIOS:
            alerts.append({'color':'amber','time':'06:05','title':'WC1 short one qualified operator','desc':'4 of 5 crew present until recovery.','href':'work_center_detail','ref':'WC1'})
        if '09:55'<=t<'11:35' and s['id'] in ABSENCE_SCENARIOS:
            alerts.append({'color':'amber','time':'09:55','title':'WC2 waiting for approved input','desc':'Assembly is fully staffed; its upstream flow is limiting.','href':'work_center_detail','ref':'WC2'})
        if t>='10:48' and s['id'] in SCRAP_SCENARIOS:
            alerts.append({'color':'red','time':'10:48','title':'TANK-0018 scrapped permanently','desc':'First-stage failure; cannot be reused.','href':'unit_detail','ref':'TANK-0018'})
        if s['changed']:
            alerts.insert(0,{'color':'red','time':t,'title':'Production/quality change needs review','desc':'A recorded inspection or open issue invalidates the canned ETA. Full rescheduling is not yet implemented.','href':'units','ref':None})
        if s['good']<10 and t>='10:48':
            alerts.insert(0,{'color':'red','time':t,'title':'ORD-1042 deadline at risk','desc':f"Projected {s['good']} of 10 good tanks by 14:30.",'href':'recovery','ref':None})
        registered=[u for u in tank if u['status']!='Proposed replacement']
        totals={'target':10,'good':sum(u['status']=='Complete' for u in registered),
                'forecast':s['good'], 'scrapped':sum(u['status']=='Scrapped' for u in registered),
                'at_risk':int(s['good']<10),
                'open_wip':sum(u['status'] not in ('Complete','Scrapped') for u in registered),
                'total_tanks':len(registered),'on_time_tanks':min(10,s['good']),
                'at_risk_tanks':max(0,10-s['good']),
                'total_components':sum(u['type']!='Tank' for u in us),
                'absent_workers':sum(w['state']=='Absent' for w in people),
                'wc1_qualified':sum('WC1' in w['skills'] for w in people),
                'inspection_pass':sum(r['verdict']=='PASS' for r in results),
                'inspection_fail':sum(r['verdict']=='FAIL' for r in results),
                'inspection_review':sum(r['verdict']=='REVIEW' for r in results)}
        assert totals['good']+totals['scrapped']+totals['open_wip']==totals['total_tanks']
        return dict(scene=s,asof=t,centers=centers_with_counts(us,s['id'],t,bool(rec)),
            units=us,workers=people,alerts=alerts,events=visible_events(t,s['id']),
            is_scrap_scenario=s['id'] in SCRAP_SCENARIOS,
            approved=rec,ctqs=CTQ_RULES,scenario_order=SCENARIO_ORDER,scenarios=SCENARIOS,stats=totals)

    @app.context_processor
    def shared():return {'csrf_token':csrf_token(),'center_map':CENTER_MAP,'all_centers':CENTERS,'routes':ROUTES,'demo_banner':'SYNTHETIC DEMONSTRATION · NO LIVE FACTORY DATA'}

    @app.route('/')
    def dashboard():return render_template('mfg/dashboard.html',**context())

    def filtered_units(ctx):
        unit_type=request.args.get('type','all')
        status=request.args.get('status','all')
        query=request.args.get('q','').strip().lower()[:100]
        selected=[u for u in ctx['units'] if (unit_type=='all' or u['type']==unit_type)
                  and (status=='all' or u['status']==status)
                  and (not query or query in u['id'].lower() or query in u['order'].lower())]
        sort=request.args.get('sort','unit')
        keys={'unit':lambda u:u['id'],'work_center':lambda u:(u['wc'],u['id']),
              'progress':lambda u:(u['progress'],u['id']),'due':lambda u:(u['due'],u['id'])}
        direction=request.args.get('direction','asc')
        selected.sort(key=keys.get(sort,keys['unit']),reverse=direction=='desc')
        return selected,{'search':query,'type_filter':unit_type,'status_filter':status,
                         'sort_by':sort if sort in keys else 'unit','direction':direction if direction in ('asc','desc') else 'asc'}

    @app.url_defaults
    def keep_replay_selection(endpoint,values):
        # Links across views retain the user's what-if scenario and replay time.
        if not has_request_context() or endpoint=='static':return
        for key in ('scenario','asof'):
            if key not in values and request.args.get(key):
                values[key]=request.args[key]

    @app.route('/units')
    def units():
        ctx=context()
        selected,filter_state=filtered_units(ctx)
        ctx.update(filtered_units=selected,**filter_state)
        return render_template('mfg/units.html',**ctx)

    @app.route('/units/<unit_id>')
    def unit_detail(unit_id):
        if unit_id not in UNIT_MAP:abort(404)
        ctx=context()
        u=next((x for x in ctx['units'] if x['id']==unit_id),None)
        if not u:abort(404)
        ctx.update(unit=u,route=ROUTES[u['type']],inspection_results=check_results(unit_id),
            unit_events=[x for x in ctx['events'] if x['unit']==unit_id])
        return render_template('mfg/unit_detail.html',**ctx)

    @app.route('/api/tank-performance')
    def api_tank_performance():
        ctx=context()
        return jsonify({'scenario':ctx['scene']['id'],'asof':ctx['asof'],
            'metrics':{k:ctx['stats'][k] for k in ('total_tanks','on_time_tanks','at_risk_tanks','target','good','forecast','scrapped')},
            'basis':'Deterministic concept-scenario projected quantity, not measured on-time plant performance'})

    @app.route('/exports/units.csv')
    def export_units_csv():
        import csv,io
        ctx=context();out=io.StringIO();w=csv.writer(out)
        w.writerow(['Unit ID','Equipment Type','Order','Work Center','Production Status','Progress %','Due Time','Record Source'])
        for u in filtered_units(ctx)[0]:
            w.writerow([u['id'],u['type'],u['order'],u['wc'],u['status'],u['progress'],u['due'],u['source']])
        return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=tank_component_demo.csv'})

    @app.route('/work-centers')
    def work_centers():return render_template('mfg/centers.html',**context())

    @app.route('/work-centers/<wc>')
    def work_center_detail(wc):
        if wc not in CENTER_MAP:abort(404)
        ctx=context()
        center=next(x for x in ctx['centers'] if x['id']==wc)
        assigned=[dict(w) for w in ctx['workers'] if w['home']==wc and w['state']!='Transferred to WC1']
        transferred=next((dict(w) for w in ctx['workers'] if w['id']=='W-012' and w['state']=='Transferred to WC1'),None)
        if wc=='WC1' and transferred:assigned.append(transferred)
        ctx.update(center=center,assigned=assigned,center_units=[u for u in ctx['units'] if u['wc']==wc],
            checks=ordered_ctqs(wc))
        return render_template('mfg/center_detail.html',**ctx)

    @app.route('/workers')
    def workers():return render_template('mfg/workers.html',**context())

    @app.route('/workers/<worker_id>')
    def worker_detail(worker_id):
        if worker_id not in WORKER_MAP:abort(404)
        ctx=context();w=next(dict(x) for x in ctx['workers'] if x['id']==worker_id)
        ctx.update(worker=w,transfer=verify_candidate(worker_id,ctx['scene']['id'],ctx['asof']),home=CENTER_MAP.get(w['home']))
        return render_template('mfg/worker_detail.html',**ctx)

    @app.route('/quality')
    def quality():
        ctx=context();wc=request.args.get('wc','all')
        ctx.update(checks=[x for x in CTQ_RULES if wc=='all' or x['wc']==wc],wc_filter=wc,
                   recorded_count=len(check_results()))
        return render_template('mfg/quality.html',**ctx)

    @app.route('/quality/<unit_id>/<check_id>',methods=['GET','POST'])
    def inspection_form(unit_id,check_id):
        if unit_id not in UNIT_MAP:abort(404)
        check=next((c for c in CTQ_RULES if c['check_id']==check_id),None)
        if not check or check['wc'] not in ROUTES[UNIT_MAP[unit_id]['type']]:abort(404)
        unit=UNIT_MAP[unit_id]
        if request.method=='POST':
            csrf_required(lambda:None)()
            with connect() as db:
                if db.execute("SELECT 1 FROM shop_defects WHERE unit_id=? AND status='OPEN'",(unit_id,)).fetchone():
                    abort(409,'This unit has an open defect report; quality review is required before new CTQ release.')
            if unit_id=='TANK-0018':abort(409,'Permanent scrap cannot be reversed or re-inspected.')
            if unit_id=='TANK-0021' and not approved_recovery():
                abort(409,'Approve the replacement scenario before inspecting its new physical unit.')
            active=overrides().get(unit_id,UNIT_MAP[unit_id])
            if not can_inspect_at_stage(UNIT_MAP[unit_id],active,check['wc'],ROUTES):
                abort(409,'An upstream stage has not been released; inspect the current stage first.')
            value=request.form.get('value','').strip()
            note=request.form.get('note','').strip()[:1200]
            inspector=request.form.get('inspector','Demo inspector').strip()[:90] or 'Demo inspector'
            if not value:flash('An answer or measurement is required.','danger');return redirect(request.url)
            if check['answer_type']=='Yes/No':
                if value not in ('Yes','No'):abort(400)
                verdict=('FAIL' if value.lower()==check['negative_answer'].lower() else 'PASS') if check['negative_answer'] else 'REVIEW'
            else:
                try:measurement=float(value)
                except ValueError:flash('Enter a numeric measurement.','danger');return redirect(request.url)
                if not isfinite(measurement) or not (-1e6<measurement<1e6):abort(400)
                value=str(measurement)
                judgement=request.form.get('manual_verdict','REVIEW')
                if judgement not in ('PASS','FAIL','REVIEW'):abort(400)
                verdict=judgement
                if judgement!='REVIEW' and not note:
                    flash('Provide an inspector rationale for numeric acceptance or failure; the workbook has no check-specific numeric limits.','danger')
                    return redirect(request.url)
            evidence=request.files.get('evidence')
            evidence_needed=(check['evidence_yes'] and value=='Yes') or (check['evidence_no'] and value=='No')
            evidence_filename=None
            evidence_data=None
            if evidence and evidence.filename:
                ext=evidence.filename.rsplit('.',1)[-1].lower() if '.' in evidence.filename else ''
                if ext not in ALLOWED_EVIDENCE:
                    flash('Evidence must be PNG, JPG or WEBP.','danger');return redirect(request.url)
                evidence_data=evidence.read()
                if not evidence_is_valid_image(evidence_data,ext):
                    flash('The uploaded file is not a valid PNG, JPG or WEBP image.','danger');return redirect(request.url)
                evidence_filename=secrets.token_hex(16)+'.'+ext
            existing=check_results(unit_id).get(check_id)
            usable_previous=existing and existing['value']==value and existing['evidence_filename']
            if evidence_needed and not evidence_filename and not usable_previous:
                flash('This workbook question requires image evidence for that answer.','danger')
                return redirect(request.url)
            evidence_filename=evidence_filename or (existing['evidence_filename'] if existing and existing['value']==value else None)
            if evidence_data is not None:
                Path(app.config['EVIDENCE_DIR']).mkdir(parents=True,exist_ok=True)
                (Path(app.config['EVIDENCE_DIR'])/evidence_filename).write_bytes(evidence_data)
            recorded_at=datetime.now().astimezone().isoformat(timespec='seconds')
            with connect() as db:
                db.execute('''INSERT INTO inspection_results VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(unit_id,check_id) DO UPDATE SET value=excluded.value,verdict=excluded.verdict,
                   note=excluded.note,evidence_filename=excluded.evidence_filename,
                   inspector=excluded.inspector,recorded_at=excluded.recorded_at''',
                   (unit_id,check_id,value,verdict,note,evidence_filename,inspector,recorded_at))
                db.execute('INSERT INTO inspection_audit(unit_id,check_id,value,verdict,note,inspector,recorded_at,evidence_filename) VALUES(?,?,?,?,?,?,?,?)',
                   (unit_id,check_id,value,verdict,note,inspector,recorded_at,evidence_filename))
                # Recompute the unit state from the saved inspection outcomes, not the last
                # answer alone. Incomplete/reviewed checks cannot release a stage.
                found={r['check_id']:r['verdict'] for r in db.execute(
                    'SELECT check_id,verdict FROM inspection_results WHERE unit_id=?',(unit_id,))}
                # Reuse the validated pre-update state instead of opening a second
                # SQLite connection while this write transaction is active.
                newstatus,newwc,newprogress=compute_quality_state(
                    UNIT_MAP[unit_id],active,check['wc'],found,ROUTES,CTQ_RULES)
                db.execute('''INSERT INTO unit_state(unit_id,status,wc,progress) VALUES(?,?,?,?)
                    ON CONFLICT(unit_id) DO UPDATE SET status=excluded.status,wc=excluded.wc,progress=excluded.progress''',
                    (unit_id,newstatus,newwc,newprogress))
            # Prior evidence remains available to the audit record until demo reset.
            flash(f'Inspection recorded: {verdict}. Audit history retained.','success')
            return redirect(url_for('unit_detail',unit_id=unit_id))
        ctx=context();view_unit=next((x for x in ctx['units'] if x['id']==unit_id),None)
        if view_unit is None:abort(404)
        with connect() as db:
            has_open_defect=bool(db.execute("SELECT 1 FROM shop_defects WHERE unit_id=? AND status='OPEN'",(unit_id,)).fetchone())
        ctx.update(unit=view_unit,check=check,
                   inspection_allowed=(not has_open_defect and unit_id!='TANK-0018' and can_inspect_at_stage(unit,overrides().get(unit_id,unit),check['wc'],ROUTES) and (unit_id!='TANK-0021' or bool(approved_recovery()))),
                   existing=check_results(unit_id).get(check_id) if ctx['asof']>='10:55' else None)
        return render_template('mfg/inspection.html',**ctx)


    @app.route('/quality/evidence/<unit_id>/<check_id>')
    def inspection_evidence(unit_id,check_id):
        if unit_id not in UNIT_MAP or check_id not in {r['check_id'] for r in CTQ_RULES}:
            abort(404)
        row=check_results(unit_id).get(check_id)
        if not row or not row['evidence_filename'] or Path(row['evidence_filename']).name!=row['evidence_filename']:
            abort(404)
        return send_from_directory(app.config['EVIDENCE_DIR'],row['evidence_filename'],as_attachment=False)

    @app.route('/recovery')
    def recovery():
        ctx=context();ctx['candidates']=[{'worker':WORKER_MAP[i],'test':verify_candidate(i,ctx['scene']['id'],ctx['asof'])} for i in ('W-012','W-006','W-023')]
        return render_template('mfg/recovery.html',**ctx)

    @app.route('/api/recovery/check/<worker_id>')
    def api_check_transfer(worker_id):
        if worker_id not in WORKER_MAP:abort(404)
        ctx=context();return jsonify(verify_candidate(worker_id,ctx['scene']['id'],ctx['asof']))

    @app.route('/api/recovery/approve',methods=['POST'])
    @csrf_required
    def approve_recovery():
        worker_id=request.form.get('worker_id')
        if worker_id!='W-012' or not verify_candidate(worker_id,'combined','10:55')['feasible']:
            flash('This transfer is not feasible. Source crew, skills and availability must be checked.','danger')
            return redirect(url_for('recovery',scenario='combined'))
        actor=request.form.get('actor','Demo supervisor').strip()[:80] or 'Demo supervisor'
        now=datetime.now().astimezone().isoformat(timespec='seconds')
        with connect() as db:
            db.execute('''INSERT OR IGNORE INTO action_log(action_key,action_type,actor,state,proposed_at,approved_at,
                started_at,worker_id,from_wc,to_wc,replacement_id,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('arun_replacement','qualified_transfer_and_replacement',actor,'approved',now,now,now,'W-012','WC4','WC1','TANK-0021',
                'PDF demo plan; 15-min handover planned, 20-min illustrative replay. Not an actual factory action.'))
        flash('Demo recovery approved: transfer Arun from WC4 and create TANK-0021. The 14:21 plan is an illustrative forecast.','success')
        return redirect(url_for('recovery',scenario='recovered'))

    @app.route('/api/recovery/reset',methods=['POST'])
    @csrf_required
    def reset_demo():
        with connect() as db:
            db.execute('DELETE FROM action_log');db.execute('DELETE FROM inspection_results');db.execute('DELETE FROM inspection_audit');db.execute('DELETE FROM unit_state')
            db.execute('DELETE FROM shop_task_events');db.execute('DELETE FROM shop_tasks')
            db.execute('DELETE FROM shop_handover_checks');db.execute('DELETE FROM shop_defects')
        evidence_dir=Path(app.config['EVIDENCE_DIR'])
        if evidence_dir.exists():
            for file in evidence_dir.iterdir():
                if file.is_file():file.unlink()
        flash('Synthetic scenario reset to its original fixture.','success')
        return redirect(url_for('dashboard',scenario='combined'))

    @app.route('/api/snapshot')
    def api_snapshot():
        ctx=context()
        return jsonify({'asof':ctx['asof'],'scenario':ctx['scene'],'metrics':ctx['stats'],
            'work_centers':ctx['centers'],'alerts':ctx['alerts'],
            'events':ctx['events'],'source':'Synthetic demo fixtures; NOT actual plant telemetry'})

    @app.route('/api/ctq')
    def api_ctq():
        wc=request.args.get('wc');return jsonify([c for c in CTQ_RULES if not wc or c['wc']==wc])

    @app.route('/api/units')
    def api_units():
        ctx=context();return jsonify(ctx['units'])

    from manufacturing.shop_routes import register_shopfloor_routes
    register_shopfloor_routes(app,connect,csrf_required,context,data_units,check_results,overrides,approved_recovery)

    return app

app=create_app()
if __name__=='__main__':
    print('GiNi Production Flow & Recovery — synthetic demonstration — http://127.0.0.1:5006')
    app.run(host='127.0.0.1',port=int(os.getenv('PORT',5006)),debug=False)
