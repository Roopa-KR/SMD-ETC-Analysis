"""Environmental readings store (v13) — a SEPARATE SQLite database (config.ENV_DATABASE_URL).

Kept apart from the WMS/LMS source tables and from the rebuildable results cache, so a cache
rebuild can never delete readings and readings can never overwrite operator, workload or
transaction data. Times are stored as UTC ISO 8601 strings ("YYYY-MM-DDTHH:MM:SS+00:00").
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import config

engine = create_engine(config.ENV_DATABASE_URL)

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS env_zone (
        zone_code TEXT PRIMARY KEY, name TEXT NOT NULL, worktype INTEGER,
        source TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_utc TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS env_device (
        device_id TEXT PRIMARY KEY, zone_code TEXT NOT NULL REFERENCES env_zone(zone_code),
        description TEXT, data_label TEXT NOT NULL DEFAULT 'ACTUAL',
        registered_utc TEXT NOT NULL, last_seen_utc TEXT)""",
    """CREATE TABLE IF NOT EXISTS env_reading (
        id INTEGER PRIMARY KEY AUTOINCREMENT, zone_code TEXT NOT NULL REFERENCES env_zone(zone_code),
        temperature_c REAL, humidity_pct REAL, reading_utc TEXT NOT NULL, received_utc TEXT NOT NULL,
        method TEXT NOT NULL CHECK (method IN ('manual','sensor','synthetic')),
        device_key TEXT NOT NULL DEFAULT '', recorded_by TEXT,
        quality TEXT NOT NULL CHECK (quality IN ('valid','suspect','invalid')), quality_note TEXT,
        data_label TEXT NOT NULL CHECK (data_label IN ('ACTUAL','SYNTHETIC')),
        UNIQUE (zone_code, reading_utc, method, device_key))""",
    "CREATE INDEX IF NOT EXISTS ix_env_reading_zone_time ON env_reading (zone_code, reading_utc)",
    """CREATE TABLE IF NOT EXISTS env_site_note (
        topic TEXT PRIMARY KEY, text TEXT NOT NULL, updated_utc TEXT NOT NULL, updated_by TEXT)""",
]


def utc_text(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def init_env(worktype_names: dict | None = None) -> None:
    """Create tables; register the verified M123 work types as zones (never invented zones)."""
    with engine.begin() as connection:
        for statement in SCHEMA:
            connection.execute(text(statement))
        for wt, name in sorted((worktype_names or {}).items()):
            connection.execute(text(
                "INSERT OR IGNORE INTO env_zone (zone_code, name, worktype, source, active, created_utc) "
                "VALUES (:code, :name, :wt, 'M123 work type', 1, :now)"),
                dict(code=f"WT{int(wt)}", name=f"WT {int(wt)} {name}", wt=int(wt), now=utc_text(now_utc())))


def _rows(sql, **params):
    with engine.connect() as connection:
        return [dict(r._mapping) for r in connection.execute(text(sql), params)]


def zones(active_only=True):
    return _rows("SELECT * FROM env_zone" + (" WHERE active = 1" if active_only else "") +
                 " ORDER BY worktype IS NULL, worktype, zone_code")


def add_zone(code: str, name: str, worktype=None) -> None:
    with engine.begin() as connection:
        try:
            connection.execute(text(
                "INSERT INTO env_zone (zone_code, name, worktype, source, active, created_utc) "
                "VALUES (:code, :name, :wt, 'user added', 1, :now)"),
                dict(code=code, name=name, wt=worktype, now=utc_text(now_utc())))
        except IntegrityError as error:
            raise ValueError(f'Zone code {code} already exists.') from error


def devices():
    return _rows("SELECT * FROM env_device ORDER BY device_id")


def device(device_id: str):
    found = _rows("SELECT * FROM env_device WHERE device_id = :d", d=device_id)
    return found[0] if found else None


def register_device(device_id: str, zone_code: str, description: str = '', data_label: str = 'ACTUAL') -> None:
    with engine.begin() as connection:
        try:
            connection.execute(text(
                "INSERT INTO env_device (device_id, zone_code, description, data_label, registered_utc) "
                "VALUES (:d, :z, :desc, :label, :now)"),
                dict(d=device_id, z=zone_code, desc=description, label=data_label, now=utc_text(now_utc())))
        except IntegrityError as error:
            raise ValueError(f'Device {device_id} is already registered.') from error


def touch_device(device_id: str, seen_utc: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE env_device SET last_seen_utc = :t WHERE device_id = :d "
            "AND (last_seen_utc IS NULL OR last_seen_utc < :t)"), dict(t=seen_utc, d=device_id))


def insert_reading(row: dict) -> str:
    """Store one reading; returns 'stored' or 'duplicate' (same zone, time, method and device)."""
    with engine.begin() as connection:
        try:
            connection.execute(text(
                "INSERT INTO env_reading (zone_code, temperature_c, humidity_pct, reading_utc, received_utc, "
                "method, device_key, recorded_by, quality, quality_note, data_label) VALUES "
                "(:zone_code, :temperature_c, :humidity_pct, :reading_utc, :received_utc, :method, "
                ":device_key, :recorded_by, :quality, :quality_note, :data_label)"), row)
        except IntegrityError:
            return 'duplicate'
    return 'stored'


def readings(zone_code=None, until_utc=None, since_utc=None, qualities=None, include_synthetic=True, limit=None,
             device_key=None):
    sql = "SELECT * FROM env_reading WHERE 1=1"
    params = {}
    if device_key:
        sql += " AND device_key = :device"; params['device'] = device_key
    if zone_code:
        sql += " AND zone_code = :zone"; params['zone'] = zone_code
    if until_utc:
        sql += " AND reading_utc <= :until"; params['until'] = until_utc
    if since_utc:
        sql += " AND reading_utc >= :since"; params['since'] = since_utc
    if qualities:
        sql += " AND quality IN (" + ",".join(f"'{q}'" for q in qualities if q in ('valid', 'suspect', 'invalid')) + ")"
    if not include_synthetic:
        sql += " AND data_label = 'ACTUAL'"
    sql += " ORDER BY reading_utc DESC, id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return _rows(sql, **params)


def has_synthetic() -> bool:
    return bool(_rows("SELECT 1 FROM env_reading WHERE data_label = 'SYNTHETIC' LIMIT 1"))


def previous_reading(zone_code: str, before_utc: str, synthetic: bool):
    """Latest non-invalid reading of the zone before a time (same data label family)."""
    label = 'SYNTHETIC' if synthetic else 'ACTUAL'
    found = _rows("SELECT * FROM env_reading WHERE zone_code = :z AND reading_utc < :t AND quality != 'invalid' "
                  "AND data_label = :label ORDER BY reading_utc DESC LIMIT 1", z=zone_code, t=before_utc, label=label)
    return found[0] if found else None


def site_notes() -> dict:
    return {r['topic']: r for r in _rows("SELECT * FROM env_site_note")}


def set_site_note(topic: str, body: str, updated_by: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO env_site_note (topic, text, updated_utc, updated_by) VALUES (:t, :x, :now, :by) "
            "ON CONFLICT(topic) DO UPDATE SET text = excluded.text, updated_utc = excluded.updated_utc, "
            "updated_by = excluded.updated_by"), dict(t=topic, x=body, now=utc_text(now_utc()), by=updated_by))


def delete_synthetic() -> int:
    with engine.begin() as connection:
        removed = connection.execute(text("DELETE FROM env_reading WHERE data_label = 'SYNTHETIC'")).rowcount
        connection.execute(text("DELETE FROM env_device WHERE data_label = 'SYNTHETIC'"))
    return removed
