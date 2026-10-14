"""Case-isolated Person Intelligence and evidence-backed social ingestion.

Only case members may read case observations. Social handles do not establish
real-world identity; AccountAttribution needs a human reviewer and evidence.
No live third-party collection is performed by these routes.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AccountAttribution, Assertion, CaseEntity, CaseMember, CaseSocialAccount,
    Evidence, Relationship, SocialAccount, SocialComment, SocialFollow,
    SocialPost, SocialProfileSnapshot, User,
)
from app.permissions import authorize_case
from app.security import current_user

router = APIRouter(prefix="/api/v1")


class SnapshotInput(BaseModel):
    account_id: UUID
    evidence_id: UUID
    username: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    biography: str | None = Field(default=None, max_length=10000)
    follower_count: int | None = Field(default=None, ge=0)
    following_count: int | None = Field(default=None, ge=0)
    observed_at: datetime | None = None


class PostInput(BaseModel):
    author_account_id: UUID
    platform_post_id: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20000)
    evidence_id: UUID
    published_at: datetime | None = None


class CommentInput(BaseModel):
    post_id: UUID
    author_account_id: UUID
    platform_comment_id: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=10000)
    evidence_id: UUID
    published_at: datetime | None = None


class AttributionInput(BaseModel):
    account_id: UUID
    entity_id: UUID
    evidence_id: UUID


class DecisionInput(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


def record_in_case(db: Session, cls, obj_id: UUID, case_id: UUID):
    row = db.get(cls, obj_id)
    if row is None or row.case_id != case_id:
        raise HTTPException(404, "Resurs tapılmadı")
    return row


def audit(db, user: User, case_id: UUID, action: str, obj_id: UUID):
    from app.models import AuditEvent
    db.add(AuditEvent(actor_id=user.id, case_id=case_id, action=action, resource_id=str(obj_id)))


def authorized(db, user: User, case_id: UUID, action="read"):
    return authorize_case(db, user, case_id, action)


def timestamp(value: datetime | None):
    return value.isoformat() if value else None


def post_data(row: SocialPost):
    return {"id": str(row.id), "author_account_id": str(row.author_account_id),
            "platform_post_id": row.platform_post_id, "content": row.content,
            "evidence_id": str(row.evidence_id), "published_at": timestamp(row.published_at),
            "observed_at": timestamp(row.observed_at)}


def comment_data(row: SocialComment):
    return {"id": str(row.id), "post_id": str(row.post_id),
            "author_account_id": str(row.author_account_id),
            "platform_comment_id": row.platform_comment_id, "content": row.content,
            "evidence_id": str(row.evidence_id), "published_at": timestamp(row.published_at),
            "observed_at": timestamp(row.observed_at)}


def save_unique(db: Session, obj, user: User, case_id: UUID, action: str):
    """Do not return a raw unique constraint error to client."""
    try:
        db.add(obj)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu mənbə qeydi artıq mövcuddur") from None
    audit(db, user, case_id, action, obj.id)
    db.commit()
    return obj


@router.get("/people/search")
def search_accessible_people(
    q: str = Query(min_length=2, max_length=100),
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    """Search *only* the cases this user belongs to; never return global hit counts."""
    clean = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    stmt = (
        select(CaseEntity)
        .join(CaseMember, CaseMember.case_id == CaseEntity.case_id)
        .where(CaseMember.user_id == user.id,
               CaseEntity.entity_type == "person",
               CaseEntity.display_name.ilike(f"%{clean}%", escape="\\"))
        .order_by(CaseEntity.display_name, CaseEntity.id).limit(50)
    )
    return [{"id": str(e.id), "case_id": str(e.case_id), "display_name": e.display_name,
             "entity_type": e.entity_type} for e in db.scalars(stmt).all()]


@router.post("/cases/{case_id}/social/profile-snapshots", status_code=201)
def add_profile_snapshot(case_id: UUID, payload: SnapshotInput, user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    authorized(db, user, case_id, "write")
    record_in_case(db, CaseSocialAccount, payload.account_id, case_id)
    record_in_case(db, Evidence, payload.evidence_id, case_id)
    if payload.observed_at and payload.observed_at > datetime.now(timezone.utc):
        raise HTTPException(422, "Müşahidə vaxtı gələcək tarix ola bilməz")
    obj = SocialProfileSnapshot(case_id=case_id, account_id=payload.account_id,
                                evidence_id=payload.evidence_id, username=payload.username,
                                display_name=payload.display_name, biography=payload.biography,
                                follower_count=payload.follower_count, following_count=payload.following_count,
                                observed_at=payload.observed_at or datetime.now(timezone.utc))
    db.add(obj)
    db.flush()
    audit(db, user, case_id, "social.profile.snapshot", obj.id)
    db.commit()
    return {"id": str(obj.id), "account_id": str(obj.account_id), "observed_at": timestamp(obj.observed_at)}


@router.get("/cases/{case_id}/social/accounts/{account_id}/profile-snapshots")
def list_profile_snapshots(case_id: UUID, account_id: UUID, user: User = Depends(current_user),
                           db: Session = Depends(get_db)):
    authorized(db, user, case_id)
    record_in_case(db, CaseSocialAccount, account_id, case_id)
    rows = db.scalars(select(SocialProfileSnapshot).where(SocialProfileSnapshot.case_id == case_id,
                    SocialProfileSnapshot.account_id == account_id)
                    .order_by(SocialProfileSnapshot.observed_at.desc()).limit(100)).all()
    return [{"id": str(x.id), "evidence_id": str(x.evidence_id), "username": x.username,
             "display_name": x.display_name, "biography": x.biography,
             "follower_count": x.follower_count, "following_count": x.following_count,
             "observed_at": timestamp(x.observed_at)} for x in rows]


@router.post("/cases/{case_id}/social/posts", status_code=201)
def add_social_post(case_id: UUID, payload: PostInput, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    authorized(db, user, case_id, "write")
    record_in_case(db, CaseSocialAccount, payload.author_account_id, case_id)
    record_in_case(db, Evidence, payload.evidence_id, case_id)
    obj = SocialPost(case_id=case_id, author_account_id=payload.author_account_id,
                     platform_post_id=payload.platform_post_id, content=payload.content,
                     evidence_id=payload.evidence_id, published_at=payload.published_at)
    return post_data(save_unique(db, obj, user, case_id, "social.post.observe"))


@router.get("/cases/{case_id}/social/posts")
def list_social_posts(case_id: UUID, account_id: UUID | None = None,
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorized(db, user, case_id)
    stmt = select(SocialPost).where(SocialPost.case_id == case_id)
    if account_id is not None:
        record_in_case(db, CaseSocialAccount, account_id, case_id)
        stmt = stmt.where(SocialPost.author_account_id == account_id)
    return [post_data(x) for x in db.scalars(stmt.order_by(SocialPost.observed_at.desc(), SocialPost.id).limit(100)).all()]


@router.post("/cases/{case_id}/social/comments", status_code=201)
def add_social_comment(case_id: UUID, payload: CommentInput, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    authorized(db, user, case_id, "write")
    record_in_case(db, CaseSocialAccount, payload.author_account_id, case_id)
    record_in_case(db, SocialPost, payload.post_id, case_id)
    record_in_case(db, Evidence, payload.evidence_id, case_id)
    obj = SocialComment(case_id=case_id, post_id=payload.post_id,
                        author_account_id=payload.author_account_id,
                        platform_comment_id=payload.platform_comment_id,
                        content=payload.content, evidence_id=payload.evidence_id,
                        published_at=payload.published_at)
    return comment_data(save_unique(db, obj, user, case_id, "social.comment.observe"))


@router.get("/cases/{case_id}/social/comments")
def list_social_comments(case_id: UUID, post_id: UUID | None = None,
                         user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorized(db, user, case_id)
    stmt = select(SocialComment).where(SocialComment.case_id == case_id)
    if post_id is not None:
        record_in_case(db, SocialPost, post_id, case_id)
        stmt = stmt.where(SocialComment.post_id == post_id)
    return [comment_data(x) for x in db.scalars(stmt.order_by(SocialComment.observed_at.desc(), SocialComment.id).limit(100)).all()]


@router.post("/cases/{case_id}/social/attributions", status_code=201)
def propose_attribution(case_id: UUID, payload: AttributionInput,
                        user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorized(db, user, case_id, "write")
    account = record_in_case(db, CaseSocialAccount, payload.account_id, case_id)
    entity = record_in_case(db, CaseEntity, payload.entity_id, case_id)
    if entity.entity_type != "person":
        raise HTTPException(422, "Şəxs obyekti tələb olunur")
    record_in_case(db, Evidence, payload.evidence_id, case_id)
    if account.identity_status == "confirmed":
        raise HTTPException(409, "Hesabın identikliyi artıq təsdiqlənib")
    pending = db.scalar(select(AccountAttribution).where(AccountAttribution.case_id == case_id,
                AccountAttribution.account_id == account.id,
                AccountAttribution.review_status == "proposed"))
    if pending:
        raise HTTPException(409, "Hesab üçün təsdiq gözləyən uyğunluq var")
    proposal = AccountAttribution(case_id=case_id, account_id=account.id,
                                  entity_id=entity.id, evidence_id=payload.evidence_id,
                                  proposed_by=user.id)
    db.add(proposal)
    db.flush()
    audit(db, user, case_id, "social.attribution.propose", proposal.id)
    db.commit()
    return {"id": str(proposal.id), "review_status": "proposed"}


@router.get("/cases/{case_id}/social/attributions")
def list_attributions(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorized(db, user, case_id)
    rows = db.scalars(select(AccountAttribution).where(AccountAttribution.case_id == case_id)
                      .order_by(AccountAttribution.created_at.desc()).limit(100)).all()
    return [{"id": str(x.id), "account_id": str(x.account_id), "entity_id": str(x.entity_id),
             "evidence_id": str(x.evidence_id), "review_status": x.review_status,
             "created_at": timestamp(x.created_at)} for x in rows]


@router.post("/cases/{case_id}/social/attributions/{attribution_id}/review")
def review_attribution(case_id: UUID, attribution_id: UUID, payload: DecisionInput,
                       user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorized(db, user, case_id, "review")
    proposal = record_in_case(db, AccountAttribution, attribution_id, case_id)
    if proposal.review_status != "proposed":
        raise HTTPException(409, "Qərar artıq verilib")
    account = record_in_case(db, CaseSocialAccount, proposal.account_id, case_id)
    if payload.decision == "approved":
        if account.identity_status == "confirmed":
            raise HTTPException(409, "Hesab artıq digər qərarla təsdiqlənib")
        account.attributed_entity_id = proposal.entity_id
        account.identity_status = "confirmed"
    proposal.review_status = payload.decision
    proposal.reviewed_by = user.id
    proposal.reviewed_at = datetime.now(timezone.utc)
    audit(db, user, case_id, f"social.attribution.{payload.decision}", proposal.id)
    db.commit()
    return {"id": str(proposal.id), "review_status": proposal.review_status}


@router.get("/cases/{case_id}/people/{person_id}/profile")
def person_profile(case_id: UUID, person_id: UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    authorized(db, user, case_id)
    person = record_in_case(db, CaseEntity, person_id, case_id)
    if person.entity_type != "person":
        raise HTTPException(404, "Şəxs tapılmadı")
    assertions = db.scalars(select(Assertion).where(Assertion.case_id == case_id,
                            Assertion.entity_id == person_id).order_by(Assertion.created_at.desc()).limit(100)).all()
    relations = db.scalars(select(Relationship).where(Relationship.case_id == case_id,
                 or_(Relationship.source_id == person_id, Relationship.target_id == person_id))
                 .order_by(Relationship.created_at.desc()).limit(100)).all()
    accounts = db.execute(select(CaseSocialAccount, SocialAccount).join(
        SocialAccount, SocialAccount.id == CaseSocialAccount.account_id).where(
        CaseSocialAccount.case_id == case_id,
        CaseSocialAccount.attributed_entity_id == person_id,
        CaseSocialAccount.identity_status == "confirmed").limit(100)).all()
    candidates = db.scalars(select(AccountAttribution).where(
        AccountAttribution.case_id == case_id, AccountAttribution.entity_id == person_id,
        AccountAttribution.review_status == "proposed").limit(100)).all()
    account_ids = [a.id for a, _ in accounts]
    posts = (db.scalars(select(SocialPost).where(SocialPost.case_id == case_id,
             SocialPost.author_account_id.in_(account_ids)).order_by(SocialPost.observed_at.desc())
             .limit(30)).all() if account_ids else [])
    return {
        "person": {"id": str(person.id), "display_name": person.display_name, "entity_type": "person"},
        "assertions": [{"id": str(a.id), "attribute": a.attribute, "value": a.value,
                        "review_status": a.review_status,
                        "evidence_id": str(a.evidence_id) if a.evidence_id else None} for a in assertions],
        "relationships": [{"id": str(r.id), "source_id": str(r.source_id), "target_id": str(r.target_id),
                           "relation_type": r.relation_type, "review_status": r.review_status,
                           "evidence_id": str(r.evidence_id) if r.evidence_id else None} for r in relations],
        "accounts": [{"id": str(a.id), "platform": s.platform, "username": a.username,
                      "identity_status": a.identity_status} for a, s in accounts],
        "account_candidates": [{"id": str(c.id), "account_id": str(c.account_id),
                                "evidence_id": str(c.evidence_id), "status": c.review_status} for c in candidates],
        "posts": [post_data(x) for x in posts],
        "data_scope": "authorized_case_only",
    }


@router.get("/cases/{case_id}/social/graph")
def social_graph(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Follow observations always connect *accounts*, never people by inference."""
    authorized(db, user, case_id)
    accounts = db.execute(select(CaseSocialAccount, SocialAccount).join(
        SocialAccount, CaseSocialAccount.account_id == SocialAccount.id).where(
        CaseSocialAccount.case_id == case_id).limit(200)).all()
    account_ids = {a.id for a, _ in accounts}
    follows = db.scalars(select(SocialFollow).where(SocialFollow.case_id == case_id)
                         .order_by(SocialFollow.observed_at.desc()).limit(500)).all()
    nodes = [{"id": str(a.id), "entity_type": "social_account", "display_name": f"{s.platform}: @{a.username}"}
             for a, s in accounts]
    edges = [{"id": str(f.id), "source": str(f.follower_id), "target": str(f.followed_id),
              "label": "FOLLOWS", "status": "observed", "evidence_id": str(f.evidence_id)}
             for f in follows if f.follower_id in account_ids and f.followed_id in account_ids]
    return {"nodes": nodes, "edges": edges,
            "truncated": len(accounts) == 200 or len(follows) == 500,
            "scope": "case_social_accounts_only"}
