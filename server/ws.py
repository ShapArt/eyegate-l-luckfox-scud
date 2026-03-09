from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.deps import get_gate_controller
from server.status_bus import status_bus

router = APIRouter()


@router.websocket("/ws/status")
async def ws_status(ws: WebSocket) -> None:
    await ws.accept()
    controller = get_gate_controller()
    queue = await status_bus.subscribe()
    # send initial snapshot
    await ws.send_text(json.dumps(controller.snapshot(), default=str))
    try:
        while True:
            data = await queue.get()
            await ws.send_text(json.dumps(data, default=str))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await status_bus.unsubscribe(queue)
