"""Evaluation, rating, and accuracy submodules."""
from __future__ import annotations

from .glicko2 import (
    Glicko2Player,
    Glicko2Result,
    INITIAL_RATING,
    INITIAL_RD,
    INITIAL_VOLATILITY,
    SCALE,
    TAU,
    elo_to_glicko2_rating,
    rating_to_elo,
    update_player,
)
from .perf_rating import (
    OpponentScore,
    expected_score,
    expected_score_fide,
    is_plus_score,
    performance_category,
    performance_rating_average_opponents,
    performance_rating_fide,
    performance_rating_informal,
    tournament_score_percentage,
)
from .cpl import (
    EvalFn,
    GameAccuracy,
    accuracy_from_cpls,
    accuracy_percent,
    average_cpl,
    centipawn_loss,
    classify_cpl,
    cpl_from_pair,
    game_accuracy,
    median_cpl,
)

__all__ = [
    # glicko2
    "Glicko2Player",
    "Glicko2Result",
    "INITIAL_RATING",
    "INITIAL_RD",
    "INITIAL_VOLATILITY",
    "SCALE",
    "TAU",
    "update_player",
    "rating_to_elo",
    "elo_to_glicko2_rating",
    # perf_rating
    "OpponentScore",
    "expected_score",
    "expected_score_fide",
    "performance_rating_informal",
    "performance_rating_fide",
    "performance_rating_average_opponents",
    "tournament_score_percentage",
    "is_plus_score",
    "performance_category",
    # cpl
    "EvalFn",
    "GameAccuracy",
    "centipawn_loss",
    "cpl_from_pair",
    "average_cpl",
    "median_cpl",
    "accuracy_percent",
    "accuracy_from_cpls",
    "classify_cpl",
    "game_accuracy",
]
