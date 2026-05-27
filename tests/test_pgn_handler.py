from __future__ import annotations

from pathlib import Path

import chess
import pytest

from chess_coach.pgn_handler import board_to_pgn, pgn_to_moves, replay_moves


class TestPgnToMoves:
    def test_simple_pgn(self):
        pgn = (
            '[Event "Test"]\n'
            '[Site "?"]\n'
            '[Date "2026.05.27"]\n'
            '[Round "?"]\n'
            '[White "?"]\n'
            '[Black "?"]\n'
            '[Result "*"]\n'
            '\n'
            '1. e4 e5 2. Nf3 Nc6 *\n'
        )
        moves = pgn_to_moves(pgn)
        assert len(moves) == 4
        assert moves[0] == chess.Move.from_uci("e2e4")
        assert moves[1] == chess.Move.from_uci("e7e5")
        assert moves[2] == chess.Move.from_uci("g1f3")
        assert moves[3] == chess.Move.from_uci("b8c6")

    def test_pgn_with_check_symbols(self):
        pgn = (
            '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Bxc6 dxc6 5. Nxe5 f6 6. Qh5+ g6\n'
            '7. Nxg6 Nf6 8. Qe5+ *\n'
        )
        moves = pgn_to_moves(pgn)
        assert len(moves) >= 8
        assert all(isinstance(m, chess.Move) for m in moves)

    def test_pgn_with_game_result(self):
        pgn = '1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n'
        moves = pgn_to_moves(pgn)
        assert len(moves) == 7

    def test_empty_pgn_raises(self):
        with pytest.raises(ValueError, match="Invalid PGN"):
            pgn_to_moves("")

    def test_pgn_headers_only(self):
        pgn = '[Event "Test"]\n[Result "*"]\n\n'
        moves = pgn_to_moves(pgn)
        assert moves == []


class TestBoardToPgn:
    def test_empty_board(self):
        board = chess.Board()
        pgn = board_to_pgn(board)
        assert '[Event "?"]' in pgn
        assert '[Result "*"]' in pgn
        assert pgn.strip().endswith("*")

    def test_single_move(self):
        board = chess.Board()
        board.push_san("e4")
        pgn = board_to_pgn(board)
        assert "1. e4" in pgn

    def test_multiple_moves(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("e5")
        board.push_san("Nf3")
        pgn = board_to_pgn(board)
        assert "1. e4 e5" in pgn
        assert "2. Nf3" in pgn

    def test_checkmate_result(self):
        board = chess.Board()
        board.push_san("f3")
        board.push_san("e5")
        board.push_san("g4")
        board.push_san("Qh4")
        pgn = board_to_pgn(board)
        assert "0-1" in pgn

    def test_roundtrip(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("e5")
        board.push_san("Nf3")
        board.push_san("Nc6")
        board.push_san("Bb5")
        pgn = board_to_pgn(board)
        moves = pgn_to_moves(pgn)
        assert len(moves) == 5
        assert moves[0] == chess.Move.from_uci("e2e4")
        assert moves[4] == chess.Move.from_uci("f1b5")

    def test_headers_default(self):
        board = chess.Board()
        pgn = board_to_pgn(board)
        assert '[Event "?"]' in pgn
        assert '[Site "?"]' in pgn
        assert '[Date "' in pgn
        assert '[Round "?"]' in pgn

    def test_custom_headers(self):
        board = chess.Board()
        headers = {"Event": "My Game", "White": "Player1"}
        pgn = board_to_pgn(board, headers=headers)
        assert '[Event "My Game"]' in pgn
        assert '[White "Player1"]' in pgn

    def test_output_is_string(self):
        board = chess.Board()
        pgn = board_to_pgn(board)
        assert isinstance(pgn, str)
        assert len(pgn) > 50


class TestReplayMoves:
    def test_replay_empty(self):
        board = chess.Board()
        result = replay_moves(board, [])
        assert result is not board
        assert result.fen() == board.fen()

    def test_replay_single_move(self):
        board = chess.Board()
        moves = [chess.Move.from_uci("e2e4")]
        result = replay_moves(board, moves)
        assert result.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)

    def test_replay_multiple(self):
        board = chess.Board()
        moves = [
            chess.Move.from_uci("e2e4"),
            chess.Move.from_uci("e7e5"),
        ]
        result = replay_moves(board, moves)
        assert result.fullmove_number == 2

    def test_replay_returns_copy(self):
        board = chess.Board()
        moves = [chess.Move.from_uci("e2e4")]
        result = replay_moves(board, moves)
        assert result is not board
        assert result.fen() != board.fen()

    def test_replay_illegal_move_raises(self):
        board = chess.Board()
        moves = [chess.Move.from_uci("e2e5")]
        with pytest.raises(ValueError, match="Illegal move"):
            replay_moves(board, moves)

    def test_replay_fools_mate(self):
        board = chess.Board()
        moves = [
            chess.Move.from_uci("f2f3"),
            chess.Move.from_uci("e7e5"),
            chess.Move.from_uci("g2g4"),
            chess.Move.from_uci("d8h4"),
        ]
        result = replay_moves(board, moves)
        assert result.is_checkmate()
