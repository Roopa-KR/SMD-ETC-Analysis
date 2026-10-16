# Shop-floor extension — test and readiness record

**Date:** 16 October 2026  
**Scope:** Existing fixed scenario prototype plus newly added operator, WO and LMS routes.

## Executed checks

- `python -m pytest -q tests/test_mfg_logic.py tests/test_mfg_render.py tests/test_mfg_schema.py tests/test_shopfloor_logic.py tests/test_manufacturing_routes.py` — **69 passed, 1 module skipped** (route module is explicitly skipped without Flask).
- Strict Jinja render: **13 pages** compiled and rendered with mock data and `StrictUndefined`, including the new operator/WO/LMS pages; not a browser integration test.
- Python AST/compileall: syntax valid for Flask entry module and manufacturing modules.
- `node --check static/js/manufacturing.js`: JS syntax valid.
- SQLite in-memory tests verified task creation, concurrent workers on same unit, double-book prevention, paused time exclusion, monotonic transitions, qualification and unit-stage validation, downstream receiving defects, open holds and all four point weights.
- `python app.py` — **failed** at `ModuleNotFoundError: No module named 'flask'`. This is an environment dependency limitation, not a validated successful startup.

## Not executed / cannot claim

- Flask server startup, HTTP GET/POST route integration, CSRF/persistence integration and reset behavior — prepared in `tests/test_manufacturing_routes.py`, *not executed* because Flask is missing.
- Real browser interaction, adaptive mobile layout, live tablet camera hardware, enterprise authentication, production system integrations.
- Real manufacturing ETC, OEE, benchmark/rank predictions or financial returns, because the supplied information does not include sufficient validated event/target data.

## Readiness decision

**Development prototype only; not cleared for customer demonstration.** Before declaring ready, install `requirements-dev.txt`, rerun the Flask route tests, start `python app.py`, check browser paths and camera/CTQ behaviors, verify all persistence/reset paths, and resolve the approvals and business-rule questions in the companion requirements document.
