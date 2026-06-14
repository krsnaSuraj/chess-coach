"""Coach flow for real-time chess coaching."""
from chess_coach.coach.side_selector import SideSelector
from chess_coach.coach.opponent_entry import OpponentEntry
from chess_coach.coach.weakness import WeaknessReport, GameSample, analyze_weaknesses
from chess_coach.coach.training_plan import TrainingPlan, build_training_plan
from chess_coach.coach.oprep import Repertoire, OpeningLine

__all__ = [
    "SideSelector",
    "OpponentEntry",
    "WeaknessReport",
    "GameSample",
    "analyze_weaknesses",
    "TrainingPlan",
    "build_training_plan",
    "Repertoire",
    "OpeningLine",
]
