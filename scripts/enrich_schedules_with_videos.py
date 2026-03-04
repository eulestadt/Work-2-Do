"""
Add videos and URLs to schedule YAMLs using Gemini 2.5 Flash.
Run after reimport_syllabi_from_pdf when you want video items and links in the digest.

Requires: GEMINI_API_KEY (in .env or environment), and data/text_extract/{code}.txt
(create with: python -m scripts.extract_syllabus_text)

  python -m scripts.enrich_schedules_with_videos
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXTRACT_DIR = DATA / "text_extract"


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    from src.pdf_sources import _load_yaml_items
    from src.gemini_schedule_check import (
        ask_gemini_for_schedule,
        load_schedule_snippet_from_txt,
        merge_gemini_into_tasks,
    )
    import os
    import yaml

    if not os.environ.get("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY to run enrichment.")
        return

    for code in ("bioethics", "doctrines"):
        yaml_path = DATA / f"{code}_schedule.yaml"
        if not yaml_path.exists():
            print(f"Skip {code}: {yaml_path} not found (run reimport_syllabi_from_pdf first)")
            continue
        txt_candidate = EXTRACT_DIR / f"{code}_schedule.txt"
        if not txt_candidate.exists():
            txt_candidate = EXTRACT_DIR / f"{code}.txt"
        if not txt_candidate.exists():
            print(f"Skip {code}: no text extract (run extract_syllabus_text)")
            continue

        print(f"Enriching {code}...", flush=True)
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        tasks = _load_yaml_items(yaml_path, code)
        snippet = load_schedule_snippet_from_txt(txt_candidate)
        if not snippet.strip():
            print(f"  No schedule snippet found in {txt_candidate.name}")
            continue
        gemini_list = ask_gemini_for_schedule(snippet, code, 2026)
        if not gemini_list:
            print(f"  No Gemini output (check API key / model)")
            continue
        tasks = merge_gemini_into_tasks(tasks, gemini_list, code, 2026)
        payload = {
            "course": raw.get("course", code),
            "source_pdf": raw.get("source_pdf", ""),
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
                for t in sorted(tasks, key=lambda x: (x.date, x.type))
            ],
        }
        yaml_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        print(f"  Updated {len(tasks)} items -> {yaml_path}")


if __name__ == "__main__":
    main()
