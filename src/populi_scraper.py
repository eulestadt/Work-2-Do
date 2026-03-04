from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright
from dateutil import parser as date_parser
import yaml
from urllib.parse import urljoin, urlparse, parse_qs

from .models import CourseConfig, TaskItem


DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}\b")
COURSE_OFFERING_ID_RE = re.compile(r"/courseofferings/(\d+)/")
# Due date patterns on assignments page (e.g. "Due Feb 28, 2026", "2/28/2026", "Feb 28")
DUE_DATE_RE = re.compile(
    r"(?:due\s+)?(?:\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s*(\d{4})?)",
    re.IGNORECASE,
)


def _load_populi_courses_from_config(config_path: Path) -> List[CourseConfig]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    courses: List[CourseConfig] = []
    for c in raw.get("courses", []):
        if c.get("source") != "populi_page":
            continue
        courses.append(
            CourseConfig(
                code=c["code"],
                name=c["name"],
                source=c["source"],
                meeting_pattern=c["meeting_pattern"],
                data_file=None,
                requires_manual_check=bool(c.get("requires_manual_check", True)),
            )
        )
    return courses


def _login(page: Page) -> None:
    load_dotenv()
    username = os.getenv("POPULI_USERNAME")
    password = os.getenv("POPULI_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "POPULI_USERNAME and POPULI_PASSWORD must be set in the environment "
            "or in a .env file in the project root."
        )

    page.goto("https://sattler.populiweb.com/")
    page.wait_for_load_state("networkidle")

    # Save the raw login HTML so we can refine selectors if needed.
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "populi_login.html").write_text(page.content(), encoding="utf-8")

    # Use the actual Populi login field IDs/names
    user_locator = page.locator(
        "#username-field, input[name='username'], input#username"
    ).first
    user_locator.wait_for(state="visible", timeout=30000)
    user_locator.fill(username)

    # Use the actual Populi password field ID/name
    pass_locator = page.locator(
        "#password-field, input[name='password'], input#password"
    ).first
    pass_locator.wait_for(state="visible", timeout=30000)
    pass_locator.fill(password)

    # Click the Log In / Sign In button
    page.locator(
        "button:has-text('Log In'), button:has-text('Sign In'), "
        "input[type='submit'][value*='Log'], input[type='submit'][value*='Sign']"
    ).first.click()
    page.wait_for_load_state("networkidle")


def _parse_date_from_text(text: str, year: int) -> date | None:
    """
    Best-effort parse of a MM/DD fragment within the given text.
    """
    m = DATE_RE.search(text)
    if not m:
        return None
    mm_dd = m.group(0)
    try:
        return date_parser.parse(f"{mm_dd}/{year}").date()
    except Exception:
        return None


def parse_syllabus_html(html: str, course_code: str, year: int) -> List[TaskItem]:
    """
    Generic parser for Populi syllabus-style pages.

    Heuristic:
      - Look for rows in tables.
      - If a row contains a MM/DD date fragment, treat that as the class date.
      - Use the remaining cell text as the title/description.
    """
    soup = BeautifulSoup(html, "html.parser")
    tasks: List[TaskItem] = []

    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if not cells:
            continue
        row_text = " ".join(cells)
        maybe_date = _parse_date_from_text(row_text, year)
        if not maybe_date:
            continue

        title = cells[1] if len(cells) > 1 else cells[0]
        description_parts = cells[2:] if len(cells) > 2 else []
        description = " | ".join(description_parts)

        tasks.append(
            TaskItem(
                course=course_code,
                date=maybe_date,
                type="reading",
                title=title,
                description=description,
                source="populi",
            )
        )

    # Also capture any embedded syllabus/document viewer as a single resource link.
    iframe = soup.find("iframe", class_="document_viewer")
    if iframe and iframe.get("src"):
        src = iframe["src"]
        url = (
            "https://sattler.populiweb.com" + src
            if src.startswith("/")
            else src
        )
        tasks.append(
            TaskItem(
                course=course_code,
                date=date.today(),
                type="resource",
                title="Course syllabus (PDF)",
                description="Open the embedded syllabus PDF for detailed schedule and readings.",
                url=url,
                is_major=False,
                source="populi",
            )
        )

    return tasks


