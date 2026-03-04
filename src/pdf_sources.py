from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

from dateutil import parser as date_parser
import yaml

from .models import CourseConfig, TaskItem


def _load_yaml_items(path: Path, fallback_course: str) -> List[TaskItem]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    course_code = raw.get("course", fallback_course)
    items: List[TaskItem] = []
    for entry in raw.get("items", []):
        raw_date = entry.get("date")
        if isinstance(raw_date, (date, datetime)):
            entry_date = raw_date if isinstance(raw_date, date) else raw_date.date()
        else:
            entry_date = date_parser.parse(str(raw_date)).date()
        items.append(
            TaskItem(
                course=course_code,
                date=entry_date,
                type=entry.get("type", "other"),
                title=entry.get("title", ""),
                description=entry.get("description", ""),
                url=entry.get("url"),
                is_major=bool(entry.get("is_major", False)),
                source=entry.get("source", "pdf"),
            )
        )
    return items


def load_pdf_tasks(root: Path, courses: List[CourseConfig]) -> List[TaskItem]:
    """Load TaskItem entries from YAML schedule files for pdf_syllabus courses."""
    tasks: List[TaskItem] = []
    for cfg in courses:
        if cfg.source != "pdf_syllabus" or not cfg.data_file:
            continue
        data_path = root / cfg.data_file
        tasks.extend(_load_yaml_items(data_path, fallback_course=cfg.code))
    return tasks

