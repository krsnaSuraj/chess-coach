"""Coach submodules: weakness analysis, training plans, opening repertoire."""
from __future__ import annotations

from .weakness import (
    CATEGORY_ENDGAME,
    CATEGORY_POSITIONAL,
    CATEGORY_TACTICS,
    CATEGORY_TIME,
    GameSample,
    PHASE_ENDGAME,
    PHASE_MIDDLEGAME,
    PHASE_OPENING,
    PhaseStats,
    WeaknessReport,
    analyze_weaknesses,
    classify_category,
    detect_phase,
    find_most_improvement_potential,
)
from .training_plan import (
    TrainingPlan,
    TrainingTask,
    build_training_plan,
    plan_to_text,
)
from .oprep import (
    OpeningLine,
    Repertoire,
    make_opening_line,
    recommend_repertoire,
    repertoire_diversity,
)

__all__ = [
    # weakness
    "CATEGORY_ENDGAME",
    "CATEGORY_POSITIONAL",
    "CATEGORY_TACTICS",
    "CATEGORY_TIME",
    "GameSample",
    "PHASE_ENDGAME",
    "PHASE_MIDDLEGAME",
    "PHASE_OPENING",
    "PhaseStats",
    "WeaknessReport",
    "analyze_weaknesses",
    "classify_category",
    "detect_phase",
    "find_most_improvement_potential",
    # training_plan
    "TrainingPlan",
    "TrainingTask",
    "build_training_plan",
    "plan_to_text",
    # oprep
    "OpeningLine",
    "Repertoire",
    "make_opening_line",
    "recommend_repertoire",
    "repertoire_diversity",
]
