"""Critical moment detection — find inflection points in eval trajectory.

A critical moment is a position where the evaluation swings significantly
(>= 100cp) within a few moves, indicating a turning point (mistake, brilliant,
tactic). These are the positions worth showing the user.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class CriticalMoment:
    """A single critical moment in a game."""
    move_number: int
    fen: str
    eval_before_cp: float
    eval_after_cp: float
    swing_cp: float         # absolute eval change
    classification: str     # blunder / brilliant / missed_win / missed_draw / equal
    move_played: str        # SAN
    best_move: str          # SAN of best alternative
    commentary: str         # human-readable explanation

    def to_dict(self) -> dict:
        return {
            "move_number": self.move_number,
            "fen": self.fen,
            "eval_before_cp": round(self.eval_before_cp, 1),
            "eval_after_cp": round(self.eval_after_cp, 1),
            "swing_cp": round(self.swing_cp, 1),
            "classification": self.classification,
            "move_played": self.move_played,
            "best_move": self.best_move,
            "commentary": self.commentary,
        }


# Thresholds (in centipawns) for classifying swing magnitude
SWING_BLUNDER = 200
SWING_MISTAKE = 100
SWING_INACCURACY = 50
SWING_BRILLIANT = 150  # positive swing for moving side


def _classify_swing(before: float, after: float, moving_side: str) -> str:
    """Determine the nature of the swing from the moving side's POV.

    before: eval before the move (from moving side's POV)
    after: eval after the move (from moving side's POV)
    """
    swing = before - after  # positive = moving side lost ground
    if swing >= SWING_BLUNDER:
        return "blunder"
    if swing >= SWING_MISTAKE:
        return "mistake"
    if swing >= SWING_INACCURACY:
        return "inaccuracy"
    # Positive swing for moving side = found a winning resource
    if after - before >= SWING_BRILLIANT:
        return "brilliant"
    return "equal"


def find_critical_moments(
    positions: Sequence[dict],
    min_swing_cp: float = 100.0,
    window: int = 2,
) -> list[CriticalMoment]:
    """Find critical moments in a game.

    positions: list of dicts, one per ply, with keys:
        - fen: position FEN
        - eval_cp: eval from side-to-move's POV (centipawns, or None if mate)
        - move_played: SAN of move just played (or first move is empty)
        - best_move: SAN of engine's top choice
        - side_to_move: 'w' or 'b' for the side that just moved (or will move for first ply)
    """
    moments: list[CriticalMoment] = []
    n = len(positions)
    if n < 2:
        return moments

    for i in range(1, n):
        p = positions[i]
        if "eval_cp" not in p or p.get("eval_cp") is None:
            continue
        if "prev_eval_cp" not in positions[i - 1] or positions[i - 1].get("prev_eval_cp") is None:
            continue

        # Normalize to moving side's perspective
        side = p.get("side_just_moved", "w")
        sign = 1.0 if side == "w" else -1.0
        before = positions[i - 1]["prev_eval_cp"] * sign
        after = p["eval_cp"] * sign
        swing = abs(after - before)

        if swing < min_swing_cp:
            continue

        classification = _classify_swing(before, after, side)
        commentary = _make_commentary(classification, before, after, swing)
        moments.append(CriticalMoment(
            move_number=i // 2 + 1,
            fen=p.get("fen", ""),
            eval_before_cp=before,
            eval_after_cp=after,
            swing_cp=swing,
            classification=classification,
            move_played=p.get("move_played", ""),
            best_move=p.get("best_move", ""),
            commentary=commentary,
        ))

    return moments


def _make_commentary(classification: str, before: float, after: float, swing: float) -> str:
    """Generate human-readable commentary for a critical moment."""
    swing_pawns = swing / 100.0
    if classification == "blunder":
        return f"Blunder: lost {swing_pawns:.1f} pawns of advantage. Consider the engine's top choice."
    if classification == "mistake":
        return f"Mistake: gave up {swing_pawns:.1f} pawns. There was a better continuation."
    if classification == "inaccuracy":
        return f"Slight inaccuracy: position worsened by {swing_pawns:.1f} pawns."
    if classification == "brilliant":
        return f"Brilliant! Found a strong resource gaining {swing_pawns:.1f} pawns."
    return f"Position shifted by {swing_pawns:.1f} pawns."


def summarize_critical_moments(moments: list[CriticalMoment]) -> dict:
    """Aggregate critical moments into a summary."""
    if not moments:
        return {"count": 0, "by_type": {}, "biggest_swing": None, "total_swing": 0.0}

    by_type: dict[str, int] = {}
    total_swing = 0.0
    biggest = moments[0]
    for m in moments:
        by_type[m.classification] = by_type.get(m.classification, 0) + 1
        total_swing += m.swing_cp
        if m.swing_cp > biggest.swing_cp:
            biggest = m
    return {
        "count": len(moments),
        "by_type": by_type,
        "biggest_swing": biggest.to_dict(),
        "total_swing": round(total_swing, 1),
    }