def parse_lessons_html(html: str, course_code: str, year: int) -> List[TaskItem]:
    """
    Generic parser for Populi lessons index pages.

    Heuristic:
      - Look for list items or lesson blocks that contain a MM/DD date.
      - Use inner text as the title; classify type based on simple keywords.
    """
    """
    Minimal fallback parser for lesson pages.

    We avoid scanning the full DOM for incidental dates (Populi's global banners can
    include dates like "2/26"), which previously produced false "assignments".

    Primary extraction for lessons now comes from:
      - the week content iframe (parsed into per-day tasks), and
      - the explicit lesson file links (embedded into those tasks).
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find(id="content_goes_here") or soup.body or soup
    text = " ".join((main.get_text(" ", strip=True) or "").split())
    if not text:
        return []
    return [
        TaskItem(
            course=course_code,
            date=date.today(),
            type="other",
            title="Lesson content",
            description=text,
            source="populi",
        )
    ]


def parse_week_content_html(
    html: str,
    course_code: str,
    week_label: str,
    week_start: date,
    file_links: List[Tuple[str, str]],
) -> List[TaskItem]:
    """
    Parse the main lesson content page (loaded from the content iframe).

    Parse the main lesson content page (loaded from the content iframe) into
    per-day tasks (Monday/Wednesday/Friday etc.).
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="content_goes_here") or soup.body or soup

    def clean_text(s: str) -> str:
        return " ".join((s or "").strip().split())

    DAY_HEADINGS = {"week overview", "everyday", "monday", "tuesday", "wednesday", "thursday", "friday"}
    overview: List[str] = []
    everyday: List[str] = []
    sections: dict[str, List[str]] = {}
    current: Optional[str] = None

    def text_after(el, child) -> str:
        """Text of el that comes after child (e.g. after <strong>Wednesday</strong> in <p>)."""
        full = (el.get_text(" ", strip=True) or "")
        sub = (child.get_text(" ", strip=True) or "")
        if not sub or full.startswith(sub):
            rest = full[len(sub):].lstrip(": \t")
            return clean_text(rest)
        return clean_text(full)

    # Walk through tags and bucket content by headings.
    for el in container.find_all(["p", "li", "strong"], recursive=True):
        if el.name == "strong":
            heading = clean_text(el.get_text(" ", strip=True)).rstrip(":")
            heading_l = heading.lower()
            if heading_l in DAY_HEADINGS:
                current = heading_l
                sections.setdefault(current, [])
                # If this strong is inside a <p>, the same <p> may have content after it (e.g. "Wednesday: Lecture: ...").
                if el.parent and el.parent.name == "p":
                    rest = text_after(el.parent, el)
                    if rest:
                        sections.setdefault(current, []).append(rest)
            continue

        txt = clean_text(el.get_text(" ", strip=True))
        if not txt:
            continue
        # Skip <p> that only contains a day heading (e.g. "<p><strong>Monday</strong>: </p>"); the strong will set current.
        if el.name == "p":
            strong = el.find("strong")
            if strong and strong.get_text(strip=True):
                strong_heading = clean_text(strong.get_text(" ", strip=True)).rstrip(":").lower()
                if strong_heading in {"monday", "tuesday", "wednesday", "thursday", "friday"}:
                    # Content after the strong was already added when we processed the strong.
                    continue

        if current == "week overview":
            overview.append(txt)
        elif current == "everyday":
            everyday.append(txt)
        elif current in {"monday", "tuesday", "wednesday", "thursday", "friday"}:
            sections.setdefault(current, []).append(txt)
        else:
            overview.append(txt)

    def format_files_description() -> str:
        if not file_links:
            return ""
        lines = ["Resources for the week (files/links):"]
        for title, url in file_links:
            lines.append(f"- {title} ({url})")
        return " ".join(lines)

    tasks: List[TaskItem] = []
    day_offsets = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
    }

    for day, offset in day_offsets.items():
        day_lines = sections.get(day, [])
        if not day_lines:
            continue
        desc_lines = []
        if overview:
            desc_lines.extend(overview)
        if everyday:
            desc_lines.append("Everyday:")
            desc_lines.extend(everyday)
        desc_lines.append(f"{day.title()}:")
        desc_lines.extend(day_lines)
        tasks.append(
            TaskItem(
                course=course_code,
                date=week_start + timedelta(days=offset),
                type="reading",
                title=f"{week_label} – {day.title()}",
                description=" ".join(desc_lines),
                source="populi",
            )
        )

    # Add a single task for the week's files/links (for the week as a whole), on week start (Monday).
    if file_links:
        tasks.append(
            TaskItem(
                course=course_code,
                date=week_start,
                type="reading",
                title=f"{week_label} – Resources (files/links)",
                description=format_files_description(),
                source="populi",
            )
        )

    # Fallback: if no day sections detected, emit a single overview item.
    if not tasks:
        text = clean_text(container.get_text(" ", strip=True))
        if text:
            desc = text
            if file_links:
                desc = desc + " " + format_files_description()
            tasks.append(
                TaskItem(
                    course=course_code,
                    date=week_start,
                    type="reading",
                    title=f"{week_label} overview",
                    description=desc,
                    source="populi",
                )
            )
        elif file_links:
            tasks.append(
                TaskItem(
                    course=course_code,
                    date=week_start,
                    type="reading",
                    title=f"{week_label} – Resources (files/links)",
                    description=format_files_description(),
                    source="populi",
                )
            )

    return tasks


