from __future__ import annotations

import math
import os
from PyQt6.QtWidgets import QWidget

from chess_coach.promotion_dialog import PromotionDialog
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QPixmap, QPainterPath,
    QResizeEvent, QPaintEvent, QMouseEvent, QCursor,
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPoint, QPointF, QTimer, QElapsedTimer

import chess

_HERE = os.path.dirname(os.path.abspath(__file__))
PIECE_IMAGES_DIR = os.path.join(_HERE, "..", "..", "static", "img", "chesspieces", "wikipedia")

PIECE_MAP = {
    "wP": "wP.png", "wN": "wN.png", "wB": "wB.png",
    "wR": "wR.png", "wQ": "wQ.png", "wK": "wK.png",
    "bP": "bP.png", "bN": "bN.png", "bB": "bB.png",
    "bR": "bR.png", "bQ": "bQ.png", "bK": "bK.png",
}

PIECE_TYPES = {
    chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B",
    chess.ROOK: "R", chess.QUEEN: "Q", chess.KING: "K",
}

COLORS: dict[str, str] = {
    "bg": "#0d1117",
    "sidebar": "#161b22",
    "border": "#30363d",
    "accent": "#58a6ff",
    "text": "#f0f6fc",
    "text_dim": "#8b949e",
    "green": "#3fb950",
    "red": "#f85149",
    "yellow": "#d29922",
    "board_light": "#f0d9b5",
    "board_dark": "#b58863",
}


