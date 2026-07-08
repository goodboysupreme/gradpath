# GradPath

BITS Pilani placement readiness tool. Point at a company + role, drop a resume (or fill a profile), get gaps, projects, prep topics, and an attack plan.

## Stack

- **Next.js 15** (App Router) + React 19 + Tailwind 4
- **Auth.js** (Google, BITS-domain gate)
- **Neon Postgres** + Drizzle ORM
- **OpenRouter** for LLM analysis
- **Python** pre-analysis (keyword overlap) with JS fallback
- **unpdf** + **tesseract.js** for resume PDF/OCR

## Setup

```powershell
cd Desktop\my_work_with_grok
npm install
copy .env.example .env.local
```

Fill `.env.local`:

| Var | Where |
|-----|--------|
| `AUTH_SECRET` | `openssl rand -base64 32` (or any long random string) |
| `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET` | [Google Cloud Console](https://console.cloud.google.com/) OAuth client. Redirect URI: `http://localhost:3000/api/auth/callback/google` |
| `DATABASE_URL` | [Neon](https://neon.tech) Postgres connection string |
| `OPENROUTER_API_KEY` | [OpenRouter](https://openrouter.ai/keys) |
| `BITS_ALLOWED_DOMAINS` | default `bits-pilani.ac.in` |

Push schema:

```powershell
npm run db:push
```

Dev server:

```powershell
npm run dev
```

Open http://localhost:3000

## Scripts

| Command | What |
|---------|------|
| `npm run dev` | Dev server |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run db:push` | Push Drizzle schema to Neon |
| `npm run db:studio` | Drizzle Studio |
| `npm run preanalyze` | Run Python keyword pre-analysis CLI |

## App routes

- `/` — landing + BITS Google sign-in
- `/analyze` — readiness console (protected)
- `/history` — past runs
- `/api/analyze` — analysis endpoint
- `/api/auth/*` — Auth.js

## Notes

- Daily analysis limit: `DAILY_LIMIT` (default 5)
- Access restricted to BE / MTech + allowed email domains
- Python pre-analysis is optional; JS fallback runs if Python fails
