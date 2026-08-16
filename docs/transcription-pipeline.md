# Bayenat Transcription Pipeline

## Pipeline contract

The pipeline converts an immutable evidence artifact into traceable, reviewable transcript artifacts. It preserves raw engine output, uses normalized copies only for comparison, and records enough metadata to explain how every result was produced.

```text
validated evidence
  -> normalized PCM audio
  -> quality assessment and optional VAD
  -> optional diarization
  -> parallel STT engine runs
  -> conservative text normalization
  -> timestamp-aware alignment
  -> consensus and confidence scoring
  -> disagreement and risk detection
  -> human review
```

## Engine adapter boundary

Every speech engine implements the same interface and returns a common `TranscriptionResult`. The orchestration layer knows only the interface and metadata contract; it must not contain provider-specific branching.

```python
class STTEngine(Protocol):
    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> TranscriptionResult:
        ...
```

The result includes engine name, model family, model name and version, language, device, compute type, duration, processing time, segments, optional words, and raw output references. Faster-Whisper and Whisper may share the same underlying model family; they are therefore not treated as fully independent votes. A third adapter remains replaceable and may initially be a controlled test adapter rather than a production claim.

## Processing profiles

Profiles define language, VAD, diarization, enabled engines, minimum successful engines, and consensus-risk flags. Profiles are configuration data, not hardcoded branches. A first profile may target Arabic with at least two successful engines, while CPU-safe test profiles use deterministic mock engines and synthetic fixtures.

## Normalization

The system stores both `raw_text` and `normalized_text`. Arabic normalization is conservative and configurable. It may normalize Unicode form, whitespace, tatweel, punctuation, and selected character variants for comparison. It must not silently change grammar, remove meaningful words, or replace the raw evidence-derived text.

## Alignment

Alignment uses timestamps, temporal overlap, and text similarity at segment and word levels. Candidate comparisons may use Levenshtein distance, WER/CER-style measures, and RapidFuzz-compatible similarity, but no single metric is treated as a truth oracle. The output preserves each engine candidate, its time range, speaker label where available, and the alignment quality.

Important risk classes include negation changes such as `تم` versus `لم يتم`, number and date differences, names, currency, technical terms, and legal terms. Alignment must be able to represent insertion, deletion, substitution, and unmatched candidates.

## Consensus

`ConsensusEngine` produces a consensus text and records the candidates and scoring inputs used to select it. The score considers cross-engine agreement, model-family diversity, configured engine reliability, word-level confidence, temporal alignment, language consistency, audio quality, and segment quality. Model-family correlation reduces the apparent independence of engines that share model weights.

The **Bayenat Confidence Score** is a platform-derived decision-support metric on a 0–100 scale. It is classified as `HIGH`, `MEDIUM`, `LOW`, or `REVIEW_REQUIRED`. It must be presented with an explanation and never described as scientific certainty or legal proof.

## Disagreement detection

The detector emits structured disagreements with a type, severity, candidates, and review requirement. Negation and number conflicts receive additional risk weight. A segment may have multiple disagreements, and a reviewer decision does not delete the original disagreement; it records the human resolution separately.

| Signal | Default risk treatment | Why it matters |
|---|---:|---|
| Exact or near-exact agreement | Lowers review pressure | Candidate stability across aligned engines |
| Model-family diversity | Raises evidentiary value of agreement | Reduces correlated-vote inflation |
| Negation conflict | Critical by default | May reverse the meaning of a statement |
| Number/date/currency conflict | High by default | Small token changes may alter material facts |
| Poor audio or overlap | Raises review pressure | Makes confidence less reliable |
| Missing engine | Partial-success warning | Reduces available comparison evidence |

## Failure handling and idempotency

Workers report progress through explicit job states. One engine failure does not automatically fail the whole job. If at least the configured minimum number of engines succeed, consensus may proceed as `PARTIAL_SUCCESS`; otherwise the job fails with complete engine-level reasons.

A processing request is identified by evidence hash, profile, model versions, configuration version, and relevant decoding parameters. An identical completed request may be reused, while an explicit reprocessing request always creates a new run and lineage branch.

## Reproducibility

Every engine run stores model family, model name, revision, library version, Python version, CUDA version when relevant, device, compute type, decoding parameters, language configuration, processing timestamps, and failure details. The pipeline version and configuration version are also persisted so scoring behavior can be compared across releases.

## Test strategy

Normal tests use mock engines and small synthetic fixtures. Required cases include matching transcripts, minor disagreement, negation conflict, number conflict, missing engine, low-confidence audio metadata, Arabic normalization, and mixed Arabic-English content. Large model downloads are not required for unit, API, or CI tests.

## References

[1]: https://github.com/SYSTRAN/faster-whisper "Faster-Whisper repository"
[2]: https://github.com/openai/whisper "OpenAI Whisper repository"
[3]: https://github.com/pyannote/pyannote-audio "pyannote.audio repository"
[4]: https://github.com/snakers4/silero-vad "Silero VAD repository"
[5]: https://github.com/rapidfuzz/RapidFuzz "RapidFuzz repository"
