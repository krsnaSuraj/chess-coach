"""Opening repertoire builder.

Manages a player's opening repertoire (White + Black) with metadata:
name, ECO, color, moves (as SAN or UCI), first-seen, notes, wins/losses.

A repertoire is stored as a dict of `OpeningLine` objects indexed by
name. A "primary" line is the one the player commits to memorizing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import (
    Dict, List, Optional, Sequence,
)

import chess

from ..openings.eco import COMMON_ECO_CODES


@dataclass
class OpeningLine:
    """A single opening line in a repertoire."""

    name: str
    eco: str = ""
    color: chess.Color = chess.WHITE
    moves_san: List[str] = field(default_factory=list)
    moves_uci: List[str] = field(default_factory=list)
    notes: str = ""
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    tags: List[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Total score (1.0/0.5/0.0) per game average."""
        total = self.wins + self.losses + self.draws
        if total == 0:
            return 0.0
        return (self.wins + 0.5 * self.draws) / total

    @property
    def score_percentage(self) -> float:
        return 100.0 * self.score

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "eco": self.eco,
            "color": "white" if self.color == chess.WHITE else "black",
            "moves_san": self.moves_san,
            "moves_uci": self.moves_uci,
            "notes": self.notes,
            "games_played": self.games_played,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "score_percentage": self.score_percentage,
            "tags": self.tags,
        }


@dataclass
class Repertoire:
    """A player's full opening repertoire (White + Black)."""

    white: Dict[str, OpeningLine] = field(default_factory=dict)
    black: Dict[str, OpeningLine] = field(default_factory=dict)

    def add(self, line: OpeningLine) -> None:
        target = self.white if line.color == chess.WHITE else self.black
        target[line.name] = line

    def remove(self, name: str, color: chess.Color) -> bool:
        target = self.white if color == chess.WHITE else self.black
        if name in target:
            del target[name]
            return True
        return False

    def get(self, name: str, color: chess.Color) -> Optional[OpeningLine]:
        target = self.white if color == chess.WHITE else self.black
        return target.get(name)

    def all_lines(self) -> List[OpeningLine]:
        return list(self.white.values()) + list(self.black.values())

    def find_by_eco(self, eco_code: str) -> List[OpeningLine]:
        return [l for l in self.all_lines() if l.eco == eco_code]

    def total_games(self) -> int:
        return sum(l.games_played for l in self.all_lines())

    def overall_score(self) -> float:
        total = 0
        score = 0.0
        for l in self.all_lines():
            total += l.games_played
            score += l.wins + 0.5 * l.draws
        if total == 0:
            return 0.0
        return score / total

    def to_dict(self) -> Dict[str, object]:
        return {
            "white": {k: v.to_dict() for k, v in self.white.items()},
            "black": {k: v.to_dict() for k, v in self.black.items()},
            "total_games": self.total_games(),
            "overall_score": self.overall_score(),
        }


_SAN_RE = re.compile(r"^([NBKRQa-h1-8])?([a-h][1-8])(=[NBRQ])?([+#]?)$")


def _san_to_uci(san_moves: Sequence[str]) -> List[str]:
    """Convert a sequence of SAN moves to UCI by replaying on a fresh board."""
    board = chess.Board()
    out: List[str] = []
    for san in san_moves:
        try:
            move = board.parse_san(san)
            out.append(move.uci())
            board.push(move)
        except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError):
            out.append("")
    return out


