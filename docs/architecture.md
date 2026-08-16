# Bayenat Architecture

## Purpose

Bayenat is an Arabic-first, AI-assisted evidence transcription and verification platform. It is designed to preserve original evidence, produce reproducible machine outputs, expose disagreements between speech-to-text engines, and support a human reviewer who creates a clearly versioned final transcript. Bayenat is **decision-support software**; it must not represent machine output or a platform score as legally conclusive or forensically authoritative.

The repository was empty at project start. This document therefore establishes a clean foundation rather than describing an inherited implementation.

## Architectural priorities

| Priority | Required behavior | Architectural consequence |
|---|---|---|
| Evidence integrity | Originals are immutable and hash-verifiable | Store originals separately from derived artifacts; record SHA-256 immediately after validation |
| Traceability | Every derived result points to its parent and processing run | Use artifact lineage, immutable machine transcript versions, and append-only audit events |
| Explainability | Consensus, confidence, and disagreement results are inspectable | Keep engine metadata, alignment candidates, scoring inputs, and algorithm versions |
| Human verification | A reviewer can inspect audio, candidates, risks, and edit segments | Treat review as a first-class workflow, not a text-editing afterthought |
| Arabic support | Arabic RTL is the initial interface and processing target | Preserve raw Arabic text and apply conservative, configurable normalization only for comparison |
| Reproducibility | A result can be understood and, where possible, repeated later | Persist model, library, device, decoding, configuration, and processing metadata |
| Privacy | Sensitive evidence is processed locally by default | External speech APIs are opt-in; storage and processing are provider-neutral |

## System boundary

The MVP is a modular monorepo with a FastAPI backend, a Next.js frontend, PostgreSQL, Redis, and a background worker. Expensive media and speech processing must never run inside a request-response cycle.

```text
Browser (Arabic RTL / English LTR)
              |
              v
        FastAPI API  ------ PostgreSQL
              |                  |
              v                  v
        Redis queue        Cases, evidence,
              |             artifacts, reviews,
              v             audit chain, reports
       Worker processes
       |       |       |
   FFmpeg   VAD   STT adapters
       |               |
       +------> alignment / consensus / risk
                       |
                       v
              versioned transcript artifacts
```

The frontend communicates only through documented API contracts. Business rules belong in application services and domain modules, not in route handlers or React components. Persistence is accessed through repositories or explicit data-access boundaries.

## Evidence lifecycle

```text
Upload
  -> validate actual media with ffprobe
  -> store immutable original
  -> calculate SHA-256
  -> create ORIGINAL artifact and custody events
  -> create derived normalized audio
  -> optional VAD and diarization
  -> run configured STT adapters in background
  -> preserve raw engine results
  -> normalize copies for comparison
  -> align candidates by time and text
  -> calculate consensus, confidence, and disagreements
  -> human review and segment-level edits
  -> finalize a new reviewed artifact
  -> generate technical and reviewed-transcript reports
  -> verify artifact and audit chains
```

No step may overwrite the original file or silently replace a prior transcript. Reprocessing creates a new processing job and new artifacts, even when an idempotency key permits reuse of an identical completed run.

## Major modules

| Module | Responsibility | Must not do |
|---|---|---|
| Evidence service | Upload validation, metadata extraction, storage, hashing, artifact registration | Modify original evidence |
| Media service | FFmpeg normalization and media-quality measurements | Decide transcript correctness |
| Processing service | Job orchestration and state transitions | Keep long-running work in HTTP requests |
| Engine adapters | Convert individual STT implementations into a common result | Know about consensus or review UI |
| Alignment service | Timestamp-aware segment and word candidate alignment | Rewrite raw engine transcripts |
| Consensus service | Produce explainable consensus candidates and scores | Treat correlated model families as independent votes |
| Risk service | Detect negations, numbers, names, dates, currency, and other disagreements | Hide disagreements behind one text result |
| Review service | Segment verification, edits, notes, finalization, authorization | Destroy machine-generated versions |
| Integrity service | Artifact hashes, audit hash chain, verification endpoint | Claim blockchain or legal authority |
| Reporting service | Technical and reviewed transcript JSON/HTML exports | Invent facts not present in stored records |
| Identity service | Authentication, tenant scoping, role permissions | Rely on frontend authorization |

## Processing states

Processing jobs use explicit state transitions: `QUEUED`, `PREPROCESSING`, `DIARIZING`, `TRANSCRIBING`, `ALIGNING`, `CONSENSUS`, `COMPLETED`, `PARTIAL_SUCCESS`, and `FAILED`. Engine-level failures are stored independently. A configured minimum number of successful engines may allow the pipeline to continue, but the final status must communicate partial success and the failure reason.

## Deployment shape

Docker Compose is the development target and includes `api`, `worker`, `postgres`, `redis`, and `frontend`. GPU processing is optional. CPU mode must remain usable for development and tests. Local filesystem storage is the development adapter; an S3-compatible interface is the production seam. No cloud provider-specific API should leak into domain services.

## Security and privacy posture

The platform assumes evidence can contain highly sensitive personal, commercial, or legal information. Uploads are validated by actual media inspection, constrained by configurable size limits, stored with generated safe paths, and never exposed through internal filesystem paths. Tenant ownership is enforced server-side on every tenant-scoped query. Secrets come from environment configuration. External APIs are disabled by default for evidence processing.

## Explicit non-goals for Phase 1

Phase 1 will not implement production-grade diarization, real multi-engine GPU inference, legal conclusions, LLM rewriting of evidentiary transcripts, semantic search, RAG, billing, or a claim that a confidence score is scientifically validated. It will establish extension points and tested seams for those capabilities.

## Risks requiring validation

The largest technical risk is not the web interface; it is whether selected Arabic speech engines produce sufficiently diverse and reproducible outputs to justify a multi-engine comparison. The second is the cost and operational complexity of diarization and model distribution. The third is the legal and privacy posture of storing sensitive recordings. These risks should be tested with a small, authorized corpus before committing to broad production claims.

## References

[1]: https://fastapi.tiangolo.com/ "FastAPI documentation"
[2]: https://ffmpeg.org/ffprobe.html "FFprobe documentation"
[3]: https://www.postgresql.org/docs/ "PostgreSQL documentation"
[4]: https://redis.io/docs/latest/ "Redis documentation"
