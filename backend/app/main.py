from __future__ import annotations

import hashlib
import mimetypes
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ArtifactType, AuditEvent, AuditEventType, Case, Evidence, EvidenceArtifact, JobStatus, ProcessingJob, Tenant, User
from app.db.session import get_db
from app.schemas.api import CaseCreate, CaseRead, EvidenceRead, IntegrityRead, JobRead
from app.services.integrity import audit_event_hash, sha256_file

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", description="Evidence transcription and verification API")

ALLOWED_MEDIA_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/aac",
    "audio/flac",
    "audio/ogg",
    "video/mp4",
    "video/quicktime",
}


def _default_principal(db: Session) -> tuple[Tenant, User]:
    tenant = db.scalar(select(Tenant).where(Tenant.name == "Development Tenant"))
    if tenant is None:
        tenant = Tenant(name="Development Tenant")
        db.add(tenant)
        db.flush()
    user = db.scalar(select(User).where(User.email == "developer@bayenat.local"))
    if user is None:
        user = User(tenant_id=tenant.id, email="developer@bayenat.local", password_hash="development-only", role="ADMIN")
        db.add(user)
        db.flush()
    return tenant, user


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bayenat-api"}


@app.post(f"{settings.api_prefix}/cases", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)) -> Case:
    tenant, user = _default_principal(db)
    case = Case(
        tenant_id=tenant.id,
        reference_number=payload.reference_number,
        title=payload.title,
        description=payload.description,
        case_type=payload.case_type,
        created_by=user.id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@app.get(f"{settings.api_prefix}/cases", response_model=list[CaseRead])
def list_cases(db: Session = Depends(get_db)) -> list[Case]:
    tenant, _ = _default_principal(db)
    cases = db.scalars(select(Case).where(Case.tenant_id == tenant.id).order_by(Case.created_at.desc())).all()
    db.commit()
    return list(cases)


@app.post(f"{settings.api_prefix}/cases/{{case_id}}/evidence", response_model=EvidenceRead, status_code=status.HTTP_201_CREATED)
def upload_evidence(case_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db)) -> Evidence:
    tenant, _ = _default_principal(db)
    case = db.scalar(select(Case).where(Case.id == case_id, Case.tenant_id == tenant.id))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if file.content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported media type")

    evidence_id = uuid.uuid4()
    storage_root = Path(settings.storage_root).resolve()
    original_dir = storage_root / "originals"
    original_dir.mkdir(parents=True, exist_ok=True)
    destination = original_dir / f"{evidence_id}.bin"
    total = 0
    with destination.open("wb") as target:
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > settings.max_upload_size_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Evidence exceeds configured upload limit")
            target.write(chunk)
    digest = sha256_file(destination)
    detected_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    evidence = Evidence(
        id=evidence_id,
        tenant_id=tenant.id,
        case_id=case.id,
        original_filename=file.filename or "unnamed-evidence",
        detected_media_type=detected_type,
        file_size=total,
        storage_uri=f"originals/{evidence_id}.bin",
        sha256=digest,
    )
    db.add(evidence)
    db.flush()
    artifact = EvidenceArtifact(
        tenant_id=tenant.id,
        evidence_id=evidence.id,
        artifact_type=ArtifactType.ORIGINAL,
        hash_value=digest,
        storage_uri=evidence.storage_uri,
    )
    db.add(artifact)
    event_payload = {"event_type": AuditEventType.UPLOADED.value, "evidence_id": str(evidence.id), "sha256": digest}
    db.add(AuditEvent(
        tenant_id=tenant.id,
        case_id=case.id,
        evidence_id=evidence.id,
        artifact_id=artifact.id,
        event_type=AuditEventType.UPLOADED,
        event_hash=audit_event_hash(event_payload, None),
        metadata_json=event_payload,
    ))
    db.commit()
    db.refresh(evidence)
    return evidence


@app.post(f"{settings.api_prefix}/evidence/{{evidence_id}}/transcribe", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def submit_transcription(evidence_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJob:
    tenant, _ = _default_principal(db)
    evidence = db.scalar(select(Evidence).where(Evidence.id == evidence_id, Evidence.tenant_id == tenant.id))
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    key = hashlib.sha256(f"{evidence.sha256}:arabic_forensic:v1".encode()).hexdigest()
    existing = db.scalar(select(ProcessingJob).where(ProcessingJob.evidence_id == evidence.id, ProcessingJob.idempotency_key == key))
    if existing is not None:
        return existing
    job = ProcessingJob(tenant_id=tenant.id, evidence_id=evidence.id, idempotency_key=key, status=JobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@app.get(f"{settings.api_prefix}/jobs/{{job_id}}", response_model=JobRead)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJob:
    tenant, _ = _default_principal(db)
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id, ProcessingJob.tenant_id == tenant.id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get(f"{settings.api_prefix}/evidence/{{evidence_id}}/integrity", response_model=IntegrityRead)
def verify_integrity(evidence_id: uuid.UUID, db: Session = Depends(get_db)) -> IntegrityRead:
    tenant, _ = _default_principal(db)
    evidence = db.scalar(select(Evidence).where(Evidence.id == evidence_id, Evidence.tenant_id == tenant.id))
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    path = Path(settings.storage_root) / evidence.storage_uri
    original_valid = path.exists() and sha256_file(path) == evidence.sha256
    artifacts = db.scalars(select(EvidenceArtifact).where(EvidenceArtifact.evidence_id == evidence.id)).all()
    artifact_valid = all(artifact.hash_value == evidence.sha256 for artifact in artifacts if artifact.artifact_type == ArtifactType.ORIGINAL)
    events = db.scalars(select(AuditEvent).where(AuditEvent.evidence_id == evidence.id).order_by(AuditEvent.created_at)).all()
    audit_valid = True
    previous: str | None = None
    for event in events:
        payload = event.metadata_json
        if event.previous_hash != previous or audit_event_hash(payload, previous) != event.event_hash:
            audit_valid = False
            break
        previous = event.event_hash
    return IntegrityRead(original_file_valid=original_valid, artifact_chain_valid=artifact_valid, audit_chain_valid=audit_valid)
