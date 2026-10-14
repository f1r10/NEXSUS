# NEXUS implementation record — initial milestone

## Invariants

1. A global identifier or external social account identity cannot imply permission to see another Case.
2. Case-specific names, assertions, evidence, observations, analyst notes and review decisions remain Case-scoped.
3. Every material association must disclose confidence/review status and original provenance; follow ≠ personal acquaintance; name similarity ≠ person identity.
4. All API endpoints must authorize server-side, before querying or returning data. Side-channel counts and graph/semantic results must also obey access controls.
5. All external OSINT connectors are disabled unless independently reviewed and allowed by the organization and platform terms.
6. Source artifacts should be immutable; later extraction and normalization jobs must preserve lineage.

## Current entity model

`User -> LoginSession`; `Workspace -> Case -> CaseMember`; `GlobalEntity -> CaseEntity -> Assertion / Relationship`; `Evidence` text source per Case; `SocialAccount` globally keyed by platform + stable external ID, `CaseSocialAccount` holding case-local attribution and username; `SocialFollow` is a directed, time-stamped, case-specific observation bound to evidence; `TransformJob` stores local transform execution; `AuditEvent` is case-scoped.

The `GlobalEntity` table is *minimal* and does not store profile content. There is currently no automatic cross-case global identity matching, no cross-case notification visibility, and no merging of duplicates. This is intentional while the full policy engine is incomplete.

## API contract summary

All paths are prefixed `/api/v1`.

- `GET /health`, `GET /auth/setup-required` — unauthenticated health/initial setup status.
- `POST /auth/bootstrap` — initial admin, `X-Bootstrap-Token` header, single-use semantics.
- `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` — server-side cookie session. POST endpoints after login require `X-CSRF-Token` returned from login/me.
- `POST /users`, `POST /workspaces` — platform administrator.
- `GET /workspaces`, `GET /cases` — authorized metadata only.
- `POST /workspaces/{id}/cases` — administrator; creator added as Case Manager.
- `POST /cases/{id}/members` — Case Manager.
- `GET|POST /cases/{id}/entities` — case-scoped search/create.
- `POST /cases/{id}/evidence/text`, `GET /cases/{id}/evidence` — text evidence; content SHA-256.
- `POST /cases/{id}/entities/{entity_id}/assertions` — proposed assertions.
- `POST /cases/{id}/relationships`, `POST /cases/{id}/relationships/{id}/review` — reviewable edges.
- `GET /cases/{id}/graph` — limited nodes/edges; `truncated` flag.
- `GET|POST /cases/{id}/social/accounts`, `GET|POST /cases/{id}/social/follows` — case-scoped social observations.
- `GET|POST /cases/{id}/transforms` — only local `graph.neighbors` currently.
- `GET /cases/{id}/audit` — Case Manager/Reviewer.

### Policy and data-layer gaps before production

- `Base.metadata.create_all` is currently a development bootstrap; replace with explicit reviewed Alembic migrations and rollback plans.
- PostgreSQL Row-Level Security and DB role separation are not yet deployed.
- Current text evidence is NOT immutable WORM storage and hash is only a byte-integrity check, not proof of authenticity.
- The supplied diagram positions are client-only; no server-side large-graph engine yet.
- Provenance for relations can be supplied from local case text evidence; accepted edges require it. Assertions still lack a dedicated review endpoint.
- Social data ingest is manual. Profile/post/comment ingestion, snapshots, collection-coverage completeness, and OSINT connectors are not implemented.
- Audit records are stored in SQL only and are not independently signed or append-only.
- Backup and disaster recovery RPO/RTO are design targets, not measured or verified.
- No real benchmark for 25–100 concurrent users, 100 GB–1 TB evidence yet.

## Intended approved decisions (not all implemented)

- On-prem, air-gapped / offline-first, Azerbaijani primary UI, 25–100 users.
- Modular monolith: Next.js + FastAPI + PostgreSQL + MinIO + isolated Python workers.
- Evidence and automated extraction kept distinct from analyst-approved claims.
- Case-specific visibility policy; classification L0–L4; no cross-case existence leak where prohibited.
- Hybrid internal search + explicitly authorized external OSINT extension.
- Shared physical blob storage *only* within compatible storage/security domains; separate Case permissions.
- Graph + timeline + map + Investigation Canvas; AI suggestions always linked to source and reviewed.

## Release acceptance milestones

- Phase 1: health, bootstrap, create Workspace/Case, members, entities, text evidence, reviewable links, case-isolation tests, UI navigation.
- Phase 2: full RLS and classification tests, independent sessions, audit immutability, backup/restore.
- Phase 3: immutable raw evidence storage, file/PDF/OCR ingest and provenance.
- Phase 4: approved connectors, rate limits, cost caps, worker recovery, cancellation.
- Phase 5: enrichment UI, profiles/posts/comments, entity matching and social provenance with real test fixtures.
