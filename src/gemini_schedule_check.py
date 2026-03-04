"""
Use Gemini 2.5 Flash to extract schedule (readings, videos, URLs) from syllabus text.
Minimal prompt and token use. Run on .txt schedule snippet; merge results into regex output.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, List, Optional

from dateutil import parser as dateutil_parser

from .models import TaskItem

SCHEDULE_START_RE = re.compile(r"Course\s+Schedule\s*[:\s]*(.*)", re.IGNORECASE | re.DOTALL)
SCHEDULE_STOP_RE = re.compile(
    r"\b(Extra credit|Assignments and Measurement|Assignments and Rubrics|How to Succeed)\b",
    re.IGNORECASE,
)
MAX_SNIPPET_CHARS = 6000

GEMINI_SCHEDULE_PROMPT = """From this syllabus schedule extract each class date's homework.
Output a JSON array only. Each element: {"date":"YYYY-MM-DD","reading":"text","video":"text or null","url":"url or null"}.
Use 2026 for year. Write every date as YYYY-MM-DD (e.g. Tue, Jan 20 -> 2026-01-20).
When a line has a semicolon (e.g. "Ch. 1; Video title here"), put the part before ; in "reading" and the part after ; in "video".
If the schedule text contains an http or https URL on the same line as a reading/video, put it in "url". If there is a "Links found in this syllabus" section below the schedule, use those URLs: match each link to the video or reading it belongs to (by title or context) and put the correct URL in the "url" field for that date's item. Only use URLs from the syllabus; do not invent links. No other text."""


def extract_schedule_snippet(full_text: str) -> str:
    """Return just the Course Schedule section for minimal tokens."""
    m = SCHEDULE_START_RE.search(full_text)
    if not m:
        return ""
    rest = m.group(1).strip()
    stop = SCHEDULE_STOP_RE.search(rest)
    if stop:
        rest = rest[: stop.start()].strip()
    return rest[:MAX_SNIPPET_CHARS].strip()


def load_schedule_snippet_from_txt(txt_path: Path) -> str:
    """Load schedule snippet from pre-extracted _schedule.txt (or extract from full .txt)."""
    text = txt_path.read_text(encoding="utf-8")
    if "_schedule.txt" in str(txt_path):
        return text
    return extract_schedule_snippet(text.replace("\n", " "))


def ask_gemini_for_schedule(
    schedule_text: str,
    course_code: str,
    default_year: int,
    api_key: Optional[str] = None,
) -> List[dict[str, Any]]:
    """Call Gemini 2.5 Flash; return list of {date, reading, video, url}. Empty if no key or error."""
    if not schedule_text.strip():
        return []
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return []
    try:
        from google import genai
    except ImportError:
        return []
    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{GEMINI_SCHEDULE_PROMPT}\n\n---\n\n{schedule_text}",
        )
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            idx = raw.find("\n")
            raw = raw[idx + 1 :].strip() if idx >= 0 else raw[3:].strip()
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3].strip()
        arr = json.loads(raw)
        if not isinstance(arr, list):
            return []
        return [x for x in arr if isinstance(x, dict) and x.get("date")]
    except Exception:
        return []


def _parse_gemini_date(s: str, default_year: int) -> Optional[date]:
    """Parse YYYY-MM-DD or flexible date string (e.g. Feb 24, Tue Jan 20)."""
    if not s:
        return None
    s = str(s).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-" and s[:4].isdigit() and s[5:7].isdigit() and s[8:10].isdigit():
        try:
            return date(int(s[:4]), int(s[5:7]), int(s[8:10]))
        except (ValueError, IndexError):
            pass
    try:
        parsed = dateutil_parser.parse(s, default=date(default_year, 1, 1))
        return parsed.date()
    except (ValueError, TypeError):
        return None


def merge_gemini_into_tasks(
    tasks: List[TaskItem],
    gemini_list: List[dict],
    course_code: str,
    default_year: int,
) -> List[TaskItem]:
    """Add video items and URLs from Gemini where regex missed them. Preserves existing tasks."""
    by_date: dict[date, List[int]] = {}  # date -> indices in tasks
    for idx, t in enumerate(tasks):
        by_date.setdefault(t.date, []).append(idx)
    result = list(tasks)
    for g in gemini_list:
        d = _parse_gemini_date(str(g.get("date", "")), default_year)
        if not d:
            continue
        video_title = g.get("video") if g.get("video") else None
        url = g.get("url") if g.get("url") else None
        indices = by_date.get(d, [])
        existing_tasks = [result[i] for i in indices]
        has_video = any(t.type == "video" for t in existing_tasks)
        if video_title and not has_video:
            result.append(
                TaskItem(
                    course=course_code,
                    date=d,
                    type="video",
                    title=video_title[:120] if len(video_title) > 120 else video_title,
                    description=video_title,
                    url=url,
                    source="gemini_schedule",
                )
            )
        elif url and indices:
            for i in indices:
                t = result[i]
                if not t.url and t.type == "reading":
                    result[i] = TaskItem(
                        course=t.course,
                        date=t.date,
                        type=t.type,
                        title=t.title,
                        description=t.description,
                        url=url,
                        is_major=t.is_major,
                        source=t.source,
                    )
                    break
    return result
