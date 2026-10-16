import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# v13: tests use their own environmental-readings database, never data/environment.db.
# Set before config is imported (python-dotenv does not override an existing variable).
import tempfile  # noqa: E402
_ENV_TMP = tempfile.mkdtemp(prefix='smd-env-tests-')
os.environ['ENV_DATABASE_URL'] = 'sqlite:///' + os.path.join(_ENV_TMP, 'environment_test.db').replace('\\', '/')
WORKBOOK = os.path.join(ROOT, "INFO", "historical", "historical_33_trucks_reference.xlsx")


@pytest.fixture(scope="session")
def results():
    from calculations.engine import run
    return run(WORKBOOK)


@pytest.fixture(scope="session")
def reference():
    from calculations.excel_io import load_reference
    return load_reference(WORKBOOK)


# v14: the synthesized scenario has two genuinely At Risk trucks at the default snapshot (18:30):
# SH0908-1034 and SH0908-1069, both departing 20:30 (pick cutoff 20:00, buffer deadline 19:50), with
# conservative ready 19:57 in OTC. Stronger pressure for the allocation tests still comes only from the
# existing per-truck loading-time setting (a supervisor input), never by forcing a status. Values below
# were derived from the calculations at snapshot 10 (18:30), SH0908-1034:
#    30 min loading (default) -> yellow (At Risk) before,             +1 (dclements)        -> green
#    70 min loading           -> red (Pick Cutoff Passed, projected),  +2 (dclements, ekim)  -> green
#   102 min loading           -> red, no plan: reallocation plus 11 temporary operators (> max 10) needed
PRESSURE_TRUCK = 'SH0908-1034'
ONE_OPERATOR_LOADING, TWO_OPERATOR_LOADING, INFEASIBLE_LOADING = 30, 70, 102


@pytest.fixture
def loading_override():
    """Set saved per-truck loading overrides for one test; always restores the previous values."""
    from models import database as db
    saved = []

    def apply(shipment=PRESSURE_TRUCK, minutes=TWO_OPERATOR_LOADING):
        saved.append((shipment, db.get_loading_overrides().get(shipment)))
        db.set_loading_override(shipment, minutes)

    yield apply
    for shipment, previous in reversed(saved):
        db.set_loading_override(shipment, previous)


@pytest.fixture
def clean_env():
    """Empty environmental store (zones re-seeded from the M123 work types) before and after a test."""
    from sqlalchemy import text
    from models import database as db
    from models import environment as env_store

    def wipe():
        env_store.init_env(db.load_sources().worktype_names)
        with env_store.engine.begin() as connection:
            for table in ('env_reading', 'env_device', 'env_site_note'):
                connection.execute(text(f'DELETE FROM {table}'))
            connection.execute(text("DELETE FROM env_zone WHERE source != 'M123 work type'"))

    wipe()
    yield env_store
    wipe()
