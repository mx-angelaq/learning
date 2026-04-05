"""Server-Sent Events for live updates."""

import asyncio
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.services.events import event_manager

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/{tournament_id}")
async def stream_events(tournament_id: int, request: Request):
    queue = event_manager.subscribe(tournament_id)

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {"data": message}
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"data": '{"type":"keepalive"}'}
        finally:
            event_manager.unsubscribe(tournament_id, queue)

    return EventSourceResponse(generate())
