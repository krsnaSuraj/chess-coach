"""v0.1.1: turn ownership, cache invalidation, modes, no-sound regression."""

from __future__ import annotations

import chess
import chess.engine

from chess_coach import server
from chess_coach.humanizer import Humanizer


class TestTurnOwnershipServer:
    def test_opponent_move_accepted_via_copy_path(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        assert client.post("/api/human_move", json={"move_uci": "e2e4"}).json()["ok"] is True
        # e7e5 is opponent (black) move — server routes to copy path, still ok
        r = client.post("/api/human_move", json={"move_uci": "e7e5"}).json()
        assert r["ok"] is True
        assert len(server.game_controller.board.move_stack) == 2

    def test_illegal_still_rejected(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r = client.post("/api/human_move", json={"move_uci": "e2e5"}).json()
        assert r["ok"] is False

    def test_undo_clears_server_cache(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.get("/api/game_state")
        with server._cache_lock:
            assert len(server._analysis_cache) >= 1
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        after_move_fen = server.game_controller.board.fen()
        client.post("/api/undo", json={})
        # Undo returns to startpos and re-analyses it; the post-move
        # position must NOT linger in cache (stale-write guard).
        with server._cache_lock:
            assert after_move_fen not in server._analysis_cache
        assert server._web_result_recorded is False


class TestModes:
    def test_must_win_always_best(self):
        h = Humanizer({"humanizer": {"target_elo": 1500, "mode": "must_win"}})
        board = chess.Board()
        cands = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": chess.engine.PovScore(chess.engine.Cp(50), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": chess.engine.PovScore(chess.engine.Cp(40), chess.WHITE),
            },
        ]
        for _ in range(30):
            assert h.select_move(cands, board).uci() == "e2e4"

    def test_safe_never_blunders(self):
        cfg = {
            "humanizer": {
                "target_elo": 1500,
                "mode": "safe",
                "error_injection": {
                    "inaccuracy_rate": 0.0,
                    "mistake_rate": 0.0,
                    "blunder_rate": 1.0,
                },
            }
        }
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
        cands = [
            {
                "pv": [chess.Move.from_uci("f3g5")],
                "score": chess.engine.PovScore(chess.engine.Cp(30), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": chess.engine.PovScore(chess.engine.Cp(25), chess.WHITE),
            },
        ]
        # The blunder injector must NEVER fire in safe mode, even at rate 1.0.
        h = Humanizer(cfg)
        calls = []
        orig = h._human_blunder
        h._human_blunder = lambda *a, **k: (calls.append(1), orig(*a, **k))[1]
        for _ in range(200):
            assert h.select_move(cands, board) is not None
        assert calls == []
        # Same config in human mode DOES inject blunders (control group).
        h2 = Humanizer(
            {
                "humanizer": {
                    "target_elo": 1500,
                    "mode": "human",
                    "error_injection": {
                        "inaccuracy_rate": 0.0,
                        "mistake_rate": 0.0,
                        "blunder_rate": 1.0,
                    },
                }
            }
        )
        calls2 = []
        orig2 = h2._human_blunder
        h2._human_blunder = lambda *a, **k: (calls2.append(1), orig2(*a, **k))[1]
        for _ in range(200):
            h2.select_move(cands, board)
        assert len(calls2) == 200

    def test_start_game_accepts_mode(self, client):
        r = client.post("/api/start_game", json={"human_is_white": True, "mode": "must_win"}).json()
        assert r["ok"] is True
        assert r["coach"]["mode"] == "must_win"


class TestNoSound:
    def test_no_sound_manager_module(self):
        import importlib.util

        assert importlib.util.find_spec("chess_coach.sound_manager") is None

    def test_mainwindow_has_no_sound_attr(self):
        import inspect

        from chess_coach import main_window

        src = inspect.getsource(main_window)
        assert "sound_manager" not in src.lower()
        assert "QsoundEffect".lower() not in src.lower()
        assert "QtMultimedia".lower() not in src.lower()

    def test_no_wav_artifact(self):
        import os

        here = os.path.dirname(os.path.abspath(server.__file__))
        wav = os.path.join(here, "..", "..", "static", "sounds", "move.wav")
        assert not os.path.exists(os.path.normpath(wav))

    def test_no_legacy_frontend_libs(self):
        import os

        here = os.path.dirname(os.path.abspath(server.__file__))
        static = os.path.normpath(os.path.join(here, "..", "..", "static"))
        for rel in ("js/jquery.min.js", "js/chess.js", "js/chessboard.js"):
            assert not os.path.exists(os.path.join(static, rel)), rel