class ChessBoard(QWidget):
    move_made = pyqtSignal(chess.Move)

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        self.board = chess.Board()
        self.dragged_piece: chess.Piece | None = None
        self.dragged_square: int | None = None
        self.drag_start_pos: QPoint | None = None
        self.mouse_pos = QPoint()
        self.setMouseTracking(True)
        self.setMinimumSize(360, 360)

        self.flipped = False
        self.playable_side: chess.Color | None = None
        self.drag_cache: QPixmap | None = None
        self.best_move: chess.Move | None = None
        self.last_move_squares: list[int] = []
        self.check_square: int | None = None
        self.legal_move_squares: list[int] = []
        self._pending_move: chess.Move | None = None

        display = config.get("display", {})
        self.light_color = QColor(display.get("light_square", COLORS["board_light"]))
        self.dark_color = QColor(display.get("dark_square", COLORS["board_dark"]))
        self.highlight_color = QColor(display.get("highlight_color", "#FFFF64"))
        self.highlight_color.setAlpha(80)
        self.check_color = QColor(display.get("check_color", "#FF3232"))
        self.check_color.setAlpha(120)
        self.dot_color = QColor(display.get("dot_color", "#646464"))
        self.dot_color.setAlpha(160)
        self.capture_ring_color = QColor(display.get("capture_ring_color", "#323232"))
        self.capture_ring_color.setAlpha(200)

        arrow_hex = display.get("arrow_color", "#00FF00")
        arrow_opacity = display.get("arrow_opacity", 0.6)
        ac = QColor(arrow_hex)
        ac.setAlphaF(arrow_opacity)
        self.arrow_color = ac

        self.last_move_color = QColor(display.get("last_move_color", "#FFFF64"))
        self.last_move_color.setAlpha(90)

        self.raw_pieces: dict[str, QPixmap] = {}
        self.scaled_pieces: dict[str, QPixmap] = {}
        self.current_scale: float = 0
        self._load_piece_images()

        self._anim_progress: float = 0.0
        self._anim_from_xy: tuple[float, float] | None = None
        self._anim_to_xy: tuple[float, float] | None = None
        self._anim_pix: QPixmap | None = None
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animation_step)
        self._anim_elapsed = QElapsedTimer()
        self._anim_duration_ms = 150

    def _load_piece_images(self) -> None:
        for key, filename in PIECE_MAP.items():
            path = os.path.join(PIECE_IMAGES_DIR, filename)
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    self.raw_pieces[key] = pix

    def _get_piece_key(self, piece: chess.Piece) -> str:
        color = "w" if piece.color == chess.WHITE else "b"
        return color + PIECE_TYPES[piece.piece_type]

    def _scale_pieces(self, square_size: float) -> None:
        if square_size == self.current_scale:
            return
        self.current_scale = square_size
        self.scaled_pieces = {}
        size = int(square_size * 0.88)
        for key, pix in self.raw_pieces.items():
            self.scaled_pieces[key] = pix.scaled(
                size, size, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        self.drag_cache = None
        super().resizeEvent(event)

    def set_board(self, board: chess.Board) -> None:
        self.board = board
        self.best_move = None
        self.dragged_piece = None
        self.dragged_square = None
        self.drag_cache = None
        self._update_board_state()
        self.update()

    def _update_board_state(self) -> None:
        self.last_move_squares = []
        self.check_square = None
        self.legal_move_squares = []
        if self.board.move_stack:
            last = self.board.peek()
            self.last_move_squares = [last.from_square, last.to_square]
        if self.board.is_check():
            king = self.board.king(self.board.turn)
            if king is not None:
                self.check_square = king

    def set_best_move(self, move: chess.Move | None) -> None:
        self.best_move = move
        self.update()

    def set_flipped(self, flipped: bool) -> None:
        self.flipped = flipped
        self.update()

    def set_legal_moves(self, squares: list[int]) -> None:
        self.legal_move_squares = squares
        self.update()

    def _board_coords(self, pos: QPointF) -> tuple[int | None, int | None, float, float, float]:
        size = min(self.width(), self.height())
        sq = size / 8
        ox = (self.width() - size) / 2
        oy = (self.height() - size) / 2
        x = pos.x() - ox
        y = pos.y() - oy
        if 0 <= x < size and 0 <= y < size:
            col = int(x / sq)
            row = int(y / sq)
            return col, row, sq, ox, oy
        return None, None, sq, ox, oy

    def _to_square(self, col: int, row: int) -> int:
        if self.flipped:
            return chess.square(7 - col, row)
        return chess.square(col, 7 - row)

    def _to_visual(self, square: int) -> tuple[int, int]:
        f = chess.square_file(square)
        r = chess.square_rank(square)
        if self.flipped:
            return 7 - f, r
        return f, 7 - r

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        size = min(self.width(), self.height())
        sq = size / 8
        ox = (self.width() - size) / 2
        oy = (self.height() - size) / 2

        if self.dragged_piece and self.drag_cache and self._pending_move is None:
            painter.drawPixmap(0, 0, self.drag_cache)
            self._draw_dragged_piece(painter, sq)
            return

        self._draw_board_bg(painter, size, ox, oy)
        self._draw_squares(painter, sq, ox, oy)
        self._draw_highlights(painter, sq, ox, oy)
        self._draw_legal_moves(painter, sq, ox, oy)
        self._draw_pieces(painter, sq, ox, oy)
        self._draw_coordinates(painter, sq, ox, oy)
        self._draw_best_move_arrow(painter, sq, ox, oy)
        self._draw_animation(painter, sq, ox, oy)

        if self.dragged_piece and self._pending_move is None:
            self._draw_dragged_piece(painter, sq)

    def _draw_board_bg(self, painter: QPainter, size: float, ox: float, oy: float) -> None:
        painter.fillRect(self.rect(), QColor(COLORS["bg"]))
        pen = QPen(QColor(COLORS["border"]), 2)
        painter.setPen(pen)
        painter.drawRect(QRectF(ox - 1, oy - 1, size + 2, size + 2))

    def _draw_squares(self, painter: QPainter, sq: float, ox: float, oy: float) -> None:
        for row in range(8):
            for col in range(8):
                f, r = (col, 7 - row) if not self.flipped else (7 - col, row)
                is_light = (f + r) % 2 != 0
                rect = QRectF(ox + col * sq, oy + row * sq, sq, sq)
                painter.fillRect(rect, self.light_color if is_light else self.dark_color)
                draw_square = chess.square(f, r)
                if draw_square in self.last_move_squares:
                    hl = self.last_move_color
                    painter.fillRect(QRectF(ox + col * sq, oy + row * sq, sq, sq), hl)

    def _draw_highlights(self, painter: QPainter, sq: float, ox: float, oy: float) -> None:
        if self.check_square is not None:
            vcol, vrow = self._to_visual(self.check_square)
            rect = QRectF(ox + vcol * sq, oy + vrow * sq, sq, sq)
            painter.fillRect(rect, self.check_color)

    def _draw_legal_moves(self, painter: QPainter, sq: float, ox: float, oy: float) -> None:
        for square in self.legal_move_squares:
            vcol, vrow = self._to_visual(square)
            cx = ox + vcol * sq + sq / 2
            cy = oy + vrow * sq + sq / 2
            piece = self.board.piece_at(square)
            if piece:
                pen = QPen(self.capture_ring_color, sq * 0.08)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(cx - sq * 0.4, cy - sq * 0.4, sq * 0.8, sq * 0.8))
            else:
                r2 = sq * 0.14
                path = QPainterPath()
                path.addEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
                painter.fillPath(path, self.dot_color)

    def _draw_pieces(self, painter: QPainter, sq: float, ox: float, oy: float) -> None:
        self._scale_pieces(sq)
        for row in range(8):
            for col in range(8):
                f, r = (col, 7 - row) if not self.flipped else (7 - col, row)
                square = chess.square(f, r)
                if square == self.dragged_square:
                    continue
                if self._pending_move and square == self._pending_move.to_square:
                    continue
                piece = self.board.piece_at(square)
                if piece:
                    key = self._get_piece_key(piece)
                    pix = self.scaled_pieces.get(key)
                    if pix:
                        x = ox + col * sq + (sq - pix.width()) / 2
                        y = oy + row * sq + (sq - pix.height()) / 2
                        painter.drawPixmap(int(x), int(y), pix)

    def _draw_dragged_piece(self, painter: QPainter, sq: float) -> None:
        if not self.dragged_piece:
            return
        self._scale_pieces(sq)
        key = self._get_piece_key(self.dragged_piece)
        pix = self.scaled_pieces.get(key)
        if pix:
            x = self.mouse_pos.x() - pix.width() / 2
            y = self.mouse_pos.y() - pix.height() / 2
            painter.setOpacity(0.85)
            painter.drawPixmap(int(x), int(y), pix)
            painter.setOpacity(1.0)

    def _draw_coordinates(self, painter: QPainter, sq: float, ox: float, oy: float) -> None:
        font = QFont("Segoe UI", int(sq * 0.12))
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        text_color = QColor(COLORS["text_dim"])
        painter.setPen(text_color)
        for i in range(8):
            if self.flipped:
                fc = chr(ord("h") - i)
            else:
                fc = chr(ord("a") + i)
            fr = 0 if self.flipped else 7
            r = QRectF(ox + i * sq, oy + fr * sq, sq, sq)
            align = (
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
                if self.flipped
                else Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
            )
            painter.drawText(r.adjusted(3, 3, -3, -3), align, fc)
        for i in range(8):
            rn = i + 1 if self.flipped else 8 - i
            rc = 7 if self.flipped else 0
            r = QRectF(ox + rc * sq, oy + i * sq, sq, sq)
            align = (
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
                if self.flipped
                else Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            )
            painter.drawText(r.adjusted(3, 3, -3, -3), align, str(rn))

    def _start_piece_animation(self, move: chess.Move, sq: float, ox: float, oy: float) -> None:
        vcol1, vrow1 = self._to_visual(move.from_square)
        vcol2, vrow2 = self._to_visual(move.to_square)
        self._anim_from_xy = (ox + vcol1 * sq + sq / 2, oy + vrow1 * sq + sq / 2)
        self._anim_to_xy = (ox + vcol2 * sq + sq / 2, oy + vrow2 * sq + sq / 2)
        self._scale_pieces(sq)
        key = self._get_piece_key(self.dragged_piece) if self.dragged_piece else None
        self._anim_pix = self.scaled_pieces.get(key) if key else None
        self._anim_progress = 0.0
        self._pending_move = move
        self.drag_cache = None
        self._anim_timer.start(16)
        self._anim_elapsed.start()

    def _animation_step(self) -> None:
        elapsed = self._anim_elapsed.elapsed()
        self._anim_progress = min(1.0, elapsed / self._anim_duration_ms)
        self.update()
        if self._anim_progress >= 1.0:
            self._anim_timer.stop()
            self._anim_progress = 0.0
            self._anim_from_xy = None
            self._anim_to_xy = None
            self._anim_pix = None
            move = self._pending_move
            self._pending_move = None
            self.dragged_piece = None
            self.dragged_square = None
            self.drag_start_pos = None
            if move:
                self.move_made.emit(move)

    def _draw_animation(self, painter: QPainter, sq: float, ox: float, oy: float) -> None:
        if self._anim_pix is None or self._anim_from_xy is None or self._anim_to_xy is None:
            return
        t = self._anim_progress
        eased = 1.0 - (1.0 - t) * (1.0 - t)
        x1, y1 = self._anim_from_xy
        x2, y2 = self._anim_to_xy
        cx = x1 + (x2 - x1) * eased
        cy = y1 + (y2 - y1) * eased
        pw = self._anim_pix.width()
        ph = self._anim_pix.height()
        painter.save()
        painter.setOpacity(0.9)
        painter.drawPixmap(int(cx - pw / 2), int(cy - ph / 2), self._anim_pix)
        painter.restore()

    def _draw_best_move_arrow(self, painter: QPainter, sq: float, ox: float, oy: float) -> None:
        if not self.best_move:
            return
        vcol1, vrow1 = self._to_visual(self.best_move.from_square)
        vcol2, vrow2 = self._to_visual(self.best_move.to_square)
        x1 = ox + vcol1 * sq + sq / 2
        y1 = oy + vrow1 * sq + sq / 2
        x2 = ox + vcol2 * sq + sq / 2
        y2 = oy + vrow2 * sq + sq / 2
        pen = QPen(self.arrow_color, sq * 0.1)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        angle = math.atan2(y2 - y1, x2 - x1)
        asz = sq * 0.22
        p1 = QPointF(x2, y2)
        p2 = QPointF(x2 - asz * math.cos(angle - 0.5), y2 - asz * math.sin(angle - 0.5))
        p3 = QPointF(x2 - asz * math.cos(angle + 0.5), y2 - asz * math.sin(angle + 0.5))
        painter.setBrush(self.arrow_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon([p1, p2, p3])

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.board.is_game_over():
            return
        pos = event.position()
        col, row, sq, ox, oy = self._board_coords(pos)
        if col is None:
            return
        square = self._to_square(col, row)
        piece = self.board.piece_at(square)
        if piece:
            if self.playable_side is not None and piece.color != self.playable_side:
                return
            self.dragged_piece = piece
            self.dragged_square = square
            self.drag_start_pos = pos.toPoint()
            self.mouse_pos = pos.toPoint()
            self.legal_move_squares = [
                m.to_square for m in self.board.legal_moves
                if m.from_square == square
            ]
            self.drag_cache = QPixmap(self.size())
            self.drag_cache.fill(Qt.GlobalColor.transparent)
            tmp = QPainter(self.drag_cache)
            tmp.setRenderHint(QPainter.RenderHint.Antialiasing)
            tmp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            sz = min(self.width(), self.height())
            sq2 = sz / 8
            ox2 = (self.width() - sz) / 2
            oy2 = (self.height() - sz) / 2
            self._draw_board_bg(tmp, sz, ox2, oy2)
            self._draw_squares(tmp, sq2, ox2, oy2)
            self._draw_highlights(tmp, sq2, ox2, oy2)
            self._draw_pieces(tmp, sq2, ox2, oy2)
            tmp.end()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if self.dragged_piece:
            self.mouse_pos = event.position().toPoint()
            self.update()
            return
        col, row, _sq, _ox, _oy = self._board_coords(event.position())
        if col is not None and not self.board.is_game_over():
            square = self._to_square(col, row)
            piece = self.board.piece_at(square)
            if piece and (self.playable_side is None or piece.color == self.playable_side):
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                return
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if not self.dragged_piece:
            return
        col, row, sq, ox, oy = self._board_coords(event.position())
        self.legal_move_squares = []
        if col is not None:
            target = self._to_square(col, row)

            legal = [
                m for m in self.board.legal_moves
                if m.from_square == self.dragged_square and m.to_square == target
            ]
            if not legal:
                self.dragged_piece = None
                self.dragged_square = None
                self.drag_cache = None
                self.drag_start_pos = None
                self.update()
                return

            legal_move = legal[0]
            if legal_move.promotion:
                piece = self.board.piece_at(self.dragged_square)
                color = piece.color if piece else legal_move.promotion
                dialog = PromotionDialog(color, self)
                if dialog.exec():
                    legal_move = chess.Move(
                        self.dragged_square, target, promotion=dialog.selected_piece
                    )
                else:
                    self.dragged_piece = None
                    self.dragged_square = None
                    self.drag_cache = None
                    self.drag_start_pos = None
                    self.update()
                    return

            self._start_piece_animation(legal_move, sq, ox, oy)
            return
        self.dragged_piece = None
        self.dragged_square = None
        self.drag_cache = None
        self.drag_start_pos = None
        self.update()
