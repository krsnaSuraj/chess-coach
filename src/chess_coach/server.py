from __future__ import annotations

import logging
import os
import re
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import chess
import chess.engine
from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from chess_coach.game_controller import GameController, GamePhase
from chess_coach.config import load_config
from chess_coach.humanizer import Humanizer, ComplexityDetector, SessionMetrics, _accuracy_for_elo
from chess_coach.eco_handler import get_opening

logger = logging.getLogger(__name__)

try:
    _cfg = load_config()
except Exception:
    _cfg = {}
    logger.warning("Failed to load config.yaml — using defaults")

config = _cfg
ENGINE_PATH = config.get("engine", {}).get("path", "stockfish.exe")
WEB_MOVETIME = config.get("engine", {}).get("web_movetime", 0.15)
MULTIPV = config.get("engine", {}).get("multipv", 5)

game_controller = GameController()
_humanizer: Humanizer = Humanizer(config)
_web_result_recorded: bool = False
_web_result_fen: str | None = None
_analysis_cache: dict[str, dict] = {}
# RLock (not Lock): _reset_for_tests nests cache ops; self-deadlock proof.
_cache_lock = threading.RLock()
_CACHE_MAX = 200

_engine: chess.engine.SimpleEngine | None = None
_engine_lock = threading.Lock()
_analyse_lock = threading.Lock()
_move_history: list[str] = []


def _reset_for_tests() -> None:
    """Reset mutable server state between tests."""
    global _web_result_recorded, _web_result_fen, _move_history
    with game_controller.lock:
        _web_result_recorded = False
        _web_result_fen = None
        _move_history = []
        _humanizer.set_mode("human")
        _humanizer.new_game()
        _humanizer._session = SessionMetrics()
    with _cache_lock:
        _analysis_cache.clear()


def get_engine() -> chess.engine.SimpleEngine | None:
    global _engine
    with _engine_lock:
        if _engine is None:
            try:
                _engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
            except Exception as e:
                logger.error("Failed to start engine: %s", type(e).__name__)
                return None
            return _engine
        try:
            _engine.ping()
        except Exception:
            logger.warning("Engine not responding, restarting")
            try:
                _engine.quit()
            except Exception:
                pass
            _engine = None
            try:
                _engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
            except Exception as e:
                logger.error("Failed to restart engine: %s", type(e).__name__)
                return None
        return _engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    get_engine()
    yield
    global _engine
    with _engine_lock:
        with _analyse_lock:
            if _engine:
                try:
                    _engine.quit()
                except Exception:
                    pass
                _engine = None


app = FastAPI(lifespan=lifespan)
_LAN_HOST = r"(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8012",
        "http://127.0.0.1:8012",
    ],
    allow_origin_regex=rf"http://{_LAN_HOST}(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def _security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


class UnifiedResponse(BaseModel):
    ok: bool
    mode: str
    fen: str
    move: str | None = None
    coach: dict | None = None
    error: str | None = None
    game_over: dict | None = None
    history: list[str] = Field(default_factory=list)
    last_move: str | None = None
    legal: dict[str, list[str]] = Field(default_factory=dict)


class StartGameRequest(BaseModel):
    human_is_white: bool
    mode: str = "human"


class HumanMoveRequest(BaseModel):
    # Generous bounds only (DoS cap); all shape validation happens in code
    # so clients always get HTTP 200 + {"ok": false} instead of 422s.
    move_uci: str = Field(max_length=256)
    promotion: str | None = Field(default=None, max_length=16)


class ModeRequest(BaseModel):
    mode: str


_VALID_MODES = ("human", "must_win", "safe")


def _normalize_mode(mode: object) -> str | None:
    if not isinstance(mode, str):
        return None
    m = mode.strip().lower()
    return m if m in _VALID_MODES else None


@app.get("/api/health")
def health_check() -> dict:
    eng = get_engine()
    return {"status": "ok", "engine_running": eng is not None}