def _week_uses_per_day_iframes(week_soup: BeautifulSoup) -> bool:
    """
    True if the week page uses the div pattern: multiple day sections (MONDAY, FRIDAY, etc.)
    each with their own content iframe. False if it uses a single iframe with all content inside.
    """
    DAY_STARTS = ("monday", "tuesday", "wednesday", "thursday", "friday")
    heading_divs = week_soup.find_all("div", class_="lesson-section-heading")
    count = 0
    for div in heading_divs:
        h2 = div.find("h2")
        if not h2:
            continue
        first_word = ((h2.get_text(" ", strip=True) or "").split()[0] or "").lower()
        if first_word in DAY_STARTS:
            content_div = div.find_next_sibling("div", class_="lesson-section-content")
            if content_div and content_div.find("iframe", class_="js-section_content_frame"):
                count += 1
    return count >= 2


def parse_day_content_html(
    html: str,
    course_code: str,
    week_label: str,
    week_start: date,
    day_heading: str,
) -> List[TaskItem]:
    """
    Parse a single day's lesson content iframe (e.g. MONDAY Rousseau, FRIDAY Constitution/Federalist)
    into one TaskItem dated to the correct day of the week.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="content_goes_here") or soup.body or soup

    def clean_text(s: str) -> str:
        return " ".join((s or "").strip().split())

    text = clean_text(container.get_text(" ", strip=True))
    if not text:
        return []

    heading_norm = (day_heading or "").strip().upper()
    # Use the first word of the heading to identify the day (e.g. "MONDAY", "FRIDAY (QUIZ 3 DUE) ...")
    first_word = heading_norm.split()[0] if heading_norm else ""
    day_key = first_word.lower()

    day_offsets = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
    }
    offset = day_offsets.get(day_key, 0)
    date_for_day = week_start + timedelta(days=offset)
    title = f"{week_label} – {day_key.title() if day_key else 'Day'}"

    return [
        TaskItem(
            course=course_code,
            date=date_for_day,
            type="reading",
            title=title,
            description=text,
            source="populi",
        )
    ]


def _extract_lesson_file_links(lesson_html: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(lesson_html, "html.parser")
    files_list = soup.find("div", id="filesList")
    out: List[Tuple[str, str]] = []
    if not files_list:
        return out
    for a in files_list.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = a["href"]
        url = "https://sattler.populiweb.com" + href if href.startswith("/") else href
        out.append((title, url))
    return out


def _download_pdf_from_viewer(page: Page, viewer_url: str, out_path: Path) -> Optional[Path]:
    """
    Open Populi's document viewer page and download the PDF via the file_id.
    The viewer uses onclick for download (e.g. window.open('/router/files/90677754/download'));
    we get file_id from the viewer URL query string and request that path directly.
    """
    page.goto(viewer_url)
    page.wait_for_load_state("networkidle")
    html = page.content()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parsed = urlparse(viewer_url)
    qs = parse_qs(parsed.query)
    file_ids = qs.get("file_id", [])
    file_id = file_ids[0] if file_ids else None

    if not file_id:
        # Fallback: look for an <a href="...download..."> (some viewers may use it)
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            if "download" in a["href"]:
                file_id = None
                download_url = urljoin("https://sattler.populiweb.com", a["href"])
                break
        else:
            download_url = None
    else:
        download_url = f"https://sattler.populiweb.com/router/files/{file_id}/download"

    if not download_url:
        return None

    resp = page.context.request.get(download_url)
    if not resp.ok:
        return None
    body = resp.body()
    if not body:
        return None
    out_path.write_bytes(body)
    return out_path


def _term_start_to_date(raw: str | date | None) -> date | None:
    """Normalize term_start from config (YAML may give str or date)."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return datetime.fromisoformat(str(raw)).date()
    except Exception:
        return None


