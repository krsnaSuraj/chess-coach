__version__ = "0.1.1"
__description__ = "Real-time chess analysis sidekick with Stockfish 18"

from chess_coach.config import load_config, find_free_port, get_local_ip, ConfigError
from chess_coach.game_controller import GameController, GamePhase
from chess_coach.eco_data import ECO_DATABASE
from chess_coach.eco_handler import get_opening
from chess_coach.engine_handler import EngineHandler
from chess_coach.humanizer import Humanizer, ComplexityDetector
from chess_coach.chess_board import ChessBoard
from chess_coach.promotion_dialog import PromotionDialog
from chess_coach.coach_dashboard import CoachDashboard
from chess_coach.main_window import MainWindow
from chess_coach.server import app, game_controller
from chess_coach.pgn_handler import board_to_pgn, pgn_to_moves, replay_moves

__all__ = [
    "load_config",
    "find_free_port",
    "get_local_ip",
    "ConfigError",
    "GameController",
    "GamePhase",
    "ECO_DATABASE",
    "get_opening",
    "EngineHandler",
    "Humanizer",
    "ComplexityDetector",
    "ChessBoard",
    "PromotionDialog",
    "CoachDashboard",
    "MainWindow",
    "app",
    "game_controller",
    "board_to_pgn",
    "pgn_to_moves",
    "replay_moves",
]
