from __future__ import annotations

import math
import os
from PyQt6.QtWidgets import QWidget

from chess_coach.promotion_dialog import PromotionDialog
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QPixmap,
    QPainterPath,
    QPaintEvent,
    QMouseEvent,
    QCursor,
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF, QTimer, QElapsedTimer

import chess

_HERE = os.path.dirname(os.path.abspath(__file__))
PIECE_IMAGES_DIR = os.path.join(_HERE, "..", "..", "static", "img", "chesspieces", "wikipedia")

PIECE_MAP = {
    "wP": "wP.png",
    "wN": "wN.png",
    "wB": "wB.png",
    "wR": "wR.png",
    "wQ": "wQ.png",
    "wK": "wK.png",
    "bP": "bP.png",
    "bN": "bN.png",
    "bB": "bB.png",
    "bR": "bR.png",
    "bQ": "bQ.png",
    "bK": "bK.png",
}

PIECE_TYPES = {
    chess.PAWN: "P",
    chess.KNIGHT: "N",
    chess.BISHOP: "B",
    chess.ROOK: "R",
    chess.QUEEN: "Q",
    chess.KING: "K",
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
        self.mouse_pos = QPointF()
        self._last_drag_paint = QPointF()
        self.setMouseTracking(True)
        self.setMinimumSize(280, 280)
        # Opaque: we fill the whole rect on every paint path, so Qt must not
        # clear/flash the background first (kills resize flicker). NOTE: no
        # WA_NoSystemBackground — with it, any missed region sticks BLACK;
        # without it the backing store preserves old pixels instead.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        self.flipped = False
        self.playable_side: chess.Color | None = None
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
        self.current_scale: tuple[int, int] = (0, 0)
        self._grab_offset: QPointF | None = None
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
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        # Whole-pixel buckets: live resize changes sq continuously; rescaling
        # 12 pixmaps per sub-pixel step caused the resize lag/jitter.
        key = (round(square_size), round(dpr * 100))
        if key == self.current_scale:
            return
        self.current_scale = key
        self.scaled_pieces = {}
        size = max(16, round(square_size * 0.88 * dpr))
        for key2, pix in self.raw_pieces.items():
            scaled = pix.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if dpr != 1.0:
                scaled.setDevicePixelRatio(dpr)
            self.scaled_pieces[key2] = scaled

    def _piece_logical_size(self, pix: QPixmap) -> tuple[float, float]:
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        if dpr and dpr != 1.0:
            return pix.width() / dpr, pix.height() / dpr
        return float(pix.width()), float(pix.height())

    def set_board(self, board: chess.Board, clear_arrow: bool = True) -> None:
        try:
            self.releaseMouse()
        except Exception:
            pass
        self.board = board
        if clear_arrow:
            self.best_move = None
        self.dragged_piece = None
        self.dragged_square = None
        self._grab_offset = None
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
        # ONE path for every frame (static, drag, animation): the old
        # drag-cache shortcut could blit a stale/short/transparent pixmap and
        # black out the board mid-drag. A full fresh paint costs ~2-3ms and
        # is always coherent — exactly what the static board already proves.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        size = min(self.width(), self.height())
        sq = size / 8
        ox = (self.width() - size) / 2
        oy = (self.height() - size) / 2

        self._draw_board_bg(painter, size, ox, oy)
        self._draw_squares(painter, sq, ox, oy)
        self._draw_highlights(painter, sq, ox, oy)
        self._draw_legal_moves(painter, sq, ox, oy)
        self._draw_pieces(painter, sq, ox, oy)
        self._draw_coordinates(painter, sq, ox, oy)
        self._draw_best_move_arrow(painter, sq, ox, oy)
        self._draw_animation(painter, sq, ox, oy)

        if self.dragged_piece and self._pending_move is None:
            self._draw_dragged_piece(painter, sq, ox, oy)

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
                        lw, lh = self._piece_logical_size(pix)
                        x = ox + col * sq + (sq - lw) / 2.0
                        y = oy + row * sq + (sq - lh) / 2.0
                        painter.drawPixmap(QPointF(x, y), pix)

    def _draw_dragged_piece(
        self, painter: QPainter, sq: float, ox: float = 0.0, oy: float = 0.0
    ) -> None:
        if not self.dragged_piece:
            return
        self._scale_pieces(sq)
        key = self._get_piece_key(self.dragged_piece)
        pix = self.scaled_pieces.get(key)
        if pix:
            lw, lh = self._piece_logical_size(pix)
            if self._grab_offset is not None:
                x = self.mouse_pos.x() - self._grab_offset.x()
                y = self.mouse_pos.y() - self._grab_offset.y()
            else:
                x = self.mouse_pos.x() - lw / 2.0
                y = self.mouse_pos.y() - lh / 2.0
            # Clamp the dragged piece inside the widget: an off-board cursor
            # must never spray ghosts outside the board area.
            size = min(self.width(), self.height())
            if size > 0:
                x = min(max(x, -lw / 2.0), self.width() - lw / 2.0)
                y = min(max(y, -lh / 2.0), self.height() - lh / 2.0)
            # Clip strictly to the board square area as well.
            painter.save()
            if size > 0:
                painter.setClipRect(QRectF(ox, oy, size, size))
            # Lift + soft shadow: hides edge tearing and reads as "picked up".
            lift = 1.06
            dw, dh = lw * lift, lh * lift
            painter.setOpacity(0.35)
            painter.drawPixmap(
                QRectF(x + (lw - dw) / 2.0 + 2.0, y + (lh - dh) / 2.0 + 4.0, dw, dh),
                pix,
                QRectF(0, 0, pix.width(), pix.height()),
            )
            painter.setOpacity(0.95)
            painter.drawPixmap(
                QRectF(x + (lw - dw) / 2.0, y + (lh - dh) / 2.0, dw, dh),
                pix,
                QRectF(0, 0, pix.width(), pix.height()),
            )
            painter.restore()

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
        lw, lh = self._piece_logical_size(self._anim_pix)
        painter.save()
        painter.setOpacity(0.9)
        painter.drawPixmap(QPointF(cx - lw / 2.0, cy - lh / 2.0), self._anim_pix)
        painter.restore()

    def _draw_best_move_arrow(self, painter: QPainter, sq: float, ox: float, oy: float) -> None:
        if not self.best_move:
            return
        vcol1, vrow1 = self._to_visual(self.best_move.from_square)
        vcol2, vrow2 = self._to_visual(self.best_move.to_square)
        x1 = ox + vcol1 * sq + sq / 2.0
        y1 = oy + vrow1 * sq + sq / 2.0
        x2 = ox + vcol2 * sq + sq / 2.0
        y2 = oy + vrow2 * sq + sq / 2.0
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return
        ux, uy = dx / length, dy / length
        # Shorten shaft so head sits on square edge, not buried under the piece
        head_len = max(12.0, sq * 0.30)
        inset_start = sq * 0.26
        inset_end = sq * 0.28 + head_len * 0.9
        sx, sy = x1 + ux * inset_start, y1 + uy * inset_start
        ex, ey = x2 - ux * inset_end, y2 - uy * inset_end
        line_w = max(3.0, min(6.0, sq * 0.07))
        # casing (dark, opaque) then core (bright) for contrast on any square
        casing = QPen(QColor(11, 14, 20, 200), line_w + 2.5)
        casing.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(casing)
        painter.drawLine(QPointF(sx, sy), QPointF(ex, ey))
        pen = QPen(self.arrow_color, line_w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(sx, sy), QPointF(ex, ey))
        angle = math.atan2(uy, ux)
        half = 0.42
        p1 = QPointF(ex + ux * head_len * 0.15, ey + uy * head_len * 0.15)
        p2 = QPointF(
            ex - head_len * math.cos(angle - half),
            ey - head_len * math.sin(angle - half),
        )
        p3 = QPointF(
            ex - head_len * math.cos(angle + half),
            ey - head_len * math.sin(angle + half),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(11, 14, 20, 200))
        painter.drawPolygon([p1, p2, p3])  # type: ignore[arg-type, call-overload]
        # shrink core head slightly so casing rims it
        cxp = (p1.x() + p2.x() + p3.x()) / 3.0
        cyp = (p1.y() + p2.y() + p3.y()) / 3.0
        shrink = 0.82
        q1 = QPointF(cxp + (p1.x() - cxp) * shrink, cyp + (p1.y() - cyp) * shrink)
        q2 = QPointF(cxp + (p2.x() - cxp) * shrink, cyp + (p2.y() - cyp) * shrink)
        q3 = QPointF(cxp + (p3.x() - cxp) * shrink, cyp + (p3.y() - cyp) * shrink)
        painter.setBrush(self.arrow_color)
        painter.drawPolygon([q1, q2, q3])  # type: ignore[arg-type, call-overload]

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None or event.button() != Qt.MouseButton.LeftButton:
            return
        if self.board.is_game_over():
            return
        if self._pending_move:
            return
        pos = event.position()
        col, row, sq, ox, oy = self._board_coords(pos)
        if col is None or row is None:
            return
        square = self._to_square(col, row)
        piece = self.board.piece_at(square)
        if piece:
            if self.playable_side is not None and piece.color != self.playable_side:
                return
            self.dragged_piece = piece
            self.dragged_square = square
            self.mouse_pos = QPointF(pos)
            self._last_drag_paint = QPointF(pos)
            # Grab offset so piece doesn't jump to cursor-center on pickup
            size = min(self.width(), self.height())
            sq2 = size / 8
            ox2 = (self.width() - size) / 2
            oy2 = (self.height() - size) / 2
            vcol, vrow = self._to_visual(square)
            sq_tl_x = ox2 + vcol * sq2
            sq_tl_y = oy2 + vrow * sq2
            self._grab_offset = QPointF(pos.x() - sq_tl_x, pos.y() - sq_tl_y)
            self.legal_move_squares = [
                m.to_square for m in self.board.legal_moves if m.from_square == square
            ]
            # Grab the mouse: releases outside the window/board still reach
            # mouseReleaseEvent. Without this, an off-window release leaves
            # dragged_piece stuck forever (permanent ghost glitch).
            try:
                self.grabMouse()
            except Exception:
                pass
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if self.dragged_piece:
            self.mouse_pos = QPointF(event.position())
            # Async update(), NOT repaint(): synchronous repaint() tears on
            # Windows (half-old/half-new frames like black bottom strips).
            # update() is double-buffered; the 1px gate bounds its rate.
            dx = self.mouse_pos.x() - self._last_drag_paint.x()
            dy = self.mouse_pos.y() - self._last_drag_paint.y()
            if dx * dx + dy * dy >= 1.0:
                self._last_drag_paint = QPointF(self.mouse_pos)
                self.update()
            return
        col, row, _sq, _ox, _oy = self._board_coords(event.position())
        if col is not None and row is not None and not self.board.is_game_over():
            square = self._to_square(col, row)
            piece = self.board.piece_at(square)
            if piece and (self.playable_side is None or piece.color == self.playable_side):
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                return
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if not self.dragged_piece or event is None:
            return
        try:
            self.releaseMouse()
        except Exception:
            pass
        col, row, sq, ox, oy = self._board_coords(event.position())
        self.legal_move_squares = []
        self._grab_offset = None
        if col is not None and row is not None:
            target = self._to_square(col, row)

            legal = [
                m
                for m in self.board.legal_moves
                if m.from_square == self.dragged_square and m.to_square == target
            ]
            if not legal:
                self.dragged_piece = None
                self.dragged_square = None
                self.update()
                return

            legal_move = legal[0]
            if legal_move.promotion:
                color = self.dragged_piece.color
                dialog = PromotionDialog(color, self)
                if dialog.exec():
                    legal_move = chess.Move(
                        self.dragged_square, target, promotion=dialog.selected_piece
                    )
                else:
                    self.dragged_piece = None
                    self.dragged_square = None
                    self.update()
                    return

            self._start_piece_animation(legal_move, sq, ox, oy)
            return
        self.dragged_piece = None
        self.dragged_square = None
        self.update()
