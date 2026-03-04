"""
Re-import Bioethics and Doctrines schedule from existing Populi syllabus PDFs.
Produces data/bioethics_schedule.yaml and data/doctrines_schedule.yaml with
one reading task per date (simple parser). Uses pre-extracted .txt when present
so no PDF read needed.

To add videos and URLs: run after this script:
  python -m scripts.enrich_schedules_with_videos
(Requires GEMINI_API_KEY and data/text_extract/*.txt from extract_syllabus_text.)

Run from project root:
  python -m scripts.reimport_syllabi_from_pdf
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXTRACT_DIR = DATA / "text_extract"


def main() -> None:
    from src.pdf_importers.populi_syllabus_importer import import_populi_syllabus_pdf_to_yaml

    term_start = date(2026, 1, 19)
    for code in ("bioethics", "doctrines"):
        pdf_path = DATA / f"populi_syllabus_{code}.pdf"
        # Prefer pre-extracted .txt so we skip slow PDF read (run extract_syllabus_text once)
        text_override = None
        for candidate in (EXTRACT_DIR / f"{code}_schedule.txt", EXTRACT_DIR / f"{code}.txt"):
            if candidate.exists():
                text_override = candidate.read_text(encoding="utf-8")
                break
        if not text_override and not pdf_path.exists():
            print(f"Skip {code}: no PDF and no text extract (run extract_syllabus_text?)")
            continue
        print(f"Parsing {code}...", flush=True)
        out_yaml = DATA / f"{code}_schedule.yaml"
        count = len(
            import_populi_syllabus_pdf_to_yaml(
                pdf_path, out_yaml, code, "TTh", term_start, 2026,
                text_override=text_override,
            )
        )
        print(f"Re-imported {code}: {count} items -> {out_yaml}")


if __name__ == "__main__":
    main()
