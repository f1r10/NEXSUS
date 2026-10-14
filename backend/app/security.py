"""Opaque server-side cookie sessions and CSRF checks; no shared default admin password."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import LoginSession, User

hasher = PasswordHasher()
SESSION_HOURS = 12
COOKIE_NAME = "nexus_session"


def hash_password(value: str) -> str:
    return hasher.hash(value)


def verify_password(stored: str, value: str) -> bool:
    try:
        return hasher.verify(stored, value)
    except (VerifyMismatchError, VerificationError):
        return False


def issue_session(db: Session, response: Response, user: User) -> str:
    raw = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    db.add(LoginSession(
        user_id=user.id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        csrf_token=csrf,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS),
    ))
    db.commit()
    response.set_cookie(
        COOKIE_NAME, raw, httponly=True,
        secure=os.getenv("NEXUS_COOKIE_SECURE", "false").lower() == "true",
        samesite="strict", max_age=SESSION_HOURS * 3600, path="/",
    )
    return csrf


def get_identity(request: Request, db: Session = Depends(get_db)) -> tuple[User, LoginSession]:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Giriş tələb olunur")
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash, LoginSession.revoked.is_(False)))
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Sessiya etibarsızdır")
    expires = session.expires_at
    if expires.tzinfo is None:  # SQLite test adapter stores naive UTC
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Sessiya bitib")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="İstifadəçi deaktivdir")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(csrf, session.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="CSRF yoxlaması uğursuz oldu")
    return user, session


def current_user(identity: tuple[User, LoginSession] = Depends(get_identity)) -> User:
    return identity[0]


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Administrator icazəsi tələb olunur")
    return user


def parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(404, "Resurs tapılmadı") from None
