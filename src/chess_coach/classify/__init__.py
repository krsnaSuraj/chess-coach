"""Move classification v2 (CAPS V2 + chess.com Expected Points Model parity).

SOTA 2026 classifications:
  - 9 move categories: Best / Excellent / Good / Inaccuracy / Mistake / Blunder /
    Miss / Brilliant / Great
  - Phase-aware (Opening / Middlegame / Endgame)
  - Sacrifice detection for Brilliant
  - Failed-to-capitalize detection for Miss
  - Only-good-move detection for Great
  - EPD (Expected Points Difference) model, not raw CPL

This module is the SOTA 2026 successor to the original `caps.py`.
"""

from chess_coach.classify.classify_v2 import (
    MoveClass,
    classify_move,
    classify_game,
    ClassificationReport,
)
from chess_coach.classify.epd import (
    winrate_to_epd,
    cp_to_winrate,
    epd_to_class,
    EPD_THRESHOLDS,
)
from chess_coach.classify.phase_detector import GamePhase, detect_phase, phase_buckets
from chess_coach.classify.brilliant import is_brilliant
from chess_coach.classify.miss import is_miss
from chess_coach.classify.great import is_only_good_move, is_great_move
from chess_coach.classify.report_card import build_report_card, ReportCard

__all__ = [
    "MoveClass",
    "classify_move",
    "classify_game",
    "ClassificationReport",
    "winrate_to_epd",
    "cp_to_winrate",
    "epd_to_class",
    "EPD_THRESHOLDS",
    "GamePhase",
    "detect_phase",
    "phase_buckets",
    "is_brilliant",
    "is_miss",
    "is_only_good_move",
    "is_great_move",
    "build_report_card",
    "ReportCard",
]
