from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class WordResult:
    word: str
    start_ms: int
    end_ms: int
    confidence: float | None = None


@dataclass(frozen=True)
class SegmentResult:
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None
    confidence: float | None = None
    words: tuple[WordResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EngineMetadata:
    engine: str
    model_family: str
    model_name: str
    model_version: str | None
    implementation: str
    language: str | None
    device: str
    compute_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    library_version: str | None = None
    python_version: str | None = None
    cuda_version: str | None = None
    configuration_version: str = "v1"


@dataclass(frozen=True)
class TranscriptionResult:
    engine_metadata: EngineMetadata
    duration_ms: int
    processing_time_ms: int
    segments: tuple[SegmentResult, ...]
    language_probability: float | None = None
    raw_output: dict[str, Any] | None = None

    @property
    def text(self) -> str:
        return " ".join(segment.text.strip() for segment in self.segments if segment.text.strip())

    def as_dict(self) -> dict[str, Any]:
        metadata = {
            "engine": self.engine_metadata.engine,
            "model_family": self.engine_metadata.model_family,
            "model_name": self.engine_metadata.model_name,
            "model_version": self.engine_metadata.model_version,
            "implementation": self.engine_metadata.implementation,
            "language": self.engine_metadata.language,
            "device": self.engine_metadata.device,
            "compute_type": self.engine_metadata.compute_type,
            "parameters": self.engine_metadata.parameters,
            "library_version": self.engine_metadata.library_version,
            "python_version": self.engine_metadata.python_version,
            "cuda_version": self.engine_metadata.cuda_version,
            "configuration_version": self.engine_metadata.configuration_version,
        }
        return {
            "engine": metadata,
            "duration_ms": self.duration_ms,
            "processing_time_ms": self.processing_time_ms,
            "language_probability": self.language_probability,
            "text": self.text,
            "segments": [
                {
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "speaker": segment.speaker,
                    "text": segment.text,
                    "confidence": segment.confidence,
                    "words": [
                        {
                            "word": word.word,
                            "start_ms": word.start_ms,
                            "end_ms": word.end_ms,
                            "confidence": word.confidence,
                        }
                        for word in segment.words
                    ],
                }
                for segment in self.segments
            ],
            "raw_output": self.raw_output,
        }


class STTEngine(Protocol):
    """Common boundary for local or future external speech-to-text engines."""

    @property
    def metadata(self) -> EngineMetadata:
        ...

    def transcribe(self, audio_path: str | Path, language: str | None = None) -> TranscriptionResult:
        ...
