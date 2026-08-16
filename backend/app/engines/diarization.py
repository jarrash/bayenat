from __future__ import annotations

import importlib.metadata
import platform
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.engines.base import SegmentResult, TranscriptionResult


@dataclass(frozen=True)
class DiarizationSegment:
    start_ms: int
    end_ms: int
    speaker: str
    confidence: float | None = None


@dataclass(frozen=True)
class DiarizationResult:
    provider: str
    model_name: str
    model_version: str | None
    duration_ms: int
    processing_time_ms: int
    segments: tuple[DiarizationSegment, ...]
    parameters: dict[str, Any] = field(default_factory=dict)


class DiarizationProvider(Protocol):
    def diarize(self, audio_path: str | Path) -> DiarizationResult:
        ...


def _overlap_ms(left_start: int, left_end: int, right_start: int, right_end: int) -> int:
    return max(0, min(left_end, right_end) - max(left_start, right_start))


def attach_speakers(transcription: TranscriptionResult, diarization: DiarizationResult) -> TranscriptionResult:
    """Attach the speaker with maximum temporal overlap to each STT segment."""
    updated: list[SegmentResult] = []
    for segment in transcription.segments:
        candidates = [
            item
            for item in diarization.segments
            if _overlap_ms(segment.start_ms, segment.end_ms, item.start_ms, item.end_ms) > 0
        ]
        speaker = None
        if candidates:
            speaker = max(
                candidates,
                key=lambda item: (
                    _overlap_ms(segment.start_ms, segment.end_ms, item.start_ms, item.end_ms),
                    item.confidence if item.confidence is not None else 0.0,
                ),
            ).speaker
        updated.append(
            SegmentResult(
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                speaker=speaker,
                confidence=segment.confidence,
                words=segment.words,
            )
        )
    return TranscriptionResult(
        engine_metadata=transcription.engine_metadata,
        duration_ms=transcription.duration_ms,
        processing_time_ms=transcription.processing_time_ms,
        segments=tuple(updated),
        language_probability=transcription.language_probability,
        raw_output={
            **(transcription.raw_output or {}),
            "diarization": {
                "provider": diarization.provider,
                "model_name": diarization.model_name,
                "model_version": diarization.model_version,
                "processing_time_ms": diarization.processing_time_ms,
                "parameters": diarization.parameters,
            },
        },
    )


class PyannoteDiarizer:
    """Optional local pyannote.audio diarization adapter.

    The pipeline is injected in tests and loaded lazily in production. A
    Hugging Face token may be required by the selected pyannote pipeline; it is
    never stored in result metadata.
    """

    def __init__(
        self,
        model_name: str = "pyannote/speaker-diarization-3.1",
        *,
        model_version: str | None = None,
        pipeline: Any | None = None,
        hf_token: str | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self._pipeline = pipeline
        self.hf_token = hf_token
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            try:
                from pyannote.audio import Pipeline
            except ImportError as exc:
                raise RuntimeError(
                    "pyannote.audio is not installed. Install backend/requirements-speech.txt "
                    "or inject a compatible pipeline for tests."
                ) from exc
            kwargs: dict[str, Any] = {}
            if self.hf_token:
                kwargs["token"] = self.hf_token
            self._pipeline = Pipeline.from_pretrained(self.model_name, **kwargs)
        return self._pipeline

    def diarize(self, audio_path: str | Path) -> DiarizationResult:
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"audio file not found: {path}")
        started = time.perf_counter()
        kwargs: dict[str, Any] = {}
        if self.min_speakers is not None:
            kwargs["min_speakers"] = self.min_speakers
        if self.max_speakers is not None:
            kwargs["max_speakers"] = self.max_speakers
        annotation = self._get_pipeline()(str(path), **kwargs)
        segments: list[DiarizationSegment] = []
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            segments.append(
                DiarizationSegment(
                    start_ms=round(float(turn.start) * 1000),
                    end_ms=round(float(turn.end) * 1000),
                    speaker=str(speaker),
                )
            )
        duration_ms = max((item.end_ms for item in segments), default=0)
        return DiarizationResult(
            provider="pyannote",
            model_name=self.model_name,
            model_version=self.model_version,
            duration_ms=duration_ms,
            processing_time_ms=round((time.perf_counter() - started) * 1000),
            segments=tuple(segments),
            parameters={
                "min_speakers": self.min_speakers,
                "max_speakers": self.max_speakers,
                "python_version": platform.python_version(),
                "pyannote_version": _package_version("pyannote.audio"),
            },
        )


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None
