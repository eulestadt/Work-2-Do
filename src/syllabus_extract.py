"""
Extract full text from Populi syllabus PDFs and write schedule snippets.
Used by the app pipeline and by scripts/extract_syllabus_text.py (CLI).
Supports PDF position-based link matching: extract link /Rect and text positions
to compute anchor text (text next to each link) for better URL-to-item matching.
"""
from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path
from typing import Any, List, Tuple

WRAP_WIDTH = 100
SCHEDULE_SNIPPET_MAX = 3500
MAX_LINKS_IN_SNIPPET = 50
# Vertical band (points) to consider text "on the same row" as a link: use the link's own vertical span plus a small margin so we get only that row
ANCHOR_ROW_MARGIN = 8


def _rect_to_list(rect: Any) -> List[float]:
    """Normalize /Rect to [x0, y0, x1, y1] floats."""
    if rect is None:
        return []
    if hasattr(rect, "__getitem__"):
        return [float(rect[i]) for i in range(4) if i < len(rect)]
    return []


def _extract_links_with_rect(reader) -> List[Tuple[str, int, List[float]]]:
    """Extract (url, page_index, rect) for each /Subtype /Link in document order. rect = [x0,y0,x1,y1]."""
    result: List[Tuple[str, int, List[float]]] = []
    seen_urls: set = set()
    for page_idx, page in enumerate(reader.pages):
        try:
            anns = page.get("/Annots")
            if not anns:
                continue
            for ref in anns if isinstance(anns, list) else [anns]:
                try:
                    obj = ref.get_object() if hasattr(ref, "get_object") else ref
                    if obj.get("/Subtype") != "/Link":
                        continue
                    action = obj.get("/A")
                    if not action:
                        continue
                    action = action.get_object() if hasattr(action, "get_object") else action
                    uri = action.get("/URI")
                    if uri is None:
                        continue
                    if isinstance(uri, str):
                        url = uri
                    elif isinstance(uri, bytes):
                        url = uri.decode("utf-8", errors="replace")
                    else:
                        url = str(uri)
                    if not url.startswith("http") or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    rect = _rect_to_list(obj.get("/Rect"))
                    if len(rect) == 4:
                        result.append((url, page_idx, rect))
                    else:
                        result.append((url, page_idx, []))
                except Exception:
                    continue
        except Exception:
            continue
    return result[:MAX_LINKS_IN_SNIPPET]


def _extract_link_urls(reader) -> List[str]:
    """Legacy: flat list of URLs in document order (from links with rect when available)."""
    return [url for url, _, _ in _extract_links_with_rect(reader)]


def _extract_text_with_positions(reader) -> List[List[Tuple[str, float, float]]]:
    """Per-page list of (text, x, y_top) fragments. y_top = top-down (0 at top of page)."""
    pages_text: List[List[Tuple[str, float, float]]] = []
    for page in reader.pages:
        fragments: List[Tuple[str, float, float]] = []
        try:
            mb = page.mediabox
            height = float(mb.top - mb.bottom) if hasattr(mb, "top") else 612.0
        except Exception:
            height = 612.0

        def visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: float) -> None:
            try:
                x = float(tm[4]) if len(tm) >= 5 else 0.0
                y_pdf = float(tm[5]) if len(tm) >= 6 else 0.0
                y_top = height - y_pdf
                fragments.append((text, x, y_top))
            except (IndexError, TypeError, ValueError):
                pass

        try:
            page.extract_text(visitor_text=visitor)
        except Exception:
            pass
        pages_text.append(fragments)
    return pages_text


