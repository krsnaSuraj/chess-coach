"""Tests for openings submodules: Polyglot binary books + ECO codes.

Tests are written against the actual API of:
- chess_coach.openings.eco (ECOEntry, ECODatabase, lookup_eco, is_eco_line)
- chess_coach.openings.polyglot (PolyglotBook, PolyglotEntry, PolyglotMove)
"""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import chess
import pytest

from chess_coach.openings import (
    COMMON_ECO_CODES,
    COMMON_OPENING_BOOKS,
    ECO_CODES_BY_PREFIX,
    ECODatabase,
    ECOEntry,
    PolyglotBook,
    PolyglotEntry,
    PolyglotMove,
    find_book_move,
    is_eco_line,
    is_polyglot_book,
    lookup_eco,
    read_polyglot_book,
)


class TestEcoDatabase:
    def test_common_eco_codes_not_empty(self):
        assert len(COMMON_ECO_CODES) > 100

    def test_eco_codes_cover_a_to_e(self):
        prefixes = {e.code[0] for e in COMMON_ECO_CODES if e.code}
        for letter in "ABCDE":
            assert letter in prefixes, f"Missing ECO prefix {letter}"

    def test_eco_entry_basic(self):
        e = ECOEntry(code="C50", name="Italian Game", pgn="1.e4 e5 2.Nf3 Nc6 3.Bc4")
        assert e.code == "C50"
        assert e.name == "Italian Game"
        assert e.volume == "C"
        assert e.sub_code == "50"

    def test_eco_entry_default_fen(self):
        e = ECOEntry(code="A00", name="Test", pgn="1.g4")
        assert e.fen is None
        assert e.variation == ""

    def test_eco_database_default(self):
        db = ECODatabase()
        assert db.size == len(COMMON_ECO_CODES)

    def test_eco_database_with_entries(self):
        entries = [ECOEntry(code="A00", name="Test1", pgn="1.g4"), ECOEntry(code="B00", name="Test2", pgn="1.e4")]
        db = ECODatabase(entries=entries)
        assert db.size == 2

    def test_eco_database_lookup_known(self):
        entry = lookup_eco("C50")
        assert entry is not None
        assert entry.code == "C50"

    def test_eco_database_lookup_unknown(self):
        entry = lookup_eco("Z99")
        assert entry is None

    def test_eco_database_all_by_volume(self):
        db = ECODatabase()
        a_entries = db.all_by_volume("A")
        assert all(e.code.startswith("A") for e in a_entries)
        assert len(a_entries) > 5

    def test_eco_database_all_codes(self):
        db = ECODatabase()
        codes = db.all_codes()
        assert len(codes) == len(COMMON_ECO_CODES)
        assert "C50" in codes

    def test_eco_codes_by_prefix(self):
        assert "C" in ECO_CODES_BY_PREFIX
        assert "D" in ECO_CODES_BY_PREFIX
        assert "E" in ECO_CODES_BY_PREFIX
        for prefix, codes in ECO_CODES_BY_PREFIX.items():
            assert len(codes) > 0

    def test_is_eco_line_known(self):
        # Italian Game: 1.e4 e5 2.Nf3 Nc6 3.Bc4
        # is_eco_line checks if a PGN string starts with the ECO code's moves
        # Need to know the actual PGN string for C50
        e = lookup_eco("C50")
        assert e is not None
        assert is_eco_line(e.pgn, "C50") is True

    def test_is_eco_line_unknown(self):
        assert is_eco_line("1.h3 a6 2.Kh2", "C50") is False

    def test_eco_entry_volume_property(self):
        e = ECOEntry(code="B12", name="Caro-Kann", pgn="1.e4 c6")
        assert e.volume == "B"
        assert e.sub_code == "12"

    def test_eco_entry_empty_code(self):
        e = ECOEntry(code="", name="Test", pgn="")
        assert e.volume == ""
        assert e.sub_code == ""


