from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PREPROCESSING = "PREPROCESSING"
    DIARIZING = "DIARIZING"
    TRANSCRIBING = "TRANSCRIBING"
    ALIGNING = "ALIGNING"
    CONSENSUS = "CONSENSUS"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class ArtifactType(str, enum.Enum):
    ORIGINAL = "ORIGINAL"
    NORMALIZED_AUDIO = "NORMALIZED_AUDIO"
    SEGMENT = "SEGMENT"
    ENGINE_TRANSCRIPT = "ENGINE_TRANSCRIPT"
    CONSENSUS_TRANSCRIPT = "CONSENSUS_TRANSCRIPT"
    REVIEWED_TRANSCRIPT = "REVIEWED_TRANSCRIPT"
    FINAL_TRANSCRIPT = "FINAL_TRANSCRIPT"
    REPORT = "REPORT"


class AuditEventType(str, enum.Enum):
    UPLOADED = "UPLOADED"
    HASHED = "HASHED"
    NORMALIZED = "NORMALIZED"
    PROCESSED = "PROCESSED"
    TRANSCRIBED = "TRANSCRIBED"
    VIEWED = "VIEWED"
    DOWNLOADED = "DOWNLOADED"
    REVIEW_STARTED = "REVIEW_STARTED"
    TRANSCRIPT_EDITED = "TRANSCRIPT_EDITED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    REPORT_GENERATED = "REPORT_GENERATED"
    EXPORTED = "EXPORTED"
    LOCKED = "LOCKED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False)
    users: Mapped[list[User]] = relationship(back_populates="tenant")
    cases: Mapped[list[Case]] = relationship(back_populates="tenant")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="VIEWER", nullable=False)
    tenant: Mapped[Tenant] = relationship(back_populates="users")


class Case(TimestampMixin, Base):
    __tablename__ = "cases"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    reference_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    case_type: Mapped[str] = mapped_column(String(80), default="DIGITAL_EVIDENCE", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    tenant: Mapped[Tenant] = relationship(back_populates="cases")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="case")


class Evidence(TimestampMixin, Base):
    __tablename__ = "evidence"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    detected_media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    storage_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case: Mapped[Case] = relationship(back_populates="evidence")
    artifacts: Mapped[list[EvidenceArtifact]] = relationship(back_populates="evidence")


class EvidenceArtifact(Base):
    __tablename__ = "evidence_artifacts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"), nullable=False, index=True)
    parent_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence_artifacts.id"))
    artifact_type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType), nullable=False)
    hash_algorithm: Mapped[str] = mapped_column(String(20), default="SHA-256", nullable=False)
    hash_value: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    evidence: Mapped[Evidence] = relationship(back_populates="artifacts")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, nullable=False)
    processing_profile: Mapped[str] = mapped_column(String(120), default="arabic_forensic", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    error_detail: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id"), index=True)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence.id"), index=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence_artifacts.id"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[AuditEventType] = mapped_column(Enum(AuditEventType), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
