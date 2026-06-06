"""Screen reader announcements using ARIA live regions.

SOTA 2026: WCAG 2.2 AA. Every state change should be announced.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any


class LiveRegion(str, enum.Enum):
    """ARIA live region politeness settings."""
    POLITE = "polite"  # Wait until user pauses
    ASSERTIVE = "assertive"  # Interrupt immediately
    OFF = "off"


@dataclass
class Announcement:
    text: str
    region: LiveRegion = LiveRegion.POLITE
    timestamp: float = field(default_factory=time.time)


class ScreenReaderAnnouncer:
    """Queue of screen reader announcements. Drained by the UI."""

    def __init__(self) -> None:
        self._queue: list[Announcement] = []
        self._history: list[Announcement] = []

    def announce(self, text: str, region: LiveRegion = LiveRegion.POLITE) -> None:
        """Add an announcement to the queue."""
        a = Announcement(text=text, region=region)
        self._queue.append(a)
        self._history.append(a)
        if len(self._history) > 100:
            self._history = self._history[-100:]

    def announce_move(self, san: str, color: str, is_check: bool = False) -> None:
        """Announce a chess move in a screen-reader-friendly way."""
        text = f"{color} plays {san}"
        if is_check:
            text += ", check"
        self.announce(text, LiveRegion.POLITE)

    def announce_evaluation(self, eval_str: str, best_move: str) -> None:
        """Announce engine evaluation."""
        self.announce(f"Evaluation: {eval_str}. Best move: {best_move}", LiveRegion.POLITE)

    def announce_game_state(self, is_check: bool, is_mate: bool, is_stalemate: bool) -> None:
        """Announce game-ending state."""
        if is_mate:
            self.announce("Checkmate", LiveRegion.ASSERTIVE)
        elif is_stalemate:
            self.announce("Stalemate", LiveRegion.ASSERTIVE)
        elif is_check:
            self.announce("Check", LiveRegion.ASSERTIVE)

    def drain(self) -> list[Announcement]:
        """Drain the queue (UI calls this to render the live region)."""
        out = list(self._queue)
        self._queue.clear()
        return out

    def history(self) -> list[Announcement]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()
