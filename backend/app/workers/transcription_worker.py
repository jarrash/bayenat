from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.engines.alignment import TranscriptAligner, enrich_with_diarization
from app.engines.base import STTEngine, TranscriptionResult
from app.engines.diarization import DiarizationProvider
from app.services.transcription_jobs import InMemoryJobQueue, JobEvent, JobKind, JobStatus, TranscriptionJob


EventSink = Callable[[JobEvent], Any]


@dataclass
class StreamState:
    stream_id: str
    tenant_id: str
    language: str | None
    chunks: list[Path] = field(default_factory=list)
    results: list[TranscriptionResult] = field(default_factory=list)


class TranscriptionWorker:
    """Process queued batch and streaming jobs without holding HTTP requests open."""

    def __init__(
        self,
        queue: InMemoryJobQueue,
        engines: dict[str, STTEngine],
        *,
        diarizer: DiarizationProvider | None = None,
        aligner: TranscriptAligner | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.queue = queue
        self.engines = engines
        self.diarizer = diarizer
        self.aligner = aligner or TranscriptAligner()
        self.event_sink = event_sink
        self.streams: dict[str, StreamState] = {}

    async def emit(self, event: JobEvent) -> None:
        if self.event_sink is None:
            return
        value = self.event_sink(event)
        if asyncio.iscoroutine(value):
            await value

    async def run_once(self) -> JobEvent:
        job = await self.queue.dequeue()
        try:
            if job.kind == JobKind.BATCH:
                event = await self.process_batch(job)
            elif job.kind == JobKind.STREAM_CHUNK:
                event = await self.process_stream_chunk(job)
            elif job.kind == JobKind.STREAM_FINALIZE:
                event = await self.finalize_stream(job)
            else:
                event = JobEvent(job.job_id, JobStatus.FAILED, 0, "Unsupported job kind", error=job.kind.value)
        except Exception as exc:
            event = JobEvent(job.job_id, JobStatus.FAILED, 0, "Transcription job failed", error=str(exc))
        await self.emit(event)
        self.queue.task_done()
        return event

    async def process_batch(self, job: TranscriptionJob) -> JobEvent:
        if not job.audio_path:
            raise ValueError("batch job requires audio_path")
        await self.emit(JobEvent(job.job_id, JobStatus.PREPROCESSING, 10, "Input ready"))
        if self.diarizer:
            await self.emit(JobEvent(job.job_id, JobStatus.DIARIZING, 25, "Running diarization"))
            diarization = await asyncio.to_thread(self.diarizer.diarize, job.audio_path)
        else:
            diarization = None
        await self.emit(JobEvent(job.job_id, JobStatus.TRANSCRIBING, 40, "Running speech engines"))
        successful, failures = await self._transcribe_parallel(job.audio_path, job.engine_names, job.language)
        if not successful:
            raise RuntimeError(f"all configured speech engines failed: {failures}")
        if diarization:
            successful = [enrich_with_diarization(result, diarization) for result in successful]
        await self.emit(JobEvent(job.job_id, JobStatus.ALIGNING, 80, "Aligning engine outputs"))
        alignment = self.aligner.align(successful)
        status = JobStatus.COMPLETED if len(successful) == len(job.engine_names) else JobStatus.PARTIAL_SUCCESS
        return JobEvent(
            job.job_id,
            status,
            100,
            "Transcription completed",
            result={
                "engine_results": [result.as_dict() for result in successful],
                "engine_failures": failures,
                "alignment": {
                    "engine_count": alignment.engine_count,
                    "segments": [
                        {
                            "start_ms": segment.start_ms,
                            "end_ms": segment.end_ms,
                            "speaker": segment.speaker,
                            "alignment_score": segment.alignment_score,
                            "candidates": [candidate.__dict__ for candidate in segment.candidates],
                        }
                        for segment in alignment.segments
                    ],
                },
            },
        )

    async def _transcribe_parallel(
        self, audio_path: str, engine_names: tuple[str, ...], language: str | None
    ) -> tuple[list[TranscriptionResult], dict[str, str]]:
        async def run(engine_name: str) -> tuple[str, TranscriptionResult | None, str | None]:
            engine = self.engines.get(engine_name)
            if engine is None:
                return engine_name, None, "engine_not_configured"
            try:
                return engine_name, await asyncio.to_thread(engine.transcribe, audio_path, language), None
            except Exception as exc:
                return engine_name, None, str(exc)

        outcomes = await asyncio.gather(*(run(name) for name in engine_names))
        successful = [result for _, result, error in outcomes if result is not None and error is None]
        failures = {engine_name: error or "unknown failure" for engine_name, result, error in outcomes if result is None}
        return successful, failures

    async def process_stream_chunk(self, job: TranscriptionJob) -> JobEvent:
        if not job.stream_id or not job.chunk_path:
            raise ValueError("stream chunk requires stream_id and chunk_path")
        state = self.streams.setdefault(job.stream_id, StreamState(job.stream_id, job.tenant_id, job.language))
        chunk = Path(job.chunk_path)
        if not chunk.is_file():
            raise FileNotFoundError(chunk)
        state.chunks.append(chunk)
        results, failures = await self._transcribe_parallel(str(chunk), job.engine_names, job.language)
        state.results.extend(results)
        return JobEvent(
            job.job_id,
            JobStatus.TRANSCRIBING,
            min(95, len(state.chunks) * 5),
            "Streaming chunk processed",
            result={"stream_id": job.stream_id, "chunk_count": len(state.chunks), "engine_results": [result.as_dict() for result in results], "engine_failures": failures},
        )

    async def finalize_stream(self, job: TranscriptionJob) -> JobEvent:
        if not job.stream_id:
            raise ValueError("stream finalization requires stream_id")
        state = self.streams.pop(job.stream_id, None)
        if state is None:
            raise ValueError(f"unknown stream: {job.stream_id}")
        alignment = self.aligner.align(state.results)
        return JobEvent(
            job.job_id,
            JobStatus.COMPLETED,
            100,
            "Streaming transcription finalized",
            result={
                "stream_id": state.stream_id,
                "chunk_count": len(state.chunks),
                "alignment": {
                    "engine_count": alignment.engine_count,
                    "segments": [segment.__dict__ for segment in alignment.segments],
                },
            },
        )
