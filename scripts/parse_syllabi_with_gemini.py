"""
Parse all syllabus schedule snippets with Gemini and write schedule YAMLs.
Logic lives in src.parse_syllabi; this script is the CLI.

  python -m scripts.parse_syllabi_with_gemini
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from src.parse_syllabi import run
    run(ROOT)


if __name__ == "__main__":
    main()
