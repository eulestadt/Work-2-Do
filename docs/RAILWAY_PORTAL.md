# Deploying the Homework Portal to Railway

This guide covers deploying the **Generalized Homework Portal** (Next.js app in `portal/`) to Railway so the iOS GetWorkToDo app can use it as its backend.

The portal is **separate** from the Flask app (`app.py`). You can run both:
- **Flask app** – Populi pipeline, viewer, daily gameplan email (see [RAILWAY.md](./RAILWAY.md))
- **Portal** – Multi-user homework management, syllabus parsing, app-facing API

---

## 1. Prerequisites

- Railway account at [railway.app](https://railway.app)
- Railway CLI: `npm i -g @railway/cli` or `brew install railway`

---

## 2. PostgreSQL

The portal uses PostgreSQL (required for Railway). For local dev, use Docker Postgres or a cloud DB (e.g. Neon):

```bash
# Example: Docker Postgres
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=portal postgres:16
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/portal"
cd portal && npx prisma migrate dev
```

---

The start script runs migrations before starting (`prisma migrate deploy && next start`).

---

## 4. Create Railway Project and Deploy

### Option A: Deploy from local (no GitHub)

```bash
cd /path/to/get-work-to-do
railway login
railway init   # Create new project or link existing
```

1. In Railway dashboard: **New → Database → PostgreSQL** (add Postgres).
2. **New → Empty Service** for the portal.
3. In the portal service: **Settings → Root Directory** → set to `portal`.
4. **Variables** – Railway will inject `DATABASE_URL` if you link the Postgres service. Add:

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `DATABASE_URL` | Yes | Auto-set if Postgres is linked; otherwise paste the Postgres connection URL |
   | `NEXTAUTH_SECRET` | Yes | Random string, e.g. `openssl rand -base64 32` |
   | `NEXTAUTH_URL` | Yes | Your portal URL, e.g. `https://your-portal.up.railway.app` |
   | `APP_ENCRYPTION_KEY` | Recommended | 32-byte hex for Gemini key encryption, e.g. `openssl rand -hex 32` |

5. **Settings → Generate Domain** to get the public URL.
6. Deploy:

   ```bash
   railway up
   ```

   If the project has multiple services, select the portal service: `railway link` first, or use `railway up --service <service-id>`.

### Option B: Deploy via GitHub

1. Connect the repo to Railway.
2. Add Postgres (New → Database → PostgreSQL).
3. New service from the same repo.
4. Set **Root Directory** to `portal`.
5. Set variables as above.
6. Deploy on push.

---

## 5. Post-Deploy: First User and App Connection

1. Open your portal URL (e.g. `https://your-portal.up.railway.app`).
2. **Register** at `/register` (create an account).
3. **Add a course** and optionally **upload a syllabus** (Settings → Gemini to add your API key for parsing).
4. **Settings → App connection**:
   - Copy the **Base URL** (your Railway domain).
   - Click **Generate API key** and copy the key (it’s shown only once).

---

## 6. Connect the iOS App

1. Open the GetWorkToDo app → **Settings**.
2. **Backend URL**: paste your portal URL, e.g. `https://your-portal.up.railway.app`.
3. **API key**: paste the key from Settings → App connection.
4. Tap **Save**.

The app will call:
- `GET /api/latest` – assignments, gameplan, digest
- `POST /api/ask_gemini` – questions about your schedule
- `POST /api/assignments/[id]/complete` – toggle completion

---

## 7. Troubleshooting

| Issue | Fix |
|-------|-----|
| "Could not find production build" | Ensure Root Directory is `portal` and build runs `next build`. |
| Prisma "schema not found" | Root Directory must be `portal` so `prisma/` is in the build context. |
| 401 on `/api/latest` | API key is required. Generate one in Settings → App connection and add it in the app. |
| "Gemini API key not configured" | Add your Gemini key in Settings → Gemini (for gameplan and Ask Gemini). |
| Migrations fail | Ensure `DATABASE_URL` is set and Postgres is linked. Run `prisma migrate deploy` manually if needed. |

---

## 8. Summary

| Step | Action |
|------|--------|
| 1 | Create Railway project, add Postgres, add portal service with **Root Directory** `portal` |
| 2 | Set `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `APP_ENCRYPTION_KEY` (and `DATABASE_URL` if not linked) |
| 3 | Generate domain, deploy |
| 4 | Register at the portal, add Gemini key in Settings, generate app API key in Settings → App connection |
| 5 | In iOS app: set Backend URL and API key, tap Save |
