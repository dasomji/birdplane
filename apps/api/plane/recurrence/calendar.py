"""Calendar intervals preserve the anchor day and local wall time.

Month ends clamp to the last day, without drifting subsequent months.
DST gaps move forward by the gap; repeated times use the first occurrence.
"""

from calendar import monthrange
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo


def occurrence(schedule, index):
    zone = ZoneInfo(schedule.timezone)
    anchor = schedule.starts_at.astimezone(zone).replace(tzinfo=None)
    step = index * schedule.interval
    if schedule.frequency in ("daily", "weekly"):
        local = anchor + timedelta(days=step * (7 if schedule.frequency == "weekly" else 1))
    else:
        months = anchor.year * 12 + anchor.month - 1 + step * (12 if schedule.frequency == "yearly" else 1)
        year, month = divmod(months, 12)
        local = anchor.replace(year=year, month=month + 1, day=min(anchor.day, monthrange(year, month + 1)[1]))
    return local.replace(tzinfo=zone, fold=0).astimezone(timezone.utc)


def latest_index(schedule, at):
    """Binary search avoids unbounded work after long outages."""
    if at < occurrence(schedule, 0):
        return -1
    lo, hi = 0, 1
    while True:
        try:
            later = occurrence(schedule, hi) > at
        except (OverflowError, ValueError):
            later = True
        if later:
            break
        lo, hi = hi, hi * 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        try:
            later = occurrence(schedule, mid) > at
        except (OverflowError, ValueError):
            later = True
        if later:
            hi = mid
        else:
            lo = mid
    return lo
