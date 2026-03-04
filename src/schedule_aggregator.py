from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Iterable, List, Tuple

from .models import TaskItem


def _meeting_weekdays(meeting_pattern: str) -> List[int]:
    pattern = meeting_pattern.strip()
    if pattern == "MWF":
        return [0, 2, 4]
    if pattern == "TTh":
        return [1, 3]
    if pattern == "M":
        return [0]
    if pattern == "T":
        return [1]
    if pattern == "W":
        return [2]
    if pattern == "Th":
        return [3]
    if pattern == "F":
        return [4]
    if pattern == "daily":
        return [0, 1, 2, 3, 4, 5, 6]
    return []


def _next_meetings(today: date, meeting_pattern: str, count: int = 2) -> List[date]:
    """Next `count` meeting dates on or after today."""
    weekdays = _meeting_weekdays(meeting_pattern)
    if not weekdays:
        return [today + timedelta(days=i) for i in range(count)]

    out: List[date] = []
    d = today
    while len(out) < count:
        if d.weekday() in weekdays:
            out.append(d)
        d = d + timedelta(days=1)
    return out


def _prev_meeting(today: date, meeting_pattern: str, count: int = 1) -> List[date]:
    """Up to `count` most recent meeting dates strictly before today (so you see last class)."""
    weekdays = _meeting_weekdays(meeting_pattern)
    if not weekdays:
        return [today - timedelta(days=1)] if count else []

    out: List[date] = []
    d = today - timedelta(days=1)  # start before today so "previous" = last class, not today
    while d >= today - timedelta(days=14) and len(out) < count:
        if d.weekday() in weekdays:
            out.append(d)
        d = d - timedelta(days=1)
    return out


DIGEST_WINDOW_DAYS = 5  # Include today ± this many days in the digest


def aggregate_schedule(
    today: date,
    tasks: List[TaskItem],
    meeting_patterns: Dict[str, str],
    major_horizon_days: int = 21,
    digest_window_days: int = DIGEST_WINDOW_DAYS,
) -> Tuple[Dict[str, List[date]], Dict[str, Dict[date, List[TaskItem]]], List[TaskItem]]:
    """
    Compute a ±N-day window per course and aggregate tasks.

    For each course, the digest includes all dates from (today - digest_window_days)
    through (today + digest_window_days), so you see tasks due in the past and
    upcoming days.

    Returns:
        (per_course_dates, per_course_items, major_items)

        - per_course_dates: dict[course_code] -> List[date] (sorted).
        - per_course_items: dict[course_code][date] -> List[TaskItem] for those dates.
        - major_items: list of TaskItem flagged as major within the given horizon.
    """
    start = today - timedelta(days=digest_window_days)
    end = today + timedelta(days=digest_window_days)
    window_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    course_codes = sorted({t.course for t in tasks} | set(meeting_patterns.keys()))
    per_course_dates: Dict[str, List[date]] = {code: list(window_dates) for code in course_codes}

    per_course: Dict[str, Dict[date, List[TaskItem]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for t in tasks:
        if t.date in per_course_dates.get(t.course, []):
            per_course[t.course][t.date].append(t)

    horizon_end = today + timedelta(days=major_horizon_days)
    major_items: List[TaskItem] = [
        t for t in tasks if t.is_major and today <= t.date <= horizon_end
    ]

    return per_course_dates, per_course, major_items

