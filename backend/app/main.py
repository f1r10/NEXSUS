"""NEXUS API v0.1: case-isolated investigation vertical slice.

No live OSINT providers are bundled: all social observations require explicit
case-scoped provenance, and external collectors must be separately approved.
"""
import hashlib
import os
import secrets
from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Assertion, AuditEvent, BootstrapGuard, Case, CaseEntity, CaseMember, CaseSocialAccount,
    Evidence, GlobalEntity, Relationship, SocialAccount, SocialFollow,
    TransformJob, User, Workspace,
)
from app.permissions import authorize_case
from app.security import (
    COOKIE_NAME, current_user, get_identity, hash_password, issue_session,
    require_admin, verify_password,
)

app = FastAPI(title="NEXUS Intelligence Platform", version="0.1.0")
origins = [x.strip() for x in os.getenv("NEXUS_CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token", "X-Bootstrap-Token"],
)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=256)


class NewUser(Credentials):
    display_name: str = Field(min_length=1, max_length=160)


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class CaseInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    classification: int = Field(default=2, ge=0, le=4)


class MemberInput(BaseModel):
    email: str
    role: str


class EntityInput(BaseModel):
    entity_type: str = Field(pattern="^(person|organization|device|digital_account|location|vehicle|event|document|other)$")
    display_name: str = Field(min_length=1, max_length=200)


class EvidenceInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100000)
    source_uri: str | None = Field(default=None, max_length=1000)


class AssertionInput(BaseModel):
    attribute: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=10000)
    evidence_id: UUID | None = None


class RelationInput(BaseModel):
    source_id: UUID
    target_id: UUID
    relation_type: str = Field(min_length=2, max_length=80)
    evidence_id: UUID | None = None


class ReviewInput(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


class SocialInput(BaseModel):
    platform: str = Field(pattern="^[a-z0-9_-]{2,50}$")
    external_id: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    attributed_entity_id: UUID | None = None


class FollowInput(BaseModel):
    follower_id: UUID
    followed_id: UUID
    evidence_id: UUID


class TransformInput(BaseModel):
    transform_name: str
    input_entity_id: UUID


def audit(db: Session, user: User, action: str, resource_id, case_id=None):
    db.add(AuditEvent(actor_id=user.id, case_id=case_id, action=action, resource_id=str(resource_id)))


def same_case(db: Session, model, entity_id, case_id):
    record = db.get(model, entity_id)
    if record is None or record.case_id != case_id:
        raise HTTPException(404, "Resurs tapılmadı")
    return record


def evidence_in_case(db: Session, case_id, evidence_id):
    if evidence_id is not None:
        same_case(db, Evidence, evidence_id, case_id)


def entity_dict(item: CaseEntity):
    return {"id": str(item.id), "entity_type": item.entity_type, "display_name": item.display_name}


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "nexus", "version": "0.1.0"}


@app.get("/api/v1/auth/setup-required")
def setup_required(db: Session = Depends(get_db)):
    return {"required": db.scalar(select(User.id).limit(1)) is None}


@app.post("/api/v1/auth/bootstrap", status_code=201)
def bootstrap_admin(payload: NewUser, response: Response,
                    x_bootstrap_token: str | None = Header(default=None),
                    db: Session = Depends(get_db)):
    secret = os.getenv("NEXUS_BOOTSTRAP_TOKEN", "")
    if not secret or len(secret) < 32:
        raise HTTPException(503, "İlkin quraşdırma açarı konfiqurasiya edilməyib")
    if not x_bootstrap_token or not secrets.compare_digest(x_bootstrap_token, secret):
        raise HTTPException(403, "İlkin quraşdırma açarı yanlışdır")
    if db.scalar(select(User.id).limit(1)) is not None:
        raise HTTPException(409, "Sistem artıq quraşdırılıb")
    # Unique DB guard closes the concurrent-initialization race (also on PostgreSQL).
    try:
        db.add(BootstrapGuard(id=1))
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Sistem artıq quraşdırılıb") from None
    user = User(email=payload.email.strip().lower(), display_name=payload.display_name.strip(),
                password_hash=hash_password(payload.password), is_admin=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, user, "auth.bootstrap", user.id)
    db.commit()
    csrf = issue_session(db, response, user)
    return {"id": str(user.id), "display_name": user.display_name, "is_admin": True, "csrf_token": csrf}


