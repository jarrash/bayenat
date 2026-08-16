from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    reference_number: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    case_type: str = Field(default="DIGITAL_EVIDENCE", max_length=80)


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference_number: str
    title: str
    description: str | None
    case_type: str
    status: str
    created_at: datetime


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    original_filename: str
    detected_media_type: str
    file_size: int
    duration_ms: int | None
    sha256: str
    created_at: datetime


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_id: UUID
    status: str
    processing_profile: str
    created_at: datetime
    updated_at: datetime
    error_detail: str | None


class IntegrityRead(BaseModel):
    original_file_valid: bool
    artifact_chain_valid: bool
    audit_chain_valid: bool
