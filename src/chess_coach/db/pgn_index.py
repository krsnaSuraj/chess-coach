"""FEN-indexed PGN search database.

Stores parsed PGN games keyed by FEN positions so you can find games
where a specific position was reached. Uses a JSON-backed store (no
external DB dependency) but also supports a sqlite backend when the
`sqlite3` module is used (always available in stdlib on Python).

This is intended for personal study collections (thousands of games),
not massive corpora. The Lichess 2024-April PGN dump is ~250M games and
should use a real database.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import (
    dataclass, field,
)
from typing import (
    Dict, Iterator, List, Optional, Tuple,
)

import chess
import chess.pgn as pgn


_FEN_BOARD_PART_RE = re.compile(r"^([rnbqkpRNBQKP1-8]+\/){7}[rnbqkpRNBQKP1-8]+")


@dataclass
class PgnGameRecord:
    """Minimal record stored in the PGN DB."""

    game_id: str
    white: str
    black: str
    event: str = ""
    site: str = ""
    date: str = ""
    round: str = ""
    result: str = "*"
    eco: str = ""
    opening: str = ""
    white_elo: int = 0
    black_elo: int = 0
    pgn: str = ""
    positions: List[str] = field(default_factory=list)  # FENs after each move (or just key positions)
    tags: Dict[str, str] = field(default_factory=dict)


def _board_part(fen: str) -> str:
    """Return just the board portion of a FEN (no side/castling/ep/halfmove/fullmove)."""
    return fen.split(" ")[0] if fen else ""


def _material_signature(board: chess.Board) -> str:
    """Reduce a board to a position signature (board + side to move).

    Useful for opening lookup regardless of castling/ep rights.
    """
    return f"{board.board_fen()} {board.turn}"


def extract_game_record(game: pgn.Game, game_id: Optional[str] = None) -> PgnGameRecord:
    """Build a PgnGameRecord from a parsed pgn.Game."""
    headers = game.headers
    gid = game_id or headers.get("Site") or headers.get("Event", "") + "/" + headers.get("Round", "")
    board = game.board()
    positions: List[str] = []
    positions.append(board.fen())
    for node in game.mainline():
        if node.move is None:
            continue
        board.push(node.move)
        positions.append(board.fen())

    return PgnGameRecord(
        game_id=gid,
        white=headers.get("White", "?"),
        black=headers.get("Black", "?"),
        event=headers.get("Event", ""),
        site=headers.get("Site", ""),
        date=headers.get("Date", ""),
        round=headers.get("Round", ""),
        result=headers.get("Result", "*"),
        eco=headers.get("ECO", ""),
        opening=headers.get("Opening", ""),
        white_elo=int(headers.get("WhiteElo", "0") or "0"),
        black_elo=int(headers.get("BlackElo", "0") or "0"),
        pgn=str(game),
        positions=positions,
        tags={k: v for k, v in headers.items()},
    )


class FenPgnIndex:
    """In-memory + sqlite-backed FEN index for a PGN collection.

    Schema:
      - games: (game_id, white, black, event, date, result, eco, opening, pgn)
      - positions: (game_id, ply, fen) — FEN after each move
      - material_keys: (game_id, ply, key) — board_fen + ' ' + turn
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, timeout=5.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        c = self._conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                white TEXT,
                black TEXT,
                event TEXT,
                site TEXT,
                date TEXT,
                round TEXT,
                result TEXT,
                eco TEXT,
                opening TEXT,
                white_elo INTEGER,
                black_elo INTEGER,
                pgn TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                game_id TEXT,
                ply INTEGER,
                fen TEXT,
                material_key TEXT,
                FOREIGN KEY(game_id) REFERENCES games(game_id)
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_positions_fen ON positions(fen)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_positions_mk ON positions(material_key)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_positions_game ON positions(game_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_games_eco ON games(eco)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_games_opening ON games(opening)")
        self._conn.commit()

    def add_game(self, record: PgnGameRecord) -> None:
        """Insert a single PgnGameRecord (replaces on conflict)."""
        c = self._conn.cursor()
        c.execute(
            """
            INSERT OR REPLACE INTO games
            (game_id, white, black, event, site, date, round, result, eco, opening,
             white_elo, black_elo, pgn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.game_id, record.white, record.black, record.event, record.site,
                record.date, record.round, record.result, record.eco, record.opening,
                record.white_elo, record.black_elo, record.pgn,
            ),
        )
        c.execute("DELETE FROM positions WHERE game_id = ?", (record.game_id,))
        for ply, fen in enumerate(record.positions):
            mk = ""
            try:
                board = chess.Board(fen)
                mk = _material_signature(board)
            except Exception:
                mk = ""
            c.execute(
                "INSERT INTO positions (game_id, ply, fen, material_key) VALUES (?, ?, ?, ?)",
                (record.game_id, ply, fen, mk),
            )
        self._conn.commit()

    def add_pgn_text(self, pgn_text: str, game_id_prefix: str = "") -> int:
        """Parse a PGN string and add all games. Returns number added."""
        added = 0
        for i, game in enumerate(_iter_pgn_text(pgn_text)):
            gid = f"{game_id_prefix}{i:08d}"
            self.add_game(extract_game_record(game, game_id=gid))
            added += 1
        return added

    def count(self) -> int:
        c = self._conn.cursor()
        c.execute("SELECT COUNT(*) FROM games")
        return c.fetchone()[0]

    def position_count(self) -> int:
        c = self._conn.cursor()
        c.execute("SELECT COUNT(*) FROM positions")
        return c.fetchone()[0]

    def find_by_fen(self, fen: str, limit: int = 100) -> List[str]:
        """Return up to `limit` game_ids that contain the exact FEN."""
        c = self._conn.cursor()
        c.execute(
            "SELECT DISTINCT game_id FROM positions WHERE fen = ? LIMIT ?",
            (fen, limit),
        )
        return [row[0] for row in c.fetchall()]

    def find_by_material(self, board: chess.Board, limit: int = 100) -> List[str]:
        """Return up to `limit` game_ids that contain a position with the same material+turn."""
        mk = _material_signature(board)
        c = self._conn.cursor()
        c.execute(
            "SELECT DISTINCT game_id FROM positions WHERE material_key = ? LIMIT ?",
            (mk, limit),
        )
        return [row[0] for row in c.fetchall()]

    def get_game(self, game_id: str) -> Optional[PgnGameRecord]:
        c = self._conn.cursor()
        c.execute("SELECT * FROM games WHERE game_id = ?", (game_id,))
        row = c.fetchone()
        if row is None:
            return None
        return PgnGameRecord(
            game_id=row[0], white=row[1], black=row[2], event=row[3], site=row[4],
            date=row[5], round=row[6], result=row[7], eco=row[8], opening=row[9],
            white_elo=row[10] or 0, black_elo=row[11] or 0, pgn=row[12],
        )

    def find_by_eco(self, eco_code: str, limit: int = 100) -> List[str]:
        c = self._conn.cursor()
        c.execute("SELECT game_id FROM games WHERE eco = ? LIMIT ?", (eco_code, limit))
        return [row[0] for row in c.fetchall()]

    def find_by_opening(self, opening_name: str, limit: int = 100) -> List[str]:
        c = self._conn.cursor()
        like = f"%{opening_name}%"
        c.execute(
            "SELECT game_id FROM games WHERE opening LIKE ? LIMIT ?",
            (like, limit),
        )
        return [row[0] for row in c.fetchall()]

    def find_by_player(self, name: str, limit: int = 100) -> List[str]:
        c = self._conn.cursor()
        like = f"%{name}%"
        c.execute(
            "SELECT game_id FROM games WHERE white LIKE ? OR black LIKE ? LIMIT ?",
            (like, like, limit),
        )
        return [row[0] for row in c.fetchall()]

    def position_frequency(self, fen: str) -> int:
        c = self._conn.cursor()
        c.execute("SELECT COUNT(*) FROM positions WHERE fen = ?", (fen,))
        return c.fetchone()[0]

    def opening_stats(self, eco_code: str) -> Tuple[int, int]:
        """Return (game_count, distinct_player_count) for a given ECO code."""
        c = self._conn.cursor()
        c.execute("SELECT COUNT(*) FROM games WHERE eco = ?", (eco_code,))
        games = c.fetchone()[0]
        c.execute(
            "SELECT COUNT(DISTINCT white) + COUNT(DISTINCT black) FROM games WHERE eco = ?",
            (eco_code,),
        )
        players = c.fetchone()[0] or 0
        return games, players

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "FenPgnIndex":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def _iter_pgn_text(text: str) -> Iterator[pgn.Game]:
    """Yield all games in a PGN string."""
    from io import StringIO
    handle = StringIO(text)
    while True:
        offset = handle.tell()
        try:
            headers = pgn.read_headers(handle)
        except Exception:
            return
        if headers is None:
            return
        handle.seek(offset)
        game = pgn.read_game(handle)
        if game is None:
            return
        yield game


def index_pgn_file(path: str, db_path: str = ":memory:") -> FenPgnIndex:
    """Build a FEN index from a PGN file."""
    index = FenPgnIndex(db_path=db_path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, game in enumerate(pgn.read_game(f) or [] for _ in [0]):
            if game is None:
                continue
            index.add_game(extract_game_record(game, game_id=f"g{i:08d}"))
    return index


__all__ = [
    "PgnGameRecord",
    "FenPgnIndex",
    "extract_game_record",
    "index_pgn_file",
    "_material_signature",
    "_board_part",
]
