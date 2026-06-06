"""Game Report Card (Lichess + chess.com Game Review v2 style).

Produces a per-game summary with:
  - Phase accuracy (Opening / Middlegame / Endgame)
  - Letter grades (A-F) per phase
  - Best move / worst move
  - Accuracy trend
  - Move class distribution
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PhaseGrade:
    phase: str
    accuracy: float
    grade: str  # A, B, C, D, F


@dataclass
class ReportCard:
    """A per-game report card."""
    game_id: str
    overall_accuracy: float
    phase_grades: list[PhaseGrade] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    best_move_ply: int | None = None
    worst_move_ply: int | None = None
    summary: str = ""


def _letter_grade(accuracy: float) -> str:
    """Convert accuracy to letter grade (chess.com convention)."""
    if accuracy >= 95:
        return "A+"
    if accuracy >= 90:
        return "A"
    if accuracy >= 85:
        return "B+"
    if accuracy >= 80:
        return "B"
    if accuracy >= 70:
        return "C"
    if accuracy >= 60:
        return "D"
    return "F"


def build_report_card(
    game_id: str,
    moves: list[dict],
    accuracy_by_phase: dict[str, float],
    counts: dict[str, int],
) -> ReportCard:
    """Build a report card from a classified game."""
    phases = ["opening", "middlegame", "endgame"]
    grades = [
        PhaseGrade(phase=p, accuracy=accuracy_by_phase.get(p, 0.0),
                   grade=_letter_grade(accuracy_by_phase.get(p, 0.0)))
        for p in phases
    ]
    # Best move = highest accuracy
    best_move = max(moves, key=lambda m: m.get("accuracy", 0)) if moves else None
    worst_move = min(moves, key=lambda m: m.get("accuracy", 0)) if moves else None
    overall = sum(accuracy_by_phase.values()) / max(1, len(accuracy_by_phase))
    summary = _make_summary(grades, counts, overall)
    return ReportCard(
        game_id=game_id,
        overall_accuracy=overall,
        phase_grades=grades,
        counts=counts,
        best_move_ply=best_move.get("ply") if best_move else None,
        worst_move_ply=worst_move.get("ply") if worst_move else None,
        summary=summary,
    )


def _make_summary(grades: list[PhaseGrade], counts: dict[str, int], overall: float) -> str:
    """Generate a 1-2 sentence natural-language summary (template-based, no LLM)."""
    grade_overall = _letter_grade(overall)
    blunders = counts.get("blunder", 0)
    brilliant = counts.get("brilliant", 0)
    great = counts.get("great", 0)
    parts = [f"Overall grade {grade_overall} ({overall:.0f}% accuracy)."]
    if brilliant:
        parts.append(f"{brilliant} brilliant move{'s' if brilliant > 1 else ''} found.")
    if great:
        parts.append(f"{great} great move{'s' if great > 1 else ''}.")
    if blunders:
        parts.append(f"{blunders} blunder{'s' if blunders > 1 else ''} to work on.")
    for g in grades:
        if g.grade in {"D", "F"}:
            parts.append(f"Weakest phase: {g.phase} ({g.accuracy:.0f}%, grade {g.grade}).")
    return " ".join(parts)
