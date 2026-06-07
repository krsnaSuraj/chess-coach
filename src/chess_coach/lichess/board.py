"""Lichess Board API - real-time gameplay streaming.

Endpoints:
- POST /api/board/seek - create a real-time game seek
- POST /api/challenge/{user} - challenge a user
- POST /api/challenge/open - open challenge (anyone can accept)
- POST /api/board/game/{id}/move/{move} - play a move
- POST /api/board/game/{id}/abort - abort
- POST /api/board/game/{id}/resign - resign
- POST /api/board/game/{id}/draw - offer/accept draw
- POST /api/board/game/{id}/takeback/{yes|no} - takeback
- GET /api/board/game/stream/{id} - stream game events (NDJSON)
"""
from __future__ import annotations

import enum
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"
NDJSON_DELIM = "\n"


class BoardState(str, enum.Enum):
    """Game state events from Board API stream."""
    GAME_FULL = "gameFull"
    STATE = "state"
    CHAT_LINE = "chatLine"
    MOVE = "move"
    OPPONENT_GONE = "opponentGone"


@dataclass
class BoardStreamEvent:
    """A single event from the Board API NDJSON stream."""
    type: BoardState
    data: dict[str, Any] = field(default_factory=dict)
    raw: str = ""

    @property
    def is_game_over(self) -> bool:
        return self.data.get("status") in ("mate", "resign", "stalemate", "timeout",
                                            "draw", "outoftime", "cheat", "noStart",
                                            "aborted", "variantEnd", "created")

    @property
    def fen(self) -> str | None:
        return self.data.get("fen")


class LichessBoard:
    """Real-time gameplay client. Requires bot account or OAuth with 'board:play' scope."""

    def __init__(self, token: str, base_url: str = LICHESS_API) -> None:
        self._token = token
        self._base = base_url

    def _request(self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None,
                 stream: bool = False) -> Any:
        url = f"{self._base}{endpoint}"
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/x-ndjson" if stream else "application/json"}
        body = urlencode(data).encode() if data else None
        req = Request(url, data=body, headers=headers, method=method)
        if stream:
            return urlopen(req, timeout=None)  # noqa: S310
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def seek(self, time_minutes: int = 10, increment: int = 0, color: str = "random",
             variant: str = "standard", rated: bool = True) -> dict[str, Any]:
        """Create a real-time game seek.

        Args:
            time_minutes: initial time in minutes.
            increment: increment in seconds.
            color: 'white', 'black', or 'random'.
            variant: standard, chess960, atomic, antichess, etc.
            rated: rated or casual.
        """
        data = {
            "time": time_minutes,
            "increment": increment,
            "color": color,
            "variant": variant,
            "rated": "true" if rated else "false",
        }
        return self._request("/board/seek", method="POST", data=data)

    def play_move(self, game_id: str, move_uci: str, offer_draw: bool = False) -> dict[str, Any]:
        """Play a move in an active game. Returns the new game state."""
        params = f"?offeringDraw={'true' if offer_draw else 'false'}"
        return self._request(f"/board/game/{game_id}/move/{move_uci}{params}", method="POST")

    def chat(self, game_id: str, room: str, text: str) -> bool:
        """Post a chat message (scope: 'board:play')."""
        self._request(f"/board/game/{game_id}/chat", method="POST",
                      data={"room": room, "text": text})
        return True

    def resign(self, game_id: str) -> bool:
        self._request(f"/board/game/{game_id}/resign", method="POST")
        return True

    def offer_draw(self, game_id: str, accept: bool = True) -> bool:
        path = "yes" if accept else "no"
        self._request(f"/board/game/{game_id}/draw/{path}", method="POST")
        return True

    def abort(self, game_id: str) -> bool:
        self._request(f"/board/game/{game_id}/abort", method="POST")
        return True

    def takeback(self, game_id: str, accept: bool = True) -> bool:
        path = "yes" if accept else "no"
        self._request(f"/board/game/{game_id}/takeback/{path}", method="POST")
        return True

    def stream(self, game_id: str) -> Iterator[BoardStreamEvent]:
        """Stream game events as an iterator of BoardStreamEvent objects."""
        resp = self._request(f"/board/game/stream/{game_id}", stream=True)
        for line in resp:
            line = line.decode("utf-8").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                event_type = obj.get("type", "state")
                if event_type == "gameFull":
                    t = BoardState.GAME_FULL
                elif event_type == "chatLine":
                    t = BoardState.CHAT_LINE
                elif event_type == "opponentGone":
                    t = BoardState.OPPONENT_GONE
                else:
                    t = BoardState.STATE
                yield BoardStreamEvent(type=t, data=obj, raw=line)
            except json.JSONDecodeError:
                continue
