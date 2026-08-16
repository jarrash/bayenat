# Bayenat Security and Privacy

## Security posture

Bayenat processes potentially sensitive audio, video, transcripts, and case metadata. The default posture is local or private processing, least privilege, explicit tenant scoping, immutable evidence handling, and human-verifiable auditability. Security controls are part of the product foundation, not a later hardening pass.

## Threat model summary

| Threat | Required control | Verification |
|---|---|---|
| Malicious upload | Actual media inspection with ffprobe, size limits, generated storage names, safe storage boundary | Upload security tests |
| Path traversal | Never concatenate user filenames into filesystem paths | Filename and traversal tests |
| Cross-tenant disclosure | Server-side tenant scope on repositories and routes | Cross-tenant authorization tests |
| Unauthorized review or export | Role and permission checks in backend services | Authorization tests |
| Evidence tampering | SHA-256 for originals and derived artifacts | Hash verification tests |
| Audit manipulation | Append-only semantics and hash chaining | Chain tamper tests |
| Secret leakage | Environment-based configuration and redacted logs | Configuration review |
| External data exposure | No external speech API by default | Deployment/configuration review |
| Unsafe generated output | Encode report fields and avoid executable content | Export tests |
| Abuse or resource exhaustion | Upload limits, rate-limit seam, queue controls, bounded worker concurrency | Integration and load planning |

## Upload and media validation

The API must not trust filename extensions or client MIME types. It validates the actual media using ffprobe/FFmpeg, accepts only configured audio/video formats, enforces a maximum size, and records detected media type and metadata. The original is stored under a generated identifier, not a user-controlled filename. User-provided filenames remain metadata and are encoded safely in UI and reports.

The original file is read-only at the application layer. Derived normalized audio is created in a separate location and receives its own artifact hash. Internal filesystem paths and storage credentials are never returned to clients.

## Authentication and authorization

The initial authorization architecture supports JWT access tokens, refresh tokens, password hashing, tenant scoping, and roles such as `ADMIN`, `CASE_MANAGER`, `EXPERT`, `REVIEWER`, `VIEWER`, and `AUDITOR`. Permissions include viewing and uploading evidence, running transcription, reviewing, approving, exporting, and viewing audit logs. Backend checks are mandatory even when the frontend hides unavailable controls.

## Privacy controls

Evidence is not sent to external APIs by default. Storage abstraction must support local development and S3-compatible production storage, while leaving room for encryption at rest, KMS integration, tenant-specific keys, retention policy, secure deletion, Saudi data residency, private deployment, and air-gapped deployment. These are deployment and governance requirements that must be explicitly configured before production use.

The system should avoid unnecessary collection of IP addresses and user agents, but custody events may record them where policy permits and where they are needed for accountability. Retention and legal-hold rules must be defined by the deploying organization; the MVP must not invent a universal retention period.

## Evidence and audit integrity

The original SHA-256 is calculated immediately after upload. Each derived artifact has its own hash and parent reference. Audit events use deterministic canonical JSON and include the previous event hash. Verification reports original-file validity, artifact-chain validity, and audit-chain validity independently. The platform must describe this as tamper-evident hash chaining, not blockchain, and must not imply that hashing alone proves the truth of the content.

## Logging and observability

Structured logs include a request ID and, where applicable, job, case, evidence, and tenant identifiers. Logs must not include raw audio, full transcripts, passwords, tokens, or unnecessary personal information. Processing durations, queue time, engine duration, failure rate, and CPU/GPU mode are tracked for operational diagnosis. The design leaves an integration seam for OpenTelemetry and Prometheus.

## Security test minimum

Before Phase 1 is accepted, tests must cover malicious filenames, path traversal, invalid media type, oversized upload, unauthorized evidence access, cross-tenant access, tampered audit events, and tampered evidence hashes. Tests use fixtures and mocks; they do not require external model downloads.

## Operational caveat

Bayenat must not be marketed as a system that independently determines legal truth, speaker identity, or forensic conclusions. Speaker labels are system identifiers until a human assigns contextual labels. Any later LLM feature must be separately stored, labeled as generated assistance, and prohibited from silently rewriting the evidentiary transcript.

## References

[1]: https://owasp.org/www-project-file-upload-cheat-sheet/ "OWASP File Upload Cheat Sheet"
[2]: https://owasp.org/www-project-api-security/ "OWASP API Security Project"
[3]: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html "OWASP Logging Cheat Sheet"
[4]: https://ffmpeg.org/ffprobe.html "FFprobe documentation"
