# Bayenat

**Bayenat** is an Arabic-first, AI-assisted evidence transcription and verification platform. It is designed to preserve original audio and video evidence, compare independent speech-to-text outputs, expose material disagreements, and support human review. It does not treat AI output as legally conclusive or forensically authoritative.

## Current status

The repository started empty. The current implementation is **Phase 1 foundation**: architecture documentation, tenant-scoped data models, immutable evidence and artifact concepts, SHA-256 integrity utilities, audit-event hash chaining, case creation, evidence upload validation, idempotent transcription-job submission, an integrity endpoint, and an Arabic RTL frontend shell.

The speech engines, background orchestration, alignment, consensus, diarization, waveform review, and reporting layers are extension points for subsequent phases. They are not represented as complete merely because the UI names them.

## Repository layout

```text
backend/       FastAPI API, SQLAlchemy models, integrity services, tests
frontend/      Next.js Arabic RTL dashboard shell
infrastructure/Docker Compose for PostgreSQL, Redis, API, and worker
docs/          Architecture, data model, pipeline, and security decisions
```

## Local development

Copy `.env.example` to `.env`, then run `make dev`. The development environment starts PostgreSQL, Redis, the API on port 8000, and the worker process. The API health check is available at `GET /health`; interactive OpenAPI documentation is available at `/docs`.

For backend-only tests, install `backend/requirements.txt`, then run `make test` and `make lint`. Tests use deterministic fixtures and do not download multi-gigabyte speech models.

For the frontend, run `cd frontend && pnpm install && pnpm dev`. The production build is verified with `pnpm build`.

## Phase 1 API surface

| Endpoint | Purpose |
|---|---|
| `GET /health` | Service health check |
| `POST /api/v1/cases` | Create a development-scoped case |
| `GET /api/v1/cases` | List development-scoped cases |
| `POST /api/v1/cases/{case_id}/evidence` | Validate and store an evidence upload |
| `POST /api/v1/evidence/{evidence_id}/transcribe` | Create an idempotent queued job record |
| `GET /api/v1/jobs/{job_id}` | Read job state |
| `GET /api/v1/evidence/{evidence_id}/integrity` | Verify original, artifact, and audit-chain state |

The current development principal is intentionally a local bootstrap seam. Production authentication and authorization must replace it before real evidence is processed.

## Important limitations

The project must not be used with real sensitive evidence until authentication, tenant isolation, encryption, retention, deployment hardening, and the full processing pipeline have been implemented and independently reviewed. The current worker entrypoint is deliberately idle; it does not claim to perform speech transcription. The confidence metric, consensus algorithm, diarization, and reports remain future phases.

Read `ARCHITECTURE_DECISIONS.md` and the documents under `docs/` before extending the system.
