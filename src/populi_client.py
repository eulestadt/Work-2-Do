from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
from typing import List

from dateutil import parser as date_parser

from .models import CourseConfig, TaskItem


POPULI_CACHE_FILE = "data/populi_cache.json"


def fetch_populi_if_enabled(root: Path, config_path: Path, ref_date: date) -> None:
    """
    Run the local Populi scraper (if available) to refresh the cache file.

    This is intended to be run on your own machine with network access and a
    proper Playwright install. It expects Populi credentials to be supplied via
    environment variables:

      - POPULI_USERNAME
      - POPULI_PASSWORD

    If scraping fails for any reason, the function prints a short message and
    leaves the existing cache untouched.
    """
    try:
        from .populi_scraper import scrape_populi_courses
    except Exception as exc:  # pragma: no cover
        print(
            "Populi scraping is not available (Playwright or scraper module missing). "
            f"Details: {exc}"
        )
        return

    try:
        tasks = scrape_populi_courses(root, config_path, ref_date)
    except Exception as exc:  # pragma: no cover
        print(f"Populi scraping failed: {exc}")
        return

    if not tasks:
        print("Populi scraping produced no tasks; cache not updated.")
        return

    dump_tasks_to_cache(root, tasks)
    print(f"Wrote {len(tasks)} Populi-derived task(s) to {POPULI_CACHE_FILE}.")


def _task_from_dict(data: dict) -> TaskItem:
    return TaskItem(
        course=data["course"],
        date=date_parser.parse(data["date"]).date()
        if isinstance(data.get("date"), str)
        else data.get("date"),
        type=data.get("type", "other"),
        title=data.get("title", ""),
        description=data.get("description", ""),
        url=data.get("url"),
        is_major=bool(data.get("is_major", False)),
        source=data.get("source", "populi"),
    )


def load_populi_tasks(root: Path, courses: List[CourseConfig]) -> List[TaskItem]:
    """
    Load TaskItem entries from a JSON cache file produced by a Populi scraper.

    Expected JSON format (list of objects):
      [
        {
          "course": "bioethics",
          "date": "2026-02-26",
          "type": "reading",
          "title": "Bioethics reading title",
          "description": "Short description",
          "url": "https://…",
          "is_major": false,
          "source": "populi"
        },
        ...
      ]
    """
    cache_path = root / POPULI_CACHE_FILE
    if not cache_path.exists():
        return []
    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    tasks: List[TaskItem] = []
    for entry in raw:
        try:
            tasks.append(_task_from_dict(entry))
        except Exception:
            continue
    return tasks


def dump_tasks_to_cache(root: Path, tasks: List[TaskItem]) -> None:
    """Utility to serialize TaskItem objects into the Populi cache JSON format."""
    cache_path = root / POPULI_CACHE_FILE
    serializable = []
    for t in tasks:
        obj = asdict(t)
        obj["date"] = t.date.isoformat()
        serializable.append(obj)
    cache_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

