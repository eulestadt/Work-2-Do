"""
Parse any syllabus PDF schedule using Gemini 2.5 Flash—no course-specific regex.
Produces a single list of TaskItems (readings, videos, quizzes, assignments) with no duplicates.
Used to replace regex-based populi_syllabus_importer for syllabus courses.
URLs inlined by Gemini when possible; fallback for nulls: PDF anchor-text match or document order.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dateutil import parser as dateutil_parser

from .models import TaskItem

# Same snippet loading as gemini_schedule_check
from .gemini_schedule_check import load_schedule_snippet_from_txt

GEMINI_SYLLABUS_PROMPT = """You are extracting the course schedule from a syllabus. The text may be from any course (e.g. Bioethics, Doctrines, Discipleship). The schedule may appear as a table (e.g. Tue, Jan 20 ...), as a list of dates (e.g. 1/22/26 ...), or by week/day. Extract every homework item regardless of format. List each distinct item exactly once—no duplicates.

Output valid JSON only. Use this exact shape:
{"items":[{"date":"YYYY-MM-DD","type":"reading"|"video"|"quiz"|"assignment"|"other","title":"short title","description":"full text or null","url":"https://... or null"},...],"links":["url1","url2",...]}

Rules:
- Use 2026 for year. Write every date as YYYY-MM-DD (e.g. Tue, Jan 20 -> 2026-01-20, 1/22/26 -> 2026-01-22).
- type: "reading" for readings/chapters, "video" for videos/watch items, "quiz" for quizzes, "assignment" for assignments/papers; use "other" only if nothing else fits.
- One row per item. **Video items only when the line has a semicolon (;)** separating the reading from the video: e.g. "Ch. 1-2; Video title here" → one reading (Ch. 1-2), one video (Video title here). If there is no semicolon, do NOT create a video—the trailing phrase (e.g. "Religion, Morality, and Meaning") is a lecture topic or description, not a video. So "Faithful Reason, ch. 3-4 Religion, Morality, and Meaning" → one reading only. Exception: when a line has no semicolon but clearly lists two distinct watch/video titles for the same date (e.g. "Intro-ch. 2 The Common Good Has our society lost its vision of what it means to be human?"), output one reading and two video items for that date. Do not duplicate.
- **Inline links:** The syllabus may include a "Links found in this syllabus" section. For each item, set "url" to the exact URL from that section that belongs to this item (match by title, description, or context—e.g. a reading titled "Humanae Vitae" gets the vatican.va link; a video titled "The Common Good" gets the YouTube link for that video). Use only URLs that appear in the syllabus; do not invent links. If you cannot determine which link goes with an item, set "url" to null. In "links" list every URL from that section in document order (for fallback).
- title: brief (e.g. "Biomedicine & Beatitude, ch. 1"). description: longer if needed, or null.
- Only include items from the schedule. No other text."""


def _extract_link_list_fallback(schedule_text: str) -> List[str]:
    """When Gemini does not return links, get URLs from 'Links found in this syllabus' by simple string search (no regex)."""
    lower = schedule_text.lower()
    marker = "links found in this syllabus"
    if marker not in lower:
        return []
    start = lower.index(marker)
    rest = schedule_text[start:]
    return [line.strip() for line in rest.splitlines() if line.strip().startswith("http")]


def _extract_link_anchor_map(schedule_text: str) -> Dict[str, str]:
    """Parse 'Link anchor text (from PDF):' block: lines of url\\tanchor. Returns url -> anchor_text."""
    out: Dict[str, str] = {}
    lower = schedule_text.lower()
    marker = "link anchor text (from pdf)"
    if marker not in lower:
        return out
    start = lower.index(marker)
    rest = schedule_text[start:]
    for line in rest.splitlines()[1:]:
        line = line.strip()
        if "\t" in line and line.startswith("http"):
            url, _, anchor = line.partition("\t")
            url = url.strip()
            anchor = anchor.strip()
            if url:
                out[url] = anchor
    return out


# Items that typically have no link in the syllabus PDF
_SKIP_LINK_TITLES = ("read syllabus", "syllabus", "spring break", "no class", "student presentations")

# Courses where links in the PDF are in schedule order: assign 1st link → 1st linkable item, etc. (doctrines). Others use YouTube→video / other→reading + title match.
_COURSES_SIMPLE_LINK_ORDER = frozenset({"doctrines"})


def _assign_urls_simple_order(tasks: List[TaskItem], link_list: List[str]) -> None:
    """Assign links in document order to tasks in schedule order. Skip items whose title matches _SKIP_LINK_TITLES. Use for courses (e.g. doctrines) where PDF link order matches schedule order."""
    tasks_sorted = sorted(tasks, key=lambda t: (t.date, t.type, t.title))
    link_idx = 0
    for t in tasks_sorted:
        if t.url or not link_list:
            continue
        if link_idx >= len(link_list):
            break
        if t.title and any(skip in t.title.strip().lower() for skip in _SKIP_LINK_TITLES):
            continue
        t.url = link_list[link_idx]
        link_idx += 1


def _normalize_for_match(s: str) -> str:
    """Lowercase, collapse spaces, remove punctuation for fuzzy title match (no regex)."""
    if not s:
        return ""
    out = "".join(c if c.isalnum() or c.isspace() else " " for c in s.lower())
    return " ".join(out.split())


def _title_match_score(task_title: str, task_desc: str, link_title: str) -> int:
    """Higher = better match. 0 = no match."""
    if not link_title:
        return 0
    a = _normalize_for_match(task_title) or _normalize_for_match(task_desc)
    b = _normalize_for_match(link_title)
    if not a or not b:
        return 0
    if a == b:
        return 3
    if a in b or b in a:
        return 2
    # Word overlap: significant word from task appears in link title
    words = [w for w in a.split() if len(w) >= 4]
    if any(w in b for w in words):
        return 1
    return 0


def _assign_urls_by_title_match(
    tasks: List[TaskItem],
    link_list: List[str],
    link_anchor_map: Optional[Dict[str, str]] = None,
) -> None:
    """Assign links using PDF anchor text only (no oEmbed). YouTube → video by anchor match; other → reading. Fall back to order-based for any remaining."""
    anchor_map = link_anchor_map or {}
    youtube_pool = [u for u in link_list if "youtu" in u.lower()]
    other_pool = [u for u in link_list if "youtu" not in u.lower()]

    tasks_sorted = sorted(tasks, key=lambda t: (t.date, t.type, t.title))
    # First pass: assign by anchor match (video → YouTube using PDF anchor text only)
    for t in tasks_sorted:
        if t.url:
            continue
        if t.type == "video" and youtube_pool:
            best_idx = -1
            best_score = 0
            for i, url in enumerate(youtube_pool):
                anchor = anchor_map.get(url, "") or ""
                score = _title_match_score(t.title, t.description or "", anchor)
                if score > best_score:
                    best_score = score
                    best_idx = i
            if best_idx >= 0:
                t.url = youtube_pool[best_idx]
                youtube_pool.pop(best_idx)
        elif t.type in ("reading", "other") and other_pool and not any(
            skip in (t.title or "").lower() for skip in _SKIP_LINK_TITLES
        ):
            best_idx = -1
            best_score = 0
            for i, url in enumerate(other_pool):
                anchor = anchor_map.get(url, "") or ""
                score = _title_match_score(t.title, t.description or "", anchor)
                if score > best_score:
                    best_score = score
                    best_idx = i
            if best_idx >= 0:
                t.url = other_pool[best_idx]
                other_pool.pop(best_idx)

    # Second pass: assign remaining links in order (fallback)
    remaining_yt = list(youtube_pool)
    remaining_other = list(other_pool)
    yi, oi = 0, 0
    for t in tasks_sorted:
        if t.url:
            continue
        if t.type == "video" and yi < len(remaining_yt):
            t.url = remaining_yt[yi]
            yi += 1
        elif t.type in ("reading", "other") and oi < len(remaining_other):
            if t.title and any(skip in t.title.strip().lower() for skip in _SKIP_LINK_TITLES):
                continue
            t.url = remaining_other[oi]
            oi += 1


def _parse_date(s: str, default_year: int) -> Optional[date]:
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


def parse_syllabus_to_tasks(
    schedule_text: str,
    course_code: str,
    default_year: int,
    api_key: Optional[str] = None,
) -> List[TaskItem]:
    """
    Call Gemini 2.5 Flash to extract the full schedule as TaskItems.
    Works for any syllabus (Bioethics, Doctrines, Discipleship, etc.). No regex.
    Returns empty list if no API key or on error.
    """
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
            contents=f"{GEMINI_SYLLABUS_PROMPT}\n\n---\n\n{schedule_text}",
        )
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            idx = raw.find("\n")
            raw = raw[idx + 1 :].strip() if idx >= 0 else raw[3:].strip()
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3].strip()
        data = json.loads(raw)
        if isinstance(data, list):
            items_data = data
            link_list = _extract_link_list_fallback(schedule_text)
        elif isinstance(data, dict) and "items" in data:
            items_data = data["items"]
            if not isinstance(items_data, list):
                return []
            link_list = data.get("links")
            if not isinstance(link_list, list):
                link_list = _extract_link_list_fallback(schedule_text)
        else:
            return []
        tasks: List[TaskItem] = []
        for x in items_data:
            if not isinstance(x, dict) or not x.get("date"):
                continue
            d = _parse_date(str(x.get("date", "")), default_year)
            if not d:
                continue
            item_type = (x.get("type") or "reading").lower()
            if item_type not in ("reading", "video", "quiz", "assignment", "other"):
                item_type = "reading"
            title = (x.get("title") or "").strip() or "Syllabus item"
            desc = x.get("description")
            if desc is not None:
                desc = str(desc).strip()
            else:
                desc = title
            url = x.get("url")
            if url is not None:
                url = str(url).strip() or None
            tasks.append(
                TaskItem(
                    course=course_code,
                    date=d,
                    type=item_type,
                    title=title[:120] if len(title) > 120 else title,
                    description=desc[:500] if desc and len(desc) > 500 else (desc or ""),
                    url=url,
                    is_major=False,
                    source="gemini_syllabus",
                )
            )
        # Fill any remaining null urls: use only links not already assigned by Gemini
        used_urls = {t.url for t in tasks if t.url}
        remaining_links = [u for u in link_list if u not in used_urls]
        link_anchor_map = _extract_link_anchor_map(schedule_text)
        if remaining_links:
            if course_code in _COURSES_SIMPLE_LINK_ORDER:
                _assign_urls_simple_order(tasks, remaining_links)
            else:
                _assign_urls_by_title_match(tasks, remaining_links, link_anchor_map)
        return tasks
    except Exception:
        return []
