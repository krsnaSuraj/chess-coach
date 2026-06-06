"""Server-side WebSocket broadcaster.

Maintains a set of connected clients and broadcasts messages to all of them.
Designed to be attached to a FastAPI app via `attach_websocket`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from chess_coach.ws.protocol import WsMessage

logger = logging.getLogger(__name__)


class WsBroadcaster:
    """Maintains connected WebSocket clients and broadcasts messages."""

    def __init__(self) -> None:
        self._clients: set[Any] = set()
        self._lock = asyncio.Lock()

    async def register(self, ws: Any) -> None:
        async with self._lock:
            self._clients.add(ws)
        logger.info("WS client connected (total=%d)", len(self._clients))

    async def unregister(self, ws: Any) -> None:
        async with self._lock:
            self._clients.discard(ws)
        logger.info("WS client disconnected (total=%d)", len(self._clients))

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, msg: WsMessage) -> None:
        if not self._clients:
            return
        text = msg.to_json()
        dead: list[Any] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.unregister(ws)

    def broadcast_sync(self, msg: WsMessage) -> None:
        """Sync wrapper: schedule broadcast in the running event loop if any."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return
        if loop.is_running():
            loop.create_task(self.broadcast(msg))
        else:
            loop.run_until_complete(self.broadcast(msg))


def attach_websocket(app: Any, path: str = "/ws") -> WsBroadcaster:
    """Attach a WebSocket endpoint to a FastAPI app.

    Usage:
        broadcaster = attach_websocket(app)
        # somewhere:
        await broadcaster.broadcast(analysis_update.to_message())
    """
    from fastapi import WebSocket, WebSocketDisconnect

    broadcaster = WsBroadcaster()

    @app.websocket(path)
    async def ws_endpoint(websocket: WebSocket) -> None:  # type: ignore[unused-ignore]
        await websocket.accept()
        await broadcaster.register(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                msg = WsMessage.from_json(raw)
                if msg.type.value == "ping":
                    pong = WsMessage(type=msg.type.__class__("pong"), data=msg.data)
                    await websocket.send_text(pong.to_json())
        except WebSocketDisconnect:
            pass
        finally:
            await broadcaster.unregister(websocket)

    return broadcaster
