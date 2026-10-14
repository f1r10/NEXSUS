"""Case-scoped model: global identifiers do not grant access to other cases."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def now():
    return datetime.now(timezone.utc)


def new_id():
    return uuid4()


class User(Base):
    __tablename__ = "users"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class BootstrapGuard(Base):
    """A unique singleton prevents concurrent first-administrator registration."""
    __tablename__ = "bootstrap_guard"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[object] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(96), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_by: Mapped[object] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (CheckConstraint("classification BETWEEN 0 AND 4", name="case_classification_range"),)
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    workspace_id: Mapped[object] = mapped_column(Uuid, ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    classification: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    visibility_policy: Mapped[str] = mapped_column(String(40), default="disabled", nullable=False)
    created_by: Mapped[object] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class CaseMember(Base):
    __tablename__ = "case_members"
    case_id: Mapped[object] = mapped_column(Uuid, ForeignKey("cases.id"), primary_key=True)
    user_id: Mapped[object] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)


class GlobalEntity(Base):
    __tablename__ = "global_entities"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class CaseEntity(Base):
    __tablename__ = "case_entities"
    __table_args__ = (Index("ix_case_entity_name", "case_id", "display_name"),)
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    case_id: Mapped[object] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    global_id: Mapped[object] = mapped_column(Uuid, ForeignKey("global_entities.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_case_sha", "case_id", "sha256"),)
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    case_id: Mapped[object] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[object] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class Assertion(Base):
    __tablename__ = "assertions"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    case_id: Mapped[object] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    entity_id: Mapped[object] = mapped_column(Uuid, ForeignKey("case_entities.id"), nullable=False)
    attribute: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[object | None] = mapped_column(Uuid, ForeignKey("evidence.id"))
    review_status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class Relationship(Base):
    __tablename__ = "relationships"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    case_id: Mapped[object] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    source_id: Mapped[object] = mapped_column(Uuid, ForeignKey("case_entities.id"), nullable=False)
    target_id: Mapped[object] = mapped_column(Uuid, ForeignKey("case_entities.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_id: Mapped[object | None] = mapped_column(Uuid, ForeignKey("evidence.id"))
    review_status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_account_platform_external"),)
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)


class CaseSocialAccount(Base):
    __tablename__ = "case_social_accounts"
    __table_args__ = (UniqueConstraint("case_id", "account_id", name="uq_case_account"),)
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    case_id: Mapped[object] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    account_id: Mapped[object] = mapped_column(Uuid, ForeignKey("social_accounts.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    attributed_entity_id: Mapped[object | None] = mapped_column(Uuid, ForeignKey("case_entities.id"))
    identity_status: Mapped[str] = mapped_column(String(32), default="unverified", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class SocialFollow(Base):
    __tablename__ = "social_follow_observations"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    case_id: Mapped[object] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    follower_id: Mapped[object] = mapped_column(Uuid, ForeignKey("case_social_accounts.id"), nullable=False)
    followed_id: Mapped[object] = mapped_column(Uuid, ForeignKey("case_social_accounts.id"), nullable=False)
    evidence_id: Mapped[object] = mapped_column(Uuid, ForeignKey("evidence.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    actor_id: Mapped[object] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    case_id: Mapped[object | None] = mapped_column(Uuid, ForeignKey("cases.id"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class TransformJob(Base):
    __tablename__ = "transform_jobs"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=new_id)
    case_id: Mapped[object] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False, index=True)
    actor_id: Mapped[object] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    transform_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_payload: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
