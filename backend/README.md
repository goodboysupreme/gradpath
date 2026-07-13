# GradPath API

Contract-first FastAPI backend for GradPath's SI, PS-II, placement, and off-campus workflows.

The public API surface is deliberately stateless at this stage. It provides domain contracts, the
BITS Superset resume template, evidence-linked requirement coverage, grounded resume/JD analysis,
private native-text document extraction, and permission-aware JD normalization without changing
the existing Next.js or Drizzle runtime. An isolated PostgreSQL catalog persistence layer and its
first Alembic migration are prepared offline, but no endpoint uses it and no live database has been
migrated.

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

Set a different random `GRADPATH_API_SOURCE_INGESTION_TOKEN` of at least 32 characters only for
trusted campus/ATS connector jobs. It must not be available to the user-facing Next.js proxy.
Privileged source normalization fails closed when this second credential is absent.

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
| `POST` | `/api/v1/documents/extract` | Internal PDF/DOCX native-text extraction |
| `GET` | `/api/v1/job-sources` | Source registry, integration status, and acquisition policy |
| `POST` | `/api/v1/job-descriptions/normalize` | Internal provenance validation and deterministic JD normalization |

## Catalog persistence deployment boundary

Alembic owns only the `career_catalog` PostgreSQL schema. Drizzle continues to own the existing
`public` schema; the catalog has no foreign key into `public.users`. Never use `npm run db:push` to
deploy or modify `career_catalog`, and do not use Drizzle schema push in production.

Render the migration without a database or secret:

```powershell
uv run python -m alembic -c alembic.ini upgrade head --sql
```

A live migration is intentionally fail-closed. Before applying it, baseline and back up the live
database, prove the restore procedure, and pre-create `gradpath_api_runtime` as a group role with
`NOLOGIN`, `NOSUPERUSER`, and `NOBYPASSRLS`. The Alembic connection must be a separate migration
owner; the future API login must be a non-owner member of `gradpath_api_runtime`. Set
`GRADPATH_API_DATABASE_URL` only in the Alembic process and then run:

```powershell
uv run python -m alembic -c alembic.ini upgrade head
```

The migration revokes PUBLIC and default privileges, forces row-level security on all four catalog
tables, grants the runtime role only the columns and operations needed for persistence, and never
grants access to encrypted authorization evidence. Application connections must not be the schema
owner, a superuser, or hold `BYPASSRLS`.

Public content deduplicates across trusted providers, while each immutable provenance receipt keeps
that provider's source/application URL, publication time, deadline, observation time, and source-run
binding. Synthetic practice receipts are structurally prevented from carrying live-listing metadata.

Only the safe `user_upload` source is seeded. Campus/provider/synthetic persistence stays disabled
until there is an authenticated Next.js principal bridge, an audited source-run registration path,
encryption and key rotation for authorization evidence, and per-user quotas. Do not manually mark a
privileged source active to bypass those prerequisites.

## Authorized JD sources

`GET /api/v1/job-sources` is a declarative registry, not a crawler. It records user uploads,
authorized campus imports, synthetic practice content, and planned official API adapters for
Greenhouse, Lever, Ashby, and SmartRecruiters. The policy forbids authenticated-page scraping and
token discovery. Provider adapters remain `planned`; this endpoint performs no network requests.

`POST /api/v1/job-descriptions/normalize` requires the internal API token. The user-facing proxy
may submit only `user_upload`; the backend derives `user_private`, `user_asserted`, and
`private_analysis_only`. Campus, synthetic, and official-provider records additionally require the
separate source-ingestion credential. Their access, verification, and catalog eligibility are
derived by the backend rather than accepted from request fields, and connector schema versions are
allowlisted per source. A campus authorization reference is bounded, treated as secret audit
evidence, omitted from output and fingerprints, and protected by route-scoped sanitized validation
responses. The raw JSON request is capped at 1 MiB before parsing.

Provider source URLs must be canonical HTTPS URLs on the declared provider host and are never
fetched by the normalizer. Ashby identities must contain the declared account and a posting path;
application links cannot target local, private, or reserved IP space. Synthetic practice records
cannot contain application/source URLs or live publication/deadline metadata. Normalized content
uses Unicode NFKC plus whitespace and case normalization inside a versioned, domain-separated
canonical JSON SHA-256 fingerprint. The public fingerprint is content metadata, not proof of
authenticity or an authorization primitive. Future persistence must scope private deduplication by
authenticated owner and campus deduplication by a trusted campus identifier.

## Private document extraction

`POST /api/v1/documents/extract` accepts exactly one multipart `kind` (`resume` or `jd`) and one
PDF or DOCX `file`. It requires the internal-token header, authenticates before parsing the form,
and returns `Cache-Control: no-store`. Upload bytes are capped at 10 MiB from the data actually
read; PDF limits are 10 resume pages and 30 JD pages; normalized output is capped at 250,000
characters. DOCX `pageCount` is `null` because OOXML does not contain reliable rendered
pagination.

Extraction is native text only and explicitly reports `layoutPreserved: false`; scanned or
image-only PDFs return a sanitized OCR-required error. Files are not durably persisted, although
Starlette may spool larger multipart uploads to temporary disk until the request closes. Parser
work runs in a cancellable, time-bounded worker process behind a two-job capacity gate. DOCX
packages are checked for exact OOXML content type, traversal, encryption, macros, embedded/ActiveX
payloads, dangerous XML declarations, duplicate members, unsupported compression, and archive
expansion limits before parsing. The deployment proxy must enforce the same whole-request limit,
disable request-body logging/caching, authorize the student session, and apply per-user quotas.

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
