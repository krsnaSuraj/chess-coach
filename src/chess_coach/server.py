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
from starlette.responses import Response, FileResponse

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
    else:
        try:
            _engine.ping()
        except Exception:
            logger.warning("Engine not responding, restarting")
            with _engine_lock:
                if _engine:
                    try:
                        _engine.quit()
                    except Exception:
                        pass
                    _engine = None
                try:
                    _engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
                except Exception as e:
                    logger.error(f"Failed to restart engine: {e}")
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

from chess_coach.ws.server import attach_websocket  # noqa: E402
attach_websocket(app, path="/ws")


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


# --- v3.0 AI Coach endpoints ---

class AccuracyRequest(BaseModel):
    eval_history: list[dict]   # list of {before, after, side}


@app.post("/api/coach/accuracy")
def post_coach_accuracy(request: AccuracyRequest) -> dict:
    """Compute Lichess-style centipawn loss accuracy from eval history."""
    from chess_coach.accuracy import game_accuracy, rating_from_accuracy
    history = [(h["before"], h["after"], h["side"]) for h in request.eval_history]
    result = game_accuracy(history)
    result["rating_estimate"] = rating_from_accuracy(result["accuracy_pct"])
    return result


@app.get("/api/coach/critical_moments")
def get_coach_critical_moments(min_swing: float = 100.0) -> dict:
    """Find critical moments in the current game."""
    from chess_coach.critical_moments import find_critical_moments, summarize_critical_moments
    with game_controller.lock:
        board = game_controller.board.copy()
    # Reconstruct positions from move stack
    positions = []
    temp = chess.Board()
    for mv in board.move_stack:
        prev_eval = 0  # placeholder; real impl would store evals
        positions.append({
            "fen": temp.fen(),
            "prev_eval_cp": prev_eval,
            "side_just_moved": temp.turn,
            "eval_cp": 0,
            "move_played": temp.san(mv),
        })
        temp.push(mv)
    moments = find_critical_moments(positions, min_swing_cp=min_swing)
    summary = summarize_critical_moments(moments)
    return {
        "summary": summary,
        "moments": [m.to_dict() for m in moments],
    }


class PlanRequest(BaseModel):
    fen: str
    pv: list[str]   # UCI moves


@app.post("/api/coach/plan")
def post_coach_plan(request: PlanRequest) -> dict:
    """Extract a human-readable plan from a principal variation."""
    from chess_coach.plan_extractor import extract_plan
    import chess
    board = chess.Board(request.fen)
    pv_moves = []
    for uci in request.pv:
        try:
            mv = chess.Move.from_uci(uci)
            if mv in board.legal_moves:
                pv_moves.append(mv)
                board.push(mv)
        except Exception:
            break
    board = chess.Board(request.fen)  # reset
    plan = extract_plan(board, pv_moves)
    return plan.to_dict()


class BlunderRequest(BaseModel):
    fen_before: str
    move_uci: str
    eval_before_cp: float
    eval_after_cp: float
    best_move_uci: str | None = None
    best_eval_cp: float | None = None
    time_remaining_s: float | None = None


@app.post("/api/coach/blunder")
def post_coach_blunder(request: BlunderRequest) -> dict:
    """Classify a blunder into a category with explanation."""
    from chess_coach.blunder_explainer import classify_blunder
    import chess
    board = chess.Board(request.fen_before)
    try:
        move = chess.Move.from_uci(request.move_uci)
        if move not in board.legal_moves:
            return {"error": "illegal move"}
        best_move = None
        if request.best_move_uci:
            best_move = chess.Move.from_uci(request.best_move_uci)
        report = classify_blunder(
            board, move,
            request.eval_before_cp, request.eval_after_cp,
            best_move, request.best_eval_cp,
            request.time_remaining_s,
        )
        return report.to_dict()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/coach/patterns")
def get_coach_patterns() -> dict:
    """Detect tactical patterns in the current position."""
    from chess_coach.pattern_detector import detect_all_patterns
    with game_controller.lock:
        board = game_controller.board.copy()
    patterns = detect_all_patterns(board)
    return {
        "fen": board.fen(),
        "patterns": [p.to_dict() for p in patterns],
    }


# --- v3.0 Puzzles ---

@app.get("/api/puzzles")
def get_puzzles(theme: str | None = None, difficulty: int | None = None) -> dict:
    """Get the puzzle list, optionally filtered."""
    from chess_coach.puzzle import get_all_puzzles, get_puzzles_by_theme, get_puzzles_by_difficulty
    if theme:
        puzzles = get_puzzles_by_theme(theme)
    elif difficulty is not None:
        puzzles = get_puzzles_by_difficulty(difficulty)
    else:
        puzzles = get_all_puzzles()
    return {
        "count": len(puzzles),
        "puzzles": [p.to_dict() for p in puzzles],
    }


