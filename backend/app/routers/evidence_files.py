"""Private MinIO/S3 file evidence with access checks and immutable random keys.

This development slice retains originals, not full malware screening, OCR,
legal holds or WORM/object-lock enforcement. NEVER serve objects as inline HTML.
"""
import hashlib
import os
from urllib.parse import quote
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent, BinaryEvidence, User
from app.permissions import authorize_case
from app.security import current_user

router = APIRouter(prefix="/api/v1")

MAX_FILE_BYTES = 20 * 1024 * 1024  # Development import cap; bulk ingest is a separate worker.
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv", ".json", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".zip"}


def storage_client():
    endpoint = os.getenv("NEXUS_S3_ENDPOINT", "")
    access = os.getenv("NEXUS_S3_ACCESS_KEY", "")
    secret = os.getenv("NEXUS_S3_SECRET_KEY", "")
    if not endpoint or not access or not secret or not os.getenv("NEXUS_S3_BUCKET"):
        raise HTTPException(503, "MinIO fayl saxlanması konfiqurasiya edilməyib")
    return boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access,
                        aws_secret_access_key=secret, region_name="us-east-1")


def bucket_name():
    return os.getenv("NEXUS_S3_BUCKET", "nexus-evidence")


def file_summary(record: BinaryEvidence):
    return {"id": str(record.id), "title": record.title, "filename": record.filename,
            "sha256": record.sha256, "byte_count": record.byte_count,
            "media_type": record.media_type, "created_at": record.created_at.isoformat()}


@router.post("/cases/{case_id}/evidence/files", status_code=201)
async def upload_case_file(case_id: UUID, file: UploadFile = File(...),
                           user: User = Depends(current_user), db: Session = Depends(get_db)):
    case, _ = authorize_case(db, user, case_id, "write")
    filename = (file.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename or len(filename) > 255 or filename in {".", ".."}:
        raise HTTPException(422, "Fayl adı düzgün deyil")
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(422, "Bu fayl formatı ilkin versiyada dəstəklənmir")
    payload = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    if not payload or len(payload) > MAX_FILE_BYTES:
        raise HTTPException(413, "Fayl boşdur və ya 20 MB həddini aşır")
    # No cross-Case deduplication or content-addressed global existence checks.
    # Storage-domain deduplication must be introduced only after classification policy.
    object_id = uuid4()
    object_key = f"case/{case.id}/{object_id.hex}/original"
    media_type = "application/octet-stream"  # force download; distrust client MIME
    client = storage_client()
    try:
        client.put_object(Bucket=bucket_name(), Key=object_key, Body=payload,
                          ContentType=media_type, Metadata={"sha256": hashlib.sha256(payload).hexdigest()})
    except (BotoCoreError, ClientError, OSError):
        raise HTTPException(503, "Obyekt saxlanmasında xəta baş verdi") from None
    record = BinaryEvidence(id=object_id, case_id=case_id, filename=filename, title=filename,
                            object_key=object_key, sha256=hashlib.sha256(payload).hexdigest(),
                            byte_count=len(payload), media_type=media_type,
                            storage_domain=f"case:{case_id}", created_by=user.id)
    try:
        db.add(record)
        db.flush()
        db.add(AuditEvent(actor_id=user.id, case_id=case_id, action="evidence.file.upload",
                          resource_id=str(record.id)))
        db.commit()
    except Exception:
        db.rollback()
        try: client.delete_object(Bucket=bucket_name(), Key=object_key)
        except Exception: pass  # Operator must reconcile any orphaned objects.
        raise
    return file_summary(record)


@router.get("/cases/{case_id}/evidence/files")
def list_case_files(case_id: UUID, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    authorize_case(db, user, case_id)
    rows = db.scalars(select(BinaryEvidence).where(BinaryEvidence.case_id == case_id)
                      .order_by(BinaryEvidence.created_at.desc()).limit(100)).all()
    return [file_summary(x) for x in rows]


@router.get("/cases/{case_id}/evidence/files/{file_id}/download")
def download_case_file(case_id: UUID, file_id: UUID, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    authorize_case(db, user, case_id)
    record = db.get(BinaryEvidence, file_id)
    if record is None or record.case_id != case_id:
        raise HTTPException(404, "Fayl tapılmadı")
    client = storage_client()
    try:
        result = client.get_object(Bucket=bucket_name(), Key=record.object_key)
    except (BotoCoreError, ClientError, OSError):
        raise HTTPException(503, "Fayl saxlanmasına çıxış mümkün deyil") from None
    body = result["Body"]

    def chunks():
        try:
            for chunk in body.iter_chunks(chunk_size=65536):
                if chunk:
                    yield chunk
        finally:
            body.close()

    db.add(AuditEvent(actor_id=user.id, case_id=case_id, action="evidence.file.download",
                      resource_id=str(record.id)))
    db.commit()
    safe_name = quote(record.filename, safe="")
    return StreamingResponse(chunks(), media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}",
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })
