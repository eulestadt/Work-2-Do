from __future__ import annotations

import re
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pypdf import PdfReader

from ..models import TaskItem


WEEK_RE = re.compile(r"\bWeek\s+(\d+)\b", re.IGNORECASE)
DAY_RE = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday)\b[:\s-]*", re.IGNORECASE
)
MMDD_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")

# Course Schedule table: "1 Tue, Jan 20 Read syllabus" or "Tue, Jan 22 Words of Life, chaps. 1-3"
SCHEDULE_TABLE_DAY_RE = re.compile(
    r"^(?:\d+\s+)?(Tue|Thu),\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\s*,?\s*(.*)$",
    re.IGNORECASE,
)
MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Discipleship-style: "Course Schedule:" then "1/22/26 Meet with Journey Groups 1/29/26 ..."
DATE_IN_SCHEDULE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")


def _meeting_offsets(meeting_pattern: str) -> List[int]:
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


def _day_offset(day_name: str) -> Optional[int]:
    day = day_name.strip().lower()
    mapping = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
    }
    return mapping.get(day)


def _week_start(term_start: date, week_num: int) -> date:
    # Assumes term_start is the Monday of Week 1.
    return term_start + timedelta(days=(week_num - 1) * 7)


def _extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    parts: List[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        parts.append(txt)
    return "\n".join(parts)


def _normalize_lines(text: str) -> List[str]:
    lines = []
    for raw in text.splitlines():
        s = " ".join(raw.strip().split())
        if s:
            lines.append(s)
    return lines


def _parse_course_schedule_table(
    lines: List[str],
    course_code: str,
    default_year: int,
) -> List[TaskItem]:
    """
    Parse "Course Schedule:" table: one reading task per date line.
    Used by Bioethics and Doctrines (TTh). Videos/URLs are added later by enrich_schedules_with_videos.
    """
    start = 0
    for idx, ln in enumerate(lines):
        if "course schedule" in ln.lower() and ":" in ln.lower():
            start = idx + 1
            break
    end = min(start + 120, len(lines))
    for idx in range(start, min(start + 200, len(lines))):
        ln = lines[idx]
        if re.match(r"^(Extra credit|Assignments and Measurement|Assignments and Rubrics)\b", ln, re.IGNORECASE):
            end = idx
            break
    work = lines[start:end]

    items: List[TaskItem] = []
    for line in work:
        m = SCHEDULE_TABLE_DAY_RE.match(line.strip())
        if not m:
            continue
        _day_name, month_name, day_num, rest = m.groups()
        month = MONTH_NAMES.get(month_name.lower()[:3])
        if month is None:
            continue
        try:
            d = date(default_year, month, int(day_num))
        except (ValueError, TypeError):
            continue
        title = rest.strip().rstrip(";")
        if not title or title.lower() in ("read syllabus", "read the syllabus"):
            title = "Syllabus / intro"
        if re.match(r"^(no class|extra credit)\s*$", title, re.IGNORECASE):
            break
        short = title if len(title) <= 120 else title[:117] + "..."
        items.append(
            TaskItem(
                course=course_code,
                date=d,
                type="reading",
                title=short,
                description=title,
                url=None,
                source="populi_pdf",
            )
        )
    return items


def _parse_date_list_schedule(
    text: str,
    course_code: str,
    default_year: int,
) -> List[TaskItem]:
    """
    Parse schedule that is a block of dates and text, e.g. Discipleship:
    "Course Schedule: ... 1/22/26 Meet with Journey Groups 1/29/26 Classroom Seminar ..."
    Splits on each M/D/YY or M/DD/YYYY and assigns the text until the next date to that date.
    """
    items: List[TaskItem] = []
    m_start = re.search(r"course\s+schedule", text, re.IGNORECASE)
    if not m_start:
        return items
    start = m_start.start()
    section = text[start:]
    lower = section.lower()
    # Stop at assignments/rubrics section so we don't pick up random dates
    for stop_marker in ("assignments and measurement", "assignments and rubrics", "see the \"assignments\"", "see the 'assignments'"):
        idx = lower.find(stop_marker)
        if idx != -1:
            section = section[:idx]
            break
    # Find all date matches (start, end, (mm, dd, yy))
    matches = []
    for m in DATE_IN_SCHEDULE_RE.finditer(section):
        mm, dd, yy = m.group(1), m.group(2), m.group(3)
        try:
            month = int(mm)
            day = int(dd)
            year = int(yy)
            if year < 100:
                year += 2000
            if 1 <= month <= 12 and 1 <= day <= 31 and 2020 <= year <= 2030:
                d = date(year, month, day)
                matches.append((m.start(), m.end(), d, m.group(0)))
        except (ValueError, TypeError):
            continue
    if not matches:
        return items
    # Sort by position in text (then by date for same position, though that shouldn't happen)
    matches.sort(key=lambda x: (x[0], x[2]))
    # Dedupe by date (keep first occurrence)
    seen: set = set()
    unique_matches = []
    for start_pos, end_pos, d, _ in matches:
        if d in seen:
            continue
        seen.add(d)
        unique_matches.append((start_pos, end_pos, d))
    for i, (start_pos, end_pos, d) in enumerate(unique_matches):
        next_start = unique_matches[i + 1][0] if i + 1 < len(unique_matches) else len(section)
        content = section[end_pos:next_start]
        content = " ".join(content.split()).strip()
        if not content:
            content = "See syllabus"
        title = content if len(content) <= 100 else content[:97] + "..."
        items.append(
            TaskItem(
                course=course_code,
                date=d,
                type="reading",
                title=title,
                description=content,
                source="populi_pdf",
            )
        )
    return items


def _parse_by_week_and_day(
    lines: List[str],
    course_code: str,
    meeting_pattern: str,
    term_start: date,
    default_year: int,
) -> List[TaskItem]:
    items: List[TaskItem] = []
    current_week: Optional[int] = None
    current_day: Optional[str] = None
    buffer: List[str] = []

    def flush():
        nonlocal buffer, current_week, current_day
        if current_week and current_day and buffer:
            offset = _day_offset(current_day)
            if offset is not None:
                d = _week_start(term_start, current_week) + timedelta(days=offset)
                items.append(
                    TaskItem(
                        course=course_code,
                        date=d,
                        type="reading",
                        title=f"Week {current_week} – {current_day.title()}",
                        description=" ".join(buffer),
                        source="populi_pdf",
                    )
                )
        buffer = []

    for line in lines:
        m_week = WEEK_RE.search(line)
        if m_week:
            flush()
            current_week = int(m_week.group(1))
            current_day = None
            continue

        m_day = DAY_RE.match(line)
        if m_day:
            flush()
            current_day = m_day.group(1).lower()
            remainder = DAY_RE.sub("", line).strip()
            if remainder:
                buffer.append(remainder)
            continue

        # If the syllabus uses explicit dates like 2/26 instead of day headings,
        # capture them as standalone dated entries.
        m_mmdd = MMDD_RE.search(line)
        if m_mmdd and (current_day is None):
            mm = int(m_mmdd.group(1))
            dd = int(m_mmdd.group(2))
            yy = m_mmdd.group(3)
            year = default_year
            if yy:
                year = int(yy) if len(yy) == 4 else int("20" + yy)
            try:
                d = date(year, mm, dd)
                items.append(
                    TaskItem(
                        course=course_code,
                        date=d,
                        type="reading",
                        title="Syllabus item",
                        description=line,
                        source="populi_pdf",
                    )
                )
                continue
            except Exception:
                pass

        # Otherwise treat as content under the current section.
        if current_week and current_day:
            buffer.append(line)

    flush()

    return items


def import_populi_syllabus_pdf_to_yaml(
    pdf_path: Path,
    out_yaml_path: Path,
    course_code: str,
    meeting_pattern: str,
    term_start: date,
    default_year: int,
    text_override: str | None = None,
) -> List[TaskItem]:
    """
    Downloaded Populi syllabus PDF -> parse -> write YAML -> return TaskItems.
    If text_override is provided, use it instead of reading the PDF (fast path).
    """
    import sys
    if text_override is not None:
        text = text_override
        if sys.stderr.isatty():
            print("  Using pre-extracted text...", flush=True)
    else:
        if sys.stderr.isatty():
            print("  Loading PDF...", flush=True)
        text = _extract_text(pdf_path)
    lines = _normalize_lines(text)
    if sys.stderr.isatty():
        print("  Parsing schedule...", flush=True)
    # Try "Course Schedule" table format first (Bioethics, Doctrines: "Tue, Jan 20 ...")
    tasks = _parse_course_schedule_table(lines, course_code, default_year)
    if not tasks:
        # Try date-list format (Discipleship: "1/22/26 Meet with Journey Groups 1/29/26 ...")
        tasks = _parse_date_list_schedule(text, course_code, default_year)
    if not tasks:
        tasks = _parse_by_week_and_day(
            lines, course_code, meeting_pattern, term_start, default_year
        )

    out_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "course": course_code,
        "source_pdf": str(pdf_path),
        "items": [
            {
                "date": t.date.isoformat(),
                "type": t.type,
                "title": t.title,
                "description": t.description,
                "url": t.url,
                "is_major": t.is_major,
                "source": t.source,
            }
            for t in tasks
        ],
    }
    out_yaml_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return tasks

