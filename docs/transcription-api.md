# Bayenat transcription API

## Batch submission

Submit an authorized evidence item with:

```http
POST /api/v1/evidence/{evidence_id}/transcribe
Content-Type: application/json
Idempotency-Key: optional-client-key

{
  "language": "ar",
  "profile": "arabic_forensic",
  "engine_names": ["faster-whisper"]
}
```

The endpoint returns `202 Accepted` with the existing `JobRead` object. Repeating the same evidence/profile/engine/language request, or reusing the same idempotency key, returns the existing job rather than enqueueing a duplicate. The queue payload contains the tenant ID, evidence ID, private storage path, language, profile, and engine names.

## REST event replay

```http
GET /api/v1/jobs/{job_id}/events?after_event_id=0
```

The response is an ordered list of `JobEventRead` objects. Clients persist the largest `event_id` they receive and pass it as `after_event_id` when reconnecting. The development event hub retains a bounded in-memory history; production must replace it with durable tenant-scoped event storage.

## Job progress WebSocket

```text
ws://host/api/v1/jobs/{job_id}/events/ws?after_event_id=42
```

The server sends a `ready` message, replays events newer than the cursor, then streams live `progress` messages. Terminal states are `COMPLETED`, `PARTIAL_SUCCESS`, and `FAILED`; the server closes normally after delivering a terminal event. If a connection drops, reconnect with the last confirmed `event_id`.

Example server messages:

```json
{"type":"ready","job_id":"...","after_event_id":42}
{"type":"progress","event":{"event_id":43,"status":"TRANSCRIBING","progress":40,"message":"Running speech engines"}}
```

The subscription registers before replaying history, preventing a progress event from being lost between the replay and live-subscription phases.

## Streaming audio WebSocket

Create a stream first:

```http
POST /api/v1/streams
Content-Type: application/json

{"language":"ar","profile":"arabic_forensic","engine_names":["faster-whisper"]}
```

Then connect to the returned WebSocket URL. Send binary WebSocket frames containing sequential audio chunks. Each chunk is written to a private stream directory before a `STREAM_CHUNK` job is enqueued. Send a text control message to finalize:

```json
{"type":"finalize"}
```

The server enqueues `STREAM_FINALIZE`, emits an alignment-progress event, sends a completion message, and closes the socket. `ping` is supported for liveness. Chunk transcripts are provisional; final alignment is the authoritative stream boundary.

## Security requirements

The current development routes use the repository’s development principal and in-memory stream registry. Before production use, require authenticated tenant-scoped principals for every route and WebSocket, verify evidence ownership before enqueueing, authorize stream IDs, apply per-tenant quotas, limit frame size and duration, encrypt temporary chunks, and avoid logging raw audio or transcript contents. WebSocket authentication may use the existing access token during the handshake; never accept an unauthenticated job ID as proof of access.
