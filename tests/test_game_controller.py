from __future__ import annotations

import chess
import pytest

from chess_coach.game_controller import GameController, GamePhase


class TestGameController:
    def test_initial_state(self, game_controller: GameController):
        assert game_controller.board.turn == chess.WHITE
        assert game_controller.game_phase == GamePhase.AWAITING_COLOR
        assert game_controller.human_side is None
        assert game_controller.cached_coach is None
        assert game_controller.cached_fen is None
        assert game_controller.redo_stack == []

    def test_start_game_white(self, game_controller: GameController):
        game_controller.start_game(True)
        assert game_controller.human_side == chess.WHITE
        assert game_controller.game_phase == GamePhase.PLAYING
        assert game_controller.move_number == 1

    def test_start_game_black(self, game_controller: GameController):
        game_controller.start_game(False)
        assert game_controller.human_side == chess.BLACK
        assert game_controller.game_phase == GamePhase.PLAYING

    def test_human_move_valid(self, game_controller: GameController):
        game_controller.start_game(True)
        err = game_controller.human_move("e2e4")
        assert err is None
        assert game_controller.board.fen().startswith("rnbqkbnr/pppppppp/8/8/4P3")
        assert game_controller.game_phase == GamePhase.PLAYING

    def test_human_move_invalid_uci(self, game_controller: GameController):
        game_controller.start_game(True)
        err = game_controller.human_move("invalid")
        assert err == "Invalid move format"

    def test_human_move_illegal(self, game_controller: GameController):
        game_controller.start_game(True)
        err = game_controller.human_move("e2e5")
        assert err == "Illegal move"

    def test_human_move_before_start(self, game_controller: GameController):
        err = game_controller.human_move("e2e4")
        assert err == "Game not in progress"

    def test_start_game_resets_state(self, game_controller: GameController):
        game_controller.start_game(True)
        game_controller.human_move("e2e4")
        game_controller.start_game(True)
        assert game_controller.board.turn == chess.WHITE
        assert game_controller.game_phase == GamePhase.PLAYING
        assert game_controller.human_side == chess.WHITE
        assert len(game_controller.board.move_stack) == 0

    def test_record_move_increments_move_number(self, game_controller: GameController):
        game_controller.start_game(True)
        game_controller.human_move("e2e4")
        game_controller.human_move("e7e5")
        assert game_controller.move_number == 2

    def test_new_game_starts_again(self, game_controller: GameController):
        game_controller.start_game(True)
        game_controller.human_move("e2e4")
        game_controller.human_move("e7e5")
        game_controller.start_game(False)
        assert game_controller.human_side == chess.BLACK
        assert len(game_controller.board.move_stack) == 0

    def test_detect_checkmate(self, game_controller: GameController):
        game_controller.start_game(True)
        game_controller.human_move("f2f3")
        game_controller.human_move("e7e5")
        game_controller.human_move("g2g4")
        game_controller.human_move("d8h4")
        assert game_controller.board.is_checkmate()
        assert game_controller.game_phase == GamePhase.GAME_OVER


class TestUndoRedo:
    def test_undo_valid(self, game_controller: GameController):
        game_controller.start_game(True)
        game_controller.human_move("e2e4")
        err = game_controller.undo()
        assert err is None
        assert len(game_controller.board.move_stack) == 0

    def test_undo_empty_stack(self, game_controller: GameController):
        game_controller.start_game(True)
        err = game_controller.undo()
        assert err == "No moves to undo"

    def test_undo_before_start(self, game_controller: GameController):
        err = game_controller.undo()
        assert err == "No game in progress"

    def test_redo_after_undo(self, game_controller: GameController):
        game_controller.start_game(True)
        game_controller.human_move("e2e4")
        game_controller.undo()
        err = game_controller.redo()
        assert err is None
        assert len(game_controller.board.move_stack) == 1
        assert game_controller.board.fen().startswith("rnbqkbnr/pppppppp/8/8/4P3")

    def test_redo_empty_stack(self, game_controller: GameController):
        game_controller.start_game(True)
        err = game_controller.redo()
        assert err == "No moves to redo"

    def test_redo_before_start(self, game_controller: GameController):
        err = game_controller.redo()
        assert err == "No game in progress"

    def test_undo_clears_cache(self, game_controller: GameController):
        game_controller.start_game(True)
        game_controller.human_move("e2e4")
        game_controller.cached_coach = {"result": True}
        game_controller.undo()
        assert game_controller.cached_coach is None

    def test_redo_clears_cache(self, game_controller: GameController):
        game_controller.start_game(True)
        game_controller.human_move("e2e4")
        game_controller.human_move("e7e5")
        game_controller.undo()
        game_controller.redo()
        assert game_controller.cached_coach is None
        assert game_controller.cached_fen is None

    def test_undo_after_game_over_returns_to_playing(
        self, game_controller: GameController
    ):
        game_controller.start_game(True)
        game_controller.human_move("f2f3")
        game_controller.human_move("e7e5")
        game_controller.human_move("g2g4")
        game_controller.human_move("d8h4")
        assert game_controller.game_phase == GamePhase.GAME_OVER
        game_controller.undo()
        assert game_controller.game_phase == GamePhase.PLAYING


class TestGamePhase:
    def test_game_phase_values(self):
        assert GamePhase.AWAITING_COLOR.value == "awaiting_color"
        assert GamePhase.PLAYING.value == "playing"
        assert GamePhase.GAME_OVER.value == "game_over"

    def test_game_phase_unique(self):
        values = [p.value for p in GamePhase]
        assert len(values) == len(set(values))
