"""
Minimal web app for Railway: serves the viewer, exposes /api/latest,
and runs the daily pipeline (scraper + digest + gameplan) on a schedule.
All secrets (POPULI_*, GEMINI_API_KEY, SENDGRID_API_KEY) must be set in Railway env vars.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, request, send_from_directory
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
VIEWER_DIR = ROOT / "viewer"
LATEST_JSON = OUTPUT_DIR / "latest.json"
DEFAULT_GAMEPLAN_RECIPIENT = "phoenix.wang24@sattler.edu"

app = Flask(__name__, static_folder=None)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _gameplan_md_to_pdf(markdown_body: str) -> bytes:
    """Convert markdown gameplan to PDF bytes using Playwright (full Unicode/emoji support)."""
    import markdown
    from playwright.sync_api import sync_playwright

    html_body = markdown.markdown(markdown_body, extensions=["nl2br", "tables"])
    html_doc = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; font-size: 9pt; line-height: 1.3; max-width: 700px; margin: 0.5em auto; padding: 0 0.5em; }}
    h1 {{ font-size: 1.5em; margin-top: 0.75em; margin-bottom: 0.25em; }}
    h2 {{ font-size: 1.25em; margin-top: 0.6em; margin-bottom: 0.2em; }}
    h3 {{ font-size: 1.1em; margin-top: 0.5em; margin-bottom: 0.15em; }}
    h1:first-child {{ margin-top: 0; }}
    ul, ol {{ margin: 0.2em 0; padding-left: 1.2em; }}
    p {{ margin: 0.5em 0; }}
    a {{ color: #0066cc; }}
    hr {{ border: none; border-top: 1px solid #ccc; margin: 0.75em 0; }}
  </style>
</head>
<body>
{html_body}
</body>
</html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_doc, wait_until="networkidle")
        pdf_bytes = page.pdf(format="A4", margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"})
        browser.close()
    return pdf_bytes


def send_gameplan_email() -> None:
    """Send the latest gameplan (today + tomorrow) to EMAIL_TO via Twilio SendGrid. Attaches PDF. No-op if not configured."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        logger.info("Email skipped: set SENDGRID_API_KEY to send gameplan.")
        return
    to_addr = os.environ.get("EMAIL_TO", DEFAULT_GAMEPLAN_RECIPIENT)
    from_addr = os.environ.get("EMAIL_FROM")
    if not from_addr:
        logger.info("Email skipped: set EMAIL_FROM (verified sender in SendGrid) to send gameplan.")
        return
    if not LATEST_JSON.exists():
        logger.warning("Email skipped: no latest.json.")
        return
    try:
        data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Email skipped: could not read latest.json: %s", e)
        return
    gameplan_yesterday_md = data.get("gameplan_yesterday_md") or ""
    gameplan_md = data.get("gameplan_md") or ""
    gameplan_tomorrow_md = data.get("gameplan_tomorrow_md") or ""
    date_str = data.get("date", "unknown")
    if not gameplan_yesterday_md and not gameplan_md and not gameplan_tomorrow_md:
        logger.info("Email skipped: no gameplan in latest.json.")
        return
    body_parts = []
    if gameplan_yesterday_md:
        try:
            yesterday_str = (date.fromisoformat(date_str) - timedelta(days=1)).strftime("%A, %b %d, %Y").replace(" 0", " ")
        except (ValueError, TypeError):
            yesterday_str = "yesterday"
        body_parts.append(f"# Gameplan for yesterday ({yesterday_str})\n\n{gameplan_yesterday_md}")
    if gameplan_md:
        body_parts.append(f"\n\n---\n\n# Gameplan for {date_str}\n\n{gameplan_md}")
    if gameplan_tomorrow_md:
        body_parts.append(f"\n\n---\n\n# Gameplan for tomorrow\n\n{gameplan_tomorrow_md}")
    body = "\n".join(body_parts)
    try:
        import base64

        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Attachment,
            Disposition,
            FileContent,
            FileName,
            FileType,
            Mail,
            PlainTextContent,
        )

        pdf_bytes = _gameplan_md_to_pdf(body)
        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
        # Sanitize filename: date_str is typically ISO (2026-03-02) or "Mar 2, 2026"
        safe_date = "".join(c if c.isalnum() or c in "-_" else "-" for c in date_str)
        filename = f"gameplan-{safe_date}.pdf"

        attachment = Attachment(
            file_content=FileContent(pdf_b64),
            file_name=FileName(filename),
            file_type=FileType("application/pdf"),
            disposition=Disposition("attachment"),
        )

        message = Mail(
            from_email=from_addr,
            to_emails=to_addr,
            subject=f"Gameplan for yesterday, {date_str}, and tomorrow",
            plain_text_content=PlainTextContent(
                "Your gameplan for yesterday, today, and tomorrow is attached as a PDF.\n\n"
                "— Work to Do"
            ),
        )
        message.attachment = attachment

        sg = SendGridAPIClient(api_key)
        sg.send(message)
        logger.info("Gameplan email with PDF attachment sent to %s via SendGrid", to_addr)
    except Exception as e:
        logger.exception("Failed to send gameplan email: %s", e)


