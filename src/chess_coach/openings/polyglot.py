"""Polyglot binary opening book reader.

A Polyglot book (.bin) is a binary file containing millions of pre-computed
opening moves keyed by Zobrist hash. Format spec:
https://www.chessprogramming.org/Polyglot

Each record is 16 bytes:
- 8 bytes: Zobrist key of the position
- 2 bytes: move (big-endian, from-to)
- 2 bytes: weight
- 4 bytes: learn
"""
from __future__ import annotations

import logging
import random
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess
import chess.polyglot

logger = logging.getLogger(__name__)

# Real-world opening book sources
COMMON_OPENING_BOOKS = {
    "codekiddy": "codekiddy.bin",  # ~3.4M entries
    "tcec": "tcec.bin",            # TCEC tournament book
    "perf": "perf.bin",            # Performance database
    "komodo": "komodo.bin",        # Komodo engine book
    "stockfish": "stockfish-book.bin",
}


@dataclass
class PolyglotMove:
    """A single weighted move from a Polyglot book."""
    uci: str
    san: str
    weight: int
    learn: int

    @property
    def move(self) -> chess.Move | None:
        try:
            return chess.Move.from_uci(self.uci)
        except ValueError:
            return None


@dataclass
class PolyglotEntry:
    """A Polyglot book entry: all moves for a single position."""
    zobrist_key: int
    fen: str
    moves: list[PolyglotMove]

    @property
    def total_weight(self) -> int:
        return sum(m.weight for m in self.moves)

    @property
    def best_move(self) -> PolyglotMove | None:
        return max(self.moves, key=lambda m: m.weight) if self.moves else None

    def weighted_choice(self, rng: random.Random | None = None) -> PolyglotMove | None:
        """Pick a move weighted by learn value (use for humanizing)."""
        if not self.moves:
            return None
        r = rng or random
        total = sum(m.learn for m in self.moves) or 1
        pick = r.random() * total
        cumulative = 0
        for m in self.moves:
            cumulative += m.learn
            if pick < cumulative:
                return m
        return self.moves[-1]


class PolyglotBook:
    """Wrapper around python-chess's polyglot reader for higher-level access."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(f"Polyglot book not found: {path}")
        self._reader: chess.polyglot.MemoryMappedReader | None = None
        self._try_open()

    def _try_open(self) -> None:
        try:
            self._reader = chess.polyglot.open_reader(str(self._path))
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not open Polyglot book: %s", e)
            self._reader = None

    @property
    def is_open(self) -> bool:
        return self._reader is not None

    def close(self) -> None:
        if self._reader:
            self._reader.close()
            self._reader = None

    def __enter__(self) -> "PolyglotBook":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def lookup(self, board: chess.Board) -> list[PolyglotMove]:
        """Look up all moves for a position. Returns weighted list."""
        if not self._reader:
            return []
        moves: list[PolyglotMove] = []
        try:
            for entry in self._reader.find_all(board):
                move = entry.move
                if move not in board.legal_moves:
                    continue
                moves.append(PolyglotMove(
                    uci=move.uci(),
                    san=board.san(move),
                    weight=entry.weight,
                    learn=entry.learn,
                ))
        except Exception as e:  # noqa: BLE001
            logger.debug("Polyglot lookup failed: %s", e)
        return moves

    def best_move(self, board: chess.Board) -> PolyglotMove | None:
        """Get the highest-weight book move."""
        moves = self.lookup(board)
        return max(moves, key=lambda m: m.weight) if moves else None

    def random_move(self, board: chess.Board, rng: random.Random | None = None) -> PolyglotMove | None:
        """Get a random book move (uniform distribution)."""
        moves = self.lookup(board)
        if not moves:
            return None
        r = rng or random
        return r.choice(moves)

    def weighted_random(self, board: chess.Board, rng: random.Random | None = None) -> PolyglotMove | None:
        """Pick a move weighted by learn value."""
        moves = self.lookup(board)
        if not moves:
            return None
        r = rng or random
        total = sum(m.learn for m in moves) or 1
        pick = r.random() * total
        cumulative = 0
        for m in moves:
            cumulative += m.learn
            if pick < cumulative:
                return m
        return moves[-1]


def is_polyglot_book(path: str | Path) -> bool:
    """Check if a file is a valid Polyglot book (.bin)."""
    path = Path(path)
    if not path.exists():
        return False
    if path.suffix.lower() != ".bin":
        return False
    # Check size: each entry is 16 bytes, valid book has at least 1 entry
    size = path.stat().st_size
    return size > 0 and size % 16 == 0


def read_polyglot_book(path: str | Path) -> list[PolyglotEntry]:
    """Read all entries from a Polyglot book (loads into memory).

    Use PolyglotBook class for memory-mapped access on large books.
    """
    path = Path(path)
    if not is_polyglot_book(path):
        raise ValueError(f"Not a valid Polyglot book: {path}")

    entries: dict[int, list[PolyglotMove]] = {}
    with open(path, "rb") as f:
        while True:
            chunk = f.read(16)
            if len(chunk) < 16:
                break
            key, move_int, weight, learn = struct.unpack(">QHHI", chunk)
            from_sq = (move_int >> 8) & 0xFF
            to_sq = move_int & 0xFF
            promo = (move_int >> 12) & 0xF
            try:
                move = chess.Move(from_sq, to_sq, promotion=promo if promo else None)
                uci = move.uci()
                entries.setdefault(key, []).append(PolyglotMove(
                    uci=uci, san="", weight=weight, learn=learn,
                ))
            except (ValueError, IndexError):
                continue

    return [
        PolyglotEntry(
            zobrist_key=key,
            fen="",
            moves=moves,
        )
        for key, moves in entries.items()
    ]


def find_book_move(entries: list[PolyglotEntry], board: chess.Board,
                   strategy: str = "best") -> chess.Move | None:
    """Find a book move for a position using a strategy.

    entries: list of PolyglotEntry (as returned by read_polyglot_book).
    strategy: 'best' (highest weight), 'random' (uniform), 'weighted' (probability).
    Returns a chess.Move or None if no book move for this position.
    """
    import random as _random
    zobrist = chess.polyglot.zobrist_hash(board)
    candidates = None
    for entry in entries:
        if entry.zobrist_key == zobrist:
            candidates = entry.moves
            break
    if not candidates:
        return None
    if strategy == "best":
        best = max(candidates, key=lambda m: m.weight)
    elif strategy == "random":
        best = _random.choice(candidates)
    elif strategy == "weighted":
        total = sum(m.weight for m in candidates)
        if total <= 0:
            best = _random.choice(candidates)
        else:
            r = _random.uniform(0, total)
            acc = 0
            best = candidates[-1]
            for m in candidates:
                acc += m.weight
                if r <= acc:
                    best = m
                    break
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    # Convert UCI to chess.Move
    try:
        from_sq = int(best.uci[0:2], 16) if best.uci[:1].isalpha() else 0
    except Exception:
        from_sq = 0
    # Use a robust parser
    try:
        return chess.Move.from_uci(best.uci)
    except Exception:
        return None
