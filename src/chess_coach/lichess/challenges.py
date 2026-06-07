"""Lichess Challenges API.

Endpoints:
- POST /api/challenge/{user} - challenge a user
- POST /api/challenge/open - open challenge
- POST /api/challenge/ai - challenge the AI
- GET /api/challenge/{id} - get challenge status
- POST /api/challenge/{id}/accept - accept
- POST /api/challenge/{id}/decline - decline
- POST /api/challenge/{id}/cancel - cancel
"""
from __future__ import annotations

import enum
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"


class ChallengeDeclineReason(str, enum.Enum):
    """Reasons for declining a challenge."""
    GENERIC = "generic"
    LATER = "later"
    TOO_FAST = "tooFast"
    TOO_SLOW = "tooSlow"
    TIME_CONTROL = "timeControl"
    RATED = "rated"
    CASUAL = "casual"
    STANDARD = "standard"
    VARIANT = "variant"
    NO_BOT = "noBot"
    ONLY_BOT = "onlyBot"


@dataclass
class Challenge:
    """A Lichess challenge (incoming or outgoing)."""
    id: str = ""
    url: str = ""
    status: str = "created"  # created/accepted/declined/canceled/offline
    challenger: dict[str, Any] = field(default_factory=dict)
    dest_user: dict[str, Any] | None = None
    variant: dict[str, Any] = field(default_factory=lambda: {"key": "standard", "name": "Standard"})
    rated: bool = False
    speed: str = "blitz"  # bullet/blitz/rapid/classical/correspondence
    time_control: dict[str, Any] = field(default_factory=dict)
    color: str = "random"
    initial_fen: str = "startpos"
    decline_reason: str | None = None
    perf: dict[str, Any] = field(default_factory=dict)
    created_at: int = 0
    expires_at: int = 0

    @property
    def initial_minutes(self) -> int:
        if "limit" in self.time_control:
            return self.time_control["limit"] // 60
        if "days" in self.time_control:
            return self.time_control["days"] * 24 * 60
        return 0

    @property
    def increment(self) -> int:
        return self.time_control.get("increment", 0)


class LichessChallenges:
    """Client for challenge-related endpoints. Requires OAuth scope: 'challenge:read', 'challenge:write'."""

    def __init__(self, token: str, base_url: str = LICHESS_API) -> None:
        self._token = token
        self._base = base_url

    def _request(self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None) -> Any:
        url = f"{self._base}{endpoint}"
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        body = urlencode(data).encode() if data else None
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def challenge_user(self, username: str, time_minutes: int = 10, increment: int = 0,
                       color: str = "random", variant: str = "standard", rated: bool = True) -> Challenge:
        """Challenge a specific user."""
        data = {
            "time": time_minutes,
            "increment": increment,
            "color": color,
            "variant": variant,
            "rated": "true" if rated else "false",
        }
        obj = self._request(f"/challenge/{username}", method="POST", data=data)
        return self._to_challenge(obj)

    def challenge_ai(self, level: int = 1, color: str = "random", variant: str = "standard",
                     fen: str | None = None) -> Challenge:
        """Challenge the AI (level 1-8, 1=beginner, 8=Stockfish)."""
        data: dict[str, Any] = {"level": level, "color": color, "variant": variant}
        if fen:
            data["fen"] = fen
        obj = self._request("/challenge/ai", method="POST", data=data)
        return self._to_challenge(obj)

    def open_challenge(self, time_minutes: int = 10, increment: int = 0,
                       variant: str = "standard", rated: bool = False,
                       name: str | None = None) -> Challenge:
        """Create an open challenge (anyone can accept)."""
        data: dict[str, Any] = {
            "time": time_minutes,
            "increment": increment,
            "variant": variant,
            "rated": "true" if rated else "false",
        }
        if name:
            data["name"] = name
        obj = self._request("/challenge/open", method="POST", data=data)
        return self._to_challenge(obj)

    def status(self, challenge_id: str) -> Challenge:
        """Get current status of a challenge."""
        obj = self._request(f"/challenge/{challenge_id}")
        return self._to_challenge(obj)

    def accept(self, challenge_id: str) -> bool:
        self._request(f"/challenge/{challenge_id}/accept", method="POST")
        return True

    def decline(self, challenge_id: str, reason: ChallengeDeclineReason = ChallengeDeclineReason.GENERIC) -> bool:
        self._request(f"/challenge/{challenge_id}/decline", method="POST",
                      data={"reason": reason.value})
        return True

    def cancel(self, challenge_id: str) -> bool:
        self._request(f"/challenge/{challenge_id}/cancel", method="POST")
        return True

    def _to_challenge(self, obj: dict[str, Any]) -> Challenge:
        return Challenge(
            id=obj.get("id", ""),
            url=obj.get("url", ""),
            status=obj.get("status", "created"),
            challenger=obj.get("challenger", {}),
            dest_user=obj.get("destUser"),
            variant=obj.get("variant", {"key": "standard", "name": "Standard"}),
            rated=obj.get("rated", False),
            speed=obj.get("speed", "blitz"),
            time_control=obj.get("timeControl", {}),
            color=obj.get("color", "random"),
            initial_fen=obj.get("initialFen", "startpos"),
            decline_reason=obj.get("declineReason"),
            perf=obj.get("perf", {}),
            created_at=obj.get("createdAt", 0),
            expires_at=obj.get("expiresAt", 0),
        )
