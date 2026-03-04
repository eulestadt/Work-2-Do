from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple

from dateutil import parser as date_parser
import yaml

from .models import TaskItem, CourseConfig
from .schedule_aggregator import aggregate_schedule
from .pdf_sources import load_pdf_tasks, _load_yaml_items


ROOT = Path(__file__).resolve().parents[1]


def load_course_configs() -> List[CourseConfig]:
    config_path = ROOT / "config" / "courses.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    courses: List[CourseConfig] = []
    for c in raw.get("courses", []):
        courses.append(
            CourseConfig(
                code=c["code"],
                name=c["name"],
                source=c["source"],
                meeting_pattern=c["meeting_pattern"],
                data_file=c.get("data_file"),
                requires_manual_check=bool(c.get("requires_manual_check", False)),
            )
        )
    return courses


def parse_date(value: str | None) -> date:
    if not value:
        ref_from_env = os.environ.get("REFERENCE_DATE")
        if ref_from_env:
            try:
                return date.fromisoformat(ref_from_env.strip())
            except (ValueError, TypeError):
                pass
        return date.today()
    return date_parser.parse(value).date()


def format_markdown(
    today: date,
    per_course_dates: dict,
    per_course_items: dict,
    major_items: List[TaskItem],
    code_to_name: dict[str, str] | None = None,
) -> str:
    lines: List[str] = []
    name_for = code_to_name or {}

    lines.append(f"## Homework & Readings Digest for {today.isoformat()}")
    lines.append("")
    lines.append(
        "Per course: tasks from 5 days ago through 5 days ahead (±5 days)."
    )
    lines.append("")

    # Ensure Stott appears last
    course_codes = sorted(per_course_items.keys(), key=lambda c: (c != "stott", c))

    for code in course_codes:
        items_by_date = per_course_items[code]
        if not any(items_by_date.values()):
            continue
        dates = per_course_dates.get(code, [])
        prev_dates = [d for d in dates if d < today]
        next_dates = [d for d in dates if d >= today]
        display_name = name_for.get(code, code)
        lines.append(f"### {display_name}")
        lines.append("")
        if prev_dates:
            lines.append(
                f"**Previous class meeting(s)**: {', '.join(d.isoformat() for d in prev_dates)}"
            )
        lines.append(
            f"**Next class meeting(s)**: {', '.join(d.isoformat() for d in next_dates)}"
        )
        lines.append("")
        for d in dates:
            day_items: List[TaskItem] = items_by_date.get(d, [])
            day_items = [it for it in day_items if it.type != "resource"]
            if not day_items:
                continue
            lines.append(f"- **{d.isoformat()}**")
            for item in day_items:
                prefix = f"  - **{item.type.capitalize()}**: {item.title}"
                if item.description and item.description != item.title:
                    prefix += f" — {item.description}"
                if item.url:
                    prefix += f" [Watch]({item.url})"
                lines.append(prefix)
        lines.append("")

    # Major items grouped by course
    lines.append("### Upcoming larger items (next 2–3 weeks)")
    lines.append("")
    if not major_items:
        lines.append("- **None detected** in the configured data files.")
    else:
        for item in sorted(major_items, key=lambda t: (t.date, t.course)):
            display_name = name_for.get(item.course, item.course)
            line = f"- **{item.date.isoformat()} – {display_name}**: {item.title} ({item.type})"
            if item.url:
                line += f" [Link]({item.url})"
            lines.append(line)

    return "\n".join(lines)


def _item_id(item: TaskItem) -> str:
    """Stable id for a task (same logical item = same id across refreshes)."""
    key = f"{item.course}|{item.date.isoformat()}|{item.type}|{item.title}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _build_context_summary_7_14(ref_date: date, all_tasks: List[TaskItem]) -> str:
    """Build deterministic 7-back/14-forward summary for Gemini context (no Gemini used)."""
    start = ref_date - timedelta(days=7)
    end = ref_date + timedelta(days=14)
    in_range = [t for t in all_tasks if start <= t.date <= end and t.type != "resource"]
    in_range.sort(key=lambda t: (t.date, t.course, t.type, t.title))
    lines: List[str] = [f"[Context window: 7 days back, 14 days forward from {ref_date.isoformat()}]", ""]
    current_date: date | None = None
    for t in in_range:
        if t.date != current_date:
            current_date = t.date
            lines.append(f"{t.date.isoformat()}:")
        major_marker = " *MAJOR*" if t.is_major else ""
        lines.append(f"  - {t.course} – {t.type}: {t.title}{major_marker}")
    return "\n".join(lines) if lines else ""


