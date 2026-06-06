"""Personality profiles — 5 chess styles with bias dictionaries.

Each personality defines how a player of that style prefers to act across:
- opening repertoire (preferred ECO codes)
- tactical vs. positional bias per move
- opening / middlegame / endgame style weights
- special heuristics (recapture, attack-on-king, pawn structure, exchanges)

The bias is applied as a multiplier on candidate move scores from the
multi-engine handler; values < 1.0 de-prioritise a move, > 1.0 prioritise.
"""

from __future__ import annotations

import chess
from dataclasses import dataclass, field
from enum import Enum


class PersonalityType(str, Enum):
    AGGRESSIVE = "aggressive"
    POSITIONAL = "positional"
    TACTICAL = "tactical"
    DEFENSIVE = "defensive"
    BALANCED = "balanced"


@dataclass(frozen=True)
class PersonalityProfile:
    """Style profile with move-bias and opening preferences."""

    name: str
    description: str
    emoji: str
    # Per-move-bias multipliers (applied to engine candidate scores)
    capture_weight: float
    check_weight: float
    attack_weight: float         # moves closer to enemy king
    center_control_weight: float
    development_weight: float    # only meaningful in opening phase
    endgame_simplify_weight: float
    recapture_weight: float      # if opponent just captured, immediately recapture
    pawn_structure_weight: float
    king_safety_weight: float
    # Phase weights: how the style shifts in opening / middlegame / endgame
    opening_weights: dict[str, float]
    middlegame_weights: dict[str, float]
    endgame_weights: dict[str, float]
    # Preferred ECO prefixes
    preferred_openings: tuple[str, ...] = field(default_factory=tuple)
    # Style consistency target (0.0-1.0): how tightly to enforce the profile
    consistency: float = 0.7
    # How much the personality influences move selection overall
    blend_factor: float = 0.3


def _attacker_distance_to_king(board: chess.Board, color: chess.Color) -> int:
    """Chebyshev distance of `color`'s pieces to enemy king (0 if no king)."""
    enemy_king = board.king(not color)
    if enemy_king is None:
        return 8
    min_d = 8
    for sq in board.pieces(chess.KNIGHT, color) | board.pieces(chess.BISHOP, color) | board.pieces(chess.ROOK, color) | board.pieces(chess.QUEEN, color):
        d = max(abs(chess.square_file(sq) - chess.square_file(enemy_king)),
                abs(chess.square_rank(sq) - chess.square_rank(enemy_king)))
        if d < min_d:
            min_d = d
    return min_d


def _king_safety_delta(board_after: chess.Board, color: chess.Color) -> float:
    """Reward a move that increases enemy-king exposure or improves own-king safety.

    Heuristic: count attackers around each king. Returns a value in [-1.0, 1.0].
    """
    own_king = board_after.king(color)
    enemy_king = board_after.king(not color)
    if own_king is None or enemy_king is None:
        return 0.0

    def _attackers_near(sq: int, by_color: chess.Color) -> int:
        if sq is None:
            return 0
        cnt = 0
        rank, file = chess.square_rank(sq), chess.square_file(sq)
        for dr in (-1, 0, 1):
            for df in (-1, 0, 1):
                if dr == 0 and df == 0:
                    continue
                r, f = rank + dr, file + df
                if 0 <= r < 8 and 0 <= f < 8:
                    s = chess.square(f, r)
                    if board_after.is_attacked_by(by_color, s):
                        cnt += 1
        return cnt

    own_threats = _attackers_near(own_king, not color)
    enemy_threats = _attackers_near(enemy_king, color)
    return (enemy_threats - own_threats) / 8.0


