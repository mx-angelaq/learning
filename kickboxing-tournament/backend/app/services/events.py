"""Server-Sent Events manager for live updates."""

import asyncio
import json
from typing import Dict, Set
from datetime import datetime


class EventManager:
    """Manages SSE connections for live tournament updates."""

    def __init__(self):
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}

    def subscribe(self, tournament_id: int) -> asyncio.Queue:
        if tournament_id not in self._subscribers:
            self._subscribers[tournament_id] = set()
        queue = asyncio.Queue()
        self._subscribers[tournament_id].add(queue)
        return queue

    def unsubscribe(self, tournament_id: int, queue: asyncio.Queue):
        if tournament_id in self._subscribers:
            self._subscribers[tournament_id].discard(queue)

    async def publish(self, tournament_id: int, event_type: str, data: dict):
        if tournament_id not in self._subscribers:
            return
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        })
        dead_queues = []
        for queue in self._subscribers[tournament_id]:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dead_queues.append(queue)
        for q in dead_queues:
            self._subscribers[tournament_id].discard(q)


event_manager = EventManager()
