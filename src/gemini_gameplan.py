"""
Generate a "What should I work on?" gameplan from the digest using the Gemini API.
API key must be set in environment: GEMINI_API_KEY (or in .env). Never commit the key.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

GEMINI_PROMPT = """I am pasting my "Homework & Readings Digest" below.
Current Date: {today_date}

Please analyze the schedule and create a prioritized workflow for TODAY. Do not just list the schedule; tell me exactly what to execute and in what order.

**Structure and formatting (follow this closely so the output is easy to scan):**

1. **Opening:** Start with one short intro sentence, e.g. "Based on your schedule, here is your prioritized workflow for **{today_date}**." You may add one line about how many classes meet today or how heavy tomorrow is (e.g. "You have a busy day with four classes meeting today, plus a heavy prep load for tomorrow.").

2. **Section headers:** Use markdown level-3 headers for the four sections:
   ### 🚨 Critical "Do Not Miss" Items
   ### 📅 Classes Meeting Today ({today_date})
   ### 📚 Homework & Prep for Tomorrow ({tomorrow_date})
   ### 🔭 Looking Ahead (Friday & Weekend)
   Put a horizontal rule `---` between each major section for visual separation.

3. **Critical "Do Not Miss" Items:** Bullet list of exams, quizzes, or major papers due in the next 48 hours. Bold key item names and deadlines.

4. **Classes Meeting Today:** Right under the section header, add this line in italics: *Ensure these are completed before you head to class:*
   Then for **each class meeting today**: put the **course name in bold** on its own line (e.g. **Greek**, **Stott (Romans)**), then bullet points beneath it using clear action labels: **Do:**, **Read:**, **Focus:**, **Prep:**, **Activity:**, **Topic:**, or **Assignment:** as appropriate. Bold specific chapters, page numbers, and assignment names. Keep each bullet to one line when possible.

5. **Homework & Prep for Tomorrow:** Right under the section header, add one line in italics, e.g. *You have four classes meeting tomorrow. This is your "homework list" for tonight:*
   Then for **each class meeting tomorrow**: same pattern—**bold course name**, then bullets with **Study:**, **Read:**, **Submit:**, **Focus:**, **Assignment:**, etc. You may add a *(Note: ...)* for follow-ups (e.g. a Saturday due date). Bold chapters, page numbers, and quiz/assignment names.

6. **Looking Ahead:** Brief bullets for the next 3–7 days (essays, exams, key readings). Bold deadline names and dates.

7. **Closing:** End with one short, friendly closing question (e.g. "Would you like me to help you quiz for the Doctrines test or break down the Physics midterm topics?").

**Rules:** Only use information from the digest. Do not invent assignments or dates. Output valid markdown only (no meta-preamble like "Here is your gameplan"—just the intro sentence and the sections above).

**Links:** The digest may contain [Watch](url) or [Link](url) markdown links for videos and readings. When you mention a specific reading, video, or assignment that has such a link in the digest, include the same link in your output (e.g. **Read:** Ch. 1 [Watch](https://...) so the user can click through.

---
Homework & Readings Digest:

{digest}
"""


def generate_gameplan(
    digest_markdown: str,
    ref_date: date,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Call Gemini to produce the gameplan. Raises if API key missing or request fails."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your .env file or environment. "
            "Get a key at https://aistudio.google.com/apikey"
        )

    try:
        from google import genai
    except ImportError:
        raise ImportError(
            "Install the Gemini SDK: pip install google-genai"
        ) from None

    client = genai.Client(api_key=key)
    model_name = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # e.g. "Wednesday, Feb 25, 2026" and "Thursday, Feb 26, 2026"
    today_str = ref_date.strftime("%A, %b %d, %Y").replace(" 0", " ")
    tomorrow = ref_date + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%A, %b %d, %Y").replace(" 0", " ")

    contents = GEMINI_PROMPT.format(
        today_date=today_str,
        tomorrow_date=tomorrow_str,
        digest=digest_markdown,
    )

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
    )
    if not response or not getattr(response, "text", None):
        raise RuntimeError("Gemini returned no text. Check model name and API key.")
    return response.text.strip()


def write_gameplan_for_date(
    root: Path,
    ref_date: date,
    digest_markdown: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Path:
    """Generate gameplan and write to output/<date>-gameplan.md. Returns path."""
    gameplan = generate_gameplan(digest_markdown, ref_date, api_key=api_key, model=model)
    output_dir = root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{ref_date.isoformat()}-gameplan.md"
    out_path.write_text(gameplan, encoding="utf-8")
    return out_path
