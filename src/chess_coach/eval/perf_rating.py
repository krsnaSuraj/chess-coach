"""FIDE-style Performance Rating (PR) calculator.

Performance Rating is the average score of a player mapped to an Elo
scale. FIDE uses 800 + 50 * (W - L) for an "informal" PR, and 800 +
sum(weights) * sum(score - E) for a tournament-rigorous PR where each
opponent's rating is used.

Reference: FIDE Handbook C.04.4
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class OpponentScore:
    rating: float
    score: float  # 1.0/0.5/0.0


def expected_score(player_rating: float, opponent_rating: float) -> float:
    """Standard Elo expected score."""
    return 1.0 / (1.0 + 10 ** ((opponent_rating - player_rating) / 400.0))


def expected_score_fide(player_rating: float, opponent_rating: float) -> float:
    """FIDE-formula expected score (uses natural log, more accurate at extremes)."""
    return 1.0 / (1.0 + math.pow(10, -(player_rating - opponent_rating) / 400.0))


def performance_rating_informal(opponent_ratings: Sequence[float], total_score: float, num_games: int) -> float:
    """W/L-based informal PR (8x W, 0x L formula)."""
    if num_games <= 0:
        return 0.0
    wins = total_score
    losses = num_games - wins
    avg = sum(opponent_ratings) / len(opponent_ratings) if opponent_ratings else 0.0
    return avg + 800.0 * (wins - losses) / num_games


def performance_rating_fide(opponent_results: Sequence[OpponentScore]) -> float:
    """Rigorous FIDE PR (sum of (score_i - E_i) over weighted opponents).

    Iteratively converges by binary search between 0 and 4000 ELO.
    """
    if not opponent_results:
        return 0.0
    total_actual = sum(r.score for r in opponent_results)

    low, high = 0.0, 4000.0
    iterations = 0
    while high - low > 0.5 and iterations < 200:
        mid = (low + high) / 2.0
        total_expected = sum(expected_score_fide(mid, r.rating) for r in opponent_results)
        if total_expected < total_actual:
            low = mid
        else:
            high = mid
        iterations += 1
    return (low + high) / 2.0


def performance_rating_average_opponents(opponent_results: Sequence[OpponentScore]) -> float:
    """PR using the simpler average-opponents formula (W, D, L counts)."""
    if not opponent_results:
        return 0.0
    num = len(opponent_results)
    avg = sum(r.rating for r in opponent_results) / num
    actual = sum(r.score for r in opponent_results)
    return avg + 400.0 * (2 * actual - num) / num


def tournament_score_percentage(opponent_results: Sequence[OpponentScore]) -> float:
    """Return the score as a percentage (0-100)."""
    if not opponent_results:
        return 0.0
    return 100.0 * sum(r.score for r in opponent_results) / len(opponent_results)


def is_plus_score(opponent_results: Sequence[OpponentScore]) -> bool:
    """True if total score > 50%."""
    return tournament_score_percentage(opponent_results) > 50.0


def performance_category(pr: float) -> str:
    """Categorize a performance rating (C.04.4 categories)."""
    if pr < 2200:
        return "Candidate Master"
    if pr < 2300:
        return "National Master"
    if pr < 2400:
        return "FIDE Master"
    if pr < 2500:
        return "International Master"
    if pr < 2600:
        return "Grandmaster norm"
    return "Super Grandmaster"


__all__ = [
    "OpponentScore",
    "expected_score",
    "expected_score_fide",
    "performance_rating_informal",
    "performance_rating_fide",
    "performance_rating_average_opponents",
    "tournament_score_percentage",
    "is_plus_score",
    "performance_category",
]
