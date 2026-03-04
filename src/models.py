from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class TaskItem:
    course: str
    date: date
    type: str  # reading, quiz, lecture, lab, homework, exam, report, project, other
    title: str
    description: str = ""
    url: Optional[str] = None
    is_major: bool = False
    source: str = "pdf"  # pdf, populi, manual


@dataclass
class CourseConfig:
    code: str
    name: str
    source: str  # populi_page, pdf_syllabus, manual
    meeting_pattern: str  # e.g. MWF, TTh, W, daily
    data_file: Optional[str] = None
    requires_manual_check: bool = False

