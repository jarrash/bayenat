from __future__ import annotations

import asyncio
import enum
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


class JobKind(str, enum.Enum):
    BATCH = "BATCH"
    STREAM_START = "STREAM_START"
    STREAM_CHUNK = "STREAM_CHUNK"
    STREAM_FINALIZE = "STREAM_FINALIZE"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PREPROCESSING = "PREPROCESSING"
    DIARIZING = "DIARIZING"
    TRANSCRIBING = "TRANSCRIBING"
    ALIGNING = "ALIGNING"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class TranscriptionJob:
    job_id: str
    kind: JobKind
    tenant_id: str
    evidence_id: str | None
    audio_path: str | None = None
    stream_id: str | None = None
    chunk_path: str | None = None
    language: str | None = None
    profile: str = "arabic_forensic"
    engine_names: tuple[str, ...] = ("faster-whisper",)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create_batch(cls, tenant_id: str, evidence_id: str, audio_path: str, **kwargs: Any) -> TranscriptionJob:
        return cls(job_id=str(uuid.uuid4()), kind=JobKind.BATCH, tenant_id=tenant_id, evidence_id=evidence_id, audio_path=audio_path, **kwargs)

    @classmethod
    def create_stream_chunk(cls, tenant_id: str, stream_id: str, chunk_path: str, **kwargs: Any) -> TranscriptionJob:
        return cls(job_id=str(uuid.uuid4()), kind=JobKind.STREAM_CHUNK, tenant_id=tenant_id, evidence_id=None, stream_id=stream_id, chunk_path=chunk_path, **kwargs)

    def to_json(self) -> str:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["engine_names"] = list(self.engine_names)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> TranscriptionJob:
        payload = json.loads(value)
        payload["kind"] = JobKind(payload["kind"])
        payload["engine_names"] = tuple(payload.get("engine_names", []))
        return cls(**payload)


@dataclass(frozen=True)
class JobEvent:
    job_id: str
    status: JobStatus
    progress: int
    message: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class JobQueue(Protocol):
    async def enqueue(self, job: TranscriptionJob) -> None:
        ...

    async def dequeue(self) -> TranscriptionJob:
        ...

    async def acknowledge(self, job: TranscriptionJob) -> None:
        ...


class InMemoryJobQueue:
    """Deterministic queue for local development and unit tests."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[TranscriptionJob] = asyncio.Queue()

    async def enqueue(self, job: TranscriptionJob) -> None:
        await self._queue.put(job)

    async def dequeue(self) -> TranscriptionJob:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()


class RedisJobQueue:
    """Redis Streams queue adapter, loaded lazily to keep CI lightweight."""

    def __init__(self, redis_url: str, stream_name: str = "bayenat:transcription") -> None:
        try:
            from redis.asyncio import Redis  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("Install redis to use RedisJobQueue") from exc
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self.stream_name = stream_name
        self.group_name = "bayenat-workers"
        self.consumer_name = f"worker-{uuid.uuid4()}"
        self._delivery_ids: dict[str, str] = {}

    async def ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(self.stream_name, self.group_name, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, job: TranscriptionJob) -> None:
        await self._redis.xadd(self.stream_name, {"job": job.to_json()})

    async def dequeue(self) -> TranscriptionJob:
        await self.ensure_group()
        messages = await self._redis.xreadgroup(self.group_name, self.consumer_name, {self.stream_name: ">"}, count=1, block=5000)
        if not messages:
            raise asyncio.TimeoutError
        _, entries = messages[0]
        message_id, fields = entries[0]
        job = TranscriptionJob.from_json(fields["job"])
        self._delivery_ids[job.job_id] = message_id
        return job

    async def acknowledge(self, job: TranscriptionJob) -> None:
        message_id = self._delivery_ids.pop(job.job_id, None)
        if message_id is None:
            raise KeyError(f"no pending delivery for job {job.job_id}")
        acknowledged = await self._redis.xack(self.stream_name, self.group_name, message_id)
        if acknowledged != 1:
            raise RuntimeError(f"Redis did not acknowledge job {job.job_id}")

    async def pending_count(self) -> int:
        pending = await self._redis.xpending(self.stream_name, self.group_name)
        return int(pending["pending"] if isinstance(pending, dict) else pending[0])
