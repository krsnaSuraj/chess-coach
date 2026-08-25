from __future__ import annotations

import chess
import chess.engine
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from chess_coach import server
from chess_coach.game_controller import GameController


@pytest.fixture
def client():
    # reset global state
    server.game_controller = GameController()
    server._analysis_cache.clear()
    server._web_result_recorded = False
    # mock engine to avoid needing stockfish binary
    mock_engine = MagicMock()
    mock_score = MagicMock()
    mock_score.relative.score.return_value = 39
    mock_score.relative.mate.return_value = None
    mock_score.relative.score.return_value = 39
    # mock analyse return
    mock_engine.analyse.return_value = [
        {
            "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
            "score": chess.engine.PovScore(chess.engine.Cp(39), chess.WHITE),
            "depth": 18,
        },
        {
            "pv": [chess.Move.from_uci("d2d4")],
            "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            "depth": 18,
        },
    ]
    with patch.object(server, "get_engine", return_value=mock_engine):
        with TestClient(server.app) as c:
            yield c


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestStartGame:
    def test_start_white(self, client):
        r = client.post("/api/start_game", json={"human_is_white": True})
        j = r.json()
        assert j["ok"] is True
        assert j["mode"] == "coach"
        assert j["fen"] == chess.STARTING_FEN
        assert j["coach"] is not None
        # humanizer is random (79% engine), so best_move may be engine or random legal
        bm = j["coach"]["best_move"]
        assert isinstance(bm, str)
        assert len(bm) >= 4
        assert chess.Move.from_uci(bm) in chess.Board().legal_moves

    def test_start_black(self, client):
        r = client.post("/api/start_game", json={"human_is_white": False})
        j = r.json()
        assert j["ok"] is True
        # black to move? Actually start position white to move, human is black -> opponent turn -> coach null
        assert j["coach"] is None
        assert "rnbqkbnr" in j["fen"]


class TestHumanMove:
    def test_valid_move(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r = client.post("/api/human_move", json={"move_uci": "e2e4"})
        assert r.json()["ok"] is True
        assert "4P3" in r.json()["fen"]

    def test_illegal_move(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r = client.post("/api/human_move", json={"move_uci": "e2e5"})
        j = r.json()
        assert j["ok"] is False
        assert "Illegal" in j["error"]

    def test_invalid_format(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r = client.post("/api/human_move", json={"move_uci": "bad"})
        assert r.json()["ok"] is False

    def test_promotion_fix(self, client):
        # promotion via promotion field should work (e7e8q)
        client.post("/api/start_game", json={"human_is_white": True})
        # set up board with pawn on 7th? use direct game_controller manipulation
        # Instead test that promotion param doesn't crash via rstrip fix
        # Send promotion with base move a7a8 -> should try to be illegal but not crash
        r = client.post("/api/human_move", json={"move_uci": "a7a8", "promotion": "q"})
        # should be illegal (no pawn there) but not 500
        assert r.status_code == 200


class TestUndoRedo:
    def test_undo_redo_cycle(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        r = client.post("/api/undo", json={})
        assert r.json()["ok"] is True
        assert r.json()["fen"] == chess.STARTING_FEN
        r2 = client.post("/api/redo", json={})
        assert r2.json()["ok"] is True
        assert "4P3" in r2.json()["fen"]

    def test_undo_no_moves(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r = client.post("/api/undo", json={})
        assert r.json()["ok"] is False

    def test_undo_no_game(self):
        # fresh controller awaiting_color
        server.game_controller = GameController()
        with patch.object(server, "get_engine", return_value=MagicMock()):
            with TestClient(server.app) as c:
                r = c.post("/api/undo", json={})
                assert r.json()["ok"] is False


class TestGameStateCache:
    def test_cache_hit(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r1 = client.get("/api/game_state")
        r2 = client.get("/api/game_state")
        # second call should be cached, same best_move
        assert r1.json()["coach"]["best_move"] == r2.json()["coach"]["best_move"]

    def test_game_over_no_coach(self, client):
        # fool's mate
        c = client
        c.post("/api/start_game", json={"human_is_white": True})
        for m in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            c.post("/api/human_move", json={"move_uci": m})
        r = c.get("/api/game_state")
        assert r.json()["mode"] == "idle"
        # coach should be None when game over
        assert r.json()["coach"] is None
