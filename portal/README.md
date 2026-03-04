# Homework Portal

Multi-user Next.js portal for managing courses, syllabi, and assignments. Powers a lockscreen-style homework widget.

## Quick start

```bash
npm install
npx prisma migrate dev
npx prisma db seed
npm run dev
```

- **Register** at http://localhost:3000/register
- **Seed user**: dev@example.com / password

## Features

- Auth (email/password + NextAuth)
- Courses: add, edit, delete
- Assignments: manual or AI-parsed from syllabi
- Syllabus upload (PDF, TXT) + Gemini parsing
- Widget view: today's assignments (lockscreen-style)
- Settings: store your Gemini API key (encrypted)

## API

- `GET /api/widget/today` – JSON of today's assignments
- `GET /api/widget/week` – JSON of next 7 days

## Environment

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Postgres URL (e.g. `postgresql://user:pass@localhost:5432/portal`). For local dev, use Docker Postgres or a cloud DB. |
| `NEXTAUTH_SECRET` | Signing secret |
| `NEXTAUTH_URL` | App URL (e.g. http://localhost:3000) |
| `APP_ENCRYPTION_KEY` | Optional; for Gemini key encryption |

## Deploy

Railway: add Postgres, set env vars, deploy. Use S3-compatible storage for syllabi in production (uploads/ is local-only).
