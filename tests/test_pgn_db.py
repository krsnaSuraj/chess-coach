"""Tests for DB submodules: FEN-indexed PGN search."""
from __future__ import annotations

import io
import os
import tempfile

import chess
import chess.pgn as pgn
import pytest

from chess_coach.db import (
    FenPgnIndex,
    PgnGameRecord,
    extract_game_record,
)


SIMPLE_PGN = """
[Event "Test Game"]
[Site "Test"]
[Date "2024.01.01"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]
[ECO "C50"]
[Opening "Italian Game"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 1-0
"""


@pytest.fixture
def pgn_index():
    """Create a fresh in-memory FEN PGN index."""
    idx = FenPgnIndex(":memory:")
    yield idx
    idx.close()


class TestPgnGameRecord:
    def test_extract_simple_game(self):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="test1")
        assert record.game_id == "test1"
        assert record.white == "Player1"
        assert record.black == "Player2"
        assert record.eco == "C50"
        assert record.opening == "Italian Game"
        assert record.result == "1-0"

    def test_positions_extracted(self):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="test1")
        # 6 positions: start + 5 moves (e4, e5, Nf3, Nc6, Bc4)
        assert len(record.positions) == 6

    def test_first_position_is_start(self):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="test1")
        board = chess.Board(record.positions[0])
        assert board.fullmove_number == 1
        assert board.turn == chess.WHITE


class TestFenPgnIndex:
    def test_create_empty(self, pgn_index):
        assert pgn_index.count() == 0
        assert pgn_index.position_count() == 0

    def test_add_game(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        assert pgn_index.count() == 1
        # 5 moves + start = 6 positions stored
        assert pgn_index.position_count() == 6

    def test_add_pgn_text(self, pgn_index):
        # Add two games
        text = SIMPLE_PGN + "\n\n" + SIMPLE_PGN
        added = pgn_index.add_pgn_text(text, game_id_prefix="g")
        assert added == 2
        assert pgn_index.count() == 2

    def test_find_by_fen(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        # Find start position
        start_fen = record.positions[0]
        results = pgn_index.find_by_fen(start_fen)
        assert "g1" in results

    def test_find_by_fen_miss(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        # Bogus FEN
        results = pgn_index.find_by_fen("8/8/8/8/8/8/8/8 w - - 0 1")
        assert results == []

    def test_find_by_material(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        # Start board
        board = chess.Board()
        results = pgn_index.find_by_material(board)
        assert "g1" in results

    def test_get_game(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        fetched = pgn_index.get_game("g1")
        assert fetched is not None
        assert fetched.game_id == "g1"
        assert fetched.white == "Player1"
        assert fetched.eco == "C50"

    def test_get_game_missing(self, pgn_index):
        assert pgn_index.get_game("nope") is None

    def test_find_by_eco(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        results = pgn_index.find_by_eco("C50")
        assert "g1" in results
        results = pgn_index.find_by_eco("C00")
        assert results == []

    def test_find_by_opening(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        results = pgn_index.find_by_opening("Italian")
        assert "g1" in results

    def test_find_by_player(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        results = pgn_index.find_by_player("Player1")
        assert "g1" in results
        results = pgn_index.find_by_player("UnknownPlayer")
        assert results == []

    def test_position_frequency(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        start_fen = record.positions[0]
        freq = pgn_index.position_frequency(start_fen)
        assert freq == 1

    def test_opening_stats(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        games, players = pgn_index.opening_stats("C50")
        assert games == 1
        # 2 distinct players (white + black)
        assert players == 2

    def test_replace_game(self, pgn_index):
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        # Add again with same id
        pgn_index.add_game(record)
        # Should still be just 1 game
        assert pgn_index.count() == 1
        # Positions replaced (5 moves + start = 6)
        assert pgn_index.position_count() == 6

    def test_file_based_index(self, tmp_path):
        """Use a file-based (not :memory:) index to test persistence."""
        db_file = tmp_path / "test_pgn.db"
        idx = FenPgnIndex(str(db_file))
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        idx.add_game(record)
        idx.close()
        # Reopen
        idx2 = FenPgnIndex(str(db_file))
        assert idx2.count() == 1
        idx2.close()

    def test_limit_param(self, pgn_index):
        # Add many games
        for i in range(20):
            game = pgn.read_game(io.StringIO(SIMPLE_PGN))
            record = extract_game_record(game, game_id=f"g{i}")
            pgn_index.add_game(record)
        results = pgn_index.find_by_player("Player1", limit=5)
        assert len(results) == 5


class TestPgnIndexIntegration:
    def test_full_pgn_round_trip(self, pgn_index):
        """Add a PGN, retrieve it, verify it parses back."""
        game = pgn.read_game(io.StringIO(SIMPLE_PGN))
        record = extract_game_record(game, game_id="g1")
        pgn_index.add_game(record)
        fetched = pgn_index.get_game("g1")
        # Re-parse the stored PGN
        game2 = pgn.read_game(io.StringIO(fetched.pgn))
        assert game2 is not None
        assert game2.headers["White"] == "Player1"
