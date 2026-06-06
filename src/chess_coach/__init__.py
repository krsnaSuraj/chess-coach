from chess_coach.config import load_config, find_free_port, get_local_ip, ConfigError
from chess_coach.game_controller import GameController, GamePhase
from chess_coach.eco_data import ECO_DATABASE
from chess_coach.eco_handler import get_opening
from chess_coach.engine_handler import EngineHandler
from chess_coach.chess_board import ChessBoard
from chess_coach.promotion_dialog import PromotionDialog
from chess_coach.coach_dashboard import CoachDashboard
from chess_coach.main_window import MainWindow
from chess_coach.server import app, game_controller
from chess_coach.pgn_handler import board_to_pgn, pgn_to_moves, replay_moves
from chess_coach.sound_manager import SoundManager

from chess_coach.elo_calibrator import (
    BayesianELOEstimator,
    ELOBand,
    EngineProfile,
    ThinkProfile,
    ACPLTarget,
    get_band,
    get_analysis_params,
    get_think_profile,
    get_acpl_target,
    get_think_time,
    phase_for_move_number,
)
from chess_coach.personality import (
    PersonalityType,
    PersonalityProfile,
    AGGRESSIVE,
    POSITIONAL,
    TACTICAL,
    DEFENSIVE,
    BALANCED,
    PROFILES,
    get_profile,
    list_personalities,
    bias_move,
)
from chess_coach.maia_engine import (
    MaiaEngine,
    MaiaConfig,
    MaiaEngineError,
    find_lc0,
    find_maia_weights,
)
from chess_coach.caps import (
    MoveClassification,
    CAPSResult,
    CAPSSummary,
    CLASSIFICATION_COLORS,
    CLASSIFICATION_LABELS,
    classify,
    classify_from_engine_info,
    compute_acpl_by_phase,
    cp_to_win_pct_simple,
    expected_points_lost,
)
from chess_coach.motif_detector import (
    Motif,
    MOTIF_LABELS,
    MotifDetection,
    detect_all_motifs,
    detect_pins,
    detect_forks,
    detect_skewers,
    detect_discovered_attack,
    detect_back_rank_weakness,
    detect_zwischenzug,
)
from chess_coach.opponent_modeler import (
    OpponentStyle,
    OpponentModel,
    OpponentMoveRecord,
    STYLE_LABELS,
    model_opponent_from_moves,
)
from chess_coach.anti_cheat_risk import (
    RiskLevel,
    RiskSignals,
    RiskResult,
    RISK_LABELS,
    compute_risk,
    update_risk_from_history,
)
from chess_coach.humanizer import (
    HumanizerConfig,
    HumanizerDecision,
    select_move,
    persona_move_only,
)
from chess_coach.multi_engine_handler import (
    MultiEngineConfig,
    MultiEngineHandler,
    StockfishAnalysisThread,
    MaiaAnalysisThread,
)

__all__ = [
    # Core
    "load_config", "find_free_port", "get_local_ip", "ConfigError",
    "GameController", "GamePhase",
    "ECO_DATABASE", "get_opening",
    "EngineHandler", "ChessBoard", "PromotionDialog",
    "CoachDashboard", "MainWindow", "SoundManager",
    "app", "game_controller",
    "board_to_pgn", "pgn_to_moves", "replay_moves",
    # ELO calibrator
    "BayesianELOEstimator", "ELOBand", "EngineProfile", "ThinkProfile", "ACPLTarget",
    "get_band", "get_analysis_params", "get_think_profile", "get_acpl_target",
    "get_think_time", "phase_for_move_number",
    # Personality
    "PersonalityType", "PersonalityProfile", "AGGRESSIVE", "POSITIONAL",
    "TACTICAL", "DEFENSIVE", "BALANCED", "PROFILES", "get_profile",
    "list_personalities", "bias_move",
    # Maia
    "MaiaEngine", "MaiaConfig", "MaiaEngineError", "find_lc0", "find_maia_weights",
    # CAPS
    "MoveClassification", "CAPSResult", "CAPSSummary",
    "CLASSIFICATION_COLORS", "CLASSIFICATION_LABELS",
    "classify", "classify_from_engine_info", "compute_acpl_by_phase",
    "cp_to_win_pct_simple", "expected_points_lost",
    # Motif
    "Motif", "MOTIF_LABELS", "MotifDetection",
    "detect_all_motifs", "detect_pins", "detect_forks", "detect_skewers",
    "detect_discovered_attack", "detect_back_rank_weakness", "detect_zwischenzug",
    # Opponent
    "OpponentStyle", "OpponentModel", "OpponentMoveRecord", "STYLE_LABELS",
    "model_opponent_from_moves",
    # Risk
    "RiskLevel", "RiskSignals", "RiskResult", "RISK_LABELS",
    "compute_risk", "update_risk_from_history",
    # Humanizer
    "HumanizerConfig", "HumanizerDecision", "select_move", "persona_move_only",
    # Multi-engine
    "MultiEngineConfig", "MultiEngineHandler",
    "StockfishAnalysisThread", "MaiaAnalysisThread",
]
