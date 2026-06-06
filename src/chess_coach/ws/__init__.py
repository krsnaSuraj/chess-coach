"""WebSocket layer: real-time eval/game updates (replaces 1500ms polling).

SOTA 2026 standard for chess UIs (Lichess, Chess.com, Chessify).
Message protocol: JSON, versioned, type-safe via dataclasses.
"""

from chess_coach.ws.protocol import (
    WsMessage,
    AnalysisUpdate,
    GameState,
    ToastMessage,
    SoundEvent,
    EvalLine,
    MessageType,
)
from chess_coach.ws.server import WsBroadcaster, attach_websocket
from chess_coach.ws.client import WsClient, MockWsClient

__all__ = [
    "WsMessage",
    "AnalysisUpdate",
    "GameState",
    "ToastMessage",
    "SoundEvent",
    "EvalLine",
    "MessageType",
    "WsBroadcaster",
    "attach_websocket",
    "WsClient",
    "MockWsClient",
]
