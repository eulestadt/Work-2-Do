# Deploying to Railway

The app runs the **viewer** (liquid glass & light UI), serves **GET /api/latest** (digest + gameplan JSON), and runs the **daily pipeline** (Populi scrape + digest + gameplan) once on startup and every day at **06:00 UTC**.

## One-time setup

1. **Create a Railway project** at [railway.app](https://railway.app) (no GitHub needed).
2. **Use the Dockerfile** – Railway will detect it and build the image (includes Playwright Chromium for the scraper).

### Deploy from local (no GitHub)

From your project directory:

```bash
# Install CLI once: npm i -g @railway/cli   (or: brew install railway)
railway login
railway init    # create a new project, or link to existing
railway up      # upload & deploy (uses Dockerfile)
```

- `railway up` uploads your code and triggers a build/deploy. No git push to GitHub required.
- To redeploy after changes, run `railway up` again.
- Railway uses `.gitignore` (and optionally `.railwayignore`) to decide what to upload; `.env` is ignored so it never gets sent.
3. **Set environment variables** in the Railway dashboard (Project → Variables). **Do not commit secrets.**

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `POPULI_USERNAME` | Yes (for scrape) | Your Populi login email |
   | `POPULI_PASSWORD` | Yes (for scrape) | Your Populi password |
   | `GEMINI_API_KEY` | Yes (for gameplan) | From [Google AI Studio](https://aistudio.google.com/apikey) |
   | `SENDGRID_API_KEY` | For email | API key from [SendGrid](https://sendgrid.com) (Mail Send permission) |
   | `EMAIL_FROM` | For email | Verified sender address in SendGrid |
   | `EMAIL_TO` | Optional | Recipient for gameplan email (default: phoenix.wang24@sattler.edu) |
   | `REFERENCE_TIMEZONE` | Optional | Timezone for "today" (e.g. `America/New_York`). If unset, uses server time (UTC). Fixes gameplan showing wrong date when server is ahead of your local time. |

4. **Generate a domain** – In Railway, open your service → Settings → Generate Domain. Use that URL to open the site.

## What runs

- **Web**: Flask serves `/` (viewer) and `/api/latest` (JSON). Gunicorn binds to `PORT` set by Railway.
- **Scheduler**: On startup, the pipeline runs once after ~10 seconds, then daily at 06:00 UTC. Pipeline = fetch-populi → extract_syllabus_text → parse_syllabi_with_gemini (Gemini 2.5 parses all syllabus PDFs; replaces regex + enrichment) → gameplan. Output is written to `output/latest.json`; then, if `SENDGRID_API_KEY` and `EMAIL_FROM` are set, the gameplan is emailed to `EMAIL_TO` via Twilio SendGrid.

## Security

- All secrets are read from **environment variables** (Railway Variables or local `.env`). No credentials are stored in the repo.
- `.env` is in `.gitignore` and is excluded from the Docker build via `.dockerignore`.

## Optional

- **Cron only, no scrape on startup**: To skip the “run once after startup” and only run at 06:00 UTC, remove or comment out the `run_once_after_startup` thread in `app.py` `start_scheduler()`.
- **Different schedule**: Edit the cron in `start_scheduler()` (e.g. `hour=7, minute=30` for 07:30 UTC).