def _week_label_for_course(term_start_raw: str | date | None, ref_date: date) -> str:
    """
    Compute a week label like 'Week 6' from a term start date and reference date.
    """
    term_start = _term_start_to_date(term_start_raw)
    if term_start is None:
        return "Week 1"
    delta_weeks = max(0, (ref_date - term_start).days // 7)
    return f"Week {delta_weeks + 1}"


def _week_num_from_label(label: str) -> Optional[int]:
    m = re.search(r"\bWeek\s+(\d+)\b", label, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _week_start_from_term_start(term_start: date, week_num: int) -> date:
    # Assumes term_start is the Monday of Week 1.
    return term_start + timedelta(days=(week_num - 1) * 7)


def _parse_assignments_html(
    html: str, course_code: str, ref_date: date
) -> List[TaskItem]:
    """
    Parse Populi assignments index page for assignment title, due date, and type.
    Returns task items for quizzes, essays, and other assignments with due dates.
    """
    soup = BeautifulSoup(html, "html.parser")
    tasks: List[TaskItem] = []
    # Find assignment links: /router/courseofferings/123/assignments/456/show
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/assignments/" in href and "/show" in href:
            title = (a.get_text(" ", strip=True) or "").strip()
            if not title:
                continue
            title_lower = title.lower()
            # Infer type from title
            if "quiz" in title_lower:
                task_type = "quiz"
            elif "essay" in title_lower or "paper" in title_lower:
                task_type = "essay"
            elif "exam" in title_lower or "test" in title_lower:
                task_type = "exam"
            else:
                task_type = "assignment"
            # Find due date in the same row or nearby container
            row = a.find_parent("tr") or a.find_parent("li") or a.find_parent("div", class_=lambda c: c and "row" in str(c))
            container = row or a
            block_text = (container.get_text(" ", strip=True) or "")
            due_date = None
            # Prefer ISO date from hidden spans (e.g. <span style="display:none;">2026-03-02 23:59:59</span>)
            # — only the due-date column uses this; availability uses "Jan 19, 2026 ... to May 8, 2026"
            if row:
                for span in row.find_all("span", style=lambda s: s and "display:none" in str(s).replace(" ", "")):
                    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", span.get_text() or "")
                    if iso_match:
                        try:
                            y, mo, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
                            if 1 <= mo <= 12 and 1 <= d <= 31:
                                due_date = date(y, mo, d)
                                break
                        except (ValueError, TypeError):
                            pass
            if not due_date:
                # Prefer MM/DD/YYYY or MM/DD in the block
                for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", block_text):
                    g = m.groups()
                    try:
                        mo, day = int(g[0]), int(g[1])
                        year = int(g[2]) if g[2] else ref_date.year
                        if year < 100:
                            year += 2000
                        if 1 <= mo <= 12 and 1 <= day <= 31:
                            due_date = date(year, mo, day)
                            break
                    except (ValueError, TypeError):
                        continue
            if not due_date:
                # Try dateutil on a short window (e.g. "Due Feb 28, 2026")
                try:
                    for m in re.finditer(
                        r"\b(?:due\s+)?([A-Za-z]+\s+\d{1,2},?\s*\d{4})\b", block_text
                    ):
                        parsed = date_parser.parse(
                            m.group(1), default=datetime(ref_date.year, 1, 1)
                        )
                        if parsed:
                            due_date = parsed.date()
                            break
                except Exception:
                    pass
            if due_date:
                tasks.append(
                    TaskItem(
                        course=course_code,
                        date=due_date,
                        type=task_type,
                        title=title,
                        description="",
                        url=urljoin("https://sattler.populiweb.com", href) if href.startswith("/") else href,
                        is_major=task_type in ("essay", "exam", "report", "project"),
                        source="populi",
                    )
                )
    return tasks


def scrape_populi_courses(
    root: Path, config_path: Path, ref_date: date
) -> List[TaskItem]:
    """
    Use Playwright to log into Populi and scrape configured courses.

    Notes:
      - This is intentionally generic and may need selector tweaks once you
        inspect the real course HTML. It is safe to run locally and adjust.
      - Raw HTML for each visited page is saved under `data/populi_raw_<code>.html`
        so you can refine the parser without re-scraping constantly.
    """
    year = ref_date.year
    courses = _load_populi_courses_from_config(config_path)
    if not courses:
        return []

    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    all_tasks: List[TaskItem] = []

    with sync_playwright() as p:
        # Use headed mode so you can see what's happening and adjust if needed.
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        _login(page)

        # Re-open config with raw dict access to get Populi URL and mode
        raw_cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        course_entries = {c["code"]: c for c in raw_cfg.get("courses", [])}

        for cfg in courses:
            entry = course_entries.get(cfg.code, {})
            populi_info = entry.get("populi", {})
            url = populi_info.get("url")
            mode = populi_info.get("mode", "syllabus")
            if not url:
                continue

            page.goto(url)
            page.wait_for_load_state("networkidle")
            html = page.content()

            # Save raw HTML for debugging/tuning
            raw_path = data_dir / f"populi_raw_{cfg.code}.html"
            raw_path.write_text(html, encoding="utf-8")

            if mode == "syllabus":
                # For Bioethics/Doctrines this will not see into the embedded
                # PDF syllabus, but it will at least surface the PDF link and
                # any visible HTML schedule.
                tasks = parse_syllabus_html(html, cfg.code, year)

                # If there is an embedded syllabus PDF viewer, download and import it.
                soup = BeautifulSoup(html, "html.parser")
                viewer_iframe = soup.find("iframe", class_="document_viewer")
                if viewer_iframe and viewer_iframe.get("src"):
                    viewer_src = viewer_iframe["src"]
                    viewer_url = (
                        "https://sattler.populiweb.com" + viewer_src
                        if viewer_src.startswith("/")
                        else viewer_src
                    )
                    pdf_path = data_dir / f"populi_syllabus_{cfg.code}.pdf"
                    downloaded = _download_pdf_from_viewer(page, viewer_url, pdf_path)
                    if downloaded:
                        from .pdf_importers.populi_syllabus_importer import (
                            import_populi_syllabus_pdf_to_yaml,
                        )
                        term_start = _term_start_to_date(entry.get("term_start"))
                        if term_start:
                            out_yaml = data_dir / f"{cfg.code}_schedule.yaml"
                            imported_tasks = import_populi_syllabus_pdf_to_yaml(
                                downloaded,
                                out_yaml,
                                cfg.code,
                                entry.get("meeting_pattern", cfg.meeting_pattern),
                                term_start,
                                year,
                            )
                            tasks.extend(imported_tasks)
            else:
                # For lessons pages (Greek, Humanities), first navigate into
                # the current week's lesson before parsing, then:
                #   - parse the lesson page for resources (e.g. PDFs),
                #   - if there is a content iframe, load it and parse into tasks.
                term_start_str = entry.get("term_start")
                week_label = _week_label_for_course(term_start_str, ref_date)
                soup = BeautifulSoup(html, "html.parser")
                week_link = soup.find(
                    "a",
                    class_="column_item_title",
                    string=lambda t: isinstance(t, str)
                    and t.strip().startswith(week_label),
                )
                lesson_tasks: List[TaskItem] = []

                if week_link and week_link.get("href"):
                    week_href = week_link["href"]
                    week_url = (
                        "https://sattler.populiweb.com" + week_href
                        if week_href.startswith("/")
                        else week_href
                    )
                    page.goto(week_url)
                    page.wait_for_load_state("networkidle")
                    week_html = page.content()
                    week_path = data_dir / f"populi_week_{cfg.code}.html"
                    week_path.write_text(week_html, encoding="utf-8")

                    file_links = _extract_lesson_file_links(week_html)

                    week_soup = BeautifulSoup(week_html, "html.parser")
                    term_start = _term_start_to_date(entry.get("term_start"))
                    week_num = _week_num_from_label(week_label)
                    week_start = (
                        _week_start_from_term_start(term_start, week_num)
                        if term_start and week_num
                        else ref_date
                    )

                    if _week_uses_per_day_iframes(week_soup):
                        # Div pattern: one iframe per day section (MONDAY, WEDNESDAY, FRIDAY, etc.).
                        # Collect all headings and their corresponding content iframes.
                        heading_divs = week_soup.find_all(
                            "div", class_="lesson-section-heading"
                        )
                        for heading_div in heading_divs:
                            h2 = heading_div.find("h2")
                            if not h2:
                                continue
                            day_heading = " ".join(
                                (h2.get_text(" ", strip=True) or "").split()
                            )
                            # Find the next lesson-section-content sibling for this heading.
                            content_div = heading_div.find_next_sibling(
                                "div", class_="lesson-section-content"
                            )
                            if not content_div:
                                continue
                            iframe = content_div.find(
                                "iframe", class_="js-section_content_frame"
                            )
                            content_src = (
                                iframe.get("data-src") if iframe else None
                            )
                            if not content_src:
                                continue
                            content_url = (
                                "https://sattler.populiweb.com" + content_src
                                if content_src.startswith("/")
                                else content_src
                            )
                            page.goto(content_url)
                            page.wait_for_load_state("networkidle")
                            content_html = page.content()
                            # Save last day's content for debugging
                            content_path = (
                                data_dir
                                / f"populi_week_content_{cfg.code}_{day_heading.split()[0].lower()}.html"
                            )
                            content_path.write_text(content_html, encoding="utf-8")
                            lesson_tasks.extend(
                                parse_day_content_html(
                                    content_html,
                                    cfg.code,
                                    week_label,
                                    week_start,
                                    day_heading,
                                )
                            )

                        # Add a single task for the week's files/links (for the week as a whole), on week start (Monday).
                        if file_links:
                            desc_lines = ["Resources for the week (files/links):"]
                            for title, url in file_links:
                                desc_lines.append(f"- {title} ({url})")
                            lesson_tasks.append(
                                TaskItem(
                                    course=cfg.code,
                                    date=week_start,
                                    type="reading",
                                    title=f"{week_label} – Resources (files/links)",
                                    description=" ".join(desc_lines),
                                    source="populi",
                                )
                            )
                    else:
                        # Default lessons behavior (e.g. Greek): single iframe parsed into per-day tasks.
                        content_iframe = week_soup.find(
                            "iframe", class_="js-section_content_frame"
                        )
                        content_src = (
                            content_iframe.get("data-src")
                            if content_iframe
                            else None
                        )
                        if content_src:
                            content_url = (
                                "https://sattler.populiweb.com" + content_src
                                if content_src.startswith("/")
                                else content_src
                            )
                            page.goto(content_url)
                            page.wait_for_load_state("networkidle")
                            content_html = page.content()
                            content_path = (
                                data_dir / f"populi_week_content_{cfg.code}.html"
                            )
                            content_path.write_text(content_html, encoding="utf-8")
                            lesson_tasks.extend(
                                parse_week_content_html(
                                    content_html,
                                    cfg.code,
                                    week_label,
                                    week_start,
                                    file_links,
                                )
                            )
                else:
                    lesson_tasks.extend(parse_lessons_html(html, cfg.code, year))

                tasks = lesson_tasks

            # Scrape assignments page for every Populi course (Bioethics, Doctrines,
            # Greek, Humanities): quizzes, essays, and other due items.
            offering_match = COURSE_OFFERING_ID_RE.search(url or "")
            if offering_match:
                offering_id = offering_match.group(1)
                assignments_url = f"https://sattler.populiweb.com/router/courseofferings/{offering_id}/assignments/index"
                try:
                    page.goto(assignments_url)
                    page.wait_for_load_state("networkidle")
                    assignments_html = page.content()
                    assignments_path = data_dir / f"populi_assignments_{cfg.code}.html"
                    assignments_path.write_text(assignments_html, encoding="utf-8")
                    assignment_tasks = _parse_assignments_html(
                        assignments_html, cfg.code, ref_date
                    )
                    tasks.extend(assignment_tasks)
                except Exception:
                    pass

            all_tasks.extend(tasks)

        browser.close()

    return all_tasks


if __name__ == "__main__":
    # Convenience entry point to run scraping directly:
    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "config" / "courses.yaml"
    tasks = scrape_populi_courses(project_root, config_path, date.today())
    from .populi_client import dump_tasks_to_cache, POPULI_CACHE_FILE

    if tasks:
        dump_tasks_to_cache(project_root, tasks)
        print(f"Wrote {len(tasks)} task(s) to {POPULI_CACHE_FILE}.")
    else:
        print("No tasks scraped; cache not updated.")