def run_daily_pipeline() -> None:
    """Run scraper, parse syllabi with Gemini (replaces regex + enrichment), then digest + gameplan."""
    logger.info("Starting daily pipeline (fetch-populi -> extract -> parse_syllabi_gemini -> gameplan)")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    # Compute ref_date in user timezone so gameplan shows correct "today"
    tz_name = os.environ.get("REFERENCE_TIMEZONE")
    if tz_name:
        try:
            ref_date = datetime.now(ZoneInfo(tz_name)).date()
        except Exception:
            ref_date = date.today()
    else:
        ref_date = date.today()
    env["REFERENCE_DATE"] = ref_date.isoformat()
    # 1. fetch-populi (subprocess)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--fetch-populi"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.warning("fetch-populi exited %s: %s", result.returncode, result.stderr or result.stdout)
        else:
            logger.info("fetch-populi finished")
    except subprocess.TimeoutExpired:
        logger.error("fetch-populi timed out")
    except Exception as e:
        logger.exception("fetch-populi failed: %s", e)
    # 2. extract syllabus text (in-process; no scripts/ dir needed in deploy)
    try:
        from src.syllabus_extract import run as run_extract
        run_extract(ROOT)
        logger.info("extract_syllabus_text finished")
    except Exception as e:
        logger.warning("extract_syllabus_text failed: %s", e)
    # 3. parse syllabi with Gemini (in-process)
    try:
        from src.parse_syllabi import run as run_parse_syllabi
        run_parse_syllabi(ROOT)
        logger.info("parse_syllabi_with_gemini finished")
    except Exception as e:
        logger.warning("parse_syllabi_with_gemini failed: %s", e)
    # 4. gameplan (subprocess)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--gameplan"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.warning("gameplan exited %s: %s", result.returncode, result.stderr or result.stdout)
        else:
            logger.info("gameplan finished")
    except subprocess.TimeoutExpired:
        logger.error("gameplan timed out")
    except Exception as e:
        logger.exception("gameplan failed: %s", e)
    send_gameplan_email()
    logger.info("Daily pipeline complete")


@app.route("/")
def index() -> str:
    with open(VIEWER_DIR / "index.html", encoding="utf-8") as f:
        return f.read()


def _ask_gemini(question: str, digest_md: str, gameplan_md: str | None, context_summary: str) -> str:
    """Call Gemini 2.5 Flash with schedule context. Raises if API key missing or request fails."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    try:
        from google import genai
    except ImportError:
        raise ImportError("Install the Gemini SDK: pip install google-genai") from None

    context_parts = [f"## Homework & Readings Digest\n\n{digest_md}"]
    if gameplan_md:
        context_parts.append(f"\n\n## Gameplan (prioritized workflow)\n\n{gameplan_md}")
    if context_summary:
        context_parts.append(f"\n\n## Schedule summary (7 days back, 14 days forward)\n\n{context_summary}")

    full_context = "\n".join(context_parts)
    prompt = f"""You are a helpful assistant. The user is asking a question about their schedule. Use ONLY the following schedule context to answer. Do not invent assignments, dates, or courses. If the answer is not in the context, say so.

---
{full_context}
---

User question: {question}

Answer (use only information from the schedule context above):"""

    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    if not response or not getattr(response, "text", None):
        raise RuntimeError("Gemini returned no text.")
    return response.text.strip()


@app.route("/api/ask_gemini", methods=["POST"])
def api_ask_gemini():
    """Answer a question about the schedule using Gemini 2.5 Flash. Expects JSON body: {question: "..."}."""
    if not LATEST_JSON.exists():
        return {"error": "No digest yet. The daily pipeline has not run."}, 404
    try:
        body = request.get_json() or {}
        question = body.get("question", "").strip()
        if not question:
            return {"error": "Missing or empty 'question' in request body."}, 400
    except Exception as e:
        return {"error": f"Invalid JSON: {e}"}, 400

    try:
        data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        logger.exception("Error reading latest.json: %s", e)
        return {"error": str(e)}, 500

    digest_md = data.get("digest_md") or ""
    gameplan_md = data.get("gameplan_md")
    context_summary = data.get("context_summary_7_14") or ""

    try:
        answer = _ask_gemini(question, digest_md, gameplan_md, context_summary)
        return {"answer": answer}
    except RuntimeError as e:
        logger.warning("ask_gemini failed: %s", e)
        return {"error": str(e)}, 503
    except Exception as e:
        logger.exception("ask_gemini failed: %s", e)
        return {"error": str(e)}, 500


@app.route("/api/latest")
def api_latest():
    """Return latest digest + gameplan JSON, or 404 if not yet generated."""
    if not LATEST_JSON.exists():
        return {"error": "No digest yet. The daily pipeline has not run."}, 404
    try:
        data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        logger.exception("Error reading latest.json: %s", e)
        return {"error": str(e)}, 500


# Static assets under /viewer/ for any relative paths the HTML might request
@app.route("/viewer/<path:filename>")
def viewer_static(filename: str):
    return send_from_directory(VIEWER_DIR, filename)


def start_scheduler() -> None:
    """Schedule the daily pipeline at 06:00 UTC and run once on startup (background)."""
    import threading

    def run_once_after_startup() -> None:
        import time
        time.sleep(10)  # Let the web server bind first
        run_daily_pipeline()

    threading.Thread(target=run_once_after_startup, daemon=True).start()

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_pipeline, "cron", hour=6, minute=0)
    scheduler.start()
    logger.info("Scheduler started: daily pipeline at 06:00 UTC and once after startup")


# Start scheduler when app is loaded (so it runs under gunicorn too)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
start_scheduler()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    app.run(host="0.0.0.0", port=port, debug=False)
