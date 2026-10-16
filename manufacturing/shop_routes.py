"""Server-rendered shop floor, WO traceability and measured task-time views."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime,timezone
from flask import abort, flash, redirect, render_template, request, url_for, jsonify
from manufacturing.model import CTQ_RULES, WORKERS, WORKER_MAP, UNIT_MAP, ROUTES, CENTER_MAP
from manufacturing.shopfloor import (WorkflowError, start_task, transition, elapsed_seconds,
    report_issue, record_handover, work_order_overview, timestamp)
from manufacturing.scoring import POINTS, work_order_score


def register_shopfloor_routes(app,connect,csrf_required,context,data_units,check_results,overrides,approved_recovery):
    def tasks_and_elapsed():
        with connect() as db:
            tasks=[dict(x) for x in db.execute('SELECT * FROM shop_tasks ORDER BY task_id DESC')]
            times={}
            for task in tasks:
                times[task['task_id']]=elapsed_seconds(db.execute(
                    'SELECT event_type,event_at FROM shop_task_events WHERE task_id=? ORDER BY id',
                    (task['task_id'],)).fetchall())
        for t in tasks:
            t['seconds']=times[t['task_id']]
            t['worker_name']=WORKER_MAP[t['worker_id']]['name']
        return tasks

    def selected_units(ctx):
        return [u for u in ctx['units'] if u['status'] not in ('Scrapped','Complete','Proposed replacement','Approved replacement')]

    @app.get('/operator')
    def operator_console():
        ctx=context()
        wc=request.args.get('wc','WC1')
        if wc not in CENTER_MAP:wc='WC1'
        worker=request.args.get('worker','')
        wc_workers=[w for w in ctx['workers'] if wc in w['skills'] and w['state']!='Absent']
        units=[u for u in selected_units(ctx) if u['wc']==wc]
        tasks=tasks_and_elapsed()
        if not worker and wc_workers:worker=wc_workers[0]['id']
        if worker and worker not in {w['id'] for w in wc_workers}:
            worker=wc_workers[0]['id'] if wc_workers else ''
        own=[t for t in tasks if t['worker_id']==worker and t['status'] in ('RUNNING','PAUSED')]
        task=own[0] if own else None
        if task:
            wc=task['wc'];units=[u for u in selected_units(ctx) if u['wc']==wc]
        chosen_unit=task['unit_id'] if task else request.args.get('unit','')
        if not task and chosen_unit not in {u['id'] for u in units}:
            chosen_unit=units[0]['id'] if units else ''
        results=check_results(chosen_unit) if chosen_unit else {}
        checks=[dict(c, recorded=results.get(c['check_id'])) for c in CTQ_RULES if c['wc']==wc]
        with connect() as db:
            handovers=[dict(x) for x in db.execute('SELECT * FROM shop_handover_checks ORDER BY id DESC LIMIT 12')]
            defects=[dict(x) for x in db.execute('SELECT * FROM shop_defects ORDER BY id DESC LIMIT 12')]
        ctx.update(selected_wc=wc,selected_worker=worker,wc_workers=wc_workers,
            selectable_units=units,selected_unit=chosen_unit,active_task=task,tasks=tasks[:15],stage_checks=checks,
            handovers=handovers,defects=defects)
        return render_template('mfg/operator.html',**ctx)

    @app.post('/operator/start')
    @csrf_required
    def start_shop_task():
        wc=request.form.get('wc','');worker=request.form.get('worker_id','');unit=request.form.get('unit_id','')
        ctx=context()
        visible=next((u for u in ctx['units'] if u['id']==unit),None)
        if visible is None:
            flash('Unit is not available in the selected demo scenario.','danger')
            return redirect(url_for('operator_console',wc=wc,worker=worker))
        scenario_worker=next((w for w in ctx['workers'] if w['id']==worker), None)
        if not scenario_worker or scenario_worker['state']=='Absent':
            flash('Worker is absent or unavailable in this scenario.','danger')
            return redirect(url_for('operator_console',wc=wc,worker=worker))
        try:
            with connect() as db:task_id=start_task(db,worker,unit,wc,visible,worker_state=scenario_worker['state'])
        except WorkflowError as exc:
            flash(str(exc),'danger');return redirect(url_for('operator_console',wc=wc,worker=worker))
        flash(f'Task #{task_id} started. Clock events are saved in UTC.','success')
        return redirect(url_for('operator_console',wc=wc,worker=worker))

    @app.post('/operator/tasks/<int:task_id>/<action>')
    @csrf_required
    def shop_task_transition(task_id,action):
        if action not in ('pause','resume','finish'):abort(404)
        with connect() as db:
            row=db.execute('SELECT worker_id,wc FROM shop_tasks WHERE task_id=?',(task_id,)).fetchone()
        if not row:abort(404)
        try:
            with connect() as db:target=transition(db,task_id,action.upper())
        except WorkflowError as exc:flash(str(exc),'danger')
        else:flash(f'Task #{task_id} is now {target.lower()}. Finishing a task does not release a CTQ gate.','success')
        return redirect(url_for('operator_console',wc=row['wc'],worker=row['worker_id']))

    @app.post('/operator/issues')
    @csrf_required
    def shop_report_issue():
        unit=request.form.get('unit_id','');wc=request.form.get('wc','');worker=request.form.get('worker_id','')
        ctx=context();visible=next((u for u in ctx['units'] if u['id']==unit), None)
        if not visible or visible['wc']!=wc or visible['status'] in ('Scrapped','Complete','Proposed replacement','Approved replacement'):
            flash('Cannot report a task issue for an unavailable unit or another work center.','danger')
            return redirect(url_for('operator_console',wc=wc,worker=worker))
        try:
            with connect() as db:report_issue(db,unit,wc,worker,request.form.get('detail',''))
        except WorkflowError as exc:flash(str(exc),'danger')
        else:flash('Issue logged for review. No fault, penalty or rework disposition has been assigned.','success')
        return redirect(url_for('operator_console',wc=wc,worker=worker))

    @app.post('/operator/incoming')
    @csrf_required
    def incoming_shop_inspection():
        unit_id=request.form.get('unit_id','');wc=request.form.get('wc','')
        worker=request.form.get('worker_id','')
        ctx=context();u=next((u for u in ctx['units'] if u['id']==unit_id),None)
        if u is None or u['wc']!=wc or u['status'] in ('Scrapped','Hold','Proposed replacement','Approved replacement'):
            flash('Receiving inspection requires the physical unit at its current, available downstream stage.','danger')
            return redirect(url_for('operator_console',wc=wc,worker=worker))
        try:
            with connect() as db:
                record_handover(db,unit_id,wc,worker,request.form.get('outcome',''),request.form.get('note',''))
        except WorkflowError as exc:flash(str(exc),'danger')
        else:flash('Incoming inspection recorded. This does not replace the CTQ gate or assign a cause.','success')
        return redirect(url_for('operator_console',wc=wc,worker=worker))

    @app.get('/work-orders')
    def work_orders():
        ctx=context()
        wo_list=work_order_overview(ctx['units'],check_results())
        selected_id=request.args.get('wo','ORD-1042' if any(o['id']=='ORD-1042' for o in wo_list) else (wo_list[0]['id'] if wo_list else ''))
        selected=next((o for o in wo_list if o['id']==selected_id),None)
        wc=request.args.get('wc','')
        if selected and wc not in ROUTES[selected['type']]:wc=ROUTES[selected['type']][0]
        unit_id=request.args.get('unit','')
        if selected and unit_id not in {u['id'] for u in selected['units']}:
            unit_id=selected['units'][0]['id']
        with connect() as db:
            tasks=[dict(x) for x in db.execute('SELECT * FROM shop_tasks ORDER BY task_id DESC')]
            incoming=[dict(x) for x in db.execute('SELECT * FROM shop_handover_checks ORDER BY id DESC')]
            defects=[dict(x) for x in db.execute('SELECT * FROM shop_defects ORDER BY id DESC')]
            audit=[dict(x) for x in db.execute('SELECT * FROM inspection_audit ORDER BY audit_id DESC')]
        unit_results=check_results(unit_id) if unit_id else {}
        records=[dict(c,recorded=unit_results.get(c['check_id'])) for c in CTQ_RULES if c['wc']==wc] if unit_id else []
        ctx.update(wo_list=wo_list,selected_order=selected,selected_wo=selected_id,selected_wc=wc,
            selected_unit=unit_id,stage_checks=records,
            operation_tasks=[t for t in tasks if selected and t['work_order']==selected_id and t['wc']==wc],
            incoming=[x for x in incoming if x['unit_id']==unit_id],
            defects=[x for x in defects if x['unit_id']==unit_id],
            audit=[x for x in audit if x['unit_id']==unit_id and any(c['check_id']==x['check_id'] for c in records)])
        return render_template('mfg/work_orders.html',**ctx)

    @app.get('/lms')
    def lms_dashboard():
        ctx=context()
        tasks=tasks_and_elapsed()
        per_worker=defaultdict(lambda:{'seconds':0,'finished':0,'open':0,'units':set(),'name':''})
        for task in tasks:
            summary=per_worker[task['worker_id']]
            summary['name']=task['worker_name']
            summary['seconds']+=task['seconds'];summary['units'].add(task['unit_id'])
            summary['finished']+=int(task['status']=='FINISHED')
            summary['open']+=int(task['status'] in ('PAUSED','RUNNING'))
        workers=sorted((dict(worker_id=k,units=len(v['units']),**{x:y for x,y in v.items() if x!='units'}) for k,v in per_worker.items()),key=lambda x:-x['seconds'])
        with connect() as db:
            handovers=[dict(x) for x in db.execute('SELECT * FROM shop_handover_checks ORDER BY id DESC LIMIT 20')]
            defects=[dict(x) for x in db.execute('SELECT * FROM shop_defects ORDER BY id DESC LIMIT 20')]
        orders=work_order_overview(ctx['units'],check_results())
        scoring=[]
        for order in orders:
            pending=[d for d in defects if d['unit_id'] in {u['id'] for u in order['units']} and d['source']=='INCOMING_INSPECTION']
            score=work_order_score(completed=(order['complete']==order['quantity']),
                rework_count=0, origin_fixed_confirmed=False, downstream_confirmed=0)
            scoring.append({'order':order,'score':score,'pending_defects':len(pending)})
        ctx.update(operators=workers,tasks=tasks, handovers=handovers,defects=defects,
            scoring=scoring,point_rules=POINTS,
            finished_tasks=sum(t['status']=='FINISHED' for t in tasks),
            active_tasks=sum(t['status'] in ('RUNNING','PAUSED') for t in tasks),
            productive_seconds=sum(t['seconds'] for t in tasks),
            wo_list=orders)
        return render_template('mfg/lms.html',**ctx)

    @app.get('/api/operator/tasks')
    def api_shop_tasks():
        return jsonify({'synthetic':True,'time_basis':'real UTC event timestamps, independent of PDF scenario replay',
            'tasks':tasks_and_elapsed()})
