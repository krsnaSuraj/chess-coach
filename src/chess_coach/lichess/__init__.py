"""Lichess ecosystem integration.

SOTA 2026 standard: connect to Lichess services for opening prep, puzzles,
studies, game sync, and OAuth login. Public + free.
"""

from chess_coach.lichess.explorer import (
    LichessExplorer,
    ExplorerResponse,
    MoveStats,
    ExplorerSource,
)
from chess_coach.lichess.puzzles import (
    LichessPuzzles,
    Puzzle,
    PuzzleTheme,
)
from chess_coach.lichess.cache import LichessCache, cached
from chess_coach.lichess.oauth import LichessOAuth, OAuthToken
from chess_coach.lichess.study_sync import StudySync, Study
from chess_coach.lichess.game_sync import GameSync, GameSummary

__all__ = [
    "LichessExplorer",
    "ExplorerResponse",
    "MoveStats",
    "ExplorerSource",
    "LichessPuzzles",
    "Puzzle",
    "PuzzleTheme",
    "LichessCache",
    "cached",
    "LichessOAuth",
    "OAuthToken",
    "StudySync",
    "Study",
    "GameSync",
    "GameSummary",
]
