"""Membership-based, fail-closed case authorization for every case endpoint."""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import Case, CaseMember, User

WRITE_ROLES = {"case_manager", "analyst", "reviewer"}
REVIEW_ROLES = {"case_manager", "reviewer"}


def authorize_case(db: Session, user: User, case_id, action: str = "read") -> tuple[Case, str]:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Araşdırma tapılmadı")
    membership = db.get(CaseMember, (case_id, user.id))
    if membership is None:
        # Do not leak whether the case actually exists.
        raise HTTPException(404, "Araşdırma tapılmadı")
    role = membership.role
    if action == "write" and role not in WRITE_ROLES:
        raise HTTPException(403, "Yazma icazəsi yoxdur")
    if action == "review" and role not in REVIEW_ROLES:
        raise HTTPException(403, "Təsdiq icazəsi yoxdur")
    if action == "manage" and role != "case_manager":
        raise HTTPException(403, "Case idarəetmə icazəsi yoxdur")
    return case, role
