from __future__ import annotations

import asyncio
import os
import time
from collections import Counter

import pytest

from app.services.transcription_jobs import RedisJobQueue, TranscriptionJob

pytestmark = pytest.mark.integration


async def run_integration() -> dict[str, object]:
    redis_url = os.getenv("BAYENAT_TEST_REDIS_URL", "redis://127.0.0.1:6381/15")
    stream = f"bayenat:integration:{time.time_ns()}"
    producer = RedisJobQueue(redis_url, stream_name=stream)
    workers = [RedisJobQueue(redis_url, stream_name=stream) for _ in range(4)]
    total = 48
    jobs = [
        TranscriptionJob.create_batch(
            tenant_id="tenant-integration",
            evidence_id=f"evidence-{index}",
            audio_path=f"/private/evidence-{index}.wav",
            language="ar",
            engine_names=("fixture",),
        )
        for index in range(total)
    ]
    for job in jobs:
        await producer.enqueue(job)

    processed: list[tuple[str, str]] = []
    lock = asyncio.Lock()

    async def consume(worker_index: int, queue: RedisJobQueue) -> None:
        while True:
            if len(processed) >= total:
                return
            try:
                job = await asyncio.wait_for(queue.dequeue(), timeout=2)
            except (asyncio.TimeoutError, TimeoutError):
                if len(processed) >= total:
                    return
                raise
            await asyncio.sleep(0.005 + (worker_index * 0.002))
            async with lock:
                processed.append((job.job_id, queue.consumer_name))
            await queue.acknowledge(job)

    await asyncio.gather(*(consume(index, queue) for index, queue in enumerate(workers)))
    processed_ids = [job_id for job_id, _ in processed]
    consumer_counts = Counter(consumer for _, consumer in processed)
    pending_after_workers = await producer.pending_count()

    probe = TranscriptionJob.create_batch(
        tenant_id="tenant-integration",
        evidence_id="evidence-probe",
        audio_path="/private/probe.wav",
        engine_names=("fixture",),
    )
    await producer.enqueue(probe)
    probe_worker = workers[0]
    delivered_probe = await probe_worker.dequeue()
    pending_before_ack = await producer.pending_count()
    await probe_worker.acknowledge(delivered_probe)
    pending_after_ack = await producer.pending_count()

    redis = producer._redis
    await redis.delete(stream)
        
    assert len(processed_ids) == total
    assert len(set(processed_ids)) == total
    assert pending_after_workers == 0
    assert pending_before_ack == 1
    assert pending_after_ack == 0
    assert len(consumer_counts) >= 2, consumer_counts
    return {
        "total_jobs": total,
        "unique_jobs": len(set(processed_ids)),
        "pending_after_workers": pending_after_workers,
        "pending_before_ack": pending_before_ack,
        "pending_after_ack": pending_after_ack,
        "consumer_counts": dict(consumer_counts),
    }


@pytest.mark.asyncio
async def test_redis_streams_concurrent_workers():
    try:
        result = await run_integration()
    except Exception as exc:
        if "Connection refused" in str(exc) or "connect" in str(exc).lower():
            pytest.skip(f"Redis integration server unavailable: {exc}")
        raise
    print(result)
