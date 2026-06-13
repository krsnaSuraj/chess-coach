"""Server-side WebSocket broadcaster.

Maintains a set of connected clients and broadcasts messages to all of them.
Designed to be attached to a FastAPI app via `attach_websocket`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

# IMPORTANT: must be at module level, not inside attach_websocket, so that
# FastAPI's get_dependant can resolve the `WebSocket` type annotation on
# the inner `ws_endpoint` closure (combined with `from __future__ import
# annotations`, annotations become strings and FastAPI evaluates them in
# the function's __globals__).
from fastapi import WebSocket, WebSocketDisconnect

from chess_coach.ws.protocol import WsMessage, MessageType

logger = logging.getLogger(__name__)

games: dict[Any, Any] = {}


async def handle_set_side(websocket: Any, data: dict) -> None:
    """Handle side selection."""
    game = games.get(websocket)
    if game:
        game.select_side(
            side=data.get("side", "w"),
            rating=data.get("rating", 1500),
            classical=data.get("classical", 0.5),
            aggression=data.get("aggression", 0.5),
        )
        await websocket.send_json({
            "type": "side_selected",
            "side": data.get("side", "w"),
        })


async def handle_opponent_move(websocket: Any, data: dict) -> None:
    """Handle opponent move entry."""
    game = games.get(websocket)
    if game:
        result = game.enter_opponent_move(data.get("uci", ""))
        if result["success"]:
            best_move = game.get_best_move()
            import asyncio
            await asyncio.sleep(best_move.get("think_time", 2.0))
            await websocket.send_json({
                "type": "best_move",
                "uci": best_move["move"],
                "eval": 0.0,
                "depth": 20,
                "think_time": best_move["think_time"],
            })
            arrows = []
            for move_uci, prob in best_move.get("top_moves", []):
                from_sq = move_uci[:2]
                to_sq = move_uci[2:4]
                arrows.append({
                    "from": from_sq,
                    "to": to_sq,
                    "color": "green" if prob > 0.5 else "yellow",
                })
            await websocket.send_json({
                "type": "arrow_update",
                "arrows": arrows,
            })
            await websocket.send_json({
                "type": "risk_assessment",
                "score": best_move.get("risk_score", 0),
                "level": best_move.get("risk_level", "SAFE"),
                "recommendation": "",
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": result.get("error", "Invalid move"),
            })


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
    broadcaster = WsBroadcaster()

    @app.websocket(path)
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        await broadcaster.register(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                msg = WsMessage.from_json(raw)
                if msg.type.value == "ping":
                    pong = WsMessage(type=MessageType("pong"), data=msg.data)
                    await websocket.send_text(pong.to_json())
                elif msg.type.value == "set_side":
                    await handle_set_side(websocket, msg.data)
                elif msg.type.value == "opponent_move":
                    await handle_opponent_move(websocket, msg.data)
        except WebSocketDisconnect:
            pass
        finally:
            await broadcaster.unregister(websocket)

    return broadcaster
