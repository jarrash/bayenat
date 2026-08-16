from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.engines.base import SegmentResult, TranscriptionResult
from app.engines.diarization import DiarizationResult, _overlap_ms, attach_speakers


@dataclass(frozen=True)
class AlignmentCandidate:
    engine: str
    start_ms: int
    end_ms: int
    speaker: str | None
    text: str
    normalized_text: str
    temporal_overlap_ms: int


@dataclass(frozen=True)
class AlignedSegment:
    start_ms: int
    end_ms: int
    speaker: str | None
    candidates: tuple[AlignmentCandidate, ...]
    alignment_score: float


@dataclass(frozen=True)
class AlignmentResult:
    segments: tuple[AlignedSegment, ...]
    engine_count: int


def normalize_for_alignment(text: str) -> str:
    """Apply comparison-only normalization without mutating source text."""
    return " ".join(text.replace("ـ", "").split()).strip()


class TranscriptAligner:
    """Align timestamped segments from one or more transcription results.

    The first implementation uses temporal overlap as the primary grouping
    signal and normalized text similarity as a secondary quality signal. It
    intentionally retains every source candidate rather than selecting one
    transcript or rewriting evidence.
    """

    def __init__(self, minimum_overlap_ms: int = 1) -> None:
        self.minimum_overlap_ms = minimum_overlap_ms

    def align(self, transcripts: Iterable[TranscriptionResult]) -> AlignmentResult:
        source_transcripts = tuple(transcripts)
        flattened: list[tuple[str, SegmentResult]] = [
            (result.engine_metadata.engine, segment)
            for result in source_transcripts
            for segment in result.segments
        ]
        flattened.sort(key=lambda item: (item[1].start_ms, item[1].end_ms, item[0]))
        groups: list[list[tuple[str, SegmentResult]]] = []
        for engine, segment in flattened:
            matching = [
                group
                for group in groups
                if any(
                    _overlap_ms(segment.start_ms, segment.end_ms, other.start_ms, other.end_ms) >= self.minimum_overlap_ms
                    for _, other in group
                )
            ]
            if not matching:
                groups.append([(engine, segment)])
                continue
            primary = matching[0]
            primary.append((engine, segment))
            for secondary in matching[1:]:
                primary.extend(secondary)
                groups.remove(secondary)

        aligned: list[AlignedSegment] = []
        for group in groups:
            start_ms = min(segment.start_ms for _, segment in group)
            end_ms = max(segment.end_ms for _, segment in group)
            speaker = self._majority_speaker(group)
            candidates = tuple(
                AlignmentCandidate(
                    engine=engine,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    speaker=segment.speaker,
                    text=segment.text,
                    normalized_text=normalize_for_alignment(segment.text),
                    temporal_overlap_ms=_overlap_ms(start_ms, end_ms, segment.start_ms, segment.end_ms),
                )
                for engine, segment in group
            )
            aligned.append(
                AlignedSegment(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    speaker=speaker,
                    candidates=candidates,
                    alignment_score=self._alignment_score(group),
                )
            )
        return AlignmentResult(segments=tuple(aligned), engine_count=len(source_transcripts))

    @staticmethod
    def _majority_speaker(group: list[tuple[str, SegmentResult]]) -> str | None:
        speakers = [segment.speaker for _, segment in group if segment.speaker]
        if not speakers:
            return None
        return max(set(speakers), key=speakers.count)

    @staticmethod
    def _alignment_score(group: list[tuple[str, SegmentResult]]) -> float:
        if len(group) <= 1:
            return 0.5
        normalized = [normalize_for_alignment(segment.text) for _, segment in group]
        agreement = sum(1 for text in normalized if text == normalized[0]) / len(normalized)
        return round(agreement, 4)


def enrich_with_diarization(transcription: TranscriptionResult, diarization: DiarizationResult) -> TranscriptionResult:
    """Convenience adapter for enriching Faster-Whisper output with speakers."""
    return attach_speakers(transcription, diarization)
