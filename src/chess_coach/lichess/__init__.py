"""Lichess API client library.

Covers 15+ endpoints: account, board (real-time), challenges, games, users,
teams, tournaments, broadcasts, studies, tablebases, puzzles, simuls, tv,
cloud evaluation, FIDE lookup, OAuth, messaging, relations.

See: https://lichess.org/api
Subdomains:
- lichess.org (main API)
- explorer.lichess.ovh (Opening Explorer)
- tablebase.lichess.ovh (Syzygy / Gaviota / Op1)
"""
from __future__ import annotations

from .explorer import LichessExplorer, ExplorerResponse, MoveStats, ExplorerSource
from .cache import LichessCache, default_cache_path
from .oauth import LichessOAuth, OAuthToken
from .puzzles import (
    LichessPuzzles,
    Puzzle,
    PuzzleTheme,
    curated_puzzles,
)
from .study_sync import StudySync, Study
from .game_sync import GameSync, GameSummary
from .account import LichessAccount, AccountProfile, Preferences, KidMode
from .users import LichessUsers, UserProfile, RatingHistory, UserStats
from .board import LichessBoard, BoardStreamEvent, BoardState
from .challenges import LichessChallenges, Challenge, ChallengeDeclineReason
from .tournaments import LichessTournaments, ArenaTournament, SwissTournament, TournamentState
from .broadcasts import LichessBroadcasts, Broadcast, BroadcastRound, BroadcastPlayer
from .teams import LichessTeams, Team, TeamMember
from .fide import LichessFide, FidePlayer
from .simuls import LichessSimuls, Simul, LichessTV, TVChannel
from .cloud_eval import LichessCloudEval, CloudEvalResult

__all__ = [
    "LichessExplorer",
    "ExplorerResponse",
    "MoveStats",
    "ExplorerSource",
    "LichessCache",
    "default_cache_path",
    "LichessOAuth",
    "OAuthToken",
    "LichessPuzzles",
    "Puzzle",
    "PuzzleTheme",
    "curated_puzzles",
    "StudySync",
    "Study",
    "GameSync",
    "GameSummary",
    "LichessAccount",
    "AccountProfile",
    "Preferences",
    "KidMode",
    "LichessUsers",
    "UserProfile",
    "RatingHistory",
    "UserStats",
    "LichessBoard",
    "BoardStreamEvent",
    "BoardState",
    "LichessChallenges",
    "Challenge",
    "ChallengeDeclineReason",
    "LichessTournaments",
    "ArenaTournament",
    "SwissTournament",
    "TournamentState",
    "LichessBroadcasts",
    "Broadcast",
    "BroadcastRound",
    "BroadcastPlayer",
    "LichessTeams",
    "Team",
    "TeamMember",
    "LichessFide",
    "FidePlayer",
    "LichessSimuls",
    "Simul",
    "LichessTV",
    "TVChannel",
    "LichessCloudEval",
    "CloudEvalResult",
]
