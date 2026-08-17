from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_stream_creation_and_binary_chunk_queueing():
    client = TestClient(app)
    response = client.post("/api/v1/streams", json={"language": "ar", "engine_names": ["fixture"]})
    assert response.status_code == 201
    stream_id = response.json()["stream_id"]

    with client.websocket_connect(f"/api/v1/streams/{stream_id}/ws") as websocket:
        assert websocket.receive_json()["type"] == "ready"
        websocket.send_bytes(b"audio-chunk")
        progress = websocket.receive_json()
        assert progress["type"] == "progress"
        assert progress["chunk_number"] == 1

    job = asyncio.run(app.state.job_queue.dequeue())
    assert job.stream_id == stream_id
    assert job.chunk_path.endswith("chunk-000001.bin")
    app.state.job_queue.task_done()


def test_job_event_rest_replay_and_websocket_replay():
    job_id = str(uuid.uuid4())
    asyncio.run(app.state.event_hub.publish_status(job_id, "QUEUED", 0, "Queued"))
    client = TestClient(app)

    response = client.get(f"/api/v1/jobs/{job_id}/events")
    assert response.status_code == 200
    assert response.json()[0]["message"] == "Queued"

    with client.websocket_connect(f"/api/v1/jobs/{job_id}/events/ws") as websocket:
        assert websocket.receive_json()["type"] == "ready"
        event = websocket.receive_json()
        assert event["type"] == "progress"
        assert event["event"]["status"] == "QUEUED"
