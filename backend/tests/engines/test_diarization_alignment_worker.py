from pathlib import Path

import pytest

from app.engines.alignment import TranscriptAligner
from app.engines.base import EngineMetadata, SegmentResult, TranscriptionResult
from app.engines.diarization import DiarizationResult, DiarizationSegment, attach_speakers
from app.services.transcription_jobs import InMemoryJobQueue, JobKind, JobStatus, TranscriptionJob
from app.workers.transcription_worker import TranscriptionWorker


def result(engine: str, text: str = "مرحبا", start: int = 0, end: int = 1000) -> TranscriptionResult:
    return TranscriptionResult(
        engine_metadata=EngineMetadata(engine, "test", "fixture", "1", "mock", "ar", "cpu", "int8"),
        duration_ms=end,
        processing_time_ms=1,
        segments=(SegmentResult(start, end, text),),
    )


def test_attach_speakers_uses_maximum_temporal_overlap():
    diarization = DiarizationResult(
        provider="mock", model_name="fixture", model_version="1", duration_ms=2000, processing_time_ms=1,
        segments=(DiarizationSegment(0, 400, "SPEAKER_01"), DiarizationSegment(400, 1500, "SPEAKER_02")),
    )
    enriched = attach_speakers(result("engine-a", start=300, end=1000), diarization)
    assert enriched.segments[0].speaker == "SPEAKER_02"


def test_alignment_preserves_candidates_and_scores_exact_agreement():
    aligned = TranscriptAligner().align([result("engine-a"), result("engine-b")])
    assert len(aligned.segments) == 1
    assert len(aligned.segments[0].candidates) == 2
    assert aligned.segments[0].alignment_score == 1.0


class FakeEngine:
    def __init__(self, engine: str, fail: bool = False):
        self.engine = engine
        self.fail = fail
        self.calls = []

    def transcribe(self, audio_path: str, language: str | None = None) -> TranscriptionResult:
        self.calls.append((audio_path, language))
        if self.fail:
            raise RuntimeError("fixture engine failure")
        return result(self.engine)


@pytest.mark.asyncio
async def test_batch_worker_reports_partial_success(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF")
    queue = InMemoryJobQueue()
    worker = TranscriptionWorker(queue, {"a": FakeEngine("a"), "b": FakeEngine("b", fail=True)})
    job = TranscriptionJob.create_batch("tenant", "evidence", str(audio), engine_names=("a", "b"))
    await queue.enqueue(job)
    event = await worker.run_once()
    assert event.status == JobStatus.PARTIAL_SUCCESS
    assert event.result["alignment"]["engine_count"] == 1
    assert "fixture engine failure" in event.result["engine_failures"]["b"]


@pytest.mark.asyncio
async def test_streaming_worker_processes_chunks_and_finalizes(tmp_path: Path):
    chunk = tmp_path / "chunk.wav"
    chunk.write_bytes(b"RIFF")
    queue = InMemoryJobQueue()
    worker = TranscriptionWorker(queue, {"a": FakeEngine("a")})
    chunk_job = TranscriptionJob.create_stream_chunk("tenant", "stream-1", str(chunk), engine_names=("a",))
    await queue.enqueue(chunk_job)
    chunk_event = await worker.run_once()
    assert chunk_event.status == JobStatus.TRANSCRIBING
    final = TranscriptionJob(job_id="final", kind=JobKind.STREAM_FINALIZE, tenant_id="tenant", evidence_id=None, stream_id="stream-1")
    await queue.enqueue(final)
    final_event = await worker.run_once()
    assert final_event.status == JobStatus.COMPLETED
    assert final_event.result["chunk_count"] == 1
