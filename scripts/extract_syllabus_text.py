#!/usr/bin/env python3
"""
Extract full text from Populi syllabus PDFs into data/text_extract/<code>.txt
and <code>_schedule.txt. Logic lives in src.syllabus_extract; this script is the CLI.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    from src.syllabus_extract import run
    print("Extracting to data/text_extract/")
    run(ROOT)
    print("Done.")


if __name__ == "__main__":
    main()