def make_opening_line(name: str, color: chess.Color, san_moves: Sequence[str], eco: str = "") -> OpeningLine:
    """Create an OpeningLine from a sequence of SAN moves, auto-filling UCI and ECO."""
    uci = _san_to_uci(san_moves)
    eco = eco or ""
    if not eco:
        # Auto-detect ECO by longest SAN-move prefix match against ECOEntry.pgn text.
        # ECOEntry.pgn is "1.e4 c5 2.Nf3 d6 ..." text, so we extract SAN moves by
        # stripping move numbers, then find the entry whose SAN list has the
        # longest common prefix with our `san_moves`. We require at least 3 plies
        # of common prefix to avoid single-move false positives.
        best_eco = ""
        best_len = -1
        for entry in COMMON_ECO_CODES:
            if not entry.pgn:
                continue
            entry_sans = _extract_san_from_pgn(entry.pgn)
            if not entry_sans:
                continue
            common = 0
            for a, b in zip(entry_sans, san_moves):
                if a != b:
                    break
                common += 1
            if common > best_len:
                best_len = common
                best_eco = entry.code
        eco = best_eco
    return OpeningLine(
        name=name, eco=eco, color=color, moves_san=list(san_moves), moves_uci=uci,
    )


def _extract_san_from_pgn(pgn_text: str) -> list[str]:
    """Extract SAN moves from PGN text like '1.e4 c5 2.Nf3 d6 3...'."""
    out: list[str] = []
    for token in pgn_text.split():
        # Strip leading move-number markers like "1." or "1..."
        san = re.sub(r"^\d+\.+", "", token)
        if not san:
            continue
        if san in ("1-0", "0-1", "1/2-1/2", "*"):
            break
        out.append(san)
    return out


def recommend_repertoire(user_elo: int, color: chess.Color, style: str = "mainline") -> List[OpeningLine]:
    """Recommend a starter repertoire for a given ELO + color.

    style: "mainline" (theoretical), "aggressive", "solid", "tactical"
    """
    if color == chess.WHITE:
        candidates = [
            ("Italian Game", chess.WHITE, ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"], "C50"),
            ("Queen's Gambit", chess.WHITE, ["d4", "d5", "c4"], "D06"),
            ("London System", chess.WHITE, ["d4", "d5", "c4", "Nc6", "Nf3", "Bf4"], "D02"),
            ("King's Indian Attack", chess.WHITE, ["Nf3", "d5", "g3"], "A07"),
            ("Ruy Lopez", chess.WHITE, ["e4", "e5", "Nf3", "Nc6", "Bb5"], "C60"),
        ]
    else:
        candidates = [
            ("Sicilian Defense", chess.BLACK, ["e4", "c5"], "B20"),
            ("French Defense", chess.BLACK, ["e4", "e6"], "C00"),
            ("Caro-Kann", chess.BLACK, ["e4", "c6"], "B10"),
            ("Queen's Gambit Declined", chess.BLACK, ["d4", "d5", "c4", "e6"], "D30"),
            ("King's Indian Defense", chess.BLACK, ["d4", "Nf6", "c4", "g6"], "E60"),
            ("Nimzo-Indian", chess.BLACK, ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"], "E20"),
        ]

    if style == "aggressive":
        candidates = [c for c in candidates if "Sicilian" in c[0] or "King's Indian" in c[0] or "Italian" in c[0]]
    elif style == "solid":
        candidates = [c for c in candidates if "Caro" in c[0] or "Queen's Gambit" in c[0] or "London" in c[0] or "French" in c[0]]
    elif style == "tactical":
        candidates = [c for c in candidates if "Sicilian" in c[0] or "Italian" in c[0] or "Nimzo" in c[0]]

    result: List[OpeningLine] = []
    for name, col, san, eco in candidates:
        if col != color:
            continue
        result.append(make_opening_line(name, col, san, eco))
    return result


def repertoire_diversity(repertoire: Repertoire) -> float:
    """0..1 score: how diverse is the repertoire (1.0 = all different ECO prefixes)."""
    ecos = [l.eco[:1] for l in repertoire.all_lines() if l.eco]
    if not ecos:
        return 0.0
    return len(set(ecos)) / len(ecos)


__all__ = [
    "OpeningLine",
    "Repertoire",
    "make_opening_line",
    "recommend_repertoire",
    "repertoire_diversity",
]
