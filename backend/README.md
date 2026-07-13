# GradPath API

Contract-first FastAPI backend for GradPath's SI, PS-II, placement, and off-campus workflows.

This first slice is deliberately stateless. It adds domain contracts, the BITS Superset resume
template definition, and evidence-linked requirement coverage without changing the existing
Next.js or Drizzle runtime.

## Run locally

```powershell
cd C:\Users\Vansh Malik\Desktop\my_work_with_grok\backend
uv sync --python 3.12 --dev
Copy-Item .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the generated API documentation.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health/live` | Process liveness |
| `GET` | `/health/ready` | Service readiness |
| `GET` | `/api/v1/capabilities` | Supported career tracks and workflows |
| `GET` | `/api/v1/resume-templates/bits-superset-v1` | BITS Superset one-page template contract |
| `POST` | `/api/v1/coverage/evaluate` | Evidence-linked JD requirement coverage |

## Verify

```powershell
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
uv run ruff check .
uv run ruff format --check .
uv run pyright
```
