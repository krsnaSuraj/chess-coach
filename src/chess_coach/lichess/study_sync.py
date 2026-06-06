"""Lichess study sync (read + write).

SOTA 2026: studies are collections of chapters (each a game/analysis).
We can import a study's PGN and re-analyze it locally.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass
class Study:
    """A Lichess study."""
    id: str
    name: str
    pgn: str = ""
    description: str = ""
    chapters: list[str] = field(default_factory=list)  # PGNs
    source: str = "lichess"


class StudySync:
    """Import + sync Lichess studies."""

    def __init__(self, oauth_token: str | None = None) -> None:
        self._token = oauth_token

    def fetch(self, study_id: str) -> Study | None:
        """Fetch a study by Lichess ID (e.g. 'kQTZ9kfG')."""
        url = f"https://lichess.org/api/study/{quote(study_id)}.pgn"
        try:
            req = Request(
                url,
                headers={"Accept": "application/x-chess-pgn"},
            )
            if self._token:
                req.add_header("Authorization", f"Bearer {self._token}")
            with urlopen(req, timeout=15.0) as resp:  # noqa: S310
                pgn = resp.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            logger.debug("Study fetch failed: %s", e)
            return None
        return Study(
            id=study_id,
            name=study_id,  # Lichess doesn't return name in PGN; we use id as fallback
            pgn=pgn,
            chapters=_split_pgn_chapters(pgn),
        )

    def export(self, study: Study) -> bool:
        """Export a study to Lichess (requires write scope)."""
        if not self._token:
            return False
        # Implementation requires Lichess study API write access
        # Stub for now; real implementation would POST PGN
        return False


def _split_pgn_chapters(pgn: str) -> list[str]:
    """Split a multi-chapter PGN into individual chapter PGNs."""
    chapters: list[str] = []
    current: list[str] = []
    for line in pgn.splitlines():
        if line.startswith("[Event "):
            if current:
                chapters.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chapters.append("\n".join(current))
    return chapters
