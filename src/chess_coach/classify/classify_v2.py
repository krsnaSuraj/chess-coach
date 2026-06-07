"""CAPS v2: 9-class move classification.

SOTA 2026 classifications: Best / Excellent / Good / Inaccuracy / Mistake /
Blunder / Miss / Brilliant / Great.

The classifier is EPD-based (chess.com V2 style), with optional Brilliant and
Miss detection layered on top.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Iterable

from chess_coach.classify.epd import (
    epd_to_class,
    winrate_to_epd,
)
from chess_coach.classify.phase_detector import GamePhase


class MoveClass(str, enum.Enum):
    """9 SOTA 2026 move classifications."""
    BOOK = "book"
    BRILLIANT = "brilliant"
    GREAT = "great"
    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"
    MISS = "miss"
    FORCED = "forced"


@dataclass
class ClassificationReport:
    moves: list[dict] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    accuracy_by_phase: dict[str, float] = field(default_factory=dict)
    accuracy_overall: float = 0.0


def classify_move(
    best_winrate: float,
    played_winrate: float,
    is_brilliant_move: bool = False,
    is_miss_move: bool = False,
    is_book: bool = False,
    is_forced: bool = False,
    multipv_count: int = 1,
) -> MoveClass:
    """Classify a single move."""
    if is_forced and multipv_count <= 1:
        return MoveClass.FORCED
    if is_book:
        return MoveClass.BOOK
    if is_brilliant_move:
        return MoveClass.BRILLIANT
    if is_miss_move:
        return MoveClass.MISS
    epd = winrate_to_epd(best_winrate, played_winrate)
    if epd == 0.0 and multipv_count > 1:
        return MoveClass.BEST
    if epd == 0.0:
        return MoveClass.BEST
    label = epd_to_class(epd)
    try:
        return MoveClass(label)
    except ValueError:
        return MoveClass.GOOD


def classify_game(
    game_moves: Iterable[dict],
    include_brilliant: bool = True,
    include_miss: bool = True,
) -> ClassificationReport:
    """Classify a full game from a list of move dicts.

    Each move dict must have:
      - best_winrate (float)
      - played_winrate (float)
      - is_brilliant (bool, optional)
      - is_miss (bool, optional)
      - is_book (bool, optional)
      - is_forced (bool, optional)
      - multipv_count (int, optional)
      - phase (GamePhase, optional)
    """
    report = ClassificationReport()
    counts: dict[str, int] = {}
    phase_accuracy: dict[str, list[float]] = {
        "opening": [],
        "middlegame": [],
        "endgame": [],
    }

    for m in game_moves:
        mc = classify_move(
            best_winrate=m["best_winrate"],
            played_winrate=m["played_winrate"],
            is_brilliant_move=m.get("is_brilliant", False) and include_brilliant,
            is_miss_move=m.get("is_miss", False) and include_miss,
            is_book=m.get("is_book", False),
            is_forced=m.get("is_forced", False),
            multipv_count=m.get("multipv_count", 1),
        )
        # Convert to per-move accuracy (Lichess formula)
        epd = winrate_to_epd(m["best_winrate"], m["played_winrate"])
        # Accuracy = max(0, 1 - epd) * 100
        move_accuracy = max(0.0, (1.0 - epd)) * 100
        phase = m.get("phase", GamePhase.MIDDLEGAME)
        phase_accuracy[phase.value].append(move_accuracy)
        counts[mc.value] = counts.get(mc.value, 0) + 1
        report.moves.append({
            "class": mc.value,
            "accuracy": move_accuracy,
            "phase": phase.value,
        })

    report.counts = counts
    for phase, accs in phase_accuracy.items():
        report.accuracy_by_phase[phase] = sum(accs) / len(accs) if accs else 0.0
    all_accs = [a for accs in phase_accuracy.values() for a in accs]
    report.accuracy_overall = sum(all_accs) / len(all_accs) if all_accs else 0.0
    return report