@app.post("/api/start_game")
def start_game(request: StartGameRequest) -> UnifiedResponse:
    try:
        global _web_result_recorded, _web_result_fen, _move_history
        norm = _normalize_mode(request.mode)
        if norm is None:
            return _error_response(f"Unknown mode {request.mode!r}")
        with game_controller.lock:
            game_controller.start_game(request.human_is_white)
            _humanizer.new_game()
            _humanizer.set_mode(norm)
            _web_result_recorded = False
            _web_result_fen = None
            _move_history = []
        with _cache_lock:
            _analysis_cache.clear()
        return _build_response()
    except Exception:
        logger.exception("start_game failed")
        return _error_response("Failed to start game")


@app.get("/api/game_state")
def get_game_state() -> UnifiedResponse:
    try:
        return _build_response()
    except Exception:
        logger.exception("game_state failed")
        return _error_response("Failed to load game state")


@app.post("/api/undo")
def undo_move() -> UnifiedResponse:
    try:
        global _web_result_recorded, _web_result_fen, _move_history
        # One lock for check-and-mutate (RLock: nested controller locks are safe).
        with game_controller.lock:
            err = game_controller.undo()
            if not err:
                if _move_history:
                    _move_history.pop()
                # NOTE: result flags are NOT reset here — undo/redo replays of
                # the same terminal position must not double-count the game.
        if err:
            return _error_response(err)
        with _cache_lock:
            _analysis_cache.clear()
        return _build_response()
    except Exception:
        logger.exception("undo failed")
        return _error_response("Undo failed")


@app.post("/api/redo")
def redo_move() -> UnifiedResponse:
    try:
        global _move_history
        with game_controller.lock:
            redo_uci = game_controller.redo_stack[-1].uci() if game_controller.redo_stack else None
            err = game_controller.redo()
            if not err and redo_uci:
                _move_history.append(redo_uci)
        if err:
            return _error_response(err)
        return _build_response()
    except Exception:
        logger.exception("redo failed")
        return _error_response("Redo failed")


@app.post("/api/mode")
def set_mode(request: ModeRequest) -> UnifiedResponse:
    """Switch coach mode mid-game (human | must_win | safe).

    Applies immediately: cached analysis from the previous mode is
    discarded so the next response uses the new mode.
    """
    try:
        norm = _normalize_mode(request.mode)
        if norm is None:
            return _error_response(f"Unknown mode {request.mode!r}")
        with game_controller.lock:
            _humanizer.set_mode(norm)
            game_controller.cached_coach = None
            game_controller.cached_fen = None
        with _cache_lock:
            _analysis_cache.clear()
        return _build_response()
    except Exception:
        logger.exception("set_mode failed")
        return _error_response("Failed to switch mode")


_UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbnQRBN]?$")


def _valid_uci(uci: str) -> bool:
    return bool(_UCI_RE.match(uci))


@app.post("/api/human_move")
def human_move(request: HumanMoveRequest) -> UnifiedResponse:
    try:
        global _move_history
        uci = request.move_uci.strip().lower()
        if request.promotion:
            promo = request.promotion.strip().lower()
            if promo not in ("q", "r", "b", "n"):
                return _error_response("Invalid promotion piece")
            if len(uci) != 4:
                return _error_response("Promotion needs a 4-char move plus piece")
            uci = uci + promo
        if not _valid_uci(uci):
            return _error_response("Invalid move format")
        with game_controller.lock:
            err = game_controller.human_move(uci)
            if err == "Not your turn — enter opponent move as copy":
                # Single entry point by design: the user copies whatever was
                # just played on the external board (own or opponent move).
                err = game_controller.copy_opponent_move(uci)
            if not err:
                _move_history.append(uci)
                # A genuinely new move re-arms terminal-result recording
                # (undo/redo replays of the same terminal do NOT double count).
                _web_result_recorded = False
                _web_result_fen = None
        if err:
            return _error_response(err)
        return _build_response()
    except Exception:
        logger.exception("human_move failed")
        return _error_response("Invalid move")