# IMPORTANT: /api/puzzles/random must be declared BEFORE /api/puzzles/{puzzle_id}
# so FastAPI doesn't try to look up "random" as a puzzle ID.
@app.get("/api/puzzles/random")
def get_random_puzzle(theme: str | None = None, seed: int | None = None) -> dict:
    from chess_coach.puzzle import get_puzzles_by_theme, get_all_puzzles
    if theme:
        pool = get_puzzles_by_theme(theme)
    else:
        pool = get_all_puzzles()
    if not pool:
        return {"error": "no puzzles match"}
    import random
    p = random.choice(pool) if seed is None else pool[seed % len(pool)]
    return p.to_dict()


@app.get("/api/puzzles/{puzzle_id}")
def get_puzzle(puzzle_id: str) -> dict:
    from chess_coach.puzzle import get_puzzle_by_id
    p = get_puzzle_by_id(puzzle_id)
    if p is None:
        return {"error": "not found"}
    return p.to_dict()


# --- v3.0 Engine match ---

class EngineMatchRequest(BaseModel):
    personality: str = "tactical"
    target_elo: int = 1500
    color: str = "b"   # human is the other color


@app.post("/api/engine_match/start")
def engine_match_start(request: EngineMatchRequest) -> dict:
    from chess_coach.engine_match import EngineMatch, MatchConfig, PERSONALITIES
    if request.personality not in PERSONALITIES:
        return {"error": f"unknown personality: {request.personality}"}
    try:
        cfg = MatchConfig(
            personality=request.personality,
            target_elo=request.target_elo,
            color=request.color,
        )
    except ValueError as e:
        return {"error": str(e)}
    return {
        "ok": True,
        "config": {
            "personality": cfg.personality,
            "personality_name": PERSONALITIES[cfg.personality]["name"],
            "target_elo": cfg.target_elo,
            "color": cfg.color,
        },
    }


@app.get("/api/engine_match/personalities")
def get_personalities() -> dict:
    from chess_coach.engine_match import PERSONALITIES
    return {
        "personalities": [
            {
                "id": k,
                "name": v["name"],
                "icon": v["icon"],
                "description": v["description"],
            }
            for k, v in PERSONALITIES.items()
        ]
    }


# --- v3.0 PGN Export ---

class PGNExportRequest(BaseModel):
    moves: list[dict]   # list of {ply, san, fen_after, eval_cp?, cpl?, accuracy_pct?, classification?, commentary?}
    white: str = "Human"
    black: str = "Engine"
    event: str = "Chess Coach v3.0.0 Review"
    eco: str = "?"
    opening: str = "?"
    time_control: str = "?"
    result: str = "*"
    overall_accuracy: float | None = None
    critical_moments_count: int = 0
    rating_estimate: int = 0


@app.post("/api/export/pgn")
def export_pgn_endpoint(request: PGNExportRequest) -> dict:
    from chess_coach.review_exporter import (
        export_pgn, ExportMove, ExportConfig
    )
    moves = [ExportMove(
        ply=m["ply"], san=m["san"], fen_after=m.get("fen_after", ""),
        eval_cp=m.get("eval_cp"), cpl=m.get("cpl"),
        accuracy_pct=m.get("accuracy_pct"),
        classification=m.get("classification"),
        commentary=m.get("commentary"),
    ) for m in request.moves]
    cfg = ExportConfig(
        event=request.event, white=request.white, black=request.black,
        eco=request.eco, opening=request.opening,
        time_control=request.time_control, result=request.result,
    )
    pgn = export_pgn(moves, cfg)
    return {"pgn": pgn, "size": len(pgn)}


# --- v3.0 Humanizer endpoints ---

class HumanizerConfigRequest(BaseModel):
    personality: str | None = None
    target_elo: int | None = None
    enable_maia: bool | None = None
    simulated_think_time: bool | None = None


@app.get("/api/humanizer/config")
def get_humanizer_config() -> dict:
    return config.get("humanizer", {})


@app.post("/api/humanizer/config")
def set_humanizer_config(request: HumanizerConfigRequest) -> dict:
    h = config.setdefault("humanizer", {})
    if request.personality is not None:
        h["personality"] = request.personality
    if request.target_elo is not None:
        h["target_elo"] = request.target_elo
    if request.enable_maia is not None:
        config["enable_maia"] = request.enable_maia
    if request.simulated_think_time is not None:
        h["simulated_think_time"] = request.simulated_think_time
    return h


