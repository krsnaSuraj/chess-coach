"""WebSocket message protocol.

All messages are JSON-serializable dataclasses.
Versioned via the `v` field (currently 1).
"""

from __future__ import annotations

import enum
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any


class MessageType(str, enum.Enum):
    """SOTA 2026 WebSocket message types."""
    ANALYSIS_UPDATE = "analysis_update"
    GAME_STATE = "game_state"
    TOAST = "toast"
    SOUND = "sound"
    EVAL = "eval"
    PUZZLE = "puzzle"
    THREAT = "threat"
    HELLO = "hello"
    PING = "ping"
    PONG = "pong"


@dataclass
class WsMessage:
    """Base WebSocket message envelope."""
    type: MessageType
    v: int = 1
    ts: int = field(default_factory=lambda: int(time.time() * 1000))
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        out = {"type": self.type.value, "v": self.v, "ts": self.ts, **self.data}
        return json.dumps(out)

    @classmethod
    def from_json(cls, raw: str | bytes) -> "WsMessage":
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        d = json.loads(raw)
        type_str = d.pop("type", "ping")
        v = d.pop("v", 1)
        ts = d.pop("ts", int(time.time() * 1000))
        return cls(type=MessageType(type_str), v=v, ts=ts, data=d)


@dataclass
class EvalLine:
    """A single principal variation line from engine."""
    multipv: int
    depth: int
    score_cp: int
    mate: int | None
    pv: list[str]
    wdl: tuple[int, int, int] | None = None
    engine: str = "Stockfish 18"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisUpdate:
    """Bulk analysis update from server to client."""
    fen: str
    lines: list[EvalLine]
    best_move: str
    classification: str
    accuracy: float
    depth: int
    finished: bool = False

    def to_message(self) -> WsMessage:
        return WsMessage(
            type=MessageType.ANALYSIS_UPDATE,
            data={
                "fen": self.fen,
                "lines": [line.to_dict() for line in self.lines],
                "best_move": self.best_move,
                "classification": self.classification,
                "accuracy": self.accuracy,
                "depth": self.depth,
                "finished": self.finished,
            },
        )


@dataclass
class GameState:
    """Current game state from server to client."""
    fen: str
    turn: str
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    is_game_over: bool
    legal_moves: list[str]
    ply: int
    pgn_moves: list[str]
    last_move: str | None = None

    def to_message(self) -> WsMessage:
        return WsMessage(
            type=MessageType.GAME_STATE,
            data=asdict(self),
        )


@dataclass
class ToastMessage:
    """UI toast notification."""
    severity: str  # info | success | warning | danger | brilliant
    title: str
    body: str = ""
    duration_ms: int = 3000

    def to_message(self) -> WsMessage:
        return WsMessage(type=MessageType.TOAST, data=asdict(self))


@dataclass
class SoundEvent:
    """Sound effect trigger."""
    sfx: str
    theme: str = "default"
    pan: float = 0.0  # -1.0 (left) to 1.0 (right)
    volume: float = 0.7

    def to_message(self) -> WsMessage:
        return WsMessage(type=MessageType.SOUND, data=asdict(self))
