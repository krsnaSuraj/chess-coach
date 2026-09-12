"""v0.1.1: game_over payload, server history, error-mode, mode validation."""

from __future__ import annotations

import chess
import chess.engine
import pytest

from chess_coach import server


def _force_board(fen: str, human_white: bool = True):
    with server.game_controller.lock:
        server.game_controller.board.set_fen(fen)
        server.game_controller.game_phase = server.GamePhase.PLAYING
        server.game_controller.human_side = chess.WHITE if human_white else chess.BLACK
        server.game_controller.redo_stack.clear()
        server.game_controller.cached_coach = None
        server.game_controller.cached_fen = None


class TestGameOverPayload:
    def test_live_position_no_game_over(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        d = client.get("/api/game_state").json()
        assert d["game_over"] is None
        assert d["mode"] == "coach"

    def test_fools_mate_checkmate(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
            r = client.post("/api/human_move", json={"move_uci": uci}).json()
            assert r["ok"] is True, uci
        d = client.get("/api/game_state").json()
        assert d["mode"] == "idle"
        assert d["game_over"]["over"] is True
        assert d["game_over"]["reason"] == "checkmate"
        assert d["game_over"]["winner"] == "Black"
        assert d["coach"] is None

    def test_stalemate_payload(self, client):
        _force_board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        d = client.get("/api/game_state").json()
        assert d["game_over"]["reason"] == "stalemate"
        assert d["mode"] == "idle"

    def test_insufficient_material_payload(self, client):
        _force_board("8/8/4k3/8/8/4K3/8/8 w - - 0 1")
        d = client.get("/api/game_state").json()
        assert d["game_over"]["reason"] == "insufficient_material"

    def test_fifty_moves_claimable_not_terminal(self, client):
        # FIDE 9.2/9.3: 50-move is claimable — game continues, coach stays live.
        _force_board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 100 50")
        d = client.get("/api/game_state").json()
        assert d["game_over"]["over"] is False
        assert d["game_over"]["reason"] == "fifty_moves"
        assert d["mode"] == "coach"
        # ...and moves are still accepted
        r = client.post("/api/human_move", json={"move_uci": "e2e4"}).json()
        assert r["ok"] is True

    def test_seventyfive_moves_terminal(self, client):
        _force_board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 150 75")
        d = client.get("/api/game_state").json()
        assert d["game_over"]["over"] is True
        assert d["game_over"]["reason"] == "seventyfive_moves"
        assert d["mode"] == "idle"


class TestServerHistory:
    def test_history_tracks_moves(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        d = client.post("/api/human_move", json={"move_uci": "e7e5"}).json()
        assert d["history"] == ["e2e4", "e7e5"]
        assert d["last_move"] == "e7e5"

    def test_undo_pops_history(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        d = client.post("/api/undo", json={}).json()
        assert d["history"] == []
        assert d["last_move"] is None

    def test_redo_restores_history(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        client.post("/api/undo", json={})
        d = client.post("/api/redo", json={}).json()
        assert d["history"] == ["e2e4"]

    def test_start_clears_history(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        d = client.post("/api/start_game", json={"human_is_white": False}).json()
        assert d["history"] == []


class TestErrorMode:
    def test_undo_empty_keeps_live_mode(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r = client.post("/api/undo", json={}).json()
        assert r["ok"] is False
        assert r["mode"] == "coach"
        assert r["error"] == "No moves to undo"

    def test_illegal_keeps_history(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        r = client.post("/api/human_move", json={"move_uci": "e2e5"}).json()
        assert r["ok"] is False
        assert r["history"] == ["e2e4"]


class TestLegalMap:
    def test_startpos_e2_targets(self, client):
        d = client.post("/api/start_game", json={"human_is_white": True}).json()
        assert set(d["legal"]["e2"]) == {"e3", "e4"}
        assert "e5" not in d["legal"]["e2"]
        assert sorted(d["legal"]["b1"]) == ["a3", "c3"]

    def test_pinned_piece_excluded(self, client):
        # Textbook pin: black bishop b4 pins white knight d2 to king e1.
        # The knight cannot move at all.
        _force_board("4r1k1/8/8/8/1b6/8/3N4/4K3 w - - 0 1")
        d = client.get("/api/game_state").json()
        assert "d2" not in d["legal"]

    def test_illegal_rejected_with_legal_echo(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r = client.post("/api/human_move", json={"move_uci": "e2e5"}).json()
        assert r["ok"] is False
        assert "e5" not in r["legal"].get("e2", [])

    def test_en_passant_in_map(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        for uci in ("e2e4", "a7a6", "e4e5", "f7f5"):
            assert client.post("/api/human_move", json={"move_uci": uci}).json()["ok"]
        d = client.get("/api/game_state").json()
        assert "f6" in d["legal"].get("e5", [])

    def test_castling_in_map(self, client):
        _force_board("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1")
        d = client.get("/api/game_state").json()
        assert "g1" in d["legal"].get("e1", [])
        assert "c1" in d["legal"].get("e1", [])


class TestModeValidation:
    def test_bad_mode_rejected(self, client):
        r = client.post("/api/start_game", json={"human_is_white": True, "mode": "evil"})
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_all_modes_accepted(self, client):
        for mode in ("human", "must_win", "safe"):
            r = client.post("/api/start_game", json={"human_is_white": True, "mode": mode}).json()
            assert r["ok"] is True
            assert r["coach"]["mode"] == mode

    def test_mode_case_insensitive(self, client):
        r = client.post("/api/start_game", json={"human_is_white": True, "mode": "MUST_WIN"}).json()
        assert r["ok"] is True
        assert r["coach"]["mode"] == "must_win"

    def test_midgame_mode_switch(self, client, mock_engine):
        client.post("/api/start_game", json={"human_is_white": True, "mode": "human"})
        before = client.get("/api/game_state").json()
        assert before["coach"]["mode"] == "human"
        n_calls = mock_engine.analyse.call_count
        switched = client.post("/api/mode", json={"mode": "must_win"}).json()
        assert switched["ok"] is True
        assert switched["coach"]["mode"] == "must_win"
        # Switch discards stale analysis: next state re-analyses fresh.
        assert mock_engine.analyse.call_count > n_calls

    def test_midgame_bad_mode_rejected(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        r = client.post("/api/mode", json={"mode": "evil"}).json()
        assert r["ok"] is False
        # previous mode intact
        d = client.get("/api/game_state").json()
        assert d["coach"]["mode"] == "human"

    def test_undo_triple_to_empty(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        client.post("/api/human_move", json={"move_uci": "e7e5"})
        assert client.post("/api/undo", json={}).json()["ok"] is True
        assert client.post("/api/undo", json={}).json()["ok"] is True
        r = client.post("/api/undo", json={}).json()
        assert r["ok"] is False
        assert r["history"] == []
        assert r["mode"] == "coach"

    def test_redo_after_new_move_rejected(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        client.post("/api/human_move", json={"move_uci": "e7e5"})
        client.post("/api/undo", json={})
        client.post("/api/human_move", json={"move_uci": "e7e6"})
        r = client.post("/api/redo", json={}).json()
        assert r["ok"] is False
        assert r["history"] == ["e2e4", "e7e6"]

    def test_mate_undo_redo_records_once(self, client):
        client.post("/api/start_game", json={"human_is_white": True})
        for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
            client.post("/api/human_move", json={"move_uci": uci})
        assert server._humanizer._session.games_played == 1
        client.post("/api/undo", json={})
        client.post("/api/redo", json={})
        client.get("/api/game_state")
        assert server._humanizer._session.games_played == 1


class TestPorts:
    def test_find_free_port_rejects_garbage(self):
        from chess_coach.config import find_free_port

        with pytest.raises(OSError):
            find_free_port(-1)
        with pytest.raises(OSError):
            find_free_port(65536)

    def test_find_free_port_zero_reports_real_port(self):
        from chess_coach.config import find_free_port

        sock, port = find_free_port(0)
        try:
            assert 1 <= port <= 65535
            assert sock.getsockname()[1] == port
        finally:
            sock.close()
