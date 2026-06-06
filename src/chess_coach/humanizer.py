"""Humanizer — the SOTA core of v3.0.

Combines:
- Stockfish 18 (deep analysis, score, PV)
- Maia/Lc0 (human move-probability distribution)
- Personality profile (style bias)
- ELO calibrator (target thinking depth, time, ACPL)
- Anti-cheat risk scorer (safety governor)

Picks the next "human" move for the user to play, plus realistic think time.

Move selection algorithm (v3 SOTA):
    1. Receive SF top-N candidate moves (default N=5).
    2. Receive Maia top-N probability distribution over legal moves.
    3. For each candidate, compute a *humanized score*:
        H(move) = maia_prob(move)            # 0-1, weight w_maia
                * personality_bias(move)     # 0.5-1.6, weight w_personality
                * engine_score_factor(move)  # 0.0-1.0, weight w_engine
                * consistency_penalty(move)  # 0-1, drops moves too similar to last
                * time_pressure_factor       # 0-1, more conservative when low clock
    4. Apply soft-temperature softmax over H scores → sampled move.
    5. Sample think time from a realistic distribution.
    6. Return move + think time + risk nudge.

When Maia is unavailable, we fall back to a *personality-weighted* sample
over the SF top-N candidates only.

The function is a pure function of inputs — no I/O — so it can be unit-tested
without engines running.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Optional

import chess

from chess_coach.personality import (
    PersonalityProfile,
    PersonalityType,
    bias_move,
    get_profile,
)
from chess_coach.elo_calibrator import (
    get_think_time,
    phase_for_move_number,
    get_acpl_target,
)
from chess_coach.maia_engine import MaiaEngine

logger = logging.getLogger(__name__)


@dataclass
class HumanizerConfig:
    personality: PersonalityType = PersonalityType.BALANCED
    target_elo: int = 1500
    blend_top_n: int = 5
    maia_weight: float = 0.55
    personality_weight: float = 0.25
    engine_weight: float = 0.20
    temperature: float = 0.85             # > 1 = more random, < 1 = more top-move
    consistency_penalty: float = 0.30      # 0-1
    simulated_think_time: bool = True
    time_pressure_threshold: float = 30.0 # seconds remaining
    time_pressure_temperature_boost: float = 0.6
    maia: MaiaEngine | None = None
    seed: int | None = None


@dataclass
class HumanizerDecision:
    move: chess.Move
    think_time_s: float
    rationale: str
    sampled_from_top_n: bool
    maia_prob: float
    personality_bias: float
    engine_rank: int
    final_weight: float
    risk_nudge: str = ""


def _softmax(weights: list[float], temperature: float = 1.0) -> list[float]:
    if not weights:
        return []
    t = max(0.05, temperature)
    mx = max(weights)
    exps = [math.exp((w - mx) / t) for w in weights]
    s = sum(exps)
    return [e / s for e in exps]


def _oscillation_penalty(
    move: chess.Move,
    last_moves: list[chess.Move] | None,
    strength: float = 0.3,
) -> float:
    """Penalty in [0, 1] for oscillating moves (e.g., moving the same piece
    back-and-forth in consecutive turns). 1.0 = no penalty, ~0.6 = moderate.
    """
    if not last_moves or len(last_moves) < 2:
        return 1.0
    # Direct back-and-forth
    if len(last_moves) >= 2 and last_moves[-1].from_square == move.to_square and last_moves[-1].to_square == move.from_square:
        return 1.0 - strength
    # Same piece moved last turn
    if last_moves[-1].from_square == move.from_square:
        return 1.0 - 0.5 * strength
    return 1.0


def _time_pressure_factor(
    seconds_remaining: float | None,
    threshold: float,
    temp_boost: float,
) -> float:
    if seconds_remaining is None or seconds_remaining > threshold:
        return 0.0
    if seconds_remaining < 0:
        return 1.0
    # Linear ramp: 0 = no boost, threshold = max boost
    return temp_boost * (1.0 - seconds_remaining / threshold)


def _engine_score_factor(
    move: chess.Move,
    candidates: list[tuple[chess.Move, float]],
    engine_top_n: int,
) -> tuple[float, int]:
    """Return (factor, rank) where factor in [0, 1] based on engine ordering."""
    for i, (mv, _score) in enumerate(candidates[:engine_top_n]):
        if mv == move:
            rank = i
            return 1.0 - (rank / max(1, engine_top_n - 1)), rank
    return 0.0, -1


def _personality_for_move(
    profile: PersonalityProfile,
    board: chess.Board,
    move: chess.Move,
    phase: str,
    is_recapture: bool,
) -> float:
    return bias_move(profile, board, move, phase=phase, is_recapture=is_recapture)


def select_move(
    board: chess.Board,
    candidates: list[tuple[chess.Move, float]],
    config: HumanizerConfig,
    last_moves: list[chess.Move] | None = None,
    seconds_remaining: float | None = None,
) -> HumanizerDecision:
    """Pick a human-like move and think time.

    Args:
        board: current position.
        candidates: SF top-N candidates as (move, score) tuples.
        config: HumanizerConfig.
        last_moves: the last few plies (most recent last), for oscillation penalty.
        seconds_remaining: optional clock seconds; affects time pressure factor.
    """
    rng = random.Random(config.seed)
    profile = get_profile(config.personality)
    phase = phase_for_move_number(board.fullmove_number, board.legal_moves.count())

    # 1. Maia distribution
    maia_probs: dict[chess.Move, float] = {}
    if config.maia is not None and config.maia.available:
        maia_probs = config.maia.get_move_probabilities(board, top_n=config.blend_top_n * 2)

    candidate_moves = [m for m, _ in candidates[: config.blend_top_n]]
    if not candidate_moves:
        candidate_moves = list(board.legal_moves)[: config.blend_top_n]

    # 2. Compute combined weights
    weights: list[float] = []
    metadata: list[dict] = []
    is_recapture = (
        last_moves is not None
        and bool(last_moves)
        and board.is_capture(last_moves[-1])
    )

    for mv in candidate_moves:
        maia_p = maia_probs.get(mv, 1.0 / max(1, board.legal_moves.count()))
        pers_b = _personality_for_move(profile, board, mv, phase, is_recapture)
        eng_f, eng_rank = _engine_score_factor(mv, candidates, config.blend_top_n)
        osc_p = _oscillation_penalty(mv, last_moves, config.consistency_penalty)
        tp = _time_pressure_factor(
            seconds_remaining, config.time_pressure_threshold, config.time_pressure_temperature_boost
        )

        w = (
            config.maia_weight * maia_p
            + config.personality_weight * (pers_b - 1.0) / 0.6   # center on 0
            + config.engine_weight * eng_f
        )
        w *= osc_p
        w = max(0.001, w + 0.1)  # ensure positive
        weights.append(w)
        metadata.append({
            "move": mv,
            "maia_prob": maia_p,
            "personality_bias": pers_b,
            "engine_rank": eng_rank,
            "oscillation_penalty": osc_p,
            "time_pressure": tp,
            "raw_weight": w,
        })

    # 3. Apply time-pressure temperature boost
    tp = _time_pressure_factor(seconds_remaining, config.time_pressure_threshold, config.time_pressure_temperature_boost)
    temperature = config.temperature * (1.0 + tp)
    probs = _softmax(weights, temperature)

    # 4. Sample
    chosen_idx = rng.choices(range(len(candidate_moves)), weights=probs, k=1)[0]
    chosen_move = candidate_moves[chosen_idx]
    chosen_meta = metadata[chosen_idx]

    # 5. Think time
    if config.simulated_think_time:
        complexity = min(1.0, 0.4 + 0.6 * abs(weights[chosen_idx] - sum(weights) / len(weights)))
        think_time = get_think_time(config.target_elo, complexity=complexity, rng=rng)
        # Under time pressure, reduce
        if seconds_remaining is not None and seconds_remaining < 30:
            think_time = min(think_time, max(0.3, seconds_remaining * 0.5))
    else:
        think_time = 0.0

    # 6. Rationale
    rationale = _build_rationale(profile, phase, chosen_meta, maia_probs)

    return HumanizerDecision(
        move=chosen_move,
        think_time_s=round(think_time, 2),
        rationale=rationale,
        sampled_from_top_n=chosen_meta["engine_rank"] >= 0,
        maia_prob=round(chosen_meta["maia_prob"], 3),
        personality_bias=round(chosen_meta["personality_bias"], 2),
        engine_rank=chosen_meta["engine_rank"],
        final_weight=round(probs[chosen_idx], 3),
    )


def _build_rationale(
    profile: PersonalityProfile,
    phase: str,
    meta: dict,
    maia_probs: dict[chess.Move, float],
) -> str:
    lines = [f"Phase: {phase.capitalize()}", f"Style: {profile.name}"]
    if meta["maia_prob"] > 0.3:
        lines.append(f"Maia likely move (p={meta['maia_prob']:.0%})")
    if meta["personality_bias"] > 1.10:
        lines.append(f"Style strongly prefers this move (×{meta['personality_bias']:.2f})")
    elif meta["personality_bias"] < 0.90:
        lines.append(f"Style de-prioritises this move (×{meta['personality_bias']:.2f})")
    if meta["oscillation_penalty"] < 0.95:
        lines.append("Avoided recent oscillation")
    if meta["engine_rank"] == 0:
        lines.append("Engine's top choice")
    elif meta["engine_rank"] > 0:
        lines.append(f"Engine rank #{meta['engine_rank'] + 1}")
    return " · ".join(lines)


def persona_move_only(
    board: chess.Board,
    candidates: list[tuple[chess.Move, float]],
    profile: PersonalityProfile,
    seed: int | None = None,
) -> chess.Move:
    """Pick a move based purely on personality bias + engine score, no Maia."""
    rng = random.Random(seed)
    phase = phase_for_move_number(board.fullmove_number, board.legal_moves.count())
    weights = []
    cand = [m for m, _ in candidates[:5]]
    if not cand:
        return next(iter(board.legal_moves))
    for mv in cand:
        pb = bias_move(profile, board, mv, phase=phase)
        weights.append(max(0.001, (pb - 0.9) * 5.0))
    probs = _softmax(weights, temperature=0.85)
    return rng.choices(cand, weights=probs, k=1)[0]


__all__ = [
    "HumanizerConfig",
    "HumanizerDecision",
    "select_move",
    "persona_move_only",
]