def bias_move(
    profile: PersonalityProfile,
    board_before: chess.Board,
    move: chess.Move,
    phase: str,
    is_recapture: bool = False,
) -> float:
    """Return a multiplier in roughly [0.5, 1.6] representing how the personality
    would score the move given the board state before the move and the
    current game phase.

    Caller multiplies this into the engine's centipawn-loss-derived score.
    """
    board_after = board_before.copy()
    board_after.push(move)

    weights = {
        "opening": profile.opening_weights,
        "middlegame": profile.middlegame_weights,
        "endgame": profile.endgame_weights,
    }.get(phase, profile.middlegame_weights)

    is_capture = board_before.is_capture(move)
    gives_check = board_after.is_check()

    dist_before = _attacker_distance_to_king(board_before, board_before.turn)
    dist_after = _attacker_distance_to_king(board_after, board_before.turn)
    moves_closer_to_king = dist_after < dist_before

    is_development = (
        phase == "opening"
        and board_before.piece_type_at(move.from_square) in (chess.KNIGHT, chess.BISHOP)
        and chess.square_rank(move.to_square) in (2, 5)  # active square
        and board_before.piece_type_at(move.to_square) is None
    )

    score = 1.0
    if is_capture:
        score *= profile.capture_weight
    if gives_check:
        score *= profile.check_weight
    if moves_closer_to_king:
        score *= profile.attack_weight
    if is_development:
        score *= profile.development_weight
    if is_recapture:
        score *= profile.recapture_weight
    if board_after.is_game_over() and board_after.result() == "1-0":
        if board_before.turn == chess.WHITE:
            score *= 1.10
    elif board_after.is_game_over() and board_after.result() == "0-1":
        if board_before.turn == chess.BLACK:
            score *= 1.10

    # King safety: reward moves that increase enemy-king exposure
    ks_delta = _king_safety_delta(board_after, board_before.turn)
    score *= 1.0 + (ks_delta * profile.king_safety_weight * 0.1)

    # Center control: bonus for central squares (d4, d5, e4, e5) in opening/middle
    to_sq = move.to_square
    if phase in ("opening", "middlegame"):
        if to_sq in (chess.D4, chess.D5, chess.E4, chess.E5):
            score *= profile.center_control_weight

    # Blend with weights dict (currently phase weights modulate overall style)
    style_blend = sum(weights.values()) / max(1, len(weights))
    score *= 0.7 + 0.3 * style_blend

    return max(0.5, min(1.6, score))


# ----------------------------- The Five Personalities ----------------------------- #

AGGRESSIVE = PersonalityProfile(
    name="Aggressive",
    description="King hunters. Sacrifices material for attack, prefers open positions, sharp tactics.",
    emoji="🔥",
    capture_weight=1.20,
    check_weight=1.35,
    attack_weight=1.30,
    center_control_weight=1.10,
    development_weight=1.05,
    endgame_simplify_weight=0.85,
    recapture_weight=1.10,
    pawn_structure_weight=0.85,
    king_safety_weight=0.80,  # tolerates own king danger
    opening_weights={"development": 1.05, "attack": 1.20, "structure": 0.85, "tactics": 1.25, "defense": 0.80},
    middlegame_weights={"development": 0.95, "attack": 1.35, "structure": 0.85, "tactics": 1.30, "defense": 0.80},
    endgame_weights={"development": 0.80, "attack": 1.20, "structure": 0.90, "tactics": 1.10, "defense": 0.85},
    preferred_openings=("B20", "B22", "B33", "C42", "C45", "C50"),
    consistency=0.8,
    blend_factor=0.35,
)

POSITIONAL = PersonalityProfile(
    name="Positional",
    description="Long-term planner. Outposts, pawn structure, prophylaxis. Avoids forcing lines.",
    emoji="♟️",
    capture_weight=0.90,
    check_weight=0.85,
    attack_weight=0.85,
    center_control_weight=1.30,
    development_weight=1.25,
    endgame_simplify_weight=1.20,
    recapture_weight=0.80,
    pawn_structure_weight=1.40,
    king_safety_weight=1.10,
    opening_weights={"development": 1.30, "attack": 0.80, "structure": 1.40, "tactics": 0.85, "defense": 1.10},
    middlegame_weights={"development": 1.00, "attack": 0.85, "structure": 1.45, "tactics": 0.90, "defense": 1.15},
    endgame_weights={"development": 0.85, "attack": 0.80, "structure": 1.50, "tactics": 0.85, "defense": 1.20},
    preferred_openings=("A15", "A30", "D02", "D30", "D37", "E20"),
    consistency=0.85,
    blend_factor=0.3,
)

