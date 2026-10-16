"""Confirmed point *weights* with cautious eligibility rules.

The customer has confirmed four weights, but not who gets the points, who
confirms defects, the rounding of fractional minutes, or the authoritative
standard times. Consequently this module can calculate verified WO-level
quality points and preview time deltas, but never guesses an employee's score.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation

POINTS = {
    'NO_REWORK_WO': 3,
    'ORIGIN_CAUGHT_FIXED_WO': 2,
    'DOWNSTREAM_CONFIRMED_DEFECT': -4,
    'TIME_DIFFERENCE_PER_MINUTE': 1,
}


def time_variance_preview(actual_minutes, target_minutes):
    """Return an *unrounded*, provisional signed difference in points.

    The sign shown here uses time saved = positive; the customer has not yet
    confirmed precise scoring polarity or integer minute rounding. This value
    is never inserted in a persisted points ledger or worker ranking.
    """
    try:
        actual = Decimal(str(actual_minutes))
        target = Decimal(str(target_minutes))
    except (ValueError, InvalidOperation):
        raise ValueError('Target and actual minutes must be numeric.') from None
    if not actual.is_finite() or not target.is_finite() or actual < 0 or target <= 0:
        raise ValueError('Durations must be finite; target must be positive.')
    return target - actual


def work_order_score(*, completed: bool, rework_count: int,
                     origin_fixed_confirmed: bool, downstream_confirmed: int):
    """Compute only verifiable *WO-level* quality points.

    Source: user-confirmed rule table. +3 is conditional on the entire WO being
    completed without rework. +2 is capped once per WO. -4 is per confirmed
    downstream defect. Reports still awaiting review are not confirmations.
    Does not assign blame to a named worker.
    """
    if rework_count < 0 or downstream_confirmed < 0:
        raise ValueError('Counts cannot be negative.')
    breakdown = {
        'no_rework': POINTS['NO_REWORK_WO'] if completed and rework_count == 0 else 0,
        'origin_fixed': POINTS['ORIGIN_CAUGHT_FIXED_WO'] if origin_fixed_confirmed else 0,
        'downstream': POINTS['DOWNSTREAM_CONFIRMED_DEFECT'] * downstream_confirmed,
    }
    return {'total': sum(breakdown.values()), 'breakdown': breakdown,
            'time_points': None, 'worker_allocation': None}
