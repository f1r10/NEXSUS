# NEXUS Intelligence Platform

**Current milestone: v0.2 development preview. Not production-ready.**

NEXUS is an offline-first, **Case-isolated** investigative evidence workspace. It is designed to unify people, source-backed claims, accounts, social activity and relationship graphs without conflating potential identity matches with verified facts.

## Current capabilities

- Azerbaijani Next.js frontend with workspace/Case navigation, Person Intelligence profile, local graph exploration, social activity, evidence and review UI.
- FastAPI + PostgreSQL backend with opaque HttpOnly sessions, CSRF checks, Case membership authorization and audit events.
- Case-scoped entities, assertions, text evidence, proposed/reviewed relationships and local `graph.neighbors` transform.
- Social accounts and directed follow observations, source-backed profile snapshots, posts, comments and **human-reviewed** account-to-person attribution. Profile API only lists **approved** attributed accounts.
- Case-filtered person search across only the user's member Cases. Global entity IDs do **not** grant global access.
- Case-scoped original-file upload/download to private MinIO (20 MB per file, SHA-256; **no cross-Case deduplication yet**).
- Automated API tests, frontend production build and Docker Compose syntax check in CI.

**Not included:** live RapidAPI/social connectors, private-account bypass, OCR, automated photo identification, multi-party approval, advanced identity resolution, import processing workers, graph-scale benchmarks, PostgreSQL RLS, WORM/virus scanning, full backup/restore, Alembic migrations or a full security audit. Do not use real classified investigations with this development preview.

## Technology

- `backend/` — FastAPI, SQLAlchemy, PostgreSQL; new Case-based APIs in `backend/app/routers/`.
- `frontend/` — Next.js, TypeScript, Azerbaijani interface and minimal Arial styling.
- `docker-compose.yml` — private PostgreSQL, private MinIO, bucket initialization, API and web frontend.
- `docs/` — architecture and v0.2 endpoint notes.

## Run on a development machine

Requires Docker Engine + Docker Compose plugin. Clone the repository and configure `.env`:

```bash
cp .env.example .env
# Generate independent secret values. Never commit .env.
python3 -c 'import secrets; print(secrets.token_urlsafe(40))'
# Set POSTGRES_PASSWORD, NEXUS_BOOTSTRAP_TOKEN and NEXUS_S3_SECRET_KEY in .env.
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Frontend: <http://localhost:3000>  
API health: <http://localhost:8000/api/v1/health>  
OpenAPI: <http://localhost:8000/docs>

The first admin setup requires the `NEXUS_BOOTSTRAP_TOKEN` (32+ characters). Login uses HttpOnly cookie sessions and CSRF protection. Only Cases of which the current user is a member are visible; admin status is **not** a blanket evidence-reading permission.

**Important network configuration:** The Compose example binds frontend and API only to `127.0.0.1` for local development; MinIO has **no host port**. Do not expose the stack to the internet. To use it over a secured internal network later, implement TLS reverse proxy, safe cookies, operational backups, scoped S3 credentials, secrets management, security review and authorization tests first.

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

All file-storage API tests use an isolated in-memory S3 test double. Tests do **not** certify that a MinIO image has been pulled or that a real deployment works; Docker Compose is syntactically validated in GitHub CI.

## Development and limitations

The database currently uses development-only `create_all` on startup. It adds missing tables, but cannot migrate existing columns safely. A versioned Alembic migration baseline is required before supported upgrades and production deployments. File originals are stored under random Case-specific keys; storage-domain deduplication and immutability enforcement are **future work**. The uploaded-file endpoint checks extensions and size but does not replace malware scanning or content parsing isolation.

The only active Transform is **local** `graph.neighbors`. OSINT provider integrations must be added through approved connectors, with authorization, terms of service, budgets and durable workers. No API output establishes that two social accounts refer to the same person until evidence-backed analyst review approves that attribution. A directed `FOLLOWS` relationship is not proof of real-world acquaintance.

Read `docs/ARCHITECTURE.md` and `docs/PERSON_INTELLIGENCE.md` for data contracts and next work.

## Responsible use

Collect and process personal information only with a documented legitimate purpose, a lawful basis and permissions appropriate to the source. Keep actual secrets and sensitive case material outside this **public** GitHub repository.