def _game_over_info() -> dict | None:
    """Must be called with game_controller.lock held. Returns None when live.

    Only AUTOMATIC terminations end the game (FIDE Laws 5.1/5.2/9.6):
    checkmate, stalemate, dead position, 75-move rule, fivefold repetition.
    50-move and threefold repetition are CLAIMABLE (9.2/9.3) — play continues
    and the client shows a "draw available" notice instead.
    """
    board = game_controller.board
    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        return {"over": True, "result": "checkmate", "winner": winner, "reason": "checkmate"}
    if board.is_stalemate():
        return {"over": True, "result": "draw", "winner": None, "reason": "stalemate"}
    if board.is_insufficient_material():
        return {"over": True, "result": "draw", "winner": None, "reason": "insufficient_material"}
    if board.is_seventyfive_moves():
        return {"over": True, "result": "draw", "winner": None, "reason": "seventyfive_moves"}
    if board.is_fivefold_repetition():
        return {"over": True, "result": "draw", "winner": None, "reason": "fivefold_repetition"}
    if board.is_fifty_moves() or board.can_claim_draw():
        return {
            "over": False,
            "result": "draw_claimable",
            "winner": None,
            "reason": "fifty_moves",
            "claimable": True,
        }
    return None


def _build_response(_retries: int = 3) -> UnifiedResponse:
    global _web_result_recorded, _web_result_fen
    while True:
        with game_controller.lock:
            game_over = _game_over_info()
            over = game_over is not None and game_over.get("over", False)
            mode = "idle"
            if game_controller.game_phase == GamePhase.PLAYING and not over:
                mode = "coach"
            if over:
                assert game_over is not None
                fen_now = game_controller.board.fen()
                # Record once per terminal position (undo/redo replays don't double count).
                if not _web_result_recorded or _web_result_fen != fen_now:
                    if game_over["reason"] == "checkmate":
                        won = game_controller.board.turn != game_controller.human_side
                        result = "win" if won else "loss"
                    else:
                        result = "draw"
                    _humanizer.record_result(result, _accuracy_for_elo(_humanizer.effective_elo))
                    _web_result_recorded = True
                    _web_result_fen = fen_now
            fen = game_controller.board.fen()
            is_human_turn = (
                mode == "coach" and game_controller.board.turn == game_controller.human_side
            )
            cache_hit = game_controller.cached_fen == fen
            cached = game_controller.cached_coach if cache_hit else None
            history = list(_move_history)
            last_move = history[-1] if history else None
            legal = _legal_targets_locked()

        coach_data = cached
        if is_human_turn and not cache_hit:
            with _cache_lock:
                coach_data = _analysis_cache.get(fen)
            if coach_data is None:
                coach_data = _run_coach_analysis_safe(fen)
            if coach_data is not None:
                # Re-check FEN: board may have moved during analysis.
                # Bounded retry loop (no unbounded recursion on move spam).
                with game_controller.lock:
                    if game_controller.board.fen() != fen:
                        if _retries <= 0:
                            coach_data = None
                            break
                        _retries -= 1
                        continue
                    game_controller.cached_coach = coach_data
                    game_controller.cached_fen = fen
                with _cache_lock:
                    _analysis_cache[fen] = coach_data
                    # LRU-ish: drop oldest instead of wiping everything
                    while len(_analysis_cache) > _CACHE_MAX:
                        _analysis_cache.pop(next(iter(_analysis_cache)))
                break
            break
        break

    return UnifiedResponse(
        ok=True,
        mode=mode,
        fen=fen,
        move=None,
        coach=coach_data,
        error=None,
        game_over=game_over,
        history=history,
        last_move=last_move,
        legal=legal,
    )


def _legal_targets_locked() -> dict[str, list[str]]:
    """Authoritative legal moves grouped by from-square. Caller holds lock."""
    out: dict[str, list[str]] = {}
    for m in game_controller.board.legal_moves:
        out.setdefault(chess.square_name(m.from_square), []).append(chess.square_name(m.to_square))
    return out


