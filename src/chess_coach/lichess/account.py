"""Lichess Account API client.

Endpoints:
- GET /api/account - profile
- GET /api/account/email - email
- GET /api/account/preferences - user preferences
- GET /api/account/kid - kid mode status
- POST /api/account/kid - set kid mode
- GET /api/timeline - activity timeline
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"


@dataclass
class Preferences:
    """Lichess user preferences."""
    dark: bool = False
    transp: bool = False
    bg: int = 0  # 0=light, 1=dark, 2=system, 3=brown, 4=green, 5=blue
    theme: str = "brown"
    pieceSet: str = "cburnett"
    theme3d: str = "modern"
    pieceSet3d: str = "Reyes"
    soundSet: str = "standard"
    blindfold: int = 0
    autoQueen: int = 1
    autoThreefold: int = 1
    takeback: int = 1
    moretime: int = 1
    clockTenths: int = 0
    clockBar: int = 1
    clockSound: int = 0
    premove: int = 1
    animation: int = 1
    captured: int = 1
    follow: int = 1
    highlight: int = 1
    destination: int = 1
    coords: int = 0
    replay: int = 1
    tactile: int = 0
    moveEvent: int = 1
    rookCastle: int = 1
    showRatings: int = 0
    submitMove: int = 1
    confirmResign: int = 1
    insightShare: int = 0
    keyboardMove: int = 0
    zen: int = 0
    pieceNotation: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Preferences":
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})


@dataclass
class AccountProfile:
    """Lichess account profile."""
    id: str
    username: str
    online: bool = False
    patron: bool = False
    rating_blitz: int | None = None
    rating_bullet: int | None = None
    rating_rapid: int | None = None
    rating_classical: int | None = None
    rating_correspondence: int | None = None
    rating_puzzle: int | None = None
    language: str = "en-US"
    profile: dict[str, Any] = field(default_factory=dict)
    playing: str | None = None
    perfs: dict[str, int] = field(default_factory=dict)
    created_at: int = 0
    seen_at: int = 0
    title: str | None = None
    url: str = ""
    nb_following: int = 0
    nb_followers: int = 0
    count: dict[str, int] = field(default_factory=dict)
    streaming: bool = False
    followable: bool = True
    following: bool = False
    blocking: bool = False
    follows_you: bool = False

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def is_strong(self) -> bool:
        return any(r and r > 2200 for r in (self.rating_blitz, self.rating_bullet,
                                            self.rating_rapid, self.rating_classical))


class KidMode:
    """Kid mode toggles."""
    YES = "yes"
    NO = "no"


class LichessAccount:
    """Client for Lichess account-related endpoints.

    Requires OAuth token with scope: 'account:read', 'account:write'.
    """

    def __init__(self, token: str, base_url: str = LICHESS_API) -> None:
        self._token = token
        self._base = base_url

    def _request(self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base}{endpoint}"
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        body = urlencode(data).encode() if data else None
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def profile(self) -> AccountProfile:
        """Get authenticated user profile."""
        data = self._request("/account")
        perfs = data.get("perfs", {})
        return AccountProfile(
            id=data.get("id", ""),
            username=data.get("username", ""),
            online=data.get("online", False),
            patron=data.get("patron", False),
            rating_blitz=perfs.get("blitz", {}).get("rating"),
            rating_bullet=perfs.get("bullet", {}).get("rating"),
            rating_rapid=perfs.get("rapid", {}).get("rating"),
            rating_classical=perfs.get("classical", {}).get("rating"),
            rating_correspondence=perfs.get("correspondence", {}).get("rating"),
            rating_puzzle=perfs.get("puzzle", {}).get("rating"),
            language=data.get("language", "en-US"),
            profile=data.get("profile", {}),
            playing=data.get("playing"),
            perfs=perfs,
            created_at=data.get("createdAt", 0),
            seen_at=data.get("seenAt", 0),
            title=data.get("title"),
            url=data.get("url", ""),
            nb_following=data.get("nbFollowing", 0),
            nb_followers=data.get("nbFollowers", 0),
            count=data.get("count", {}),
            streaming=data.get("streaming", False),
        )

    def email(self) -> str:
        """Get authenticated user email (scope: 'email:read')."""
        data = self._request("/account/email")
        return data.get("email", "")

    def preferences(self) -> Preferences:
        """Get user preferences."""
        data = self._request("/account/preferences")
        return Preferences.from_dict(data)

    def set_kid_mode(self, value: str) -> bool:
        """Toggle kid mode ('yes' or 'no')."""
        self._request("/account/kid", method="POST", data={"v": value})
        return True

    def timeline(self, n: int = 50) -> list[dict[str, Any]]:
        """Get recent activity timeline."""
        return self._request(f"/timeline?nb={n}")
