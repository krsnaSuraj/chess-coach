"""Tests for the new AI coach server endpoints (Phase D)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from chess_coach.server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestPuzzleEndpoints:
    def test_get_puzzles(self, client):
        r = client.get("/api/puzzles")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 50
        assert "puzzles" in data
        assert all("id" in p for p in data["puzzles"])

    def test_filter_by_theme(self, client):
        r = client.get("/api/puzzles", params={"theme": "fork"})
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1
        assert all(p["theme"] == "fork" for p in data["puzzles"])

    def test_filter_by_difficulty(self, client):
        r = client.get("/api/puzzles", params={"difficulty": 1})
        assert r.status_code == 200
        data = r.json()
        assert all(p["difficulty"] == 1 for p in data["puzzles"])

    def test_get_puzzle_by_id(self, client):
        r = client.get("/api/puzzles/p001")
        assert r.status_code == 200
        assert r.json()["id"] == "p001"

    def test_get_puzzle_missing(self, client):
        r = client.get("/api/puzzles/nonexistent")
        assert r.status_code == 200
        assert r.json() == {"error": "not found"}

    def test_random_puzzle(self, client):
        r = client.get("/api/puzzles/random")
        assert r.status_code == 200
        assert "id" in r.json()

    def test_random_puzzle_with_theme(self, client):
        r = client.get("/api/puzzles/random", params={"theme": "fork"})
        assert r.status_code == 200
        assert r.json()["theme"] == "fork"

    def test_random_puzzle_with_seed(self, client):
        r1 = client.get("/api/puzzles/random", params={"seed": 5})
        r2 = client.get("/api/puzzles/random", params={"seed": 5})
        assert r1.json()["id"] == r2.json()["id"]

    def test_random_puzzle_no_match(self, client):
        r = client.get("/api/puzzles/random", params={"theme": "nonexistent_theme"})
        assert r.status_code == 200
        assert "error" in r.json()


class TestAccuracyEndpoint:
    def test_basic_accuracy(self, client):
        r = client.post("/api/coach/accuracy", json={
            "eval_history": [
                {"before": 50, "after": 50, "side": "w"},
                {"before": 0, "after": 0, "side": "b"},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["accuracy_pct"] >= 99
        assert "rating_estimate" in data
        assert "summary" in data

    def test_terrible_accuracy(self, client):
        r = client.post("/api/coach/accuracy", json={
            "eval_history": [
                {"before": 1000, "after": -1000, "side": "w"},
                {"before": 1000, "after": -1000, "side": "b"},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["accuracy_pct"] < 5
        assert data["summary"]["blunder"] == 2

    def test_empty_history(self, client):
        r = client.post("/api/coach/accuracy", json={"eval_history": []})
        assert r.status_code == 200
        assert r.json()["accuracy_pct"] == 100.0


class TestPlanEndpoint:
    def test_italian_opening_plan(self, client):
        r = client.post("/api/coach/plan", json={
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "pv": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"],
        })
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "steps" in data
        assert "themes" in data
        assert len(data["steps"]) == 5

    def test_short_pv(self, client):
        r = client.post("/api/coach/plan", json={
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "pv": ["e2e4"],
        })
        assert r.status_code == 200
        assert len(r.json()["steps"]) == 1


class TestBlunderEndpoint:
    def test_hanging_piece(self, client):
        r = client.post("/api/coach/blunder", json={
            "fen_before": "4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1",
            "move_uci": "a1a8",
            "eval_before_cp": 50,
            "eval_after_cp": -200,
        })
        assert r.status_code == 200
        data = r.json()
        assert "category" in data
        assert "explanation" in data
        assert "suggestion" in data

    def test_illegal_move_error(self, client):
        # Position with white rook on a1, black rook on a8. a1a8 is illegal (blocked).
        r = client.post("/api/coach/blunder", json={
            "fen_before": "4k3/r7/8/8/8/8/8/R3K2R w KQ - 0 1",
            "move_uci": "a1a8",  # rook can't jump over pieces
            "eval_before_cp": 50,
            "eval_after_cp": -200,
        })
        assert r.status_code == 200
        assert "error" in r.json()


class TestPatternsEndpoint:
    def test_get_patterns(self, client):
        r = client.get("/api/coach/patterns")
        assert r.status_code == 200
        data = r.json()
        assert "patterns" in data
        assert "fen" in data
        assert isinstance(data["patterns"], list)


class TestEngineMatchEndpoints:
    def test_get_personalities(self, client):
        r = client.get("/api/engine_match/personalities")
        assert r.status_code == 200
        data = r.json()
        assert "personalities" in data
        assert len(data["personalities"]) == 5
        ids = {p["id"] for p in data["personalities"]}
        assert ids == {"aggressive", "defensive", "positional", "tactical", "wild"}

    def test_start_match(self, client):
        r = client.post("/api/engine_match/start", json={
            "personality": "tactical",
            "target_elo": 1800,
            "color": "b",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["config"]["target_elo"] == 1800
        assert data["config"]["personality_name"] == "Tactical"

    def test_start_match_invalid_elo(self, client):
        r = client.post("/api/engine_match/start", json={
            "personality": "tactical",
            "target_elo": 5000,  # out of range
            "color": "b",
        })
        assert r.status_code == 200
        assert "error" in r.json()

    def test_start_match_invalid_personality(self, client):
        r = client.post("/api/engine_match/start", json={
            "personality": "unknown",
            "target_elo": 1500,
            "color": "b",
        })
        assert r.status_code == 200
        assert "error" in r.json()


class TestPGNExportEndpoint:
    def test_export_pgn(self, client):
        r = client.post("/api/export/pgn", json={
            "moves": [
                {"ply": 1, "san": "e4", "eval_cp": 30.0, "accuracy_pct": 95.0},
                {"ply": 2, "san": "e5", "eval_cp": -10.0, "accuracy_pct": 90.0},
                {"ply": 3, "san": "Nf3", "eval_cp": 50.0, "accuracy_pct": 100.0,
                 "classification": "brilliant"},
            ],
            "white": "Test",
            "black": "Engine",
            "result": "1-0",
        })
        assert r.status_code == 200
        data = r.json()
        assert "pgn" in data
        assert "size" in data
        pgn = data["pgn"]
        assert '[White "Test"]' in pgn
        assert '[Result "1-0"]' in pgn
        assert "1. e4 e5 2. Nf3" in pgn or "1. e4" in pgn

    def test_export_pgn_with_classification(self, client):
        r = client.post("/api/export/pgn", json={
            "moves": [
                {"ply": 1, "san": "Nxf7", "classification": "brilliant"},
                {"ply": 2, "san": "Kxf7", "classification": "blunder"},
            ],
            "white": "A", "black": "B",
        })
        assert r.status_code == 200
        pgn = r.json()["pgn"]
        assert "[BRILLIANT]" in pgn
        assert "[BLUNDER]" in pgn


class TestCriticalMomentsEndpoint:
    def test_get_critical_moments(self, client):
        r = client.get("/api/coach/critical_moments", params={"min_swing": 100})
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "moments" in data
        assert isinstance(data["moments"], list)
