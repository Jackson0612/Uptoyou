"""Ticket 20 — the circle's live channel, in memory, in this process.

D52 keys the stream on the circle, so the broker is a set of queues per circle id. The write
endpoints publish after their transaction commits — an event for a write that rolled back
would be a lie, and an event before the commit races the snapshot a new subscriber builds.

In-memory is a deliberate ceiling, not an oversight: one API process serves five friends
(D6 measured the workload), and presence — like every cross-restart guarantee — was already
priced at "nowhere durable to live" by D52. The stream's correctness on reconnect never
rests on the broker anyway: D56 makes the snapshot the first event, so a dropped queue costs
a reconnect exactly what a network blip costs, and the snapshot answers both.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager

_subscribers: dict[int, set[asyncio.Queue]] = defaultdict(set)


def publish(circle_id: int, event: dict) -> None:
    """Hand one event to every open stream on this circle. Never blocks a write path."""
    for queue in _subscribers[circle_id]:
        queue.put_nowait(event)


@asynccontextmanager
async def subscribe(circle_id: int):
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[circle_id].add(queue)
    try:
        yield queue
    finally:
        _subscribers[circle_id].discard(queue)
