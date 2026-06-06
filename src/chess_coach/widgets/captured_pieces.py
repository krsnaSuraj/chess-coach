"""CapturedPieces — display captured pieces tray with material count.

Shows which pieces each side has captured, plus the net material advantage.
Material values: P=1, N=3, B=3, R=5, Q=9.

Custom-painted (not QLabel-based) for reliability across themes.
"""

from __future__ import annotations

import os

import chess
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QPainter, QPixmap, QColor, QFont
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy

from chess_coach.theme_manager import Theme, get_theme

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

_HERE = os.path.dirname(os.path.abspath(__file__))
_PIECE_IMG = os.path.normpath(os.path.join(
    _HERE, "..", "..", "..", "static", "img", "chesspieces", "wikipedia"))

_LETTERS = ("P", "N", "B", "R", "Q", "K")


def _load_pixmaps() -> dict[str, QPixmap]:
    cache: dict[str, QPixmap] = {}
    for letter in _LETTERS:
        for color in ("w", "b"):
            p = os.path.join(_PIECE_IMG, f"{color}{letter}.png")
            if os.path.exists(p):
                cache[color + letter] = QPixmap(p)
    return cache


class CapturedPieces(QWidget):
    """Horizontal tray: top half = pieces white captured (black icons),
    bottom half = pieces black captured (white icons). Material count in
    the middle column.
    """

    def __init__(self, theme: Theme | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme or get_theme()
        self._board = chess.Board()
        self._cache = _load_pixmaps()
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_board(self, board: chess.Board) -> None:
        self._board = board
        self.update()

    def _captured_by(self, by_color: chess.Color) -> list[chess.Piece]:
        """Return list of pieces that have been captured by ``by_color``."""
        captured: list[chess.Piece] = []
        for sq in chess.SQUARES:
            piece = self._board.piece_at(sq)
            if piece and piece.color != by_color:
                captured.append(piece)
        captured.sort(key=lambda p: -PIECE_VALUES.get(p.piece_type, 0))
        return captured

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        row_h = h // 2
        # Captured by white = black pieces still on board (top row)
        cap_by_white = self._captured_by(chess.WHITE)
        cap_by_black = self._captured_by(chess.BLACK)
        # Material count text in middle
        white_mat = sum(PIECE_VALUES[p.piece_type] for p in cap_by_white)
        black_mat = sum(PIECE_VALUES[p.piece_type] for p in cap_by_black)
        diff = white_mat - black_mat
        mat_text = "±0" if diff == 0 else (f"+{diff}" if diff > 0 else f"−{abs(diff)}")
        # Draw pieces
        piece_h = max(12, min(row_h - 4, 24))
        self._draw_pieces(p, cap_by_white, "b", y=2, h=piece_h)
        self._draw_pieces(p, cap_by_black, "w", y=row_h + 2, h=piece_h)
        # Material count in center column
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(self._theme.accent))
        mat_w = 40
        p.drawText(QRectF(w // 2 - mat_w // 2, 0, mat_w, h),
                   Qt.AlignmentFlag.AlignCenter, mat_text)

    def _draw_pieces(self, p: QPainter, pieces: list, color: str, y: int, h: int) -> None:
        x = 4
        spacing = 2
        for piece in pieces:
            letter = "PNBRQK"[piece.piece_type]
            pix = self._cache.get(color + letter)
            if pix is None or pix.isNull():
                x += h + spacing
                continue
            scaled = pix.scaled(h, h, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(x, y, scaled)
            x += scaled.width() + spacing

    def sizeHint(self) -> QSize:
        return QSize(300, 56)


__all__ = ["CapturedPieces", "PIECE_VALUES"]
