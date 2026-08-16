# Bayenat Data Model

## Modeling principles

Bayenat separates **evidence**, **derived artifacts**, **machine transcripts**, **consensus results**, **human review**, and **finalized output**. A transcript is never an in-place mutation of the original evidence or a prior transcript version. All tenant-owned records carry `tenant_id`, and all timestamps are stored in UTC.

## Core entities

| Entity | Key fields | Integrity and lifecycle rules |
|---|---|---|
| Tenant | `id`, `name`, `status`, `created_at` | Root scope for tenant-owned data |
| User | `id`, `tenant_id`, `email`, `password_hash`, `status` | Passwords are never stored in plaintext |
| Role / permission | `role`, `permissions` | Enforced server-side for every protected action |
| Case | `id`, `tenant_id`, `reference_number`, `title`, `case_type`, `status`, `created_by` | Soft deletion may apply; ownership is tenant-scoped |
| Evidence | `id`, `tenant_id`, `case_id`, filename, detected media metadata, storage URI, SHA-256 | Original file is immutable; deletion is restricted |
| EvidenceArtifact | `id`, `tenant_id`, `evidence_id`, `parent_artifact_id`, `artifact_type`, hash, processing job | Forms a lineage tree from original to reports |
| ProcessingJob | `id`, `tenant_id`, `evidence_id`, profile, status, idempotency key, timestamps | State transitions are explicit and auditable |
| EngineRun | `id`, `processing_job_id`, engine metadata, status, error, duration | Each engine succeeds or fails independently |
| Transcript | `id`, `artifact_id`, `engine_run_id`, `kind`, raw payload, normalized payload | Machine outputs are immutable once recorded |
| TranscriptSegment | `id`, `transcript_id`, start/end, speaker, raw text, normalized text | Coordinates remain tied to the source media timeline |
| TranscriptWord | `id`, `segment_id`, start/end, word, confidence | Optional when an engine provides word timing |
| ConsensusSegment | `id`, `processing_job_id`, time range, text, score, review flag | Stores candidates and scoring metadata, not only selected text |
| Disagreement | `id`, `consensus_segment_id`, type, severity, candidates, review flag | High-risk disagreements remain visible after review |
| Review | `id`, `tenant_id`, `evidence_id`, reviewer, status, timestamps | Status transitions are controlled and audited |
| ReviewEdit | `id`, `review_id`, `segment_id`, before/after, note, actor | Every edit creates a durable event |
| AuditEvent | `id`, tenant/case/evidence/artifact references, type, payload, previous hash, event hash | Append-only application semantics and deterministic hash chaining |
| Report | `id`, evidence/job references, type, artifact, format, generated metadata | Report is a derived artifact and can be regenerated |

## Artifact lineage

The expected artifact types are `ORIGINAL`, `NORMALIZED_AUDIO`, `SEGMENT`, `ENGINE_TRANSCRIPT`, `CONSENSUS_TRANSCRIPT`, `REVIEWED_TRANSCRIPT`, `FINAL_TRANSCRIPT`, and `REPORT`. Each artifact has a `parent_artifact_id` where applicable, a content hash, a hash algorithm, a creator, a creation timestamp, and an optional processing-job reference.

```text
ORIGINAL
  └── NORMALIZED_AUDIO
        └── SEGMENT (optional, one or more)
              ├── ENGINE_TRANSCRIPT (one per engine run)
              ├── CONSENSUS_TRANSCRIPT
              └── REVIEWED_TRANSCRIPT
                    └── FINAL_TRANSCRIPT
                          └── REPORT
```

This structure allows an auditor to distinguish the uploaded bytes from normalized working media, machine output, consensus output, and human-approved text.

## Tenant isolation

Every repository method that reads or writes tenant-owned data accepts a tenant scope. The API obtains the tenant from the authenticated principal and never trusts a client-supplied tenant identifier for authorization. Cross-tenant access tests are mandatory before the foundation is considered complete.

## Review state machine

The review status progression is:

```text
MACHINE_GENERATED -> REVIEW_REQUIRED -> IN_REVIEW -> REVIEWED -> APPROVED -> LOCKED
```

A reviewer may mark individual segments verified or uncertain. Finalization creates a new final artifact and does not erase the consensus transcript, engine transcripts, or prior review edits. A locked transcript cannot be edited in place; a new review or version must be created according to the eventual governance policy.

## Audit-chain payload

Audit events use canonical JSON with stable key ordering, normalized timestamps, and explicit event metadata. The event hash is calculated from the canonical payload plus the previous event hash. Integrity verification checks the original file hash, artifact hashes, and audit chain independently so one failure does not obscure the others.

## Indexing priorities

Initial indexes should cover tenant and case ownership, evidence hash, case/evidence relationships, processing-job status and timestamps, engine-run job relationship, transcript segment time ranges, disagreement severity, and audit-event evidence/timestamp. Later deployments may add full-text or vector indexes, but those are not required for the evidence foundation.

## Deletion and retention

Evidence, artifacts, transcripts, audit events, and reports require stricter deletion rules than ordinary user-interface records. The initial implementation should expose no destructive evidence deletion endpoint. Retention, secure deletion, legal hold, and tenant-specific encryption keys remain policy-driven extensions and must be documented before production deployment.

## References

[1]: https://www.postgresql.org/docs/current/ddl-constraints.html "PostgreSQL constraints"
[2]: https://www.postgresql.org/docs/current/datatype.html "PostgreSQL data types"
