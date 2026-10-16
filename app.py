"""Truck ETC supervisor app (Flask). Run: python app.py  ->  http://127.0.0.1:5006"""
from flask import Flask, abort, render_template, request, session, redirect, url_for, flash, Response, jsonify

import config
import secrets
import time
import csv
import io
from datetime import datetime
from types import SimpleNamespace
from threading import RLock
from calculations.supervisor import (build_state, candidates, eligible_candidates, preview_state, assignment_risks, recommend_minimum,
                                     SAFETY_BUFFER_MINUTES, RISK_STATUSES, CUTOFF_PASSED, explain_status,
                                     TEMP_OPERATOR_MAX)
from calculations.dashboard_view import departed_status, category, display_trucks, summary, operational_insights
from calculations.excel_io import serial_to_datetime, serial_to_datetime as scenario_datetime
from calculations.detail import clock as serial_clock, dur, truck_detail
from calculations.truck_detail_view import area_recommendations
from calculations.ready_comparison import ready_time_comparison
from calculations.temporary import temporary_requirement
from calculations.engine import run
from calculations.operator import operator_profile
from models import database as db
from models import environment as env_store
from calculations import environment as env
from calculations.environment_analysis import analyse as analyse_environment

# Both preview and confirmed advisory allocations are TEMPORARY supervisor-session
# scenarios; no allocation is persisted or passed to the WMS. Browser cookie holds
# only an opaque session id. Idle sessions are discarded after eight hours.
_SCENARIOS: dict[str, dict] = {}
_SCENARIOS_LOCK = RLock()


def supervisor_scenario():
    key = session.get("scenario_id")
    if not key:
        key = secrets.token_urlsafe(32)
        session["scenario_id"] = key
    with _SCENARIOS_LOCK:
        now = time.monotonic()
        for old in [k for k,v in _SCENARIOS.items() if now-v.get('touched',now)>8*3600]:
            _SCENARIOS.pop(old,None)
        scenario = _SCENARIOS.setdefault(key, {"confirmed_moves": [], "preview": {}, "version": 0,
                                               # v12: temporary operators, session only
                                               "confirmed_temps": [], "temp_preview": {}})
        scenario.setdefault("confirmed_temps", [])
        scenario.setdefault("temp_preview", {})
        scenario['touched'] = now
        return scenario


STATUS_STYLE = {"ON TIME": "success", "ALL PICKED": "success", "AT RISK": "warning", "PICK CUTOFF PASSED": "danger",
                "PICK CUTOFF PASSED - LATE": "danger",
                "NO RATE": "warning", "DEPARTED COMPLETE": "secondary", "NO WORK RELEASED YET": "light"}


def status_style(status: str | None) -> str:
    if not status:
        return "light"
    if status.startswith("DEPARTED - "):
        return "dark"
    return STATUS_STYLE.get(status, "light")


def hhmm(hours) -> str:
    if hours is None:
        return "—"
    minutes = int(hours * 60 + 1e-6)
    return f"{minutes // 60}:{minutes % 60:02d}"


def rebuild_all() -> None:
    """Workbook -> calculation engine -> SQLite (results + the source rows the drill-down needs)."""
    results = run(config.WORKBOOK_PATH)
    db.rebuild(results)
    db.store_sources(results.inputs, db.workbook_stamp(config.WORKBOOK_PATH))


