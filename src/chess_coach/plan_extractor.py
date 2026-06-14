"""Plan extraction from principal variation (PV).

Given a sequence of moves the engine recommends, generate a human-readable
plan summary. Uses simple heuristics based on piece trajectories, pawn
structure changes, and piece coordination.
"""

from __future__ import annotations

import chess
from dataclasses import dataclass


@dataclass
class PlanStep:
    """A single step in a plan."""
    ply: int
    move: str
    intent: str
    target: str

    def to_dict(self) -> dict:
        return {"ply": self.ply, "move": self.move, "intent": self.intent, "target": self.target}


@dataclass
class Plan:
    """Full plan extracted from a PV."""
    summary: str
    steps: list[PlanStep]
    themes: list[str]

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "steps": [s.to_dict() for s in self.steps],
            "themes": self.themes,
        }


CENTER = {chess.E4, chess.D4, chess.E5, chess.D5}
EXTENDED_CENTER = CENTER | {chess.C4, chess.C5, chess.F4, chess.F5}


def extract_plan(board: chess.Board, pv_moves: list[chess.Move]) -> Plan:
    """Extract a human-readable plan from a principal variation.

    board: position BEFORE the first PV move
    pv_moves: list of moves in the PV (SAN or Move objects)
    """
    if not pv_moves:
        return Plan(summary="No plan available.", steps=[], themes=[])

    working = board.copy()
    steps: list[PlanStep] = []
    themes: set[str] = set()

    for i, mv in enumerate(pv_moves):
        if working.is_game_over():
            break
        if isinstance(mv, str):
            try:
                move = working.parse_san(mv)
            except (chess.InvalidMoveError, chess.AmbiguousMoveError, ValueError):
                break
        else:
            move = mv
        san = working.san(move)
        intent, target = _classify_move(working, move, i)
        themes.add(_theme_of(intent))
        steps.append(PlanStep(ply=i + 1, move=san, intent=intent, target=target))
        working.push(move)

    summary = _build_summary(steps, themes)
    return Plan(summary=summary, steps=steps, themes=sorted(themes))


def _classify_move(board: chess.Board, move: chess.Move, ply: int) -> tuple[str, str]:
    """Classify the intent of a single move."""
    piece = board.piece_at(move.from_square)
    to_sq = move.to_square
    from_sq = move.from_square
    target = chess.square_name(to_sq)

    if not piece:
        return "unknown", target

    # Castling
    if board.is_castling(move):
        side = "kingside" if chess.square_file(to_sq) > chess.square_file(from_sq) else "queenside"
        return f"castle {side}", target

    # Capture
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            cap_name = chess.piece_name(captured.piece_type)
            return f"capture {cap_name}", target

    # Promotion
    if move.promotion:
        promo_name = chess.piece_name(move.promotion)
        return f"promote to {promo_name}", target

    # Check
    board.push(move)
    gives_check = board.is_check()
    board.pop()
    if gives_check:
        return "give check", target

    # Center control (first 10 plies)
    if ply < 10 and to_sq in EXTENDED_CENTER:
        return "control center", target

    # Pawn push
    if piece.piece_type == chess.PAWN:
        if to_sq in CENTER:
            return "advance pawn to center", target
        if _is_passed_pawn(board, to_sq, piece.color) and not board.is_capture(move):
            return "push passed pawn", target
        return "pawn advance", target

    # Knight to outpost
    if piece.piece_type == chess.KNIGHT:
        if to_sq in EXTENDED_CENTER and not board.piece_at(to_sq):
            return "develop knight", target
        return "knight maneuver", target

    # Bishop
    if piece.piece_type == chess.BISHOP:
        if from_sq in (chess.B1, chess.G1, chess.B8, chess.G8):
            return "develop bishop", target
        return "bishop maneuver", target

    # Rook
    if piece.piece_type == chess.ROOK:
        rank = chess.square_rank(to_sq)
        if rank == 6 and piece.color:  # 7th rank for white
            return "occupy 7th rank", target
        if rank == 1 and not piece.color:  # 7th rank for black
            return "occupy 7th rank", target
        if to_sq in (chess.A1, chess.H1, chess.A8, chess.H8):
            return "rook to back rank", target
        return "rook maneuver", target

    # Queen
    if piece.piece_type == chess.QUEEN:
        return "queen maneuver", target

    # King
    if piece.piece_type == chess.KING:
        return "king move", target

    return "reposition", target


def _is_passed_pawn(board: chess.Board, square: int, color: chess.Color) -> bool:
    """Check if a pawn on the given square is a passed pawn."""
    pawn_file = chess.square_file(square)
    pawn_rank = chess.square_rank(square)
    forward_dir = 1 if color == chess.WHITE else -1
    # Check squares in front of pawn on same file and adjacent files
    for f in [pawn_file - 1, pawn_file, pawn_file + 1]:
        if 0 <= f <= 7:
            for r in range(pawn_rank + forward_dir, 8 if color == chess.WHITE else -1, forward_dir):
                sq = chess.square(f, r)
                p = board.piece_at(sq)
                if p and p.piece_type == chess.PAWN and p.color != color:
                    return False
    return True


def _theme_of(intent: str) -> str:
    """Group intents into themes for the plan summary."""
    if "castle" in intent:
        return "king_safety"
    if "capture" in intent or "tactic" in intent or "fork" in intent:
        return "tactics"
    if "center" in intent or "develop" in intent:
        return "opening_development"
    if "pawn" in intent:
        return "pawn_structure"
    if "knight" in intent or "bishop" in intent:
        return "minor_piece_activity"
    if "rook" in intent or "queen" in intent:
        return "heavy_piece_activity"
    if "king" in intent:
        return "king_safety"
    return "positional"


def _build_summary(steps: list[PlanStep], themes: set[str]) -> str:
    """Build a one-paragraph summary of the plan."""
    if not steps:
        return "No plan available."

    first_intent = steps[0].intent
    last_step = steps[-1]

    # Opening patterns
    if "castle" in first_intent:
        opener = "Castle first to ensure king safety"
    elif "control center" in first_intent or "develop" in first_intent:
        opener = "Start with development and center control"
    elif "capture" in first_intent:
        opener = "Address the tactical situation immediately"
    else:
        opener = f"Begin with {first_intent}"

    # Theme list
    theme_phrases = {
        "king_safety": "king safety",
        "tactics": "tactical opportunities",
        "opening_development": "piece development",
        "pawn_structure": "pawn structure",
        "minor_piece_activity": "minor piece activity",
        "heavy_piece_activity": "heavy piece coordination",
        "positional": "positional improvement",
    }
    focus = ", ".join(theme_phrases.get(t, t) for t in sorted(themes))

    return (f"{opener}. Plan focuses on {focus}. "
            f"Ends with {last_step.intent} ({last_step.move}).")