@app.post("/api/v1/auth/login")
def login(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None or not user.is_active or not verify_password(user.password_hash, payload.password):
        raise HTTPException(401, "Giriş məlumatları yanlışdır")
    csrf = issue_session(db, response, user)
    audit(db, user, "auth.login", user.id)
    db.commit()
    return {"id": str(user.id), "display_name": user.display_name, "is_admin": user.is_admin, "csrf_token": csrf}


@app.get("/api/v1/auth/me")
def me(identity=Depends(get_identity)):
    user, session = identity
    return {"id": str(user.id), "display_name": user.display_name, "email": user.email,
            "is_admin": user.is_admin, "csrf_token": session.csrf_token}


@app.post("/api/v1/auth/logout")
def logout(response: Response, identity=Depends(get_identity), db: Session = Depends(get_db)):
    user, session = identity
    session.revoked = True
    audit(db, user, "auth.logout", user.id)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.post("/api/v1/users", status_code=201)
def create_user(payload: NewUser, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Email artıq mövcuddur")
    user = User(email=email, display_name=payload.display_name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    audit(db, admin, "user.create", user.id)
    db.commit()
    return {"id": str(user.id), "email": user.email, "display_name": user.display_name}


@app.post("/api/v1/workspaces", status_code=201)
def create_workspace(payload: WorkspaceInput, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    ws = Workspace(name=payload.name.strip(), created_by=admin.id)
    db.add(ws)
    db.flush()
    audit(db, admin, "workspace.create", ws.id)
    db.commit()
    return {"id": str(ws.id), "name": ws.name}


@app.get("/api/v1/workspaces")
def list_workspaces(user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Admin receives workspace metadata only; not access to case evidence.
    if user.is_admin:
        rows = db.scalars(select(Workspace).order_by(Workspace.name)).all()
    else:
        rows = db.scalars(select(Workspace).join(Case).join(CaseMember).where(CaseMember.user_id == user.id).distinct()).all()
    return [{"id": str(w.id), "name": w.name} for w in rows]


@app.post("/api/v1/workspaces/{workspace_id}/cases", status_code=201)
def create_case(workspace_id: UUID, payload: CaseInput, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.get(Workspace, workspace_id) is None:
        raise HTTPException(404, "Workspace tapılmadı")
    case = Case(workspace_id=workspace_id, name=payload.name.strip(), classification=payload.classification,
                visibility_policy="disabled", created_by=admin.id)
    db.add(case)
    db.flush()
    db.add(CaseMember(case_id=case.id, user_id=admin.id, role="case_manager"))
    audit(db, admin, "case.create", case.id, case.id)
    db.commit()
    return {"id": str(case.id), "name": case.name, "classification": case.classification}


@app.get("/api/v1/cases")
def list_cases(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Case).join(CaseMember).where(CaseMember.user_id == user.id).order_by(Case.name)).all()
    return [{"id": str(c.id), "name": c.name, "classification": c.classification,
             "workspace_id": str(c.workspace_id)} for c in rows]


@app.post("/api/v1/cases/{case_id}/members", status_code=201)
def add_member(case_id: UUID, payload: MemberInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "manage")
    if payload.role not in {"case_manager", "analyst", "reviewer", "viewer"}:
        raise HTTPException(422, "Etibarsız Case rolu")
    target = db.scalar(select(User).where(User.email == payload.email.strip().lower(), User.is_active.is_(True)))
    if target is None:
        raise HTTPException(404, "İstifadəçi tapılmadı")
    if db.get(CaseMember, (case_id, target.id)) is not None:
        raise HTTPException(409, "Üzvlük mövcuddur")
    db.add(CaseMember(case_id=case_id, user_id=target.id, role=payload.role))
    audit(db, user, "case.member.add", target.id, case_id)
    db.commit()
    return {"user_id": str(target.id), "role": payload.role}


@app.post("/api/v1/cases/{case_id}/entities", status_code=201)
def add_entity(case_id: UUID, payload: EntityInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "write")
    global_entity = GlobalEntity(entity_type=payload.entity_type)
    db.add(global_entity)
    db.flush()
    local = CaseEntity(case_id=case_id, global_id=global_entity.id, entity_type=payload.entity_type,
                       display_name=payload.display_name.strip())
    db.add(local)
    db.flush()
    audit(db, user, "entity.create", local.id, case_id)
    db.commit()
    return entity_dict(local)


@app.get("/api/v1/cases/{case_id}/entities")
def find_entities(case_id: UUID, q: str = "", entity_type: str | None = None,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id)
    stmt = select(CaseEntity).where(CaseEntity.case_id == case_id)
    if q:
        stmt = stmt.where(CaseEntity.display_name.ilike(f"%{q[:100].replace('%','').replace('_','')}%"))
    if entity_type:
        stmt = stmt.where(CaseEntity.entity_type == entity_type)
    rows = db.scalars(stmt.order_by(CaseEntity.display_name).limit(100)).all()
    return [entity_dict(e) for e in rows]


@app.post("/api/v1/cases/{case_id}/evidence/text", status_code=201)
def add_evidence(case_id: UUID, payload: EvidenceInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "write")
    record = Evidence(case_id=case_id, title=payload.title.strip(), content=payload.content,
                      sha256=hashlib.sha256(payload.content.encode("utf-8")).hexdigest(),
                      source_uri=payload.source_uri, created_by=user.id)
    db.add(record)
    db.flush()
    audit(db, user, "evidence.text.create", record.id, case_id)
    db.commit()
    return {"id": str(record.id), "title": record.title, "sha256": record.sha256}


@app.get("/api/v1/cases/{case_id}/evidence")
def list_evidence(case_id: UUID, q: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id)
    stmt = select(Evidence).where(Evidence.case_id == case_id)
    if q:
        pattern = f"%{q[:100].replace('%','').replace('_','')}%"
        stmt = stmt.where(or_(Evidence.title.ilike(pattern), Evidence.content.ilike(pattern)))
    rows = db.scalars(stmt.order_by(Evidence.created_at.desc()).limit(100)).all()
    return [{"id": str(e.id), "title": e.title, "sha256": e.sha256,
             "content": e.content, "source_uri": e.source_uri} for e in rows]


@app.post("/api/v1/cases/{case_id}/entities/{entity_id}/assertions", status_code=201)
def add_assertion(case_id: UUID, entity_id: UUID, payload: AssertionInput,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "write")
    same_case(db, CaseEntity, entity_id, case_id)
    evidence_in_case(db, case_id, payload.evidence_id)
    record = Assertion(case_id=case_id, entity_id=entity_id, attribute=payload.attribute,
                       value=payload.value, evidence_id=payload.evidence_id)
    db.add(record)
    db.flush()
    audit(db, user, "assertion.propose", record.id, case_id)
    db.commit()
    return {"id": str(record.id), "review_status": record.review_status}


@app.post("/api/v1/cases/{case_id}/relationships", status_code=201)
def add_relation(case_id: UUID, payload: RelationInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "write")
    same_case(db, CaseEntity, payload.source_id, case_id)
    same_case(db, CaseEntity, payload.target_id, case_id)
    evidence_in_case(db, case_id, payload.evidence_id)
    if payload.source_id == payload.target_id:
        raise HTTPException(422, "Özünə əlaqə bu versiyada dəstəklənmir")
    relation = Relationship(case_id=case_id, source_id=payload.source_id, target_id=payload.target_id,
                            relation_type=payload.relation_type.upper(), evidence_id=payload.evidence_id)
    db.add(relation)
    db.flush()
    audit(db, user, "relationship.propose", relation.id, case_id)
    db.commit()
    return {"id": str(relation.id), "review_status": relation.review_status}


@app.post("/api/v1/cases/{case_id}/relationships/{relation_id}/review")
def review_relation(case_id: UUID, relation_id: UUID, payload: ReviewInput,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "review")
    relation = same_case(db, Relationship, relation_id, case_id)
    if relation.review_status != "proposed":
        raise HTTPException(409, "Qərar artıq verilib")
    if payload.decision == "approved" and relation.evidence_id is None:
        raise HTTPException(422, "Təsdiq üçün mənbə sübutu tələb olunur")
    relation.review_status = payload.decision
    audit(db, user, "relationship.review." + payload.decision, relation.id, case_id)
    db.commit()
    return {"id": str(relation.id), "review_status": relation.review_status}


@app.get("/api/v1/cases/{case_id}/graph")
def graph(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id)
    entities = db.scalars(select(CaseEntity).where(CaseEntity.case_id == case_id).order_by(CaseEntity.created_at).limit(200)).all()
    relationships = db.scalars(select(Relationship).where(Relationship.case_id == case_id).order_by(Relationship.created_at).limit(500)).all()
    allowed_ids = {e.id for e in entities}
    edges = [{"id": str(r.id), "source": str(r.source_id), "target": str(r.target_id),
              "label": r.relation_type, "status": r.review_status} for r in relationships
             if r.source_id in allowed_ids and r.target_id in allowed_ids]
    return {"nodes": [entity_dict(e) for e in entities], "edges": edges,
            "truncated": len(entities) == 200 or len(relationships) == 500}


@app.post("/api/v1/cases/{case_id}/social/accounts", status_code=201)
def add_account(case_id: UUID, payload: SocialInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "write")
    if payload.attributed_entity_id is not None:
        e = same_case(db, CaseEntity, payload.attributed_entity_id, case_id)
        if e.entity_type != "person":
            raise HTTPException(422, "Şəxs obyekti tələb olunur")
    global_account = db.scalar(select(SocialAccount).where(SocialAccount.platform == payload.platform,
                                                         SocialAccount.external_id == payload.external_id))
    if global_account is None:
        global_account = SocialAccount(platform=payload.platform, external_id=payload.external_id)
        db.add(global_account)
        db.flush()
    record = db.scalar(select(CaseSocialAccount).where(CaseSocialAccount.case_id == case_id,
                                                      CaseSocialAccount.account_id == global_account.id))
    if record is not None:
        raise HTTPException(409, "Hesab bu araşdırmada mövcuddur")
    record = CaseSocialAccount(case_id=case_id, account_id=global_account.id, username=payload.username,
                               attributed_entity_id=payload.attributed_entity_id, identity_status="unverified")
    db.add(record)
    db.flush()
    audit(db, user, "social.account.add", record.id, case_id)
    db.commit()
    return {"id": str(record.id), "platform": payload.platform,
            "username": record.username, "identity_status": record.identity_status}


@app.get("/api/v1/cases/{case_id}/social/accounts")
def social_accounts(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id)
    rows = db.execute(select(CaseSocialAccount, SocialAccount).join(SocialAccount, CaseSocialAccount.account_id == SocialAccount.id)
                      .where(CaseSocialAccount.case_id == case_id).limit(100)).all()
    return [{"id": str(a.id), "platform": s.platform, "username": a.username,
             "identity_status": a.identity_status, "attributed_entity_id": str(a.attributed_entity_id) if a.attributed_entity_id else None}
            for a, s in rows]


@app.post("/api/v1/cases/{case_id}/social/follows", status_code=201)
def add_follow(case_id: UUID, payload: FollowInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "write")
    same_case(db, CaseSocialAccount, payload.follower_id, case_id)
    same_case(db, CaseSocialAccount, payload.followed_id, case_id)
    evidence_in_case(db, case_id, payload.evidence_id)
    if payload.follower_id == payload.followed_id:
        raise HTTPException(422, "Özünə izləmə əlaqəsi etibarsızdır")
    record = SocialFollow(case_id=case_id, follower_id=payload.follower_id,
                          followed_id=payload.followed_id, evidence_id=payload.evidence_id)
    db.add(record)
    db.flush()
    audit(db, user, "social.follow.observe", record.id, case_id)
    db.commit()
    return {"id": str(record.id), "status": "observed"}


@app.get("/api/v1/cases/{case_id}/social/follows")
def list_follows(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id)
    rows = db.scalars(select(SocialFollow).where(SocialFollow.case_id == case_id).limit(200)).all()
    return [{"id": str(x.id), "follower_id": str(x.follower_id), "followed_id": str(x.followed_id),
             "evidence_id": str(x.evidence_id), "observed_at": x.observed_at.isoformat()} for x in rows]


@app.get("/api/v1/cases/{case_id}/transforms")
def available_transforms(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id)
    return [{"id": "graph.neighbors", "label": "Qraf qonşularını tap", "network_access": False,
             "description": "Yalnız bu Case-in mövcud əlaqələrini araşdırır"}]


@app.post("/api/v1/cases/{case_id}/transforms", status_code=201)
def run_local_transform(case_id: UUID, payload: TransformInput,
                        user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_case(db, user, case_id, "write")
    if payload.transform_name != "graph.neighbors":
        raise HTTPException(422, "Təsdiqlənməmiş Transform. Xarici OSINT connector-lar hələ aktiv deyil")
    same_case(db, CaseEntity, payload.input_entity_id, case_id)
    edges = db.scalars(select(Relationship).where(Relationship.case_id == case_id,
                 or_(Relationship.source_id == payload.input_entity_id,
                     Relationship.target_id == payload.input_entity_id)).limit(100)).all()
    result = {"neighbors": [str(r.target_id if r.source_id == payload.input_entity_id else r.source_id)
                            for r in edges], "truncated": len(edges) == 100}
    job = TransformJob(case_id=case_id, actor_id=user.id, transform_name=payload.transform_name,
                       status="succeeded", input_payload={"entity_id": str(payload.input_entity_id)},
                       result_payload=result, finished_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()
    audit(db, user, "transform.local.run", job.id, case_id)
    db.commit()
    return {"job_id": str(job.id), "status": job.status, "result": result}


@app.get("/api/v1/cases/{case_id}/audit")
def case_audit(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, role = authorize_case(db, user, case_id)
    if role not in {"case_manager", "reviewer"}:
        raise HTTPException(403, "Audit icazəsi yoxdur")
    events = db.scalars(select(AuditEvent).where(AuditEvent.case_id == case_id)
                        .order_by(AuditEvent.created_at.desc()).limit(100)).all()
    return [{"action": e.action, "resource_id": e.resource_id, "actor_id": str(e.actor_id),
             "created_at": e.created_at.isoformat()} for e in events]
