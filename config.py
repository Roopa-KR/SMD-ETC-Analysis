"""Application settings, read from .env (python-dotenv)."""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _path(value: str) -> str:
    return value if os.path.isabs(value) else os.path.join(BASE_DIR, value)


WORKBOOK_PATH = _path(os.getenv("WORKBOOK_PATH", "data/workbook.xlsx"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/truck_etc.db")
if DATABASE_URL.startswith("sqlite:///") and not os.path.isabs(DATABASE_URL[len("sqlite:///"):]):
    # a relative SQLite path is taken from the project folder, wherever the app is started from
    DATABASE_URL = "sqlite:///" + _path(DATABASE_URL[len("sqlite:///"):]).replace("\\", "/")
DEFAULT_SNAPSHOT = int(os.getenv("DEFAULT_SNAPSHOT", "10"))
# Minutes that picking must finish BEFORE the pick cutoff (pick cutoff = departure - loading time).
# Safety buffer deadline = pick cutoff - SAFETY_BUFFER_MINUTES. Default loading time comes from
# the workbook (TRUCK_CONFIG.LOADING_MINUTES); per-truck overrides are saved from the planner.
SAFETY_BUFFER_MINUTES = int(os.getenv("SAFETY_BUFFER_MINUTES", "10"))
if not 0 <= SAFETY_BUFFER_MINUTES <= 240:
    raise ValueError("SAFETY_BUFFER_MINUTES must be between 0 and 240")
# Planning pace basis (v11). 'picking_time' = lines / picking time, where a gap longer than
# PACE_GAP_CAP_MINUTES between an operator's picks counts as waiting, not picking.
# 'logged_time' = lines / logged-in hours, i.e. the original Excel ETC equation.
PACE_BASIS = os.getenv("PACE_BASIS", "picking_time").strip().lower()
if PACE_BASIS not in ("picking_time", "logged_time"):
    raise ValueError("PACE_BASIS must be 'picking_time' or 'logged_time'")
PACE_GAP_CAP_MINUTES = int(os.getenv("PACE_GAP_CAP_MINUTES", "10"))
if not 1 <= PACE_GAP_CAP_MINUTES <= 120:
    raise ValueError("PACE_GAP_CAP_MINUTES must be between 1 and 120")
# Temporary operators (v12): used only after safe reallocation of existing operators is evaluated.
# Assumed pace = TEMP_OPERATOR_PACE_PCT % of the work type's measured per-person rate (the earlier
# SMD workbook used TEMP_PACE_PCT = 100%). SYNTHESIZED ASSUMPTION - no temporary-staff history exists.
TEMP_OPERATOR_PACE_PCT = int(os.getenv("TEMP_OPERATOR_PACE_PCT", "100"))
if not 10 <= TEMP_OPERATOR_PACE_PCT <= 200:
    raise ValueError("TEMP_OPERATOR_PACE_PCT must be between 10 and 200")
# Most temporary operators that can be added to one work type (earlier workbook pool: 10).
TEMP_OPERATOR_MAX = int(os.getenv("TEMP_OPERATOR_MAX", "10"))
if not 1 <= TEMP_OPERATOR_MAX <= 50:
    raise ValueError("TEMP_OPERATOR_MAX must be between 1 and 50")

# ---------- v13 Environmental conditions (context only; never used in ETC or allocation) ----------
# Separate database: readings never touch the WMS/LMS source tables or the rebuildable cache.
ENV_DATABASE_URL = os.getenv("ENV_DATABASE_URL", "sqlite:///data/environment.db")
if ENV_DATABASE_URL.startswith("sqlite:///") and not os.path.isabs(ENV_DATABASE_URL[len("sqlite:///"):]):
    ENV_DATABASE_URL = "sqlite:///" + _path(ENV_DATABASE_URL[len("sqlite:///"):]).replace("\\", "/")
WAREHOUSE_TIMEZONE = os.getenv("WAREHOUSE_TIMEZONE", "America/New_York")  # to be confirmed by the client
ENV_STALE_MINUTES = int(os.getenv("ENV_STALE_MINUTES", "60"))
ENV_DEVICE_SILENT_MINUTES = int(os.getenv("ENV_DEVICE_SILENT_MINUTES", "30"))
ENV_TEMP_MIN_C = float(os.getenv("ENV_TEMP_MIN_C", "-40"))
ENV_TEMP_MAX_C = float(os.getenv("ENV_TEMP_MAX_C", "85"))
ENV_MAX_STEP_C = float(os.getenv("ENV_MAX_STEP_C", "10"))
ENV_MAX_STEP_RH = float(os.getenv("ENV_MAX_STEP_RH", "30"))
ENV_INGEST_TOKEN = os.getenv("ENV_INGEST_TOKEN", "").strip()      # empty = sensor API disabled
ENV_ENTRY_KEY = os.getenv("ENV_ENTRY_KEY", "").strip()            # empty = no entry key required
ENV_MIN_PAIRED_HOURS = int(os.getenv("ENV_MIN_PAIRED_HOURS", "30"))
ENV_MIN_DAYS = int(os.getenv("ENV_MIN_DAYS", "5"))
ENV_MIN_TEMP_SPREAD_C = float(os.getenv("ENV_MIN_TEMP_SPREAD_C", "3"))
ENV_TREND_MIN_READINGS = int(os.getenv("ENV_TREND_MIN_READINGS", "3"))
for _name, _value, _lo, _hi in (("ENV_STALE_MINUTES", ENV_STALE_MINUTES, 1, 1440),
                                ("ENV_DEVICE_SILENT_MINUTES", ENV_DEVICE_SILENT_MINUTES, 1, 1440),
                                ("ENV_MIN_PAIRED_HOURS", ENV_MIN_PAIRED_HOURS, 5, 100000),
                                ("ENV_MIN_DAYS", ENV_MIN_DAYS, 1, 3650)):
    if not _lo <= _value <= _hi:
        raise ValueError(f"{_name} must be between {_lo} and {_hi}")
if ENV_TEMP_MIN_C >= ENV_TEMP_MAX_C:
    raise ValueError("ENV_TEMP_MIN_C must be below ENV_TEMP_MAX_C")
