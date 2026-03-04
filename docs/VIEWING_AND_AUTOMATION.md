# Viewing the digest & gameplan, and daily automation

## Quick start: beautiful local view

1. Generate digest (and optional gameplan):
   ```bash
   python -m src.cli --fetch-populi --gameplan
   ```
   Or without re-fetching Populi: `python -m src.cli --gameplan`

2. Serve the viewer from the **project root**:
   ```bash
   python -m http.server 8765
   ```
   Then open: **http://localhost:8765/viewer/**

   You’ll see the gameplan (“What should I work on?”) and the full digest. Don’t miss anything: the full digest is in the “Full digest” section below.

3. **API key (gameplan):** Put your Gemini API key in a `.env` file in the project root (never commit it):
   ```
   GEMINI_API_KEY=your_key_here
   ```
   Get a key at [Google AI Studio](https://aistudio.google.com/apikey). The key is only used locally when you run `--gameplan`; it is never sent anywhere except Google’s API.

---

## Daily automation

Run the pipeline once per day so the digest and gameplan stay current.

### Option 1: Mac / Linux – cron

```bash
# Edit crontab
crontab -e

# Run every day at 6:00 AM (fetch Populi + digest + gameplan)
0 6 * * * cd /path/to/get-work-to-do && .venv/bin/python -m src.cli --fetch-populi --gameplan
```

Use your actual project path. Ensure `.env` is in the project root so `GEMINI_API_KEY` and `POPULI_*` are available (cron usually has a minimal env, so you may need to source a file or put the vars in crontab).

### Option 2: Mac – launchd (recommended on Mac)

Create `~/Library/LaunchAgents/com.getworktodo.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.getworktodo.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/get-work-to-do/.venv/bin/python</string>
    <string>-m</string>
    <string>src.cli</string>
    <string>--fetch-populi</string>
    <string>--gameplan</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/get-work-to-do</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/tmp/get-work-to-do.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/get-work-to-do.err</string>
</dict>
</plist>
```

Then:

```bash
launchctl load ~/Library/LaunchAgents/com.getworktodo.daily.plist
```

Populi scraping needs a logged-in session with a browser; see “Important” below.

### Option 3: Raspberry Pi (e.g. for e-ink)

- Install the project and dependencies on the Pi (including Playwright if you scrape there).
- Run the same CLI command on a schedule (cron):
  ```bash
  0 6 * * * cd /path/to/get-work-to-do && .venv/bin/python -m src.cli --fetch-populi --gameplan
  ```
- Use `output/latest.json` or the markdown files to drive your e-ink display (e.g. a small Python or Node script that renders the digest/gameplan to the display). The viewer HTML can be adapted to a minimal layout for e-ink (high contrast, few fonts).

---

## Viewing on different devices

### Mac (sidebar / always visible)

- **Browser window:** Keep a tab open to `http://localhost:8765/viewer/` (with the server running). Pin the tab.
- **Menu bar / sidebar:** Use a menu-bar browser or “open in sidebar” if your browser supports it; or run the viewer in a small standalone window (e.g. Electron or native wrapper) that loads the same URL.

### iPad (homescreen “app”)

1. On your Mac (or a machine that can serve the files), run `python -m http.server 8765` from the project root.
2. On iPad, in Safari open `http://<your-mac-ip>:8765/viewer/` (use your Mac’s local IP, e.g. 192.168.1.x).
3. Tap Share → “Add to Home Screen”. You get an icon that opens the viewer like an app.

For this to work when you’re away from home, you’d need the viewer and `output/latest.json` to be reachable (e.g. via Railway or a tunnel like ngrok).

### Railway (web-hosted viewer)

So that you don’t miss anything when you’re not on your home network:

1. **What to deploy:** A tiny static server that serves the `viewer/` folder and a single JSON endpoint that returns the contents of `output/latest.json`.
2. **Data flow:** The digest and gameplan are generated **on your machine** (or Pi) where Populi scraping runs. Then either:
   - **Push:** A script (run after `src.cli`) POSTs `output/latest.json` to a small Railway backend that stores it and serves it at e.g. `GET /output/latest.json`, or
   - **Sync:** You use a file-sync (e.g. Dropbox, iCloud) to sync the `output/` folder to a machine that Railway can read from (more involved).

Recommended: a minimal Railway app with one protected POST endpoint (e.g. API key in header) to upload `latest.json`, and a GET that returns it. The existing `viewer/index.html` can point to your Railway URL for the JSON so the same viewer works on the web.

### Raspberry Pi + e-ink

- Run the scraper + CLI on the Pi (or copy `output/` from another machine).
- A separate script reads `output/latest.json` (or the markdown files) and renders to the e-ink display (e.g. using the display’s Python library). You can strip HTML and use plain text or a simple layout so nothing important is missed.

---

## Important: Populi scraping and automation

- Populi scraping uses **Playwright** and needs to **log in** (username/password from `.env`). In a headless cron job, login may fail or require 2FA.
- **Practical approach:** Run **with a display** at least once per day (e.g. when you sit down at your Mac), or run the scraper manually when you know you’re logged in, then use cron only for `python -m src.cli --gameplan` (no `--fetch-populi`) so it just regenerates the digest and gameplan from the last cached data.
- Alternatively, run the full command (`--fetch-populi --gameplan`) once daily from a GUI launcher or a shortcut so the browser can open if needed.

---

## Summary

| Goal                         | What to do |
|-----------------------------|------------|
| View locally, don’t miss anything | Run `python -m src.cli --gameplan`, then `python -m http.server 8765` and open **http://localhost:8765/viewer/** |
| Daily automation            | Cron or launchd running `src.cli --fetch-populi --gameplan` (or without `--fetch-populi` if you scrape by hand) |
| iPad homescreen             | Serve from Mac, open viewer URL in Safari, “Add to Home Screen” |
| Railway                     | Deploy a small backend that accepts an upload of `latest.json` and serves it; point the viewer at that URL |
| Pi + e-ink                  | Run CLI (or sync `output/`), then a script that reads `latest.json` and drives the e-ink display |

Keep **GEMINI_API_KEY** and **POPULI_*** only in `.env` (or environment) and never commit them.
