"""
Parse all syllabus schedule snippets with Gemini and write schedule YAMLs.
Used by the app pipeline and by scripts/parse_syllabi_with_gemini.py (CLI).
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from .gemini_schedule_check import load_schedule_snippet_from_txt
from .gemini_syllabus_parser import parse_syllabus_to_tasks


def run(root_path: Path) -> None:
    """Parse data/text_extract/*_schedule.txt (or *.txt) with Gemini and write data/*_schedule.yaml."""
    data = root_path / "data"
    extract_dir = data / "text_extract"
    if not os.environ.get("GEMINI_API_KEY"):
        return
    for pdf_path in sorted(data.glob("populi_syllabus_*.pdf")):
        code = pdf_path.stem.replace("populi_syllabus_", "")
        txt_candidate = extract_dir / f"{code}_schedule.txt"
        if not txt_candidate.exists():
            txt_candidate = extract_dir / f"{code}.txt"
        if not txt_candidate.exists():
            continue
        snippet = load_schedule_snippet_from_txt(txt_candidate)
        if not snippet.strip():
            continue
        tasks = parse_syllabus_to_tasks(snippet, code, 2026)
        if not tasks:
            continue
        yaml_path = data / f"{code}_schedule.yaml"
        payload = {
            "course": code,
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
                for t in sorted(tasks, key=lambda x: (x.date, x.type, x.title))
            ],
        }
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