def create_app() -> Flask:
    app = Flask(__name__)
    # Ephemeral signing key; no allocation stored in a cookie, workbook, or SQLite.
    app.secret_key = secrets.token_bytes(32)
    app.jinja_env.filters.update(hhmm=hhmm, status_style=status_style,
                                 clock=lambda t: t.strftime("%H:%M") if t else "")
    app.jinja_env.filters.update(sclock=serial_clock, dur=dur,
                                 pct=lambda v: f"{v:.0%}" if isinstance(v, (int, float)) else "",
                                 num=lambda v, d=0: f"{v:,.{d}f}" if isinstance(v, (int, float)) else "")
    db.init_db()
    if db.needs_rebuild(config.WORKBOOK_PATH):
        rebuild_all()
    env_store.init_env(db.load_sources().worktype_names)   # v13: separate environmental database
    # Always purge any v7 advisory database records on migration; user approved
    # only in-memory, session-scoped reallocation scenarios.
    with db.engine.begin() as connection:
        from sqlalchemy import text
        connection.execute(text('DROP TABLE IF EXISTS scenario_allocation'))

    @app.context_processor
    def workbook_identity():
        src = db.load_sources()
        analysis_date = serial_to_datetime(float(src.config["ANALYSIS_DATE"]))
        return dict(business_client=src.config["CLIENTID_FILTER"],
                    warehouse_id=int(float(src.config["WHID_FILTER"])),
                    analysis_date=analysis_date.strftime("%d-%b-%Y"))

    @app.cli.command("init-db")
    def init_db_command():
        """Recalculate everything from the workbook and reload the database."""
        rebuild_all()
        print("Database rebuilt from", config.WORKBOOK_PATH)

    @app.context_processor
    def supervisor_navigation():
        requested = request.values.get('snapshot', default=config.DEFAULT_SNAPSHOT, type=int)
        snaps = db.snapshots()
        return dict(session_moves=supervisor_scenario().get("confirmed_moves", []),
                    session_temps=supervisor_scenario().get("confirmed_temps", []),
                    safety_buffer_minutes=SAFETY_BUFFER_MINUTES,
                    header_snapshot_no=requested if any(x.snapshot_no == requested for x in snaps)
                                       else config.DEFAULT_SNAPSHOT,
                    header_snaps=snaps)

    def current_state(snapshot_no):
        inp = db.load_sources()
        memory = supervisor_scenario()
        return build_state(inp, db.worktype_context(snapshot_no), db.trucks_at(snapshot_no),
                           snapshot_no, db.get_loading_overrides(), memory.get("confirmed_moves", []),
                           temporaries=memory.get("confirmed_temps", []))

    def original_state(snapshot_no):
        """Original operator assignments: same deadlines/overrides, no session moves."""
        inp = db.load_sources()
        return build_state(inp, db.worktype_context(snapshot_no), db.trucks_at(snapshot_no),
                           snapshot_no, db.get_loading_overrides(), [])

    def ready_chart(snapshot_no, shipment, state=None):
        """v10 before/after ready-time comparison for one truck (shared by truck page and planner)."""
        state = state or current_state(snapshot_no)
        memory = supervisor_scenario()
        return ready_time_comparison(db.load_sources(), original_state(snapshot_no), state, shipment,
                                     snapshot_no, memory.get('preview', {}), memory.get('temp_preview', {}))

    def risk_rows(state):
        """Work-type pickup rows, derived from the same scenario calculation as planner."""
        rows = []
        for row in state['rows']:
            if not row['open']:
                continue
            status = row['status']
            risk = (('Pick cutoff passed' if state['now'] >= row['physical_cutoff'] - 1e-9
                     else 'Projected to miss pick cutoff') if status == CUTOFF_PASSED else
                    'At risk: ready inside safety buffer' if status == 'AT RISK' else
                    'Insufficient data' if status == 'NO RATE' else 'On track')
            slack = ((row['deadline'] - row['conservative_ready']) * 1440
                     if row['conservative_ready'] is not None else None)
            rows.append(dict(**row, risk=risk, slack_minutes=slack))
        return sorted(rows, key=lambda r: (r['status'] == 'ON TIME', r['deadline'], r['shipment'], r['worktype']))

    def require_csrf():
        if not secrets.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "invalid")):
            abort(400, "Invalid form token")

    def handle_temporary(action, memory, state, snapshot_no, dest, ship, preview_key, selected):
        """v12 Temporary Operators actions. Raises ValueError with a supervisor-readable message."""
        src = db.load_sources()
        temp_preview = memory.setdefault('temp_preview', {})
        if action == 'temp_clear':
            temp_preview.pop(preview_key, None)
            return
        requirement = temporary_requirement(src, state, dest, ship, selected, temp_preview.get(preview_key))
        if action == 'temp_plan':
            if not requirement['plan_available']:
                raise ValueError(requirement['reason'])
            names = list(requirement['selected']) + list(requirement['plan']['realloc'])
            preview_state(src, state, dest, names, shipment=ship)   # validates cumulative source safety
            memory['preview'][preview_key] = names
            temp_preview[preview_key] = int(requirement['plan']['temps'])
            return
        if action == 'temp_set':
            count = int(request.form.get('temp_count', ''))
            if not 0 <= count <= TEMP_OPERATOR_MAX:
                raise ValueError(f'Enter between 0 and {TEMP_OPERATOR_MAX} temporary operators.')
            if count and not requirement['allowed']:
                raise ValueError(requirement['reason'])
            temp_preview[preview_key] = count
            return
        # allocate_temps: confirm the selected reallocations (if any) and the temporary operators together
        expected = request.form.get('scenario_version', type=int)
        if expected is None or expected != memory['version']:
            raise ValueError('Scenario changed. Refresh and review the current plan before confirming.')
        count = int(temp_preview.get(preview_key, requirement['proposed_count']) or 0)
        if count <= 0:
            raise ValueError('Set the number of temporary operators before confirming.')
        if not requirement['allowed']:
            raise ValueError(requirement['reason'])
        moves = list(memory['confirmed_moves'])
        additions = []
        if selected:
            projection = preview_state(src, state, dest, selected, shipment=ship)
            additions = [dict(operator=step['operator'], source=step['source'], dest=dest,
                              start_snapshot=snapshot_no, destination_pace=step['pace'],
                              pace_basis=step['evidence'], experience=step['experience'])
                         for step in projection['steps']]
            if set(m['operator'] for m in moves) & set(m['operator'] for m in additions):
                raise ValueError('Operator is already confirmed in this session.')
        temps = list(memory.get('confirmed_temps', []))
        temps.append(dict(id=f"TEMP-{len(temps) + 1}", dest=dest, count=count, start_snapshot=snapshot_no,
                          shipment=ship, pace_pct=requirement['pace_pct'],
                          assumed_pace=requirement['pace']['pace']))
        # All-or-nothing in-memory update after complete validation.
        memory['confirmed_moves'] = moves + additions
        memory['confirmed_temps'] = temps
        memory['version'] += 1
        memory['preview'] = {}
        memory['temp_preview'] = {}
        refreshed = current_state(snapshot_no)
        truck = next(t for t in refreshed['trucks'] if t['shipment'] == ship)
        moved = f"{len(additions)} reallocated and " if additions else ''
        if truck['status'] in ('ON TIME', 'ALL PICKED'):
            flash(f"{moved}{count} temporary operator(s) allocated to WT {dest} for THIS SESSION ONLY. "
                  f"Truck {ship} now meets its safety buffer deadline. No WMS, workbook or database changes.",
                  'success')
        else:
            flash(f"{moved}{count} temporary operator(s) allocated to WT {dest} for this session. Truck {ship} "
                  f"is still {truck['status']}; review the remaining gap and other work types.", 'warning')

    @app.route("/planner", methods=["GET", "POST"])
    def planner():
        snaps = db.snapshots()
        snapshot_no = request.values.get("snapshot", default=config.DEFAULT_SNAPSHOT, type=int)
        if not any(s.snapshot_no == snapshot_no for s in snaps):
            abort(404)
        dest = request.values.get("worktype", default=2, type=int)
        if dest not in db.load_sources().worktype_names:
            abort(404)
        # A preview belongs to one shipment and worktype, not just a worktype.
        # Otherwise changing trucks could silently carry selected operators into
        # a different recommendation before supervisor confirmation.
        state = current_state(snapshot_no)
        ship = request.values.get('shipment', '')
        ship_ids = {t['shipment'] for t in state['trucks']}
        if ship not in ship_ids or not any(r['shipment']==ship and r['worktype']==dest and r['open'] for r in state['rows']):
            priority = [r for r in state['rows'] if r['worktype']==dest and r['open']]
            priority.sort(key=lambda r: (r['status'] not in RISK_STATUSES,
                                         r['deadline'],r['shipment']))
            ship = priority[0]['shipment'] if priority else state['trucks'][0]['shipment']
        preview_key = f"{snapshot_no}:{dest}:{ship}"
        if request.method == "POST":
            require_csrf()
            action = request.form.get("action")
            scenario_memory = supervisor_scenario()
            current_preview = scenario_memory.get("preview", {})
            temp_preview = scenario_memory.get("temp_preview", {})
            selected = list(current_preview.get(preview_key, []))
            try:
                if action == "loading":
                    ship = request.form.get("shipment", "")
                    if ship not in {t['shipment'] for t in state['trucks']}:
                        abort(400, "Unknown shipment")
                    minutes = int(request.form.get("minutes", ""))
                    db.set_loading_override(ship, minutes, state['default_loading_minutes'])
                    scenario_memory["preview"] = {}  # old previews used old deadlines
                    scenario_memory["temp_preview"] = {}
                    flash(f"Loading time for {ship} updated to {minutes} minutes; saved across restarts.", "success")
                elif action == "add":
                    name = request.form.get("operator", "")
                    if name in selected:
                        raise ValueError("Operator already selected")
                    new = selected + [name]
                    preview_state(db.load_sources(), state, dest, new,
                                  shipment=ship)  # validate source safety
                    current_preview[preview_key] = new
                    scenario_memory["preview"] = current_preview
                elif action == "remove":
                    name = request.form.get("operator", "")
                    current_preview[preview_key] = [n for n in selected if n != name]
                    scenario_memory["preview"] = current_preview
                elif action == "clear":
                    current_preview.pop(preview_key, None)
                    temp_preview.pop(preview_key, None)   # temporary count depended on the selection
                    scenario_memory["preview"] = current_preview
                elif action == "allocate":
                    if not selected:
                        raise ValueError("Select an operator before confirming allocation")
                    projection = preview_state(db.load_sources(), state, dest, selected,
                                               shipment=ship)
                    if not projection['steps']:
                        raise ValueError("No validated operator selection")
                    expected = request.form.get('scenario_version', type=int)
                    if expected is None or expected != scenario_memory['version']:
                        raise ValueError('Scenario changed. Refresh and review the current plan before confirming.')
                    moves = list(scenario_memory['confirmed_moves'])
                    additions = [dict(operator=step['operator'], source=step['source'], dest=dest,
                                      start_snapshot=snapshot_no, destination_pace=step['pace'],
                                      pace_basis=step['evidence'], experience=step['experience'])
                                 for step in projection['steps']]
                    if set(m['operator'] for m in moves) & set(m['operator'] for m in additions):
                        raise ValueError('Operator is already confirmed in this session.')
                    # All-or-nothing in-memory update after complete validation.
                    scenario_memory['confirmed_moves'] = moves + additions
                    scenario_memory['version'] += 1
                    current_preview.clear()  # projected source state has changed everywhere
                    scenario_memory['preview'] = current_preview
                    scenario_memory['temp_preview'] = {}
                    refreshed = current_state(snapshot_no)
                    requested = ship
                    checked = next((t for t in refreshed['trucks'] if t['shipment']==requested),None)
                    if checked and checked['status'] not in ('ON TIME','ALL PICKED'):
                        flash(f"{len(additions)} temporary move(s) confirmed. Truck {requested} remains {checked['status']}; review other at-risk worktypes.", 'warning')
                    else:
                        flash(f"{len(additions)} temporary move(s) confirmed for THIS SESSION ONLY. No WMS, workbook or allocation database changes.", 'success')
                elif action in ("temp_set", "temp_plan", "temp_clear", "allocate_temps"):
                    handle_temporary(action, scenario_memory, state, snapshot_no, dest, ship,
                                     preview_key, selected)
                elif action == "reset_scenario":
                    scenario_memory["confirmed_moves"] = []
                    scenario_memory["confirmed_temps"] = []
                    scenario_memory["temp_preview"] = {}
                    scenario_memory["preview"] = {}
                    scenario_memory['version'] += 1
                    flash("Temporary session scenario reset: reallocated and temporary operators removed; "
                          "original assignments restored.", "info")
                else:
                    abort(400, "Unknown action")
            except (ValueError, TypeError) as error:
                flash(str(error), "danger")
            return redirect(url_for("planner", snapshot=snapshot_no, worktype=dest,
                                    shipment=ship))

        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(24)
        src = db.load_sources()
        selected = supervisor_scenario().get("preview", {}).get(preview_key, [])
        try:
            comparison = preview_state(src, state, dest, selected, shipment=ship)
        except ValueError:
            comparison = preview_state(src, state, dest, [], shipment=ship)
            selected = []
        strict = eligible_candidates(src, dict(state, rates=comparison['rates']), dest, selected)
        eligible = strict['all_experienced']
        recommendation = recommend_minimum(src,state,dest,ship,selected)
        memory = supervisor_scenario()
        temporary = temporary_requirement(src, state, dest, ship, selected,
                                          memory.get('temp_preview', {}).get(preview_key))
        flagged = [r for r in assignment_risks(src, state) if r['status'] in RISK_STATUSES]
        flagged.sort(key=lambda x:(x['deadline'],x['shipment'],x['worktype'],x['assignment']))
        date = lambda v: scenario_datetime(v).strftime('%H:%M') if v is not None else '—'
        # Source-area impact chart only; the target truck chart is the shared v10 ready-time panel.
        plot = {'shipment':ship,
                'sources':[dict(operator=s['operator'], worktype=s['source'],
                                before=date(s['source_before']['finish']),
                                after=date(s['source_after']['finish']),
                                deadline=date(s['source_after']['deadline']),
                                status_before=s['source_before']['status'],
                                status_after=s['source_after']['status']) for s in comparison['steps']]}
        _, env_contexts = area_conditions(snapshot_no)   # v13: context only; never an allocation input
        return render_template('planner.html', snaps=snaps, snapshot_no=snapshot_no, env_contexts=env_contexts,
                               dest=dest, wt_names=src.worktype_names, state=state,
                               eligible=eligible, comparison=comparison, recommendation=recommendation, flagged=flagged,
                               risk_pickups=risk_rows(state), excluded_count=len(strict['excluded']),
                               conditional=[],
                               scenario_version=supervisor_scenario()['version'],
                               selected=selected, shipment=ship,
                               loading=db.get_loading_overrides().get(ship, state['default_loading_minutes']),
                               default_loading=state['default_loading_minutes'],
                               ready=ready_chart(snapshot_no, ship, state),
                               temporary=temporary, temp_explicit=preview_key in memory.get('temp_preview', {}),
                               confirmed_temps=memory.get('confirmed_temps', []),
                               temp_applied=state.get('temporaries_applied', []),
                               csrf=session['csrf_token'], timefmt=date, plot=plot)

    @app.route('/api/snapshots/<int:snapshot_no>/at-risk-pickups')
    def at_risk_pickups_api(snapshot_no):
        if not any(s.snapshot_no == snapshot_no for s in db.snapshots()):
            abort(404)
        status = request.args.get('status', '').upper()
        rows = risk_rows(current_state(snapshot_no))
        if status:
            rows = [r for r in rows if r['status'] == status]
        return jsonify(snapshot=snapshot_no, scenario_version=supervisor_scenario()['version'], pickups=[dict(
            shipment=r['shipment'], worktype=r['worktype'], worktype_name=r['name'], open_lines=r['open'],
            cutoff=scenario_datetime(r['deadline']).isoformat(), estimated_completion=(scenario_datetime(r['conservative_ready']).isoformat() if r['conservative_ready'] is not None else None),
            slack_minutes=r['slack_minutes'], status=r['status'], risk=r['risk']) for r in rows])

    @app.route('/api/snapshots/<int:snapshot_no>/worktypes/<int:worktype>/eligible-operators')
    def eligible_operators_api(snapshot_no, worktype):
        if not any(s.snapshot_no == snapshot_no for s in db.snapshots()):
            abort(404)
        state = current_state(snapshot_no)
        if worktype not in state['names']:
            abort(404)
        result = eligible_candidates(db.load_sources(), state, worktype)
        return jsonify(snapshot=snapshot_no, scenario_version=supervisor_scenario()['version'], **result)

    def snapshot_display(snapshot_no):
        """Single source for on-screen and exported supervisor scenario values."""
        baseline = db.trucks_at(snapshot_no)
        state = current_state(snapshot_no)
        return display_trucks(baseline, state), state

    @app.route("/export/trucks.csv")
    def export_trucks():
        snapshot_no = request.args.get('snapshot', default=config.DEFAULT_SNAPSHOT, type=int)
        if not any(s.snapshot_no == snapshot_no for s in db.snapshots()):
            abort(404)
        trucks, _ = snapshot_display(snapshot_no)
        search = request.args.get('q', '').strip().casefold()
        risk = request.args.get('risk', '').strip()
        if risk not in ('', 'healthy', 'risk', 'critical', 'unknown'):
            risk = ''
        selection = [t for t in trucks if (search in t.shipment_id.casefold() or
                     search in (t.planning_status or '').casefold() or
                     search in (t.bottleneck or '').casefold()) and
                     (not risk or t.category == risk)]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['snapshot','shipment_id','status','risk_category','departure',
                         'buffered_pick_deadline','loading_minutes','conservative_ready_time',
                         'conservative_etc_hours','open_lines','released_lines','staffed_work_areas',
                         'open_work_areas','bottleneck_worktype','conservative_slack'])
        for t in selection:
            writer.writerow([snapshot_no,t.shipment_id,t.planning_status,t.category,
                             t.departure.isoformat() if t.departure else '',
                             t.pick_cutoff.isoformat() if t.pick_cutoff else '',
                             t.loading_minutes,
                             t.ready_time_late.isoformat() if t.ready_time_late else '',
                             round(t.etc_high_hours, 4) if t.etc_high_hours is not None else '',
                             t.open_lines,t.lines_released,t.staffed_areas,t.open_areas,
                             t.bottleneck,t.planning_slack_text])
        return Response(output.getvalue(), mimetype='text/csv; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="truck-etc-snapshot-{snapshot_no}.csv"',
                                 'Cache-Control': 'no-store'})

    @app.route("/operators")
    def operators():
        snaps = db.snapshots()
        snapshot_no = request.args.get('snapshot', default=config.DEFAULT_SNAPSHOT, type=int)
        current = next((s for s in snaps if s.snapshot_no == snapshot_no), None)
        if current is None:
            abort(404)
        src = db.load_sources()
        state = current_state(snapshot_no)
        names = sorted({str(n) for n in src.lm.RESOURCENAME.dropna().unique()})
        rows = []
        for name in names:
            wt = state['active'].get(name)
            stats = state['stats'].get((name, wt), {}) if wt is not None else {}
            rows.append(dict(name=name, worktype=wt,
                             worktype_name=src.worktype_names.get(wt, '') if wt is not None else '',
                             pace=stats.get('pace'), observed_hours=stats.get('logged_hours', 0),
                             picking_hours=stats.get('picking_hours', 0),
                             observed_lines=stats.get('lines', 0)))
        moved = {m['operator']: m for m in state['applied']}
        for row in rows:
            move = moved.get(row['name'])
            row['role'] = 'Reallocated' if move else 'Existing'
            row['role_detail'] = (f"WT {move['source']} → WT {move['dest']} (session only)" if move
                                  else 'Original assignment')
        temporary_rows = []
        for alloc in state.get('temporaries_applied', []):
            for i in range(int(alloc['count'])):
                temporary_rows.append(dict(name=f"{alloc['id']}-{i + 1}", worktype=int(alloc['dest']),
                                           worktype_name=src.worktype_names.get(int(alloc['dest']), ''),
                                           pace=alloc['pace'], shipment=alloc['shipment']))
        return render_template('operators.html', operators=rows, current=current, snaps=snaps,
                               pace_info=state['pace_info'], temporary_rows=temporary_rows)

    @app.route("/")
    def dashboard():
        snaps = db.snapshots()
        snapshot_no = request.args.get('snapshot', default=config.DEFAULT_SNAPSHOT, type=int)
        current = next((s for s in snaps if s.snapshot_no == snapshot_no), None)
        if current is None:
            abort(404)
        trucks, scenario = snapshot_display(current.snapshot_no)
        counts = {}
        for t in trucks:
            key = 'DEPARTED' if t.planning_status.startswith('DEPARTED') else t.planning_status
            counts[key] = counts.get(key, 0) + 1
        metrics = summary(trucks)
        search = request.args.get('q', '').strip()
        risk_filter = request.args.get('risk', '').strip()
        if risk_filter not in ('', 'healthy', 'risk', 'critical', 'unknown'):
            risk_filter = ''
        shown = [t for t in trucks
                 if (search.casefold() in t.shipment_id.casefold() or
                     search.casefold() in t.planning_status.casefold() or
                     search.casefold() in (t.bottleneck or '').casefold())
                 and (not risk_filter or t.category == risk_filter)]
        shown.sort(key=lambda t: (['critical','risk','unknown','healthy'].index(t.category),
                                  t.departure, t.shipment_id))
        # Re-evaluate the same scenario state at each point on the historical replay.
        # Never extrapolate it into a future stream of pick events.
        inputs = db.load_sources()
        overrides = db.get_loading_overrides()
        committed = supervisor_scenario()['confirmed_moves']
        committed_temps = supervisor_scenario().get('confirmed_temps', [])
        trend = []
        last_picked = None
        for snap in snaps:
            if snap.snapshot_no > current.snapshot_no:
                break
            base = db.trucks_at(snap.snapshot_no)
            st = build_state(inputs, db.worktype_context(snap.snapshot_no), base,
                             snap.snapshot_no, overrides, committed, temporaries=committed_temps)
            subset = display_trucks(base, st)
            stat = summary(subset)
            picked = sum(t.lines_picked for t in base)
            trend.append(dict(time=snap.snapshot_time.strftime('%H:%M'),
                              snapshot=snap.snapshot_no, on_time=stat['on_time_pct'],
                              healthy=stat['healthy'], risk=stat['risk'], critical=stat['critical'],
                              unknown=stat['unknown'],
                              completed=None if last_picked is None else max(0, picked-last_picked)))
            last_picked = picked
        active = [t for t in trucks if t.open_lines > 0 and not t.status.startswith('DEPARTED')]
        chart = {'trucks':[f"{t.shipment_id} ({t.departure:%H:%M})" for t in active],
                 'etc':[t.etc_hours for t in active],
                 'etc_high':[t.etc_high_hours for t in active],
                 'cutoff':[max(0,t.hours_to_cutoff) for t in active],
                 'status':[t.planning_status for t in active]}
        # v13: environmental summary — context only; computed after every ETC figure above.
        env_conditions, env_contexts = area_conditions(current.snapshot_no)
        environment_summary = None if env_conditions is None else dict(
            zones=env_conditions['zones'], attention=env_conditions['attention'],
            synthetic=env_conditions['synthetic_present'],
            at_risk_areas=len(cutoff_context(current.snapshot_no, env_contexts)))
        return render_template('dashboard.html', snaps=snaps, current=current,
                               environment_summary=environment_summary,
                               trucks=shown, total_matching=len(shown), counts=counts,
                               metrics=metrics, search=search, risk_filter=risk_filter,
                               insights=operational_insights(trucks, scenario, committed),
                               trend=trend, chart=chart, all_trucks=trucks,
                               moves_count=len(committed),
                               temps_count=sum(int(t['count']) for t in committed_temps))

    @app.route("/truck/<shipment_id>")
    def truck(shipment_id):
        snaps = db.snapshots()
        snapshot_no = request.args.get("snapshot", default=config.DEFAULT_SNAPSHOT, type=int)
        current = next((s for s in snaps if s.snapshot_no == snapshot_no), snaps[0])
        hist = db.truck_history(shipment_id)
        if not hist:
            abort(404)
        src = db.load_sources()
        detail = truck_detail(src, src.snapshots, current.snapshot_no, shipment_id, hist,
                              db.worktype_rows(current.snapshot_no, shipment_id), src.worktype_names,
                              db.reallocation_moves(current.snapshot_no))
        scenario = current_state(current.snapshot_no)
        scenario_truck = next(v for v in scenario['trucks'] if v['shipment'] == shipment_id)
        engine_status = str(detail['truck'].get('TRUCK_STATUS') or '')
        detail['truck']['PLANNING_STATUS'] = departed_status(engine_status, scenario_truck)
        detail['truck']['PHYSICAL_CUTOFF'] = scenario_truck['cutoff']
        detail['truck']['SCENARIO_OPEN_LINES'] = scenario_truck['open_lines']
        detail['truck']['HISTORY_OPEN_LINES'] = scenario_truck['history_open_lines']
        detail['truck']['PLANNING_SLACK'] = (f"{scenario_truck['slack_minutes']:+.0f} min"
                                               if scenario_truck['slack_minutes'] is not None else '')
        detail['truck']['PICK_CUTOFF'] = scenario_truck['deadline']
        detail['truck']['TRUCK_STATUS_AFTER'] = detail['truck']['PLANNING_STATUS']
        detail['truck']['PLANNING_STATUS_AFTER'] = detail['truck']['PLANNING_STATUS']
        detail['truck']['PLANNING_SLACK_AFTER'] = detail['truck']['PLANNING_SLACK']
        detail['truck']['REALLOCATIONS'] = ', '.join(m['operator'] for m in scenario['applied'])
        selected_rows = [r for r in scenario['rows'] if r['shipment']==shipment_id and r['open']]
        point_times = [r['point_ready'] for r in selected_rows if r['point_ready'] is not None]
        slow_times = [r['conservative_ready'] for r in selected_rows if r['conservative_ready'] is not None]
        computed_point = max(point_times) if len(point_times)==len(selected_rows) and selected_rows else None
        computed_slow = max(slow_times) if len(slow_times)==len(selected_rows) and selected_rows else None
        detail['truck']['TRUCK_STATUS'] = ('ON TIME' if computed_point is not None
            and computed_point <= scenario_truck['deadline'] else detail['truck']['PLANNING_STATUS'])
        detail['truck']['ETC_HOURS'] = ((computed_point - scenario['now'])*24 if computed_point is not None else None)
        detail['truck']['ETC_LOW_HOURS'] = detail['truck']['ETC_HOURS']
        detail['truck']['ETC_HIGH_HOURS'] = ((computed_slow - scenario['now'])*24 if computed_slow is not None else None)
        detail['truck']['READY_TIME'] = computed_point
        detail['truck']['READY_TIME_EARLY'] = computed_point
        detail['truck']['READY_TIME_LATE'] = computed_slow
        detail['truck']['PLANNING_OPERATOR_GAP'] = ''
        detail['truck']['OPERATOR_GAP'] = ''
        detail['truck']['UNCERTAINTY_CHANGES_RISK'] = False
        detail['truck']['TIME_SAVED_MIN'] = None
        # Single source of truth for the gap card and projection chart. This adapter
        # uses the same conservative minimum-staffing and preview functions as planner.
        area_forecasts, detail['operator_gap'] = area_recommendations(
            src, scenario, shipment_id, current.snapshot_no,
            supervisor_scenario().get('preview', {}))
        forecast_by_worktype = {item['worktype']: item for item in area_forecasts}
        for wt in detail['worktypes']:
            matching = next((r for r in scenario['rows'] if r['shipment'] == shipment_id
                             and r['worktype'] == wt['worktype']), None)
            if matching:
                resolved_moves=[m['operator'] for m in scenario['applied'] if int(m['dest'])==matching['worktype']]
                temp_here = sum(int(t['count']) for t in scenario.get('temporaries_applied', [])
                                if int(t['dest']) == matching['worktype'])
                if temp_here:
                    resolved_moves.append(f"{temp_here} temporary")
                projected_gap = forecast_by_worktype.get(matching['worktype'], {}).get('recommendation')
                wt.update(planning_status=matching['status'], status=matching['point_status'],
                          planning_meets=('YES' if matching['status']=='ON TIME' else 'NO'),
                          rate=matching['rate'], ready=matching['point_ready'],
                          ready_late=matching['conservative_ready'],
                          ready_after=matching['point_ready'], ready_after_late=matching['conservative_ready'],
                          ahead_other=max(0, matching['ahead'] - matching['open']),
                          additional_conservative=(projected_gap['required'] if projected_gap and projected_gap['possible']
                                                  else 'Unavailable' if projected_gap else ''),
                          reallocated_out='', 
                          planning_meets_after=('YES' if matching['status']=='ON TIME' else 'NO'),
                          status_after=matching['status'], reallocated_in=', '.join(resolved_moves),
                          etc=matching['point_etc'], etc_high=matching['conservative_etc'],
                          open_lines=matching['open'])
        # Replace historical baseline risk/slack in the truck trend with the same
        # buffered scenario used by the dashboard. Picking facts remain historical.
        overrides = db.get_loading_overrides()
        active_moves = supervisor_scenario()['confirmed_moves']
        points = db.snapshots()
        history = []
        for index, snap_no in enumerate(range(1, current.snapshot_no+1)):
            earlier = build_state(src,db.worktype_context(snap_no),db.trucks_at(snap_no),
                                  snap_no,overrides,active_moves,
                                  temporaries=supervisor_scenario().get('confirmed_temps', []))
            truck_point = next((x for x in earlier['trucks'] if x['shipment']==shipment_id),None)
            if truck_point:
                if index < len(detail['trends']['status']):
                    detail['trends']['status'][index]=truck_point['status']
                    detail['trends']['slack'][index]=truck_point['slack_minutes']
                engine_then = next((t.status for t in db.trucks_at(snap_no) if t.shipment_id == shipment_id), '')
                history.append(dict(time=scenario_datetime(earlier['now']).strftime('%H:%M'), snapshot=snap_no,
                                    status=departed_status(engine_then or '', truck_point),
                                    open=truck_point['open_lines'], history_open=truck_point['history_open_lines'],
                                    ready=(scenario_datetime(truck_point['conservative_ready']).strftime('%H:%M')
                                           if truck_point['conservative_ready'] is not None else '—'),
                                    reason=explain_status(earlier, shipment_id)))
        # v14: every status change at each snapshot, with the numbers that caused it (newest first)
        for i, entry in enumerate(history):
            entry['changed'] = i == 0 or entry['status'] != history[i - 1]['status']
        detail['status_history'] = list(reversed(history))
        detail['reallocations'] = []  # legacy automatically generated proposals are NOT confirmed allocations
        operational_alerts = [a for a in detail['alerts']
                              if any(k in a[1] for k in ('Low pace', 'Idle', 'Assigned', 'Logged out', 'short picks'))]
        deadline_alerts = [('danger', f"{r['name']} conservative finish "
                            f"{scenario_datetime(r['conservative_ready']).strftime('%H:%M') if r['conservative_ready'] is not None else 'unknown'} "
                            f"fails the buffered deadline {scenario_datetime(r['deadline']).strftime('%H:%M')}",
                            'Review the experienced operators in Supervisor planner')
                           for r in scenario['rows'] if r['shipment']==shipment_id and r['open']
                           and r['status'] in RISK_STATUSES]
        detail['alerts'] = deadline_alerts + operational_alerts
        detail['why_now'] = explain_status(scenario, shipment_id)
        detail['why'] = (f"Rules: pick cutoff = departure - {scenario_truck['loading_minutes']} min loading; "
                         f"safety-buffer deadline = pick cutoff - {scenario['buffer_minutes']} min. On Time = conservative "
                         f"ready by the buffer deadline; At Risk = after the buffer deadline but not after the pick cutoff; "
                         f"Pick Cutoff Passed = ready after the pick cutoff, or the cutoff has passed with lines open. "
                         f"The slowest outstanding work type controls readiness. Allocations are session-only scenarios: "
                         f"from the snapshot after confirmation, the lines the added capacity would have picked are "
                         f"subtracted (and a moved operator's own source picks reopened), never written to the WMS.")
        # v10: one truck-level before/after ready-time comparison (green/yellow/red vs cutoff and buffer).
        ready = ready_chart(current.snapshot_no, shipment_id, scenario)
        _, env_contexts = area_conditions(current.snapshot_no)   # v13: context only, after every ETC figure
        return render_template("truck_detail.html", snaps=snaps, current=current, d=detail, ship=shipment_id, ready=ready,
                               env_contexts=env_contexts,
                               wt_names=src.worktype_names,
                               style=status_style(detail["truck"].get("PLANNING_STATUS") or detail["truck"]["TRUCK_STATUS"]))

    @app.route("/operator/<operator_name>")
    def operator(operator_name):
        snaps = db.snapshots()
        snapshot_no = request.args.get("snapshot", default=config.DEFAULT_SNAPSHOT, type=int)
        current = next((s for s in snaps if s.snapshot_no == snapshot_no), snaps[0])
        src = db.load_sources()
        profile = operator_profile(src, src.snapshots, current.snapshot_no, operator_name,
                                   db.worktype_context(current.snapshot_no), src.worktype_names, [])
        if profile is None:
            abort(404)
        current_scenario = current_state(current.snapshot_no)
        temporary_move = next((m for m in current_scenario['applied'] if m['operator'] == operator_name), None)
        # v11: planning pace (picking-time basis) used by ETC and allocation, beside the logged-time figures
        planning = current_scenario['stats'].get((operator_name, profile['current_worktype']), {})
        profile['planning_pace'], profile['picking_hours'] = planning.get('pace'), planning.get('picking_hours')
        profile['pace_basis'] = current_scenario['pace_info']['basis']
        for m in profile['worktype_metrics']:
            own = current_scenario['stats'].get((operator_name, int(m['worktype'])), {})
            m['planning_pace'], m['picking_hours'] = own.get('pace'), own.get('picking_hours')
        source_rows = [r for r in current_scenario['rows'] if
                       r['worktype']==profile['current_worktype'] and r['open']]
        if source_rows:
            profile['cutoff'] = min(r['deadline'] for r in source_rows)
            profile['cutoff_status'] = ('AT RISK' if any(r['status'] not in ('ON TIME','ALL PICKED') for r in source_rows)
                                        else 'ON TIME')
        else:
            profile['cutoff'],profile['cutoff_status'] = None,'No outstanding source-worktype work'
        for entry in profile['eligibility']:
            row = next((r for r in candidates(src,current_scenario,entry['worktype'])
                        if r['operator']==operator_name),None)
            entry['at_risk_trucks'] = sum(r['status'] in RISK_STATUSES and bool(r['open'])
                                          for r in current_scenario['rows'] if r['worktype']==entry['worktype'])
            if row is None:
                entry['state'],entry['reason'] = 'Not eligible', 'No currently active eligible scenario operator or already moved.'
            else:
                entry['state'] = 'Eligible candidate' if row['safe'] else 'Not eligible'
                entry['reason'],entry['estimated_pace'] = row['reason'],row['pace']
        return render_template("operator_detail.html", snaps=snaps, current=current, o=profile,
                               temporary_move=temporary_move, wt_names=src.worktype_names)

    # ---------------- v13 Environmental conditions (context only) ----------------
    def snapshot_local_time(snapshot_no):
        snap = next((s for s in db.snapshots() if s.snapshot_no == snapshot_no), None)
        return snap.snapshot_time if snap else None

    def environment_conditions(snapshot_no):
        as_of = snapshot_local_time(snapshot_no)
        return env.zone_conditions(as_of) if as_of else None

    def area_conditions(snapshot_no):
        """Context lines per work type for the truck page, planner and dashboard.

        Never raises: if the environment database is unavailable the pages still render with the
        unchanged baseline ETC and say that conditions are unavailable.
        """
        try:
            conditions = environment_conditions(snapshot_no)
        except Exception as error:  # noqa: BLE001 - environment data must never break ETC pages
            app.logger.warning('Environment data unavailable: %s', error)
            return None, {}
        if conditions is None:
            return None, {}
        return conditions, {int(wt): env.worktype_context(conditions, wt)
                            for wt in db.load_sources().worktype_names}

    def cutoff_context(snapshot_no, contexts, state=None):
        """Open work-type rows that miss the buffered deadline under the BASELINE (measured-pace) ETC,
        with the area's latest conditions beside them. No environmental estimate is computed."""
        state = state or current_state(snapshot_no)
        rows = [r for r in risk_rows(state) if r['status'] not in ('ON TIME', 'ALL PICKED')]
        fmt = lambda v: scenario_datetime(v).strftime('%H:%M') if v is not None else '—'
        return [dict(shipment=r['shipment'], worktype=r['worktype'], name=r['name'], status=r['status'],
                     risk=r['risk'], open=r['open'], deadline=fmt(r['deadline']),
                     ready=fmt(r['conservative_ready']), slack=r['slack_minutes'],
                     condition=contexts.get(int(r['worktype']))) for r in rows]

    def require_entry_key():
        if config.ENV_ENTRY_KEY and not secrets.compare_digest(request.form.get('entry_key', ''),
                                                               config.ENV_ENTRY_KEY):
            raise ValueError('Entry key required: only authorized users can record readings or change settings.')

    @app.route('/environment', methods=['GET', 'POST'])
    def environment():
        snaps = db.snapshots()
        snapshot_no = request.values.get('snapshot', default=config.DEFAULT_SNAPSHOT, type=int)
        current = next((s for s in snaps if s.snapshot_no == snapshot_no), None)
        if current is None:
            abort(404)
        if request.method == 'POST':
            require_csrf()
            action = request.form.get('action', '')
            try:
                if action in ('reading', 'zone', 'device', 'note', 'load_synthetic', 'delete_synthetic'):
                    require_entry_key()
                by = request.form.get('recorded_by', '').strip()[:60]
                if action == 'reading':
                    when = datetime.strptime(request.form.get('reading_time', ''), '%Y-%m-%dT%H:%M')
                    outcome = env.record_reading(request.form.get('zone', ''), request.form.get('temperature', ''),
                                                 request.form.get('humidity', ''), env.local_to_utc(when),
                                                 'manual', recorded_by=by or 'not stated')
                    if outcome['status'] == 'duplicate':
                        flash('A manual reading for this zone and time already exists; not stored twice.', 'warning')
                    elif outcome['quality'] == 'suspect':
                        flash(f"Reading stored but marked SUSPECT: {outcome['note']}.", 'warning')
                    else:
                        flash('Reading stored (manual entry, context only — not used in ETC).', 'success')
                elif action == 'zone':
                    code = request.form.get('zone_code', '').strip().upper()
                    name = request.form.get('zone_name', '').strip()
                    if not code or not name or len(code) > 20 or not code.replace('-', '').replace('_', '').isalnum():
                        raise ValueError('Enter a zone code (letters, digits, - or _) and a name.')
                    worktype = request.form.get('worktype', type=int)
                    env_store.add_zone(code, name, worktype if worktype in db.load_sources().worktype_names else None)
                    flash(f'Zone {code} added (user added).', 'success')
                elif action == 'device':
                    device_id = request.form.get('device_id', '').strip()
                    zone = request.form.get('zone', '')
                    if not device_id or len(device_id) > 40 or zone not in {z['zone_code'] for z in env_store.zones()}:
                        raise ValueError('Enter a device identifier (max 40 characters) and choose its zone.')
                    env_store.register_device(device_id, zone, request.form.get('description', '').strip()[:120])
                    flash(f'Device {device_id} registered to {zone}. It can now post readings to the API.', 'success')
                elif action == 'note':
                    topic = request.form.get('topic', '')
                    if topic not in ('hydration_stations', 'break_policy', 'procedures'):
                        raise ValueError('Unknown note topic')
                    env_store.set_site_note(topic, request.form.get('text', '').strip()[:4000], by or 'not stated')
                    flash('Site information saved (client-documented).', 'success')
                elif action == 'load_synthetic':
                    count = env.load_synthetic(current.snapshot_time.date())
                    flash(f'{count} SYNTHETIC demo readings loaded. They are labelled, excluded from analysis, '
                          'and can be deleted at any time.', 'info')
                elif action == 'delete_synthetic':
                    flash(f'{env_store.delete_synthetic()} SYNTHETIC demo readings deleted.', 'info')
                else:
                    abort(400, 'Unknown action')
            except (ValueError, TypeError) as error:
                flash(str(error), 'danger')
            anchor = {'device': 'sensors', 'zone': 'sensors', 'note': 'heat-safety',
                      'load_synthetic': 'demo', 'delete_synthetic': 'demo'}.get(action, 'record')
            return redirect(url_for('environment', snapshot=snapshot_no, done=anchor) + '#' + anchor)
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(24)
        conditions, contexts = area_conditions(current.snapshot_no)
        if conditions is None:
            abort(503, 'Environment database unavailable; truck ETC pages are unaffected.')
        src = db.load_sources()
        analysis = analyse_environment(src.tc, src.worktype_names)
        recent = env_store.readings(until_utc=None, limit=40)
        for r in recent:
            r['local_time'] = env.utc_to_local(r['reading_utc']).strftime('%d-%b-%Y %H:%M')
        # Colour follows the zone (fixed order of the zone list), never the series position.
        zone_list = env_store.zones()
        palette = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
        colours = {z['name']: (palette[i] if i < len(palette) else '#8a94a6') for i, z in enumerate(zone_list)}
        trends = env.trend_series(current.snapshot_time)
        for series in trends:
            series['color'] = colours.get(series['zone'], '#8a94a6')
        return render_template('environment.html', snaps=snaps, current=current, c=conditions,
                               trends=trends, analysis=analysis,
                               cutoff=cutoff_context(current.snapshot_no, contexts),
                               productivity=analysis.get('productivity_table', []),
                               recent=recent, notes=env_store.site_notes(), zones=env_store.zones(),
                               wt_names=src.worktype_names, tz=env.timezone_status(),
                               api_enabled=bool(config.ENV_INGEST_TOKEN), entry_key_required=bool(config.ENV_ENTRY_KEY),
                               default_time=current.snapshot_time.strftime('%Y-%m-%dT%H:%M'),
                               csrf=session['csrf_token'], cfg=config)

    @app.route('/api/environment/readings', methods=['POST'])
    def environment_ingest():
        """Sensor ingestion. Bearer token (ENV_INGEST_TOKEN); disabled when the token is empty."""
        if not config.ENV_INGEST_TOKEN:
            return jsonify(error='Sensor API disabled: set ENV_INGEST_TOKEN in .env'), 503
        supplied = request.headers.get('Authorization', '')
        if not secrets.compare_digest(supplied, f'Bearer {config.ENV_INGEST_TOKEN}'):
            return jsonify(error='Invalid or missing bearer token'), 401
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify(error='Body must be JSON'), 400
        try:
            results = env.ingest(payload)
        except OverflowError as error:
            return jsonify(error=str(error)), 413
        return jsonify(results=results, stored=sum(r['status'] == 'stored' for r in results))

    @app.route('/api/environment/zones')
    def environment_zones_api():
        snapshot_no = request.args.get('snapshot', default=config.DEFAULT_SNAPSHOT, type=int)
        conditions = environment_conditions(snapshot_no)
        if conditions is None:
            abort(404)
        return jsonify(as_of=conditions['as_of'].isoformat(), timezone=env.timezone_status()['name'],
                       used_in_etc=False, zones=[dict(
            zone=c['zone']['zone_code'], name=c['zone']['name'], worktype=c['zone']['worktype'],
            freshness=c['freshness'], age_minutes=c['age_minutes'],
            temperature_c=c['reading']['temperature_c'] if c['reading'] else None,
            humidity_pct=c['reading']['humidity_pct'] if c['reading'] else None,
            quality=c['reading']['quality'] if c['reading'] else None,
            data_label=c['reading']['data_label'] if c['reading'] else None,
            method=c['reading']['method'] if c['reading'] else None,
            reading_time_local=c['local_time']) for c in conditions['zones']],
            attention=[a['text'] for a in conditions['attention']])

    return app


app = create_app()

if __name__ == "__main__":
    import os
    app.run(debug=os.getenv('FLASK_DEBUG','0') == '1', port=5006)