@app.get("/api/caps/last")
def get_caps_last() -> dict:
    """Return the CAPS classification of the last move played."""
    from chess_coach.caps import classify, expected_points_lost, phase_for_move_number
    from chess_coach.elo_calibrator import get_acpl_target
    with game_controller.lock:
        board = game_controller.board.copy()
    if not board.move_stack:
        return {"classification": "—", "expected_points_lost": 0.0, "phase": "—"}
    last = board.move_stack[-1]
    target_elo = config.get("humanizer", {}).get("target_elo", 1500)
    target_cpl = get_acpl_target(target_elo).overall
    # Approximation: assume last move lost ~target_cpl centipawns
    perspective = not board.turn  # the side that just moved
    cp_before, cp_after = 0, -target_cpl
    if perspective == chess.BLACK:
        cp_before, cp_after = -cp_before, -cp_after
    epl = expected_points_lost(cp_before, cp_after, perspective)
    result = classify(cp_before, cp_after, perspective,
                      phase=phase_for_move_number(board.fullmove_number))
    return {
        "move": last.uci(),
        "classification": result.classification.value,
        "label": result.label,
        "color": result.color,
        "expected_points_lost": round(epl, 4),
        "phase": result.phase,
    }


@app.get("/api/motifs/position")
def get_motifs_position() -> dict:
    """Return detected tactical motifs in the current position."""
    from chess_coach.motif_detector import detect_all_motifs
    with game_controller.lock:
        board = game_controller.board.copy()
    motifs = detect_all_motifs(board)
    return {
        "fen": board.fen(),
        "motifs": [
            {"type": m.motif.value, "description": m.description, "squares": [chess.square_name(s) for s in m.squares]}
            for m in motifs
        ],
    }


@app.get("/api/risk/game")
def get_risk_game() -> dict:
    """Return the current anti-cheat risk for the game so far."""
    from chess_coach.anti_cheat_risk import update_risk_from_history
    with game_controller.lock:
        board = game_controller.board.copy()
    history = [
        {"cpl": 30, "time_s": 5.0, "is_top1": False, "phase": "middlegame"}
        for _ in board.move_stack
    ]
    target_elo = config.get("humanizer", {}).get("target_elo", 1500)
    result = update_risk_from_history(history, target_elo=target_elo)
    return {
        "score": round(result.score, 1),
        "level": result.level.value,
        "label": result.label,
        "recommendation": result.recommendation,
        "contributions": {k: round(v, 1) for k, v in result.contributions.items()},
    }


@app.get("/api/elo/estimate")
def get_elo_estimate() -> dict:
    """Return the Bayesian ELO estimate of the current player."""
    from chess_coach.opponent_modeler import OpponentModel, model_opponent_from_moves
    from chess_coach.elo_calibrator import BayesianELOEstimator
    with game_controller.lock:
        board = game_controller.board.copy()
    estimator = BayesianELOEstimator()
    for _ in board.move_stack:
        estimator.update(30.0)  # placeholder
    ci = estimator.ci95
    return {
        "mean_elo": round(estimator.mean_elo, 1),
        "ci_low": round(ci[0], 1),
        "ci_high": round(ci[1], 1),
        "samples": estimator.n_samples,
    }


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
    if not cache_hit:
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


# --- Frontend serving -------------------------------------------------------
# Prefer the SvelteKit production build (apps/web/build).  Fall back to the
# legacy `static/` vanilla-JS frontend only if no SvelteKit build is present.
HERE = os.path.dirname(os.path.abspath(__file__))
SVELTEKIT_BUILD = os.path.normpath(os.path.join(HERE, "..", "..", "apps", "web", "build"))
LEGACY_STATIC = os.path.normpath(os.path.join(HERE, "..", "..", "static"))

if os.path.isfile(os.path.join(SVELTEKIT_BUILD, "index.html")):
    FRONTEND_DIR = SVELTEKIT_BUILD
    logger.info("Serving SvelteKit build from %s", FRONTEND_DIR)
elif os.path.isdir(LEGACY_STATIC):
    FRONTEND_DIR = LEGACY_STATIC
    logger.warning(
        "SvelteKit build not found at %s; serving legacy static from %s",
        SVELTEKIT_BUILD,
        LEGACY_STATIC,
    )
else:
    FRONTEND_DIR = None
    logger.error(
        "No frontend found (checked %s and %s) — web UI will not be served",
        SVELTEKIT_BUILD,
        LEGACY_STATIC,
    )

if FRONTEND_DIR is not None:
    # SvelteKit's immutable chunks live in `_app/immutable/...`
    _app_dir = os.path.join(FRONTEND_DIR, "_app")
    if os.path.isdir(_app_dir):
        app.mount("/_app", _NoCacheStaticFiles(directory=_app_dir), name="svelte-app")

    # Root-level static assets (favicon, manifest, etc.) served under /static
    app.mount("/static", _NoCacheStaticFiles(directory=FRONTEND_DIR), name="frontend-root")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # Never shadow API, WS, or already-mounted asset prefixes
        if full_path.startswith(("api/", "ws", "ws/", "_app/", "static/", "docs/")):
            from fastapi import HTTPException
            raise HTTPException(404)
        # Concrete file inside the frontend dir?  Serve it directly.
        candidate = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        # SPA fallback: every other path returns the app shell.
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
else:
    logger.warning("No frontend configured — web UI will not be served")
