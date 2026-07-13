# GradPath API

Contract-first FastAPI backend for GradPath's SI, PS-II, placement, and off-campus workflows.

The backend is deliberately stateless at this stage. It provides domain contracts, the BITS
Superset resume template, evidence-linked requirement coverage, and grounded resume/JD analysis
without changing the existing Next.js or Drizzle runtime.

## Run locally

```powershell
cd C:\Users\Vansh Malik\Desktop\my_work_with_grok\backend
uv sync --python 3.12 --dev
Copy-Item .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

Set a random `GRADPATH_API_INTERNAL_API_TOKEN` of at least 32 characters, the server-side
`GRADPATH_API_OPENROUTER_API_KEY`, and an explicitly approved `GRADPATH_API_OPENROUTER_MODEL`
before enabling AI analysis. A blank token, key, or model keeps the route unavailable. The
internal token belongs only in the Next.js server route; never expose it through a
`NEXT_PUBLIC_*` variable or browser request.

Open `http://localhost:8000/docs` for the generated API documentation.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health/live` | Process liveness |
| `GET` | `/health/ready` | Service readiness |
| `GET` | `/api/v1/capabilities` | Supported career tracks and workflows |
| `GET` | `/api/v1/resume-templates/bits-superset-v1` | BITS Superset one-page template contract |
| `POST` | `/api/v1/coverage/evaluate` | Evidence-linked JD requirement coverage |
| `POST` | `/api/v1/analyses/evaluate` | Internal, evidence-grounded resume/JD readiness analysis |

## Grounded analysis

`POST /api/v1/analyses/evaluate` accepts JSON with `jdText`, `resumeText`, optional target context,
`intakeMode`, an optional `track`, and the explicit consent flag `allowRemoteProcessing: true`.
Calls require the `X-GradPath-Internal-Token` header. Before provider processing, the service
best-effort redacts common email, phone, BITS ID, URL, social-handle, date-of-birth, and explicitly
labelled name/address patterns. This is not de-identification. OpenRouter routing requires
providers that deny data collection and support zero-data retention; production must use a
dedicated key with account-level prompt logging disabled.

The future authenticated Next.js proxy must obtain this consent from an explicit student action,
show that resume/JD content is sent to OpenRouter, and persist the consent version and timestamp.
It must never synthesize `allowRemoteProcessing` on the student's behalf. Keep this backend private
to that proxy and add per-user rate and cost limits before enabling it for students.

The response preserves the existing core frontend fields such as `matchScore`, `strengths`,
`gaps`, `projects`, `roadmap`, and `resumeBullets`. `matchScore` is deterministic lexical coverage,
not a hiring probability, and `scoreConfidence` shows how much detected skill evidence supports
it. The response also includes deterministic `preAnalysis` counts and source `grounding`
citations. Strengths and JD gaps are rejected when their evidence cannot be found in the supplied
documents or their skill labels are not lexically supported by those excerpts. All model-authored
analysis is returned with `analysisNeedsConfirmation: true`. Resume bullet suggestions must be
extractive and are separately returned with `resumeBulletsNeedConfirmation: true`; the student
must verify all generated guidance before use. Provider failures return sanitized errors and never
fall back to invented content.

This internal endpoint is not a drop-in replacement for the current Next.js page envelope. Its
server-side proxy must add the persisted analysis `id` and target context, and translate FastAPI's
`detail` error into the frontend `error` shape. The `PS2` track currently supplies career-track
context only; PS-II station/allotment-specific reasoning belongs in a later workflow.

## Verify

```powershell
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
uv run ruff check .
uv run ruff format --check .
uv run pyright
```
