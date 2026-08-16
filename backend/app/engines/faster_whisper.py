from __future__ import annotations

import importlib.metadata
import math
import platform
import time
from pathlib import Path
from typing import Any, Protocol

from app.engines.base import EngineMetadata, SegmentResult, TranscriptionResult, WordResult


class WhisperSegmentLike(Protocol):
    start: float
    end: float
    text: str
    avg_logprob: float | None
    words: list[Any] | None


class WhisperInfoLike(Protocol):
    duration: float | None
    language: str | None
    language_probability: float | None


class WhisperModelLike(Protocol):
    def transcribe(self, audio_path: str, **kwargs: Any) -> tuple[Any, WhisperInfoLike]:
        ...


class FasterWhisperEngine:
    """Local STT adapter backed by ``faster-whisper``.

    The dependency is loaded only when a model is constructed, which keeps the
    normal test suite free from model downloads and GPU requirements. Tests can
    inject a compatible model object into ``model``.
    """

    def __init__(
        self,
        model_name: str = "large-v3",
        *,
        device: str = "cpu",
        compute_type: str = "int8",
        model_version: str | None = None,
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = True,
        word_timestamps: bool = True,
        condition_on_previous_text: bool = False,
        download_root: str | Path | None = None,
        model: WhisperModelLike | None = None,
        configuration_version: str = "v1",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.default_language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.word_timestamps = word_timestamps
        self.condition_on_previous_text = condition_on_previous_text
        self.download_root = str(download_root) if download_root else None
        self._model = model
        self._model_version = model_version
        self.configuration_version = configuration_version

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine="faster-whisper",
            model_family="whisper",
            model_name=self.model_name,
            model_version=self._model_version or self.model_name,
            implementation="ctranslate2",
            language=self.default_language,
            device=self.device,
            compute_type=self.compute_type,
            parameters=self._parameters(),
            library_version=self._package_version(),
            python_version=platform.python_version(),
            cuda_version=self._cuda_version(),
            configuration_version=self.configuration_version,
        )

    def _parameters(self) -> dict[str, Any]:
        return {
            "beam_size": self.beam_size,
            "vad_filter": self.vad_filter,
            "word_timestamps": self.word_timestamps,
            "condition_on_previous_text": self.condition_on_previous_text,
            "download_root": self.download_root,
        }

    @staticmethod
    def _package_version() -> str | None:
        try:
            return importlib.metadata.version("faster-whisper")
        except importlib.metadata.PackageNotFoundError:
            return None

    @staticmethod
    def _cuda_version() -> str | None:
        try:
            import torch

            return torch.version.cuda
        except (ImportError, AttributeError):
            return None

    def _get_model(self) -> WhisperModelLike:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed. Install backend/requirements-speech.txt "
                    "or inject a compatible model for tests."
                ) from exc
            kwargs: dict[str, Any] = {"device": self.device, "compute_type": self.compute_type}
            if self.download_root:
                kwargs["download_root"] = self.download_root
            self._model = WhisperModel(self.model_name, **kwargs)
        return self._model

    @staticmethod
    def _confidence(segment: Any) -> float | None:
        average_logprob = getattr(segment, "avg_logprob", None)
        if average_logprob is None:
            return None
        return max(0.0, min(1.0, math.exp(float(average_logprob))))

    @staticmethod
    def _milliseconds(seconds: float | None) -> int:
        return max(0, round(float(seconds or 0.0) * 1000))

    def _convert_word(self, word: Any, segment_start_ms: int) -> WordResult | None:
        start = getattr(word, "start", None)
        end = getattr(word, "end", None)
        if start is None or end is None:
            return None
        return WordResult(
            word=str(getattr(word, "word", "")).strip(),
            start_ms=self._milliseconds(start),
            end_ms=self._milliseconds(end),
            confidence=getattr(word, "probability", None),
        )

    def _convert_segment(self, segment: Any) -> SegmentResult:
        start_ms = self._milliseconds(getattr(segment, "start", 0.0))
        words = tuple(
            word_result
            for word in (getattr(segment, "words", None) or [])
            if (word_result := self._convert_word(word, start_ms)) is not None and word_result.word
        )
        return SegmentResult(
            start_ms=start_ms,
            end_ms=self._milliseconds(getattr(segment, "end", 0.0)),
            text=str(getattr(segment, "text", "")).strip(),
            confidence=self._confidence(segment),
            words=words,
        )

    def transcribe(self, audio_path: str | Path, language: str | None = None) -> TranscriptionResult:
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(f"audio file not found: {path}")
        started = time.perf_counter()
        requested_language = language or self.default_language
        options = {
            "language": requested_language,
            "beam_size": self.beam_size,
            "vad_filter": self.vad_filter,
            "word_timestamps": self.word_timestamps,
            "condition_on_previous_text": self.condition_on_previous_text,
        }
        segments, info = self._get_model().transcribe(str(path), **options)
        converted = tuple(self._convert_segment(segment) for segment in segments)
        duration_ms = self._milliseconds(getattr(info, "duration", None))
        metadata = self.metadata
        if requested_language != metadata.language:
            metadata = EngineMetadata(**{**metadata.__dict__, "language": requested_language})
        return TranscriptionResult(
            engine_metadata=metadata,
            duration_ms=duration_ms,
            processing_time_ms=round((time.perf_counter() - started) * 1000),
            segments=converted,
            language_probability=getattr(info, "language_probability", None),
            raw_output={"detected_language": getattr(info, "language", None)},
        )
