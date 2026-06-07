"""Personalized training plan generator.

Builds a 4-week training plan based on a WeaknessReport. The plan
allocates more time to the user's weakest areas (highest ACPL or
blunder rate) and includes specific recommendations like
"solve 20 tactics daily" or "study endgame rook vs pawn".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Dict, List,
)

from .weakness import (
    CATEGORY_ENDGAME,
    CATEGORY_POSITIONAL,
    CATEGORY_TACTICS,
    CATEGORY_TIME,
    PHASE_ENDGAME,
    PHASE_MIDDLEGAME,
    PHASE_OPENING,
    WeaknessReport,
)


@dataclass
class TrainingTask:
    """A single training task for one day."""

    day: int  # 1..28
    category: str  # opening | middlegame | endgame | tactics | positional | time
    title: str
    description: str
    minutes: int = 30

    def to_dict(self) -> Dict[str, object]:
        return {
            "day": self.day,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "minutes": self.minutes,
        }


@dataclass
class TrainingPlan:
    """4-week training plan with daily tasks."""

    user_elo: int = 1500
    weakness_summary: str = ""
    tasks: List[TrainingTask] = field(default_factory=list)
    focus_areas: List[str] = field(default_factory=list)
    weekly_summary: Dict[int, int] = field(default_factory=dict)  # week -> total minutes

    def to_dict(self) -> Dict[str, object]:
        return {
            "user_elo": self.user_elo,
            "weakness_summary": self.weakness_summary,
            "tasks": [t.to_dict() for t in self.tasks],
            "focus_areas": self.focus_areas,
            "weekly_summary": self.weekly_summary,
        }


_TACTICS_TITLES = {
    "low": ("Pattern Recognition",
            "Solve 15-20 mixed tactics. Focus on pins, forks, skewers. Use Lichess/Puzzle Rush."),
    "mid": ("Tactical Vision",
            "Solve 20-25 hard tactics. Focus on deflection, discovered attacks, zwischenzug."),
    "high": ("Advanced Tactics",
            "Solve 30+ puzzles (2000+ rated). Focus on long forcing sequences, sacrifices."),
}

_ENDGAME_TITLES = {
    "low": ("Basic Checkmates",
            "K+Q vs K, K+R vs K, K+2B vs K until consistent. 15 min daily."),
    "mid": ("Pawn Endgames",
            "OPR rule, square rule, rook pawns, opposition. 20 min daily."),
    "high": ("Complex Endgames",
            "Lucena, Philidor, K+P vs K+B, R+P vs R endings. 30 min study."),
}

_OPENING_TITLES = {
    "low": ("Opening Repertoire",
            "Pick 2 openings as White, 1 vs 1.e4, 1 vs 1.d4. Memorize first 8 moves."),
    "mid": ("Opening Repertoire Refinement",
            "Study middlegame plans for your openings. Review GM games in your lines."),
    "high": ("Opening Novelties",
            "Use engines to find novelties. Maintain a 15-move repertoire with analysis."),
}

_MIDDLEGAME_TITLES = {
    "low": ("Piece Activity",
            "Study outposts, weak squares, prophylaxis. 20 min pattern study."),
    "mid": ("Strategic Mastery",
            "Pawn structure, color complexes, exchange sacrifices. 25 min."),
    "high": ("Deep Strategy",
            "Compare Karpov vs Kasparov endgames. Study 30 min daily."),
}


def _elo_band(elo: int) -> str:
    if elo < 1400:
        return "low"
    if elo < 1800:
        return "mid"
    return "high"


def build_training_plan(report: WeaknessReport, user_elo: int = 1500, total_days: int = 28) -> TrainingPlan:
    """Build a personalized training plan from a WeaknessReport.

    Total minutes per day is roughly equal (30-45 min). The plan
    rotates through categories, weighted by weakness severity.
    """
    plan = TrainingPlan(user_elo=user_elo)

    # Determine focus areas
    focus: List[tuple[str, float]] = []
    if report.worst_phase:
        focus.append((report.worst_phase, 2.0))
    if report.worst_category:
        focus.append((report.worst_category, 1.5))
    for cat, acpl in sorted(report.by_category.items(), key=lambda kv: -kv[1].acpl)[:2]:
        if not any(c == cat for c, _ in focus):
            focus.append((cat, 1.0))

    if not focus:
        focus = [(CATEGORY_TACTICS, 1.5), (PHASE_ENDGAME, 1.0)]
    plan.focus_areas = [c for c, _ in focus]

    band = _elo_band(user_elo)

    def make_task(day: int, category: str) -> TrainingTask:
        if category == CATEGORY_TACTICS or category == "tactics":
            title, desc = _TACTICS_TITLES[band]
            return TrainingTask(day=day, category=category, title=title, description=desc, minutes=30)
        if category == CATEGORY_ENDGAME or category == PHASE_ENDGAME:
            title, desc = _ENDGAME_TITLES[band]
            return TrainingTask(day=day, category=category, title=title, description=desc, minutes=30)
        if category == PHASE_OPENING or category == "opening":
            title, desc = _OPENING_TITLES[band]
            return TrainingTask(day=day, category=category, title=title, description=desc, minutes=20)
        if category == PHASE_MIDDLEGAME or category == "middlegame":
            title, desc = _MIDDLEGAME_TITLES[band]
            return TrainingTask(day=day, category=category, title=title, description=desc, minutes=25)
        if category == CATEGORY_POSITIONAL:
            title, desc = _MIDDLEGAME_TITLES[band]
            return TrainingTask(day=day, category=CATEGORY_POSITIONAL, title=f"Positional: {title}", description=desc, minutes=20)
        if category == CATEGORY_TIME:
            return TrainingTask(
                day=day,
                category=category,
                title="Time Pressure Drills",
                description="Play 5+3, 5+0, 3+0 games. Practice premoves.",
                minutes=20,
            )
        return TrainingTask(day=day, category=category, title="Review", description="Analyze your last 3 games.", minutes=15)

    # Generate daily tasks: rotate through focus, biased by weight
    for day in range(1, total_days + 1):
        idx = (day - 1) % len(focus)
        category, _ = focus[idx]
        # Add 1 day of game review per week
        if day % 7 == 0:
            plan.tasks.append(
                TrainingTask(
                    day=day,
                    category="review",
                    title="Weekly Review",
                    description="Analyze all games from the week. Identify 3 patterns.",
                    minutes=45,
                )
            )
        else:
            plan.tasks.append(make_task(day, category))

    # Weekly summary
    for task in plan.tasks:
        week = (task.day - 1) // 7 + 1
        plan.weekly_summary[week] = plan.weekly_summary.get(week, 0) + task.minutes

    # Build summary text
    parts = []
    for area, _ in focus:
        parts.append(area)
    plan.weakness_summary = f"Focus: {', '.join(parts)}. ELO band: {band}."

    return plan


def plan_to_text(plan: TrainingPlan) -> str:
    """Format a TrainingPlan as human-readable text."""
    lines = [f"Training Plan for ELO {plan.user_elo}", "=" * 32, ""]
    lines.append(plan.weakness_summary)
    lines.append("")
    for week in sorted(plan.weekly_summary):
        lines.append(f"Week {week}: {plan.weekly_summary[week]} minutes total")
    lines.append("")
    for task in plan.tasks:
        lines.append(f"Day {task.day:2d} ({task.category:>12s}): {task.title} — {task.minutes}min")
        lines.append(f"           {task.description}")
    return "\n".join(lines)


__all__ = [
    "TrainingTask",
    "TrainingPlan",
    "build_training_plan",
    "plan_to_text",
]
