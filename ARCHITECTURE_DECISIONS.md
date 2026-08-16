# Bayenat Architecture Decisions

## ADR-001: Start from an empty Bayenat repository

**Decision.** Bayenat will be implemented as a new platform in `jarrash/bayenat`. Fleetbase and SearchPhone are reference repositories only and will not be copied into the product unless a later decision identifies a concrete reusable component.

**Rationale.** Fleetbase solves logistics operations, while SearchPhone solves a different phone-number intelligence problem. Treating either as the implicit base would create architectural coupling and product confusion.

## ADR-002: Preserve evidence and derived artifacts as separate versions

**Decision.** Original evidence is immutable at the application layer. Normalized media, engine transcripts, consensus transcripts, reviewed transcripts, final transcripts, and reports are separate artifacts with hashes and parent lineage.

**Rationale.** A serious evidence workflow must distinguish source bytes from machine and human-derived outputs. In-place mutation would make review and later verification ambiguous.

## ADR-003: Use asynchronous jobs for processing

**Decision.** Upload and job-submission endpoints return quickly. Redis-backed workers process normalization, speech engines, alignment, consensus, and reporting asynchronously.

**Rationale.** Recordings can be long and model inference can be expensive. Keeping an HTTP request open is unreliable and prevents progress reporting, retries, partial success, and independent engine failure handling.

## ADR-004: Use an adapter interface for speech engines

**Decision.** The pipeline depends on a common STT engine contract. Faster-Whisper, Whisper, and future providers implement adapters; the orchestration layer never calls provider-specific APIs directly.

**Rationale.** This keeps model changes replaceable and supports local, private, CPU, GPU, or future cloud deployments without contaminating business logic.

## ADR-005: Correct for model-family correlation

**Decision.** Consensus weighting includes model-family metadata and a correlation adjustment. Two implementations using essentially the same model family do not count as fully independent evidence.

**Rationale.** Naive majority voting would overstate confidence when engines share training data or weights.

## ADR-006: Make the reviewer the authority over final text

**Decision.** Bayenat may propose consensus text and highlight risk, but only a human workflow can create reviewed or approved output. Machine output is retained and never silently rewritten.

**Rationale.** The product’s value is traceable assistance and efficient verification, not an unsupported claim that AI determines legal or forensic truth.

## ADR-007: Arabic-first, bilingual-ready interface

**Decision.** The initial interface is Arabic RTL with an English LTR structure prepared through centralized translation keys.

**Rationale.** Arabic is the initial target language, but the platform must support mixed Arabic-English evidence and future English workflows without duplicating components.

## ADR-008: Local processing by default

**Decision.** Evidence processing is local/private by default. External APIs are optional integrations and are not enabled implicitly.

**Rationale.** Audio and video evidence can contain sensitive information. A cloud speech call must be a deliberate deployment decision with an explicit data-processing policy.

## ADR-009: Phase 1 is foundation, not a fake end-to-end demo

**Decision.** Phase 1 prioritizes repository structure, Docker services, database models, authentication skeleton, case management, upload validation, hashing, artifact registration, and tests. Speech inference and the reviewer experience follow in later phases.

**Rationale.** The critical failure mode is building a visually convincing application that cannot preserve lineage, enforce tenancy, or reproduce results. Foundation controls must be tested before model and UI expansion.

## ADR-010: Confidence is a platform metric, not scientific certainty

**Decision.** The product names its score the Bayenat Confidence Score, documents the inputs and limitations, and always exposes review-required conditions.

**Rationale.** A numerical score can help prioritize human attention, but it cannot independently establish transcript truth or legal admissibility.

## Open decisions before production

| Decision | Why it matters | Proposed time |
|---|---|---|
| Authorized user and deployment jurisdiction | Determines privacy, retention, residency, and access policies | Before pilot |
| Evidence corpus and evaluation protocol | Needed to measure Arabic accuracy and disagreement quality | Before engine selection |
| Third STT architecture | Determines genuine model diversity and operating cost | Before Phase 2 completion |
| Governance for approval and locking | Determines who may finalize output and how corrections are versioned | Before Phase 5 |
| Storage encryption and key ownership | Determines production security boundary | Before handling real evidence |
