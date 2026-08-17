from __future__ import annotations

import hashlib
import mimetypes
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ArtifactType, AuditEvent, AuditEventType, Case, Evidence, EvidenceArtifact, JobStatus, ProcessingJob, Tenant, User
from app.db.session import get_db
from app.schemas.api import CaseCreate, CaseRead, EvidenceRead, IntegrityRead, JobRead
from app.schemas.transcription import JobEventRead, StreamCreate, StreamCreated, TranscriptionSubmit, WebSocketClientMessage
from app.services.job_events import JobEventHub
from app.services.transcription_jobs import InMemoryJobQueue, JobKind, JobStatus as QueueJobStatus, TranscriptionJob
from app.services.integrity import audit_event_hash, sha256_file

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", description="Evidence transcription and verification API")
app.state.job_queue = InMemoryJobQueue()
app.state.event_hub = JobEventHub()
app.state.streams = {}

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
async def submit_transcription(evidence_id: uuid.UUID, payload: TranscriptionSubmit | None = None, db: Session = Depends(get_db)) -> ProcessingJob:
    tenant, _ = _default_principal(db)
    evidence = db.scalar(select(Evidence).where(Evidence.id == evidence_id, Evidence.tenant_id == tenant.id))
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    request = payload or TranscriptionSubmit()
    profile = request.profile
    key_material = request.idempotency_key or f"{evidence.sha256}:{profile}:{','.join(request.engine_names)}:{request.language}"
    key = hashlib.sha256(key_material.encode()).hexdigest()
    existing = db.scalar(select(ProcessingJob).where(ProcessingJob.evidence_id == evidence.id, ProcessingJob.idempotency_key == key))
    if existing is not None:
        return existing
    job = ProcessingJob(tenant_id=tenant.id, evidence_id=evidence.id, idempotency_key=key, status=JobStatus.QUEUED, processing_profile=profile, metadata_json={"language": request.language, "engine_names": request.engine_names})
    db.add(job)
    db.commit()
    db.refresh(job)
    await app.state.job_queue.enqueue(TranscriptionJob(job_id=str(job.id), kind=JobKind.BATCH, tenant_id=str(tenant.id), evidence_id=str(evidence.id), audio_path=str(Path(settings.storage_root) / evidence.storage_uri), language=request.language, profile=profile, engine_names=tuple(request.engine_names)))
    await app.state.event_hub.publish_status(str(job.id), QueueJobStatus.QUEUED.value, 0, "Transcription job queued")
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


@app.get(f"{settings.api_prefix}/jobs/{{job_id}}/events", response_model=list[JobEventRead])
async def list_job_events(job_id: uuid.UUID, after_event_id: int = Query(default=0, ge=0)) -> list[JobEventRead]:
    return await app.state.event_hub.replay(str(job_id), after_event_id)


@app.websocket(f"{settings.api_prefix}/jobs/{{job_id}}/events/ws")
async def job_events_websocket(websocket: WebSocket, job_id: uuid.UUID) -> None:
    await websocket.accept()
    after_event_id = int(websocket.query_params.get("after_event_id", "0"))
    job_key = str(job_id)
    await websocket.send_json({"type": "ready", "job_id": job_key, "after_event_id": after_event_id})
    try:
        async for event in app.state.event_hub.subscribe_from(job_key, after_event_id):
            await websocket.send_json({"type": "progress", "event": event.model_dump(mode="json")})
            if event.status in {QueueJobStatus.COMPLETED.value, QueueJobStatus.PARTIAL_SUCCESS.value, QueueJobStatus.FAILED.value}:
                await websocket.close(code=1000)
                return
    except WebSocketDisconnect:
        return


@app.post(f"{settings.api_prefix}/streams", response_model=StreamCreated, status_code=status.HTTP_201_CREATED)
async def create_stream(payload: StreamCreate) -> StreamCreated:
    stream_id = str(uuid.uuid4())
    app.state.streams[stream_id] = {
        "tenant_id": "development-tenant",
        "language": payload.language,
        "profile": payload.profile,
        "engine_names": tuple(payload.engine_names),
        "chunk_count": 0,
    }
    return StreamCreated(stream_id=stream_id, websocket_url=f"{settings.api_prefix}/streams/{stream_id}/ws")


@app.websocket(f"{settings.api_prefix}/streams/{{stream_id}}/ws")
async def stream_websocket(websocket: WebSocket, stream_id: str) -> None:
    await websocket.accept()
    stream = app.state.streams.get(stream_id)
    if stream is None:
        await websocket.send_json({"type": "error", "message": "Unknown stream"})
        await websocket.close(code=1008)
        return
    await websocket.send_json({"type": "ready", "stream_id": stream_id})
    stream_dir = Path(settings.storage_root) / "streams" / stream_id
    stream_dir.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            message = await websocket.receive()
            if message.get("bytes") is not None:
                stream["chunk_count"] += 1
                chunk_number = stream["chunk_count"]
                chunk_path = stream_dir / f"chunk-{chunk_number:06d}.bin"
                chunk_path.write_bytes(message["bytes"])
                job = TranscriptionJob.create_stream_chunk(
                    tenant_id=stream["tenant_id"],
                    stream_id=stream_id,
                    chunk_path=str(chunk_path),
                    language=stream["language"],
                    profile=stream["profile"],
                    engine_names=stream["engine_names"],
                )
                await app.state.job_queue.enqueue(job)
                await app.state.event_hub.publish_status(job.job_id, QueueJobStatus.TRANSCRIBING.value, 5, "Audio chunk queued")
                await websocket.send_json({"type": "progress", "stream_id": stream_id, "chunk_number": chunk_number, "job_id": job.job_id})
                continue
            if message.get("text") is not None:
                command = WebSocketClientMessage.model_validate_json(message["text"])
                if command.type == "ping":
                    await websocket.send_json({"type": "pong", "stream_id": stream_id})
                elif command.type == "finalize":
                    job = TranscriptionJob(job_id=str(uuid.uuid4()), kind=JobKind.STREAM_FINALIZE, tenant_id=stream["tenant_id"], evidence_id=None, stream_id=stream_id, language=stream["language"], profile=stream["profile"], engine_names=stream["engine_names"])
                    await app.state.job_queue.enqueue(job)
                    await app.state.event_hub.publish_status(job.job_id, QueueJobStatus.ALIGNING.value, 90, "Stream finalization queued")
                    await websocket.send_json({"type": "completed", "stream_id": stream_id, "job_id": job.job_id})
                    app.state.streams.pop(stream_id, None)
                    await websocket.close(code=1000)
                    return
    except WebSocketDisconnect:
        return
    finally:
        if websocket.client_state.name != "CONNECTED":
            return