def _build_items_list(per_course: dict) -> List[dict]:
    """Flatten per_course into a list of item dicts with stable ids (excludes resource type)."""
    items: List[dict] = []
    seen_ids: set[str] = set()
    for code in sorted(per_course.keys(), key=lambda c: (c != "stott", c)):
        items_by_date = per_course[code]
        for d, day_items in sorted(items_by_date.items()):
            for item in day_items:
                if item.type == "resource":
                    continue
                iid = _item_id(item)
                if iid in seen_ids:
                    continue
                seen_ids.add(iid)
                items.append({
                    "id": iid,
                    "course": item.course,
                    "date": item.date.isoformat(),
                    "type": item.type,
                    "title": item.title,
                    "description": item.description or "",
                    "url": item.url or "",
                    "is_major": item.is_major,
                })
    return items


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate homework and readings for the next two academic days."
    )
    parser.add_argument(
        "--date",
        help="Reference date in ISO format (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--fetch-populi",
        action="store_true",
        help="Fetch and refresh Populi data into the local cache (if configured).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw items per course for sanity checking.",
    )
    parser.add_argument(
        "--gameplan",
        action="store_true",
        help="Generate a Gemini-powered gameplan (What should I work on?) and write to output/<date>-gameplan.md. Requires GEMINI_API_KEY.",
    )

    args = parser.parse_args(argv)
    ref_date = parse_date(args.date)

    from .populi_client import fetch_populi_if_enabled, load_populi_tasks

    courses = load_course_configs()

    if args.fetch_populi:
        fetch_populi_if_enabled(ROOT, ROOT / "config" / "courses.yaml", ref_date)

    pdf_tasks = load_pdf_tasks(ROOT, courses)
    populi_tasks = load_populi_tasks(ROOT, courses)

    # For Populi syllabus courses: use schedule YAML as canonical for syllabus content.
    # Keep from cache any task that does NOT duplicate a YAML item (same date, type, and
    # title match). So lessons/assignments content that's not in the syllabus PDF still
    # gets added without duplicates. Generalizable: no hardcoded types; dedupe by content.
    data_dir = ROOT / "data"
    syllabus_yaml_codes = {
        c.code for c in courses
        if c.source == "populi_page"
        and (data_dir / f"{c.code}_schedule.yaml").exists()
    }
    yaml_by_course: dict[str, List[TaskItem]] = {}
    for c in courses:
        if c.source != "populi_page":
            continue
        schedule_path = data_dir / f"{c.code}_schedule.yaml"
        if schedule_path.exists():
            yaml_by_course[c.code] = _load_yaml_items(schedule_path, fallback_course=c.code)

    def _title_matches(a: str, b: str) -> bool:
        na, nb = a.strip().lower(), b.strip().lower()
        if na == nb:
            return True
        if len(na) >= 8 and len(nb) >= 8 and (na in nb or nb in na):
            return True
        return False

    def keep_cache_task(t: TaskItem) -> bool:
        if t.course not in syllabus_yaml_codes:
            return True
        yaml_items = yaml_by_course.get(t.course, [])
        for y in yaml_items:
            if y.date == t.date and y.type == t.type and _title_matches(t.title, y.title):
                return False  # duplicate: drop cache task, use YAML version
        return True  # no duplicate: keep (e.g. lessons/assignments not in syllabus)

    populi_tasks = [t for t in populi_tasks if keep_cache_task(t)]
    for code, items in yaml_by_course.items():
        populi_tasks.extend(items)

    all_tasks = pdf_tasks + populi_tasks

    meeting_patterns = {c.code: c.meeting_pattern for c in courses}
    per_course_dates, per_course, major_items = aggregate_schedule(
        ref_date, all_tasks, meeting_patterns
    )

    if args.debug:
        print("Raw items by course:")
        for course in sorted({t.course for t in all_tasks}):
            print(f"- {course}")
            for t in sorted(
                (x for x in all_tasks if x.course == course), key=lambda x: x.date
            ):
                print(
                    f"  {t.date.isoformat()} [{t.type}] {t.title} "
                    f"{'(MAJOR)' if t.is_major else ''}"
                )
        print("")

    code_to_name = {c.code: c.name for c in courses}
    markdown = format_markdown(
        ref_date, per_course_dates, per_course, major_items, code_to_name=code_to_name
    )

    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{ref_date.isoformat()}.md"
    out_path.write_text(markdown, encoding="utf-8")

    gameplan_yesterday_md = ""
    gameplan_md = ""
    gameplan_tomorrow_md = ""
    if args.gameplan:
        try:
            from .gemini_gameplan import write_gameplan_for_date

            # Generate gameplan for yesterday
            yesterday = ref_date - timedelta(days=1)
            per_course_dates_yesterday, per_course_yesterday, major_yesterday = aggregate_schedule(
                yesterday, all_tasks, meeting_patterns
            )
            markdown_yesterday = format_markdown(
                yesterday, per_course_dates_yesterday, per_course_yesterday, major_yesterday, code_to_name=code_to_name
            )
            gameplan_yesterday_path = write_gameplan_for_date(
                ROOT, yesterday, markdown_yesterday
            )
            gameplan_yesterday_md = gameplan_yesterday_path.read_text(encoding="utf-8")
            print(f"Gameplan for yesterday written to {gameplan_yesterday_path}")
            print("")

            gameplan_path = write_gameplan_for_date(ROOT, ref_date, markdown)
            gameplan_md = gameplan_path.read_text(encoding="utf-8")
            print("")
            print(f"Gameplan written to {gameplan_path}")

            # Also generate gameplan for tomorrow and include in latest.json
            tomorrow = ref_date + timedelta(days=1)
            per_course_dates_tomorrow, per_course_tomorrow, major_tomorrow = aggregate_schedule(
                tomorrow, all_tasks, meeting_patterns
            )
            markdown_tomorrow = format_markdown(
                tomorrow, per_course_dates_tomorrow, per_course_tomorrow, major_tomorrow, code_to_name=code_to_name
            )
            gameplan_tomorrow_path = write_gameplan_for_date(
                ROOT, tomorrow, markdown_tomorrow
            )
            gameplan_tomorrow_md = gameplan_tomorrow_path.read_text(encoding="utf-8")
            print(f"Gameplan for tomorrow written to {gameplan_tomorrow_path}")
        except Exception as e:
            print("")
            print(f"Gameplan generation failed: {e}")
    else:
        yesterday = ref_date - timedelta(days=1)
        gameplan_yesterday_path = output_dir / f"{yesterday.isoformat()}-gameplan.md"
        if gameplan_yesterday_path.exists():
            gameplan_yesterday_md = gameplan_yesterday_path.read_text(encoding="utf-8")
        gameplan_path = output_dir / f"{ref_date.isoformat()}-gameplan.md"
        if gameplan_path.exists():
            gameplan_md = gameplan_path.read_text(encoding="utf-8")
        tomorrow = ref_date + timedelta(days=1)
        gameplan_tomorrow_path = output_dir / f"{tomorrow.isoformat()}-gameplan.md"
        if gameplan_tomorrow_path.exists():
            gameplan_tomorrow_md = gameplan_tomorrow_path.read_text(encoding="utf-8")

    # Write latest.json for the viewer (digest + gameplan_yesterday + gameplan + gameplan_tomorrow + items + context summary)
    items_list = _build_items_list(per_course)
    context_summary_7_14 = _build_context_summary_7_14(ref_date, all_tasks)
    latest = {
        "date": ref_date.isoformat(),
        "digest_md": markdown,
        "gameplan_yesterday_md": gameplan_yesterday_md or None,
        "gameplan_md": gameplan_md or None,
        "gameplan_tomorrow_md": gameplan_tomorrow_md or None,
        "items": items_list,
        "context_summary_7_14": context_summary_7_14,
    }
    (output_dir / "latest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )

    print("")
    print(markdown)
    print("")
    print(f"(Also written to {out_path})")


if __name__ == "__main__":
    main()

