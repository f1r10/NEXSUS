# NEXUS Intelligence Platform

**Status: v0.1 engineering foundation — not production-ready.**

NEXUS is an offline-first, case-isolated investigation workspace. The initial, demonstrable vertical slice provides an Azerbaijani Next.js UI, a FastAPI/PostgreSQL backend, protected user sessions, Case membership authorization, case-scoped entities, case-scoped text evidence, proposed/reviewed relationships, a visual graph explorer, case-scoped social accounts/follow observations, and a single explicitly local graph transform.

NEXUS does **not** yet collect real social-media data, bypass site access restrictions, import PDFs, parse OCR, serve maps, or perform AI entity resolution. There is no live RapidAPI integration in this milestone. The app makes no claims that people with a social relationship are personally acquainted; graph edges retain review status and, when confirmed, require evidence.

## Architecture

- `frontend/` — Next.js App Router + TypeScript, Azerbaijani interface, Arial typography, responsive layout.
- `backend/` — FastAPI, SQLAlchemy 2, PostgreSQL, server-side opaque-cookie sessions with CSRF protection, case authorization.
- `backend/tests/` — regression tests for security boundaries and core workflows.
- `docker-compose.yml` — PostgreSQL, backend, frontend. Ports bound to `127.0.0.1` by default.
- `.github/workflows/ci.yml` — backend tests and frontend build.
- `docs/` — design boundaries, API, operational notes, roadmap.

## Local quick start (Docker)

Requires Docker Engine and Docker Compose plugin.

```bash
cp .env.example .env
# Set secure values for POSTGRES_PASSWORD and NEXUS_BOOTSTRAP_TOKEN.
# Example generators:
python -c "import secrets; print(secrets.token_urlsafe(40))"
docker compose up --build -d
docker compose ps
```

Open `http://localhost:3000` and complete **İlkin quraşdırma** with the value of `NEXUS_BOOTSTRAP_TOKEN`, a local administrator email and a password with at least 12 characters. API health: `http://localhost:8000/api/v1/health`; OpenAPI: `http://localhost:8000/docs`.

**Security:** The default compose setup is strictly a local development deployment. Do not bind it to a public address or add real operational data. Put TLS, secure cookies, backup, access policies, migration management, virus scanning, audit integrity protection, secrets management, and independent security verification in place before any production deployment. Use `NEXUS_COOKIE_SECURE=true` behind HTTPS; for production put frontend/API under one controlled HTTPS origin.

## Local quick start (without Docker)

Backend (Python 3.12+):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./nexus.db
export NEXUS_BOOTSTRAP_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(40))')"
python -m app.init_db
uvicorn app.main:app --reload --port 8000
```

For frontend, in another terminal:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

SQLite is supported for local experimentation/tests only, not the production backend.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

A GitHub Actions workflow also installs frontend dependencies and performs a production build. CI has not been executed until this project is pushed to GitHub.

## Implemented permission boundaries

- The first administrator account requires an environment bootstrap token (>=32 chars) and is created once.
- All normal mutations require an authenticated session plus a CSRF header.
- Users only see Cases where they are members. A platform administrator does **not** automatically receive access to existing classified Case evidence.
- `viewer` is read-only; `analyst` and `reviewer` can propose data; only `reviewer` or `case_manager` can review relationships; only `case_manager` can manage membership.
- Cross-case foreign keys supplied to entity relationship or social-follow endpoints are rejected, even if the current user can access both cases.
- Verified relationships cannot be approved without a case-scoped evidence reference.
- No external connector may run in this version. The sole transform `graph.neighbors` traverses approved/proposed local case records and returns review statuses in the graph view.

**Limitations:** Application-level access checks are implemented, but production-grade PostgreSQL RLS, classification-level policy engine, multi-person approval, global matching notifications, ShareGrant workflows, immutable MinIO evidence ingest, append-only audit integrity, cryptographic domain isolation, and encryption key lifecycles are future work.

## Documented development sequence

1. v0.1 — API + frontend + core Case isolation (this milestone).
2. Schema versioning (Alembic), PostgreSQL RLS + policy decision tests, bootstrapping hardening.
3. EvidenceFile / ExtractionRun / SourceFragment, MinIO immutable object ingest, storage-domain encryption + dedup boundaries.
4. Connector registry, signed manifests, controlled RapidAPI integrations **where permitted**, quota/cost/rate limits, durable background queue.
5. SocialPost / SocialComment / snapshots + entity resolution and human review/merge/unmerge.
6. Graph traversal and large graph visualization, full Person Intelligence profile and Investigation Canvas.
7. Local OCR/NER, semantic search, timeline, maps, audited exports, backup/restore and performance benchmarks.

For engineering detail see `docs/ARCHITECTURE.md`.

## Responsible use

Only collect data you are authorized to access, in accordance with applicable law and provider terms. Avoid storing secrets, personal data, or real evidence in this public repository. NEXUS is intended for legitimate investigative analysis with documented purpose, scoped access and human review.
