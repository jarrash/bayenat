from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import AsyncIterator

from app.schemas.transcription import JobEventRead


class JobEventHub:
    """Development event bus; production should back replay with durable storage."""

    def __init__(self, max_events_per_job: int = 200) -> None:
        self._next_id = 0
        self._events: dict[str, deque[JobEventRead]] = defaultdict(lambda: deque(maxlen=max_events_per_job))
        self._subscribers: dict[str, set[asyncio.Queue[JobEventRead]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, event: JobEventRead) -> JobEventRead:
        async with self._lock:
            self._next_id += 1
            stored = event.model_copy(update={"event_id": self._next_id})
            self._events[event.job_id].append(stored)
            subscribers = tuple(self._subscribers[event.job_id])
        for subscriber in subscribers:
            await subscriber.put(stored)
        return stored

    async def replay(self, job_id: str, after_event_id: int = 0) -> list[JobEventRead]:
        async with self._lock:
            return [event for event in self._events[job_id] if event.event_id > after_event_id]

    async def subscribe(self, job_id: str) -> AsyncIterator[JobEventRead]:
        async for event in self.subscribe_from(job_id, 0):
            yield event

    async def subscribe_from(self, job_id: str, after_event_id: int = 0) -> AsyncIterator[JobEventRead]:
        queue: asyncio.Queue[JobEventRead] = asyncio.Queue()
        async with self._lock:
            replay = [event for event in self._events[job_id] if event.event_id > after_event_id]
            self._subscribers[job_id].add(queue)
        try:
            for event in replay:
                yield event
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[job_id].discard(queue)
                if not self._subscribers[job_id]:
                    self._subscribers.pop(job_id, None)

    async def publish_status(self, job_id: str, status: str, progress: int, message: str, *, result: dict | None = None, error: str | None = None) -> JobEventRead:
        return await self.publish(JobEventRead(
            event_id=0,
            job_id=job_id,
            status=status,
            progress=progress,
            message=message,
            result=result,
            error=error,
            created_at=datetime.now(timezone.utc),
        ))
