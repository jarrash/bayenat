from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TranscriptionSubmit(BaseModel):
    language: str | None = Field(default="ar", max_length=20)
    profile: str = Field(default="arabic_forensic", max_length=120)
    engine_names: list[str] = Field(default_factory=lambda: ["faster-whisper"], min_length=1, max_length=8)
    idempotency_key: str | None = Field(default=None, max_length=128)


class JobEventRead(BaseModel):
    event_id: int
    job_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    message: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime


class StreamCreate(BaseModel):
    language: str | None = Field(default="ar", max_length=20)
    profile: str = Field(default="arabic_forensic", max_length=120)
    engine_names: list[str] = Field(default_factory=lambda: ["faster-whisper"], min_length=1, max_length=8)


class StreamCreated(BaseModel):
    stream_id: str
    websocket_url: str
    status: Literal["OPEN"] = "OPEN"


class WebSocketClientMessage(BaseModel):
    type: Literal["ping", "finalize", "metadata"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebSocketServerMessage(BaseModel):
    type: Literal["ready", "progress", "completed", "error", "pong"]
    event: JobEventRead | None = None
    stream_id: str | None = None
    message: str | None = None
