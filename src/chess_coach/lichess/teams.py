"""Lichess Teams API.

Endpoints:
- GET /api/team/{id} - team info
- GET /api/team/{id}/users - team members
- POST /api/team/{id}/join - join
- POST /api/team/{id}/quit - leave
- POST /api/team/{id}/kick - kick (admin)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"


@dataclass
class Team:
    """Lichess team info."""
    id: str = ""
    name: str = ""
    description: str = ""
    leader: str = ""
    nb_members: int = 0
    open: bool = False
    location: str | None = None
    country: str | None = None
    joined: bool = False
    flair: str | None = None
    icon: str | None = None
    url: str = ""


@dataclass
class TeamMember:
    """A member of a Lichess team."""
    username: str = ""
    rating_blitz: int | None = None
    rating_bullet: int | None = None
    rating_rapid: int | None = None
    rating_classical: int | None = None
    joined_at: int = 0
    role: str = "member"  # member/leader/co-leader

    @property
    def is_leader(self) -> bool:
        return self.role in ("leader", "co-leader")


class LichessTeams:
    """Client for Lichess teams endpoints."""

    def __init__(self, token: str | None = None, base_url: str = LICHESS_API) -> None:
        self._token = token
        self._base = base_url

    def _request(self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None) -> Any:
        url = f"{self._base}{endpoint}"
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        body = urlencode(data).encode() if data else None
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def get(self, team_id: str) -> Team:
        obj = self._request(f"/team/{team_id}")
        return Team(
            id=obj.get("id", ""),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            leader=obj.get("leader", ""),
            nb_members=obj.get("nbMembers", 0),
            open=obj.get("open", False),
            location=obj.get("location"),
            country=obj.get("country"),
            joined=obj.get("joined", False),
            flair=obj.get("flair"),
            icon=obj.get("icon"),
            url=obj.get("url", ""),
        )

    def members(self, team_id: str) -> list[TeamMember]:
        """Get all team members."""
        obj = self._request(f"/team/{team_id}/users")
        members: list[TeamMember] = []
        for u in obj:
            perfs = u.get("perfs", {})
            members.append(TeamMember(
                username=u.get("username", ""),
                rating_blitz=perfs.get("blitz", {}).get("rating"),
                rating_bullet=perfs.get("bullet", {}).get("rating"),
                rating_rapid=perfs.get("rapid", {}).get("rating"),
                rating_classical=perfs.get("classical", {}).get("rating"),
                joined_at=u.get("joinedTeamAt", 0),
            ))
        return members

    def join(self, team_id: str, password: str | None = None) -> bool:
        data: dict[str, Any] = {}
        if password:
            data["password"] = password
        self._request(f"/team/{team_id}/join", method="POST", data=data)
        return True

    def leave(self, team_id: str) -> bool:
        self._request(f"/team/{team_id}/quit", method="POST")
        return True
