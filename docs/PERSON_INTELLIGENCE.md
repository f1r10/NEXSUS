# NEXUS v0.2: Person Intelligence and File Evidence

## Intent

This is a **development vertical slice**, not a complete OSINT collection or production investigative service. It supports human-controlled ingestion of authorized data from documents or API snapshots. No external OSINT providers are activated and no private social-platform access is automated.

## API contracts

Every endpoint below requires a session cookie. Mutating endpoints require `X-CSRF-Token`. Resource IDs must belong to the `case_id` in the route, or the API returns `404` even when the caller has access to some other Case.

| Method | Endpoint | Scope |
|---|---|---|
| GET | `/api/v1/people/search?q=...` | Person search limited to member Cases |
| GET | `/api/v1/cases/{case_id}/people/{person_id}/profile` | Profile, assertions, relationships, approved accounts, candidate attributions and approved-account posts |
| POST/GET | `/api/v1/cases/{case_id}/social/posts` | Platform post observation; requires Case-local account and evidence |
| POST/GET | `/api/v1/cases/{case_id}/social/comments` | Comment observation; requires Case-local post, author and evidence |
| POST | `/api/v1/cases/{case_id}/social/profile-snapshots` | Profile snapshot with evidence and observation timestamp |
| GET | `/api/v1/cases/{case_id}/social/accounts/{account_id}/profile-snapshots` | Profile history for authorized account |
| POST/GET | `/api/v1/cases/{case_id}/social/attributions` | Suggest account-to-person match with mandatory evidence |
| POST | `/api/v1/cases/{case_id}/social/attributions/{id}/review` | Reviewer/Case Manager approves or rejects attribution |
| GET | `/api/v1/cases/{case_id}/social/graph` | Directional Account → Account `FOLLOWS` network |
| POST/GET | `/api/v1/cases/{case_id}/evidence/files` | Binary file upload/list (20 MB cap) |
| GET | `/api/v1/cases/{case_id}/evidence/files/{file_id}/download` | Server-side authenticated attachment download |

### Identity boundaries

- `CaseSocialAccount` is **not** synonymous with `CaseEntity(person)`.
- `AccountAttribution` proposals must reference a Case-local person, account and evidence.
- Only an **approved** attribution populates the person's confirmed accounts. Existing unverified candidate IDs do not satisfy this criterion.
- Social follow edges are direction-specific, versioned observations, not bidirectional relationships or claims that two people know one another.
- Posts/comments preserve their platform IDs, observation dates and source evidence references. Duplicate post/comment IDs within a Case are rejected.
- API lists are capped to bound processing; pagination and more complete snapshot coverage tracking are future work.

### File evidence

- Objects are placed in a **private** S3-compatible bucket (MinIO in the Compose development stack).
- A random UUID and Case namespace form the object key; there is **no global content hash lookup** and no deduplication or cross-Case content-existence oracle.
- API metadata stores the original name, SHA-256, media type, size and Case identity. Downloads are served as `application/octet-stream` with `Content-Disposition: attachment`, `nosniff`, and `no-store`.
- Bucket versioning/Object Lock, encryption-domain design, malware scanning, OCR, quotas per Case, streaming multipart uploads, orphan-object reconciliation and retention rules are not implemented yet.

## Next engineering priorities

1. Alembic migrations and explicit PostgreSQL RLS integration tests against PostgreSQL.
2. Signed connector registry, secrets isolation, API budgets, provider licensing, safe network egress, durable job state and retry.
3. Evidence processing pipeline (OCR, extracted fragments and source offsets).
4. Identity merge/unmerge with full lineage, share grants and audited cross-Case discovery.
5. Production MinIO/S3 credentials, backup/restore, WORM or Object Lock and storage-domain deduplication policy.
