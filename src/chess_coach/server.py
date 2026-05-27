from __future__ import annotations

import os
import logging
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import chess
import chess.engine
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from chess_coach.game_controller import GameController, GamePhase
from chess_coach.config import load_config

logger = logging.getLogger(__name__)

try:
    _cfg = load_config()
except Exception:
    _cfg = {}
    logger.warning("Failed to load config.yaml — using defaults")

config = _cfg
ENGINE_PATH = config.get("engine", {}).get("path", "stockfish.exe")
WEB_MOVETIME = config.get("engine", {}).get("web_movetime", 0.15)

game_controller = GameController()

_engine: chess.engine.SimpleEngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> chess.engine.SimpleEngine | None:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                try:
                    _engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
                except Exception as e:
                    logger.error(f"Failed to start engine: {e}")
                    return None
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    get_engine()
    yield
    global _engine
    if _engine:
        try:
            _engine.quit()
        except Exception:
            pass
        _engine = None


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class UnifiedResponse(BaseModel):
    ok: bool
    mode: str
    fen: str
    move: str | None = None
    coach: dict | None = None
    error: str | None = None


class StartGameRequest(BaseModel):
    human_is_white: bool


class HumanMoveRequest(BaseModel):
    move_uci: str
    promotion: str | None = None


@app.get("/api/health")
def health_check() -> dict:
    eng = get_engine()
    return {"status": "ok", "engine_running": eng is not None}


@app.post("/api/start_game")
def start_game(request: StartGameRequest) -> UnifiedResponse:
    try:
        game_controller.start_game(request.human_is_white)
        return _build_response()
    except Exception as e:
        return _error_response(str(e))


@app.get("/api/game_state")
def get_game_state() -> UnifiedResponse:
    try:
        return _build_response()
    except Exception as e:
        return _error_response(str(e))


@app.post("/api/undo")
def undo_move() -> UnifiedResponse:
    try:
        err = game_controller.undo()
        if err:
            return _error_response(err)
        return _build_response()
    except Exception as e:
        return _error_response(str(e))


@app.post("/api/redo")
def redo_move() -> UnifiedResponse:
    try:
        err = game_controller.redo()
        if err:
            return _error_response(err)
        return _build_response()
    except Exception as e:
        return _error_response(str(e))


@app.post("/api/human_move")
def human_move(request: HumanMoveRequest) -> UnifiedResponse:
    try:
        uci = request.move_uci
        if request.promotion:
            uci = uci.rstrip(" qrbn") + request.promotion.lower()
        err = game_controller.human_move(uci)
        if err:
            return _error_response(err)
        return _build_response()
    except Exception as e:
        return _error_response(str(e))


def _build_response() -> UnifiedResponse:
    with game_controller.lock:
        mode = "idle"
        if game_controller.game_phase == GamePhase.PLAYING:
            mode = "coach"
        fen = game_controller.board.fen()
        is_human_turn = (
            mode == "coach"
            and game_controller.board.turn == game_controller.human_side
        )
        cache_hit = game_controller.cached_fen == fen
        cached = game_controller.cached_coach if cache_hit else None

    coach_data = cached
    if is_human_turn and not cache_hit:
        coach_data = _run_coach_analysis_safe()
        with game_controller.lock:
            game_controller.cached_coach = coach_data
            game_controller.cached_fen = fen

    return UnifiedResponse(ok=True, mode=mode, fen=fen, move=None, coach=coach_data, error=None)


def _error_response(msg: str) -> UnifiedResponse:
    with game_controller.lock:
        fen = game_controller.board.fen()
    return UnifiedResponse(ok=False, mode="idle", fen=fen, error=msg)


def _run_coach_analysis_safe() -> dict | None:
    eng = get_engine()
    if eng is None:
        return None
    try:
        with game_controller.lock:
            board_snapshot = game_controller.board.copy()
        info = eng.analyse(board_snapshot, chess.engine.Limit(time=WEB_MOVETIME))
        score = info.get("score")
        if score is None:
            return None

        cp = score.relative.score(mate_score=10000)
        mate = score.relative.mate()
        depth = info.get("depth", 0)

        if mate is not None:
            eval_text = f"M{abs(mate)}"
            eval_text = f"+{eval_text}" if mate > 0 else f"-{eval_text}"
        else:
            eval_text = f"{cp / 100:.2f}"
            if cp > 0:
                eval_text = "+" + eval_text

        pv = info.get("pv", [])
        best_move = pv[0].uci() if pv else None

        return {
            "best_move": best_move,
            "eval": eval_text,
            "pv": " ".join(m.uci() for m in pv),
            "thinking": [f"Depth {depth}: {eval_text}"],
        }
    except Exception as e:
        logger.error(f"Coach error: {e}")
        return None


class _NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args: object, **kwargs: object) -> Response:
        resp = super().file_response(*args, **kwargs)
        resp.headers.setdefault("Cache-Control", "no-cache, no-store, must-revalidate")
        return resp


HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "..", "..", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", _NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")
else:
    logger.warning("Static directory not found at %s — web UI will not be served", STATIC_DIR)
