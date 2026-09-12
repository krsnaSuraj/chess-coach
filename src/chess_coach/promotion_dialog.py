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
        self.setWindowTitle("Promote to…")
        self.setModal(True)
        self.setFixedSize(320, 140)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
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
            else:
                # Text fallback so missing PNGs never yield blank buttons.
                btn.setText(names[pt])
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

        cancel = QPushButton("Cancel", self)
        cancel.setStyleSheet("""
            QPushButton {
                background-color: #161b22;
                color: #f0f6fc;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover { border-color: #58a6ff; }
        """)
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, 1, 0, 1, 4)

    def _select(self, piece_type: int) -> None:
        self.selected_piece = piece_type
        self.accept()
