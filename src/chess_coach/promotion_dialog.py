from __future__ import annotations

import os
from PyQt6.QtWidgets import QDialog, QGridLayout, QPushButton
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize
import chess

_HERE = os.path.dirname(os.path.abspath(__file__))
_IMG = os.path.join(_HERE, "..", "..", "static", "img", "chesspieces", "wikipedia")

_PIECE_TYPES: list[int] = [
    chess.QUEEN,
    chess.ROOK,
    chess.BISHOP,
    chess.KNIGHT,
]


class PromotionDialog(QDialog):
    def __init__(self, color: chess.Color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Promotion")
        self.setModal(True)
        self.setFixedSize(320, 88)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.selected_piece: int = chess.QUEEN
        self._setup_ui(color)

    def _setup_ui(self, color: chess.Color) -> None:
        prefix = "w" if color == chess.WHITE else "b"
        layout = QGridLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        for i, pt in enumerate(_PIECE_TYPES):
            btn = QPushButton(self)
            names = {
                chess.QUEEN: "Q",
                chess.ROOK: "R",
                chess.BISHOP: "B",
                chess.KNIGHT: "N",
            }
            path = os.path.join(_IMG, f"{prefix}{names[pt]}.png")
            pix = QPixmap(path)
            if not pix.isNull():
                btn.setIcon(QIcon(pix))
                btn.setIconSize(QSize(56, 56))
            btn.setFixedSize(72, 72)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0d9b5;
                    border: 2px solid #b58863;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #fff3d6;
                    border-color: #58a6ff;
                }
            """)
            btn.clicked.connect(lambda checked, t=pt: self._select(t))
            layout.addWidget(btn, 0, i)

    def _select(self, piece_type: int) -> None:
        self.selected_piece = piece_type
        self.accept()
