from __future__ import annotations

import threading
from enum import Enum

import chess


class GamePhase(Enum):
    AWAITING_COLOR = "awaiting_color"
    PLAYING = "playing"
    GAME_OVER = "game_over"


class GameController:
    def __init__(self) -> None:
        self.board = chess.Board()
        self.human_side: chess.Color | None = None
        self.game_phase: GamePhase = GamePhase.AWAITING_COLOR
        self.move_number: int = 1
        self.lock = threading.RLock()
        self.redo_stack: list[chess.Move] = []
        self.cached_coach: dict | None = None
        self.cached_fen: str | None = None

    def start_game(self, human_is_white: bool) -> None:
        with self.lock:
            self.board.reset()
            self.human_side = chess.WHITE if human_is_white else chess.BLACK
            self.move_number = 1
            self.game_phase = GamePhase.PLAYING
            self.redo_stack.clear()
            self.cached_coach = None
            self.cached_fen = None

    def record_move(self, move: chess.Move) -> None:
        with self.lock:
            self.board.push(move)
            self.redo_stack.clear()
            self.cached_coach = None
            self.cached_fen = None
            if self.board.turn == chess.WHITE:
                self.move_number += 1
            if self.board.is_game_over():
                self.game_phase = GamePhase.GAME_OVER

    def undo(self) -> str | None:
        with self.lock:
            if self.game_phase not in (GamePhase.PLAYING, GamePhase.GAME_OVER):
                return "No game in progress"
            if not self.board.move_stack:
                return "No moves to undo"
            move = self.board.pop()
            self.redo_stack.append(move)
            if self.board.turn == chess.BLACK:
                self.move_number -= 1
            if self.game_phase == GamePhase.GAME_OVER:
                self.game_phase = GamePhase.PLAYING
            self.cached_coach = None
            self.cached_fen = None
        return None

    def redo(self) -> str | None:
        with self.lock:
            if self.game_phase != GamePhase.PLAYING:
                return "No game in progress"
            if not self.redo_stack:
                return "No moves to redo"
            move = self.redo_stack.pop()
            self.board.push(move)
            if self.board.turn == chess.WHITE:
                self.move_number += 1
            if self.board.is_game_over():
                self.game_phase = GamePhase.GAME_OVER
            self.cached_coach = None
            self.cached_fen = None
        return None

    def human_move(self, move_uci: str) -> str | None:
        try:
            move = chess.Move.from_uci(move_uci)
        except Exception:
            return "Invalid move format"
        with self.lock:
            if self.game_phase != GamePhase.PLAYING:
                return "Game not in progress"
            if move not in self.board.legal_moves:
                return "Illegal move"
            self.record_move(move)
        return None

    def get_san(self, move: chess.Move) -> str:
        with self.lock:
            return self.board.san(move)

    def is_human_turn(self) -> bool:
        with self.lock:
            return (
                self.game_phase == GamePhase.PLAYING
                and self.board.turn == self.human_side
            )