def _compute_anchor_text(
    links_with_rect: List[Tuple[str, int, List[float]]],
    text_by_page: List[List[Tuple[str, float, float]]],
    page_heights: List[float],
) -> List[Tuple[str, str]]:
    """For each (url, page_idx, rect), compute anchor text from text on same line. Returns (url, anchor_text) in same order as links. When multiple links share a line, partition fragments by link x."""
    result: List[Tuple[str, str]] = []
    for url, page_idx, rect in links_with_rect:
        if page_idx >= len(text_by_page):
            result.append((url, ""))
            continue
        fragments = text_by_page[page_idx]
        if not rect or len(rect) < 4:
            result.append((url, ""))
            continue
        x0, y0, x1, y1 = rect[0], rect[1], rect[2], rect[3]
        try:
            h = page_heights[page_idx] if page_idx < len(page_heights) else 612.0
        except Exception:
            h = 612.0
        link_y_top = h - max(y0, y1)
        link_y_bottom = h - min(y0, y1)
        link_left = min(x0, x1)
        link_right = max(x0, x1)
        same_line: List[Tuple[float, str]] = []
        for text, x, y_top in fragments:
            if link_y_top - ANCHOR_ROW_MARGIN <= y_top <= link_y_bottom + ANCHOR_ROW_MARGIN:
                same_line.append((x, text))
        same_line.sort(key=lambda t: t[0])
        if not same_line:
            result.append((url, ""))
            continue
        # In a table, the link is usually in a right-hand "Watch" column; the title is to the left.
        # Take all text on this row that is to the left of (or overlapping) the link.
        anchor_parts = [t[1] for t in same_line if t[0] <= link_right + 30]
        result.append((url, " ".join(anchor_parts).strip()))
    return result


def _get_page_heights(reader) -> List[float]:
    heights = []
    for page in reader.pages:
        try:
            mb = page.mediabox
            heights.append(float(mb.top - mb.bottom) if hasattr(mb, "top") else 612.0)
        except Exception:
            heights.append(612.0)
    return heights


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _extract_schedule_via_gemini(clean: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key or len(clean) > 50000:
        return ""
    try:
        from google import genai
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="From this syllabus text, extract only the section that contains the course schedule (dates and homework). Return that section and nothing else. No commentary.\n\n---\n\n" + clean[:30000],
        )
        out = (response.text or "").strip()
        return out[:SCHEDULE_SNIPPET_MAX].strip() if out else ""
    except Exception:
        return ""


def _extract_schedule_section(clean: str) -> str:
    gemini_section = _extract_schedule_via_gemini(clean)
    if gemini_section:
        return gemini_section
    m = re.search(r"Course\s+Schedule\s*[:\s]*(.*)", clean, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    rest = m.group(1).strip()
    for stop in ("Extra credit", "Assignments and Measurement", "Assignments and Rubrics", "See the \"Assignments\"", "How to Succeed"):
        idx = re.search(re.escape(stop), rest, re.IGNORECASE)
        if idx:
            rest = rest[: idx.start()].strip()
    return rest[:SCHEDULE_SNIPPET_MAX].strip()


def run(root_path: Path) -> None:
    """Extract syllabus text and schedule snippets for all populi_syllabus_*.pdf under data/."""
    from pypdf import PdfReader

    data = root_path / "data"
    extract_dir = data / "text_extract"
    extract_dir.mkdir(parents=True, exist_ok=True)
    for pdf_path in sorted(data.glob("populi_syllabus_*.pdf")):
        code = pdf_path.stem.replace("populi_syllabus_", "")
        out_path = extract_dir / f"{code}.txt"
        reader = PdfReader(str(pdf_path))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                parts.append("")
        raw = "\n".join(parts)
        clean = _normalize(raw)
        wrapped = textwrap.fill(clean, width=WRAP_WIDTH)
        out_path.write_text(wrapped, encoding="utf-8")
        schedule_only = _extract_schedule_section(clean)
        links_with_rect = _extract_links_with_rect(reader)
        link_urls = [url for url, _, _ in links_with_rect]
        if schedule_only and link_urls:
            schedule_only = schedule_only + "\n\nLinks found in this syllabus (use for videos/readings when they match):\n" + "\n".join(link_urls)
            text_by_page = _extract_text_with_positions(reader)
            page_heights = _get_page_heights(reader)
            anchor_list = _compute_anchor_text(links_with_rect, text_by_page, page_heights)
            anchor_lines = [f"{url}\t{anchor}" for url, anchor in anchor_list]
            if anchor_lines:
                schedule_only = schedule_only + "\n\nLink anchor text (from PDF):\n" + "\n".join(anchor_lines)
        if schedule_only:
            sched_path = extract_dir / f"{code}_schedule.txt"
            sched_path.write_text(schedule_only.strip(), encoding="utf-8")
