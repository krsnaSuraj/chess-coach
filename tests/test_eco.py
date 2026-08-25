from __future__ import annotations

import chess

from chess_coach.eco_data import ECO_DATABASE
from chess_coach.eco_handler import get_opening


class TestEcoDatabase:
    def test_all_entries_have_correct_length(self) -> None:
        for entry in ECO_DATABASE:
            assert len(entry) == 3, f"Bad entry: {entry!r}"

    def test_all_eco_codes_are_valid(self) -> None:
        valid_codes = {f"{letter}{n:02d}" for letter in "ABCDE" for n in range(100)}
        for eco_code, _name, _moves in ECO_DATABASE:
            assert eco_code in valid_codes, f"Invalid ECO code: {eco_code}"

    def test_all_move_strings_are_nonempty(self) -> None:
        for _eco, _name, moves in ECO_DATABASE:
            assert moves.strip(), f"Empty moves for {_eco}"

    def test_no_duplicate_entries(self) -> None:
        seen = set()
        for entry in ECO_DATABASE:
            key = (entry[0], entry[2])
            assert key not in seen, f"Duplicate: {entry[0]} {entry[2]}"
            seen.add(key)


class TestGetOpening:
    def test_no_moves_returns_none(self) -> None:
        board = chess.Board()
        assert get_opening(board) is None

    def test_ruy_lopez(self) -> None:
        board = chess.Board()
        for uci in ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]:
            board.push(chess.Move.from_uci(uci))
        result = get_opening(board)
        assert result is not None
        code, name = result
        assert code == "C60"
        assert "Ruy Lopez" in name

    def test_sicilian_najdorf(self) -> None:
        board = chess.Board()
        for uci in [
            "e2e4",
            "c7c5",
            "g1f3",
            "d7d6",
            "d2d4",
            "c5d4",
            "f3d4",
            "g8f6",
            "b1c3",
            "a7a6",
        ]:
            board.push(chess.Move.from_uci(uci))
        result = get_opening(board)
        assert result is not None
        code, name = result
        assert code == "B90"
        assert "Najdorf" in name

    def test_longest_match_wins(self) -> None:
        board = chess.Board()
        for uci in ["d2d4", "g8f6", "c2c4", "e7e6", "g1f3", "b7b6"]:
            board.push(chess.Move.from_uci(uci))
        result = get_opening(board)
        assert result is not None
        code, name = result
        assert code == "E12"

    def test_french_defense(self) -> None:
        board = chess.Board()
        for uci in ["e2e4", "e7e6", "d2d4", "d7d5"]:
            board.push(chess.Move.from_uci(uci))
        result = get_opening(board)
        assert result is not None
        code, name = result
        assert code == "C00"

    def test_french_advance(self) -> None:
        board = chess.Board()
        for uci in ["e2e4", "e7e6", "d2d4", "d7d5", "e4e5"]:
            board.push(chess.Move.from_uci(uci))
        result = get_opening(board)
        assert result is not None
        code, name = result
        assert code == "C02"

    def test_caro_kann(self) -> None:
        board = chess.Board()
        for uci in ["e2e4", "c7c6", "d2d4", "d7d5"]:
            board.push(chess.Move.from_uci(uci))
        result = get_opening(board)
        assert result is not None
        code, name = result
        assert code == "B12"

    def test_italian_game(self) -> None:
        board = chess.Board()
        for uci in ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]:
            board.push(chess.Move.from_uci(uci))
        result = get_opening(board)
        assert result is not None
        code, name = result
        assert code == "C50"

    def test_unknown_opening_returns_none(self) -> None:
        board = chess.Board()
        for uci in ["h2h4", "h7h5"]:
            board.push(chess.Move.from_uci(uci))
        result = get_opening(board)
        assert result is None
