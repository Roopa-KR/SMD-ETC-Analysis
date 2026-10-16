"""Validate the SQL schema without importing Flask (offline CI smoke)."""
import ast
import sqlite3
from pathlib import Path


def test_schema_ddl_executes_and_has_expected_keys():
    source=Path(__file__).resolve().parents[1].joinpath('app.py').read_text()
    tree=ast.parse(source)
    scripts=[n.args[0].value for n in ast.walk(tree)
             if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
             and n.func.attr=='executescript' and n.args
             and isinstance(n.args[0],ast.Constant)]
    assert len(scripts)==1
    connection=sqlite3.connect(':memory:')
    connection.executescript(scripts[0])
    tables={x[0] for x in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'inspection_results','inspection_audit','unit_state','action_log'}<=tables
    inspection={x[1] for x in connection.execute('PRAGMA table_info(inspection_audit)')}
    assert 'evidence_filename' in inspection
    connection.execute("INSERT INTO inspection_results VALUES('TANK-0020','CTQ-003','100','REVIEW','','','Demo','now')")
    try:
        connection.execute("INSERT INTO inspection_results VALUES('TANK-0020','CTQ-003','200','PASS','','','Demo','now')")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError('Inspection result composite primary key is not unique')
    connection.close()
