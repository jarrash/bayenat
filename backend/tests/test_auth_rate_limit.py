from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.auth import create_access_token, decode_access_token
from app.main import app
from app.middleware.rate_limit import SlidingWindowLimiter


def test_jwt_round_trip_preserves_tenant_claims():
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="REVIEWER", email="reviewer@example.test")
    principal = decode_access_token(token)
    assert principal.user_id == user_id
    assert principal.tenant_id == tenant_id
    assert principal.role == "REVIEWER"


def test_rate_limiter_rejects_after_window_limit():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    assert limiter.allow("tenant:test")[0] is True
    assert limiter.allow("tenant:test")[0] is True
    allowed, retry_after = limiter.allow("tenant:test")
    assert allowed is False
    assert retry_after >= 1
    assert limiter.allow("tenant:other")[0] is True


def test_event_replay_rejects_other_tenant():
    job_id = uuid.uuid4()
    owner_tenant = uuid.uuid4()
    attacker_tenant = uuid.uuid4()
    app.state.job_tenants[str(job_id)] = owner_tenant
    token = create_access_token(user_id=uuid.uuid4(), tenant_id=attacker_tenant, role="REVIEWER", email="attacker@example.test")
    response = TestClient(app).get(f"/api/v1/jobs/{job_id}/events", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    app.state.job_tenants.pop(str(job_id), None)


def test_websocket_rejects_other_tenant_stream():
    client = TestClient(app)
    stream = client.post("/api/v1/streams", json={"engine_names": ["fixture"]}).json()
    attacker = create_access_token(user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="REVIEWER", email="attacker@example.test")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"{stream['websocket_url']}?access_token={attacker}"):
            pass