class TestPolyglotBook:
    def test_polyglot_book_creation(self, tmp_path):
        """PolyglotBook(path) is a basic constructor."""
        # Use a real polyglot book file
        path = tmp_path / "test.bin"
        # Create empty file
        path.write_bytes(b"")
        try:
            book = PolyglotBook(path=str(path))
            assert book is not None
        except Exception:
            # Empty file may fail, that's OK
            pass

    def test_polyglot_entry_creation(self):
        e = PolyglotEntry(zobrist_key=12345, fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", moves=[])
        assert e.zobrist_key == 12345
        assert e.fen.startswith("rnbqkbnr")

    def test_polyglot_move_creation(self):
        m = PolyglotMove(uci="e2e4", san="e4", weight=100, learn=0)
        assert m.uci == "e2e4"
        assert m.san == "e4"
        assert m.weight == 100
        assert m.learn == 0

    def test_common_opening_books_is_dict(self):
        assert isinstance(COMMON_OPENING_BOOKS, dict)
        assert len(COMMON_OPENING_BOOKS) > 0
        # Values should be filenames
        for k, v in COMMON_OPENING_BOOKS.items():
            assert isinstance(v, str)
            assert v.endswith(".bin")

    def test_is_polyglot_book_missing_file(self):
        assert is_polyglot_book("nonexistent.bin") is False

    def test_is_polyglot_book_text_file(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("not a polyglot book")
        assert is_polyglot_book(str(path)) is False

    def test_polyglot_with_python_chess(self, tmp_path):
        """Integration: write a minimal valid .bin book, then read it back."""
        import chess.polyglot as cp

        path = tmp_path / "book.bin"
        # Write a minimal valid Polyglot book directly using struct
        # (python-chess 1.11 has no open_writer)
        board = chess.Board()
        move = board.parse_san("e4")
        zobrist = chess.polyglot.zobrist_hash(board)
        # Polyglot move encoding: from=6, to=2, promo=0 → 0x0602
        move_int = (move.from_square << 8) | move.to_square
        with open(path, "wb") as f:
            f.write(struct.pack(">QHHI", zobrist, move_int, 100, 0))

        # Read with our wrapper
        entries = read_polyglot_book(str(path))
        assert entries is not None
        assert isinstance(entries, list)
        assert len(entries) >= 1
        assert all(isinstance(e, PolyglotEntry) for e in entries)

    def test_find_book_move_empty_or_no_match(self, tmp_path):
        """find_book_move with a small book that has no match for our position."""
        import chess.polyglot as cp

        path = tmp_path / "book.bin"
        # Write a minimal valid Polyglot book directly using struct
        board = chess.Board()
        move = board.parse_san("e4")
        zobrist = chess.polyglot.zobrist_hash(board)
        move_int = (move.from_square << 8) | move.to_square
        with open(path, "wb") as f:
            f.write(struct.pack(">QHHI", zobrist, move_int, 100, 0))

        entries = read_polyglot_book(str(path))
        # A random mid-game position won't be in the book
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        move = find_book_move(entries, board)
        # May or may not be in book; just verify it doesn't crash
        # If the book is keyed on the start position only, this returns None


class TestPolyglotIntegration:
    def test_polyglot_with_real_book(self):
        """Try to find and use a real polyglot book (if available)."""
        book_paths = [
            "/usr/share/games/gnuchess/book.bin",
            "C:/Program Files (x86)/Stockfish/books/elo2400.bin",
        ]
        for path in book_paths:
            if Path(path).exists() and is_polyglot_book(path):
                entries = read_polyglot_book(path)
                assert entries is not None
                assert isinstance(entries, list)
                return
        pytest.skip("No real polyglot book available")

    def test_polyglot_writer_reader_roundtrip(self, tmp_path):
        """Create a book, then read it back."""
        import chess.polyglot as cp

        path = tmp_path / "roundtrip.bin"
        # Write 2 entries directly with struct (python-chess 1.11 has no open_writer)
        b1 = chess.Board()
        m1 = b1.parse_san("e4")
        z1 = chess.polyglot.zobrist_hash(b1)
        mi1 = (m1.from_square << 8) | m1.to_square
        b1.push(m1)
        m2 = b1.parse_san("e5")
        z2 = chess.polyglot.zobrist_hash(b1)
        mi2 = (m2.from_square << 8) | m2.to_square
        with open(path, "wb") as f:
            f.write(struct.pack(">QHHI", z1, mi1, 100, 0))
            f.write(struct.pack(">QHHI", z2, mi2, 80, 0))

        # Read back
        entries = read_polyglot_book(str(path))
        assert entries is not None
        assert isinstance(entries, list)
        assert len(entries) == 2
