"""Shared ready-time colour bands (v12: used by the chart and the temporary-operator planner).

    green   ready <= safety buffer deadline            (pick cutoff - safety buffer)
    yellow  safety buffer deadline < ready <= pick cutoff (departure - loading time)
    red     ready > pick cutoff
    unknown no measurable ready time (a required work type has no pick rate)
"""
from __future__ import annotations

from calculations.excel_io import serial_to_datetime
from calculations.truck import le

BANDS = {
    'green': dict(label='On time', meaning='Ready by the safety buffer deadline'),
    'yellow': dict(label='At risk', meaning='Meets the pick cutoff but not the safety buffer'),
    'red': dict(label='Pick cutoff passed', meaning='Misses the pick cutoff'),
    'unknown': dict(label='Unknown', meaning='No pick rate for a required work type; ready time cannot be estimated'),
}
COLORS = {'green': '#0ca30c', 'yellow': '#fab219', 'red': '#d03b3b', 'unknown': '#98a2b3', 'etc': '#2563eb'}


def band(ready, buffer_deadline, cutoff) -> str:
    """Green / yellow / red / unknown classification of a projected ready time."""
    if ready is None:
        return 'unknown'
    if le(ready, buffer_deadline):
        return 'green'
    if le(ready, cutoff):
        return 'yellow'
    return 'red'


def clock(serial) -> str | None:
    return serial_to_datetime(serial).strftime('%H:%M') if serial is not None else None


def iso(serial) -> str | None:
    return serial_to_datetime(serial).isoformat(timespec='seconds') if serial is not None else None
