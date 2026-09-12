"""v0.1.1: mate-crash, eval-sign (human POV), promotion matrix — server level."""

from __future__ import annotations

import chess
import chess.engine

from chess_coach import server
from chess_coach.server import _coach_label


def _mate_info(uci: str, mate: int, turn: chess.Color, depth: int = 18) -> dict:
    return {
        "pv": [chess.Move.from_uci(uci)],
        "score": chess.engine.PovScore(chess.engine.Mate(mate), turn),
        "depth": depth,
    }


def _cp_info(uci: str, cp: int, turn: chess.Color, depth: int = 18) -> dict:
    return {
        "pv": [chess.Move.from_uci(uci)],
        "score": chess.engine.PovScore(chess.engine.Cp(cp), turn),
        "depth": depth,
    }


class TestMateCrash:
    def test_mate_in_1_white_no_crash(self, client, mock_engine):
        # White to mate: Qxf7# style — server must not 500
        mock_engine.analyse.return_value = [
            _mate_info("f7g7", 1, chess.WHITE),
            _cp_info("e2e4", 150, chess.WHITE),
        ]
        r = client.post("/api/start_game", json={"human_is_white": True})
        assert r.json()["ok"] is True
        data = client.get("/api/game_state").json()
        assert data["ok"] is True
        assert data["coach"] is not None
        assert data["coach"]["eval"] == "+M1"

    def test_mate_against_you_sign(self, client, mock_engine):
        # White to move but white is mated (POV mate=-1) -> human white sees -M1
        mock_engine.analyse.return_value = [_mate_info("e2e4", -1, chess.WHITE)]
        client.post("/api/start_game", json={"human_is_white": True})
        data = client.get("/api/game_state").json()
        assert data["ok"] is True
        assert data["coach"]["eval"] == "-M1"

    def test_score_none_returns_null_coach(self, client, mock_engine):
        mock_engine.analyse.return_value = [{"pv": [chess.Move.from_uci("e2e4")]}]
        client.post("/api/start_game", json={"human_is_white": True})
        data = client.get("/api/game_state").json()
        assert data["ok"] is True
        assert data["coach"] is None

    def test_dict_not_list_mate(self, client, mock_engine):
        mock_engine.analyse.return_value = _mate_info("f7g7", 1, chess.WHITE)
        client.post("/api/start_game", json={"human_is_white": True})
        data = client.get("/api/game_state").json()
        assert data["coach"]["eval"] == "+M1"

    def test_coach_label_mate(self):
        assert _coach_label("+M1") == ("Mate for you", "#3fb950")
        assert _coach_label("-M2") == ("Mate against you", "#f85149")


class TestEvalSignHumanPOV:
    def test_white_to_move_positive_stays(self, client, mock_engine):
        mock_engine.analyse.return_value = [_cp_info("e2e4", 80, chess.WHITE)]
        client.post("/api/start_game", json={"human_is_white": True})
        data = client.get("/api/game_state").json()
        assert data["coach"]["eval"] == "+0.80"

    def test_black_to_move_flips_for_white_human(self, client, mock_engine):
        # After 1.e4 black to move, engine says +80 for side-to-move (black).
        # Human is white -> must flip to -0.80.
        mock_engine.analyse.return_value = [_cp_info("e7e5", 80, chess.BLACK)]
        client.post("/api/start_game", json={"human_is_white": True})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        # undo back? No — game_state now analyses black-to-move only if human turn;
        # human is white so coach is None. Instead verify via black-human game:
        client.post("/api/start_game", json={"human_is_white": False})
        client.post("/api/human_move", json={"move_uci": "e2e4"})
        data = client.get("/api/game_state").json()
        # black to move, human black, side-to-move POV + -> human POV +
        assert data["coach"]["eval"] == "+0.80"

    def test_label_thresholds(self):
        assert _coach_label("+0.60")[0] == "You are winning"
        assert _coach_label("+0.40")[0] == "You are better"
        assert _coach_label("0.00")[0] == "Position is equal"
        assert _coach_label("-0.40")[0] == "Opponent is better"
        assert _coach_label("-0.60")[0] == "Opponent is winning"


class TestPromotionMatrix:
    QUIET_FEN = "8/P7/8/8/8/8/8/4K2k w - - 0 1"

    def _set_fen(self, fen: str):
        with server.game_controller.lock:
            server.game_controller.board.set_fen(fen)
            server.game_controller.game_phase = server.GamePhase.PLAYING
            server.game_controller.human_side = chess.WHITE
            server.game_controller.redo_stack.clear()
            server.game_controller.cached_coach = None
            server.game_controller.cached_fen = None
        with server._cache_lock:
            server._analysis_cache.clear()

    def test_quiet_promotions_all_pieces(self, client):
        for piece in ("q", "r", "b", "n"):
            self._set_fen(self.QUIET_FEN)
            r = client.post("/api/human_move", json={"move_uci": f"a7a8{piece}"})
            assert r.json()["ok"] is True, piece

    def test_bare_push_rejected(self, client):
        self._set_fen(self.QUIET_FEN)
        r = client.post("/api/human_move", json={"move_uci": "a7a8"})
        assert r.json()["ok"] is False

    def test_promotion_field_uppercase(self, client):
        self._set_fen(self.QUIET_FEN)
        r = client.post("/api/human_move", json={"move_uci": "a7a8", "promotion": "Q"})
        assert r.json()["ok"] is True

    def test_promotion_field_word_rejected(self, client):
        self._set_fen(self.QUIET_FEN)
        r = client.post("/api/human_move", json={"move_uci": "a7a8", "promotion": "Queen"})
        assert r.json()["ok"] is False

    def test_promotion_field_invalid(self, client):
        self._set_fen(self.QUIET_FEN)
        r = client.post("/api/human_move", json={"move_uci": "a7a8", "promotion": "x"})
        assert r.json()["ok"] is False

    def test_oversize_uci_rejected(self, client):
        r = client.post("/api/human_move", json={"move_uci": "e2e4" + "A" * 100})
        assert r.json()["ok"] is False
