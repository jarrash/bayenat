# Bayenat Asynchronous Transcription Architecture

## Processing boundary

The API creates a `TranscriptionJob` and enqueues it; it never holds an HTTP request open for model inference. A worker consumes the job, invokes the provider-neutral `STTEngine` contract, optionally runs diarization, aligns the resulting timestamped segments, and emits progress and final events.

```text
API
  -> JobQueue
      -> TranscriptionWorker
          -> media preprocessing
          -> optional diarization provider
          -> parallel STTEngine adapters
          -> timestamp-aware TranscriptAligner
          -> result event / persistence boundary
```

## Job kinds

| Kind | Input | Output |
|---|---|---|
| `BATCH` | Immutable audio path and evidence ID | Full engine results, optional speaker labels, aligned candidates |
| `STREAM_CHUNK` | Stream ID and durable chunk path | Incremental engine results for the chunk |
| `STREAM_FINALIZE` | Stream ID | Final alignment over accumulated chunk results |

Streaming chunks are persisted before enqueueing. The worker keeps only stream state and result references in memory in this development implementation; production should move chunk manifests and partial results into durable storage with a TTL and tenant scope.

## Queue implementations

`InMemoryJobQueue` supports local development and deterministic tests. `RedisJobQueue` uses Redis Streams and consumer groups for production-oriented delivery, allowing multiple workers to share work. The queue payload contains IDs and paths, not raw audio bytes or secrets.

Production additions required before real evidence use include retry policy, dead-letter handling, idempotency keys, stale consumer recovery, visibility timeout policy, job cancellation, durable progress events, and tenant-aware rate limits.

The real integration test is `backend/tests/integration/test_redis_streams.py`. Start an isolated Redis instance and run it with:

```bash
redis-server --port 6381 --bind 127.0.0.1 --save '' --appendonly no --daemonize yes
cd backend
BAYENAT_TEST_REDIS_URL=redis://127.0.0.1:6381/15 python3 -m pytest -q -s -m integration tests/integration/test_redis_streams.py
```

The test publishes 48 jobs, consumes them with four distinct consumer identities, verifies every job is delivered exactly once in the successful run, checks that pending count reaches zero after explicit acknowledgments, and probes that an unacknowledged delivery remains pending until it is acknowledged.

## Failure semantics

Each engine is invoked independently through `asyncio.to_thread`, so synchronous model inference does not block the event loop. A failed engine is omitted from the successful result set but must be recorded by the persistence layer. If at least one engine succeeds, the worker may emit `PARTIAL_SUCCESS`; if all fail, the job is `FAILED`. The current in-memory implementation preserves this status boundary and is ready for durable engine-run records.

## Diarization and alignment

`PyannoteDiarizer` is an optional local adapter. It returns time-bounded system speaker labels such as `SPEAKER_01`; it never infers real identities. `attach_speakers` assigns the label with maximum temporal overlap to each transcription segment. `TranscriptAligner` groups segments by timestamp overlap, retains every engine candidate, records normalized comparison text, and emits an alignment score. It does not choose a consensus transcript or overwrite raw text.

## Streaming limitations

Chunk-level transcription can repeat or omit words at chunk boundaries. The current architecture therefore treats chunk outputs as provisional and requires finalization before an authoritative alignment is produced. A production streaming implementation should add overlap windows, stable-prefix detection, boundary reconciliation, and a final pass over the complete normalized stream.

## Security and privacy

Queue messages contain references to private storage and tenant/evidence IDs. Workers must verify tenant ownership before reading paths, must not log raw audio or full transcripts, and must redact credentials from errors. A real deployment should use durable object storage, encrypted temporary workspaces, resource limits, and cleanup on success and failure.
