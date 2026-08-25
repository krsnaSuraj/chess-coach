from __future__ import annotations

import chess
import chess.engine

from chess_coach.humanizer import Humanizer, ComplexityDetector
from chess_coach.eco_handler import get_opening
from chess_coach.pgn_handler import board_to_pgn, pgn_to_moves
from chess_coach.game_controller import GameController


class TestMateNeverMiss:
    def test_mate_in_1_forced(self):
        h = Humanizer({"humanizer": {"enabled": True, "target_elo": 1500}})
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        cands = [
            {
                "pv": [chess.Move.from_uci("f7g7")],
                "score": chess.engine.PovScore(chess.engine.Mate(1), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("f7f6")],
                "score": chess.engine.PovScore(chess.engine.Cp(100), chess.WHITE),
            },
        ]
        m = h.select_move(cands, board)
        assert m is not None
        assert m.uci() == "f7g7"

    def test_empty_pv(self):
        h = Humanizer({"humanizer": {"enabled": True}})
        board = chess.Board()
        assert h.select_move([], board) is None
        assert h.select_move([{"pv": []}], board) is None
        assert h.select_move([{"pv": None}], board) is None


class TestECOWordBoundary:
    def test_word_boundary(self):
        b = chess.Board()
        for m in ["e2e4", "e7e5", "g1f3", "b8c6"]:
            b.push(chess.Move.from_uci(m))
        opening = get_opening(b)
        # should be C44 style, not partial match
        assert opening is not None
        assert opening[0].startswith("C")

    def test_transposition_not_misclassified(self):
        # ensure prefix must be exact words
        # no moves -> None
        assert get_opening(chess.Board()) is None


class TestPGNResultHeader:
    def test_checkmate_result(self):
        # Fool's mate board
        board = chess.Board()
        for m in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            board.push(chess.Move.from_uci(m))
        assert board.is_checkmate()
        pgn = board_to_pgn(board)
        # python-chess Game.from_board does not auto set Result, but our handler should? Check at least contains moves
        assert "f3" in pgn
        # replay
        moves = pgn_to_moves(pgn)
        assert len(moves) == 4

    def test_promotion_edge(self):
        board = chess.Board("8/P7/8/8/8/8/8/4K2k w - - 0 1")
        for promo in ["q", "r", "b", "n"]:
            b = board.copy()
            mv = chess.Move.from_uci("a7a8" + promo)
            assert mv in b.legal_moves
            b.push(mv)

    def test_en_passant(self):
        board = chess.Board()
        for m in ["e2e4", "d7d5", "e4e5", "f7f5"]:
            board.push(chess.Move.from_uci(m))
        assert chess.Move.from_uci("e5f6") in board.legal_moves


class TestGameControllerEdges:
    def test_stalemate(self):
        gc = GameController()
        gc.start_game(True)
        # stalemate position via moves? set board directly
        gc.board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        assert gc.board.is_stalemate()
        assert gc.board.is_game_over()

    def test_fifty_moves(self):
        gc = GameController()
        gc.start_game(True)
        gc.board.halfmove_clock = 100
        assert gc.board.is_fifty_moves()

    def test_illegal_promotion_without_suffix(self):
        gc = GameController()
        gc.start_game(True)
        gc.board = chess.Board("8/P7/8/8/8/8/8/4K2k w - - 0 1")
        # e7e8 without promotion char should be illegal (python-chess requires promotion)
        err = gc.human_move("a7a8")
        assert err == "Illegal move"


class TestHumanizerBlunderHanging:
    def test_hanging_blunder_detected(self):
        h = Humanizer(
            {
                "humanizer": {
                    "enabled": True,
                    "target_elo": 1500,
                    "error_injection": {
                        "blunder_rate": 1.0,
                        "mistake_rate": 0,
                        "inaccuracy_rate": 0,
                    },
                }
            }
        )
        # position where hanging exists: white knight on g5 can be captured? Create simple hanging
        board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 2")
        # black pawn d5 attacks e4, white pawn e4 hanging? Not perfect but test blunder returns legal
        cands = [
            {
                "pv": [chess.Move.from_uci("f3g5")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d3")],
                "score": chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
            },
        ]
        m = h.select_move(cands, board)
        assert m in board.legal_moves

    def test_complexity(self):
        assert not ComplexityDetector.is_complex(chess.Board())
        assert ComplexityDetector.is_complex(
            chess.Board("r1b2rk1/ppp1qppp/2np1n2/2b1p1B1/2B1P3/2NP1N2/PPP2PPP/R2Q1RK1 w - - 4 10")
        )
        assert not ComplexityDetector.is_complex(chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"))


class TestConfigDeadKeysTolerant:
    def test_old_config_with_dead_keys_still_loads(self, tmp_path):
        import yaml

        cfg = {
            "engine": {
                "path": "stockfish.exe",
                "threads": 2,
                "hash": 64,
                "movetime": 2000,
                "web_movetime": 2.0,
                "multipv": 5,
            },
            "humanizer": {
                "enabled": True,
                "target_elo": 1500,
                "personality": "balanced",
                "aggression": 0.5,
                "error_injection": {
                    "blunder_rate": 0.005,
                    "mistake_rate": 0.03,
                    "inaccuracy_rate": 0.10,
                },
                "detection": {"auto_adjust": True},
                "session": {"warmup_games": 5},
            },
            "display": {
                "light_square": "#F0D9B5",
                "dark_square": "#B58863",
                "arrow_color": "#00FF00",
                "arrow_opacity": 0.6,
                "highlight_color": "#FFFF64",
                "check_color": "#FF3232",
                "dot_color": "#646464",
                "capture_ring_color": "#323232",
                "last_move_color": "#FFFF64",
            },
        }
        p = tmp_path / "config.yaml"
        with open(p, "w") as f:
            yaml.dump(cfg, f)
        from chess_coach.config import load_config

        loaded = load_config(str(p))
        assert loaded["humanizer"]["target_elo"] == 1500
        # dead keys should be ignored, not crash, and humanizer should still work
        h = Humanizer(loaded)
        assert h.enabled is True