def _error_response(msg: str) -> UnifiedResponse:
    with game_controller.lock:
        fen = game_controller.board.fen()
        game_over = _game_over_info()
        over = game_over is not None and game_over.get("over", False)
        if game_controller.game_phase == GamePhase.PLAYING and not over:
            mode = "coach"
        else:
            mode = "idle"
        history = list(_move_history)
        last_move = history[-1] if history else None
        legal = _legal_targets_locked()
    return UnifiedResponse(
        ok=False,
        mode=mode,
        fen=fen,
        error=msg,
        game_over=game_over,
        history=history,
        last_move=last_move,
        legal=legal,
    )


def _coach_label(eval_text: str) -> tuple[str, str]:
    if "M" in eval_text:
        if eval_text.startswith("+M"):
            return "Mate for you", "#3fb950"
        return "Mate against you", "#f85149"
    try:
        n = float(eval_text)
    except ValueError:
        return "Position is equal", "#6e7681"
    if n > 0.5:
        return "You are winning", "#3fb950"
    if n > 0.3:
        return "You are better", "#3fb950"
    if n < -0.5:
        return "Opponent is winning", "#f85149"
    if n < -0.3:
        return "Opponent is better", "#f85149"
    return "Position is equal", "#6e7681"


def _run_coach_analysis_safe(fen: str) -> dict | None:
    eng = get_engine()
    if eng is None:
        return None
    try:
        with game_controller.lock:
            board_snapshot = game_controller.board.copy()
            human_side = game_controller.human_side
        # FEN changed while waiting for lock — caller re-checks anyway
        if board_snapshot.fen() != fen:
            return None
        # SimpleEngine is not thread-safe: serialize all analyse calls.
        with _analyse_lock:
            multi = eng.analyse(
                board_snapshot,
                chess.engine.Limit(time=WEB_MOVETIME),
                multipv=MULTIPV,
            )
        if isinstance(multi, dict):
            multi = [multi]
        if not multi:
            return None

        is_complex = ComplexityDetector.is_complex(board_snapshot)
        best = multi[0]
        score = best.get("score")
        if score is None:
            return None

        # --- mate-safe eval (score() returns None on mate) ---
        mate = score.relative.mate()
        if mate is not None:
            eval_score = 10.0  # winning — humanizer plays safe, less random
            mate_for_human = (mate > 0 and board_snapshot.turn == human_side) or (
                mate < 0 and board_snapshot.turn != human_side
            )
            eval_text = f"+M{abs(mate)}" if mate_for_human else f"-M{abs(mate)}"
        else:
            cp = score.relative.score(mate_score=10000)
            if cp is None:
                return None
            eval_score = abs(cp) / 100.0
            # Convert side-to-move POV -> human POV
            if human_side is not None and board_snapshot.turn != human_side:
                cp = -cp
            eval_text = f"{cp / 100:.2f}"
            if cp > 0:
                eval_text = "+" + eval_text

        human_move = _humanizer.select_move(
            multi, board_snapshot, is_complex=is_complex, eval_score=eval_score
        )

        depth = best.get("depth", 0)

        pv = best.get("pv", [])
        best_move = human_move.uci() if human_move else (pv[0].uci() if pv else None)

        opening_info = get_opening(board_snapshot)
        opening_name = f"[{opening_info[0]}] {opening_info[1]}" if opening_info else None
        label, eval_color = _coach_label(eval_text)

        return {
            "best_move": best_move,
            "eval": eval_text,
            "pv": " ".join(m.uci() for m in pv),
            "depth": depth,
            "opening": opening_name,
            "label": label,
            "eval_color": eval_color,
            "thinking": [f"Depth {depth}: {eval_text}"],
            "mode": _humanizer.mode,
        }
    except Exception:
        logger.exception("Coach analysis failed")
        return None


class _NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        resp = super().file_response(*args, **kwargs)
        resp.headers.setdefault("Cache-Control", "no-cache, no-store, must-revalidate")
        return resp


HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "..", "..", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", _NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")
else:
    logger.warning("Static directory not found at %s — web UI will not be served", STATIC_DIR)
