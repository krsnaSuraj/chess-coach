"""Expected Points Difference (EPD) model.

Chess.com's Game Review v2 (2024+) uses EPD, not raw CPL.
EPD is the win-probability drop from best move to played move.
This module provides the canonical chess.com thresholds.

References:
  - https://www.chess.com/blog/TheMythicBlog/
  - https://support.chess.com/en/articles/8706677
"""

from __future__ import annotations

# EPD thresholds (chess.com V2):
#   Best:    0.00-0.00
#   Excellent: 0.00-0.02
#   Good:    0.02-0.05
#   Inaccuracy: 0.05-0.10
#   Mistake: 0.10-0.20
#   Blunder: 0.20-1.00
EPD_THRESHOLDS: dict[str, tuple[float, float]] = {
    "best":      (0.00, 0.00),
    "excellent": (0.00, 0.02),
    "good":      (0.02, 0.05),
    "inaccuracy": (0.05, 0.10),
    "mistake":   (0.10, 0.20),
    "blunder":   (0.20, 1.00),
}


def cp_to_winrate(cp: int) -> float:
    """Sigmoid cp-to-winrate: 400cp = 10x winrate, clamped at +/-1000cp."""
    if cp >= 1000:
        return 1.0
    if cp <= -1000:
        return 0.0
    return 1.0 / (1.0 + 10 ** (-cp / 400.0))


def winrate_to_epd(best_winrate: float, played_winrate: float) -> float:
    """Expected Points Difference: positive means the player lost EPs.

    EP = winrate + 0.5 * drawrate. In winrate-only form, EP ~= winrate + (1-winrate)*0.
    We use the chess.com formula: EPD = best_winrate - played_winrate, clamped [0, 1].
    """
    diff = best_winrate - played_winrate
    return max(0.0, min(1.0, diff))


def epd_to_class(epd: float) -> str:
    """Map EPD to a classification label."""
    if epd == 0.0:
        return "best"
    for label, (lo, hi) in EPD_THRESHOLDS.items():
        if label == "best":
            continue
        if lo <= epd < hi:
            return label
    return "blunder"