TACTICAL = PersonalityProfile(
    name="Tactical",
    description="Puzzle-solver. Sees combinations, sacrifices for concrete gain, thrives in complications.",
    emoji="⚔️",
    capture_weight=1.30,
    check_weight=1.20,
    attack_weight=1.10,
    center_control_weight=1.05,
    development_weight=1.10,
    endgame_simplify_weight=0.90,
    recapture_weight=1.30,
    pawn_structure_weight=0.95,
    king_safety_weight=0.95,
    opening_weights={"development": 1.10, "attack": 1.10, "structure": 0.95, "tactics": 1.30, "defense": 0.95},
    middlegame_weights={"development": 0.95, "attack": 1.20, "structure": 0.95, "tactics": 1.40, "defense": 0.95},
    endgame_weights={"development": 0.90, "attack": 1.10, "structure": 1.00, "tactics": 1.30, "defense": 0.95},
    preferred_openings=("B12", "B15", "B90", "C00", "C42", "C45"),
    consistency=0.75,
    blend_factor=0.4,
)

DEFENSIVE = PersonalityProfile(
    name="Defensive",
    description="Counter-puncher. Holds structure, trades pieces, exploits opponent over-extension.",
    emoji="🛡️",
    capture_weight=1.05,
    check_weight=0.90,
    attack_weight=0.80,
    center_control_weight=1.00,
    development_weight=1.20,
    endgame_simplify_weight=1.30,
    recapture_weight=1.05,
    pawn_structure_weight=1.25,
    king_safety_weight=1.30,
    opening_weights={"development": 1.25, "attack": 0.75, "structure": 1.25, "tactics": 0.90, "defense": 1.40},
    middlegame_weights={"development": 1.00, "attack": 0.80, "structure": 1.30, "tactics": 0.95, "defense": 1.40},
    endgame_weights={"development": 0.90, "attack": 0.75, "structure": 1.35, "tactics": 0.90, "defense": 1.30},
    preferred_openings=("B12", "B18", "C00", "C41", "D02", "D30"),
    consistency=0.85,
    blend_factor=0.3,
)

BALANCED = PersonalityProfile(
    name="Balanced",
    description="Classical complete player. Adapts style to position; no strong bias in any direction.",
    emoji="⚖️",
    capture_weight=1.00,
    check_weight=1.00,
    attack_weight=1.00,
    center_control_weight=1.00,
    development_weight=1.00,
    endgame_simplify_weight=1.00,
    recapture_weight=1.00,
    pawn_structure_weight=1.00,
    king_safety_weight=1.00,
    opening_weights={"development": 1.00, "attack": 1.00, "structure": 1.00, "tactics": 1.00, "defense": 1.00},
    middlegame_weights={"development": 1.00, "attack": 1.00, "structure": 1.00, "tactics": 1.00, "defense": 1.00},
    endgame_weights={"development": 1.00, "attack": 1.00, "structure": 1.00, "tactics": 1.00, "defense": 1.00},
    preferred_openings=(),
    consistency=0.5,
    blend_factor=0.2,
)


PROFILES: dict[PersonalityType, PersonalityProfile] = {
    PersonalityType.AGGRESSIVE: AGGRESSIVE,
    PersonalityType.POSITIONAL: POSITIONAL,
    PersonalityType.TACTICAL: TACTICAL,
    PersonalityType.DEFENSIVE: DEFENSIVE,
    PersonalityType.BALANCED: BALANCED,
}


def get_profile(personality: PersonalityType | str) -> PersonalityProfile:
    if isinstance(personality, str):
        personality = PersonalityType(personality.lower())
    return PROFILES[personality]


def list_personalities() -> list[PersonalityProfile]:
    return list(PROFILES.values())


__all__ = [
    "PersonalityType",
    "PersonalityProfile",
    "AGGRESSIVE",
    "POSITIONAL",
    "TACTICAL",
    "DEFENSIVE",
    "BALANCED",
    "PROFILES",
    "get_profile",
    "list_personalities",
    "bias_move",
]
