from __future__ import annotations

import chess
import chess.pgn
import io


def board_to_pgn(board: chess.Board, headers: dict[str, str] | None = None) -> str:
    game = chess.pgn.Game.from_board(board)
    if headers:
        for key, value in headers.items():
            game.headers[key] = value
    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
    return game.accept(exporter)  # type: ignore[no-any-return]


def pgn_to_moves(pgn: str) -> list[chess.Move]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("Invalid PGN")
    moves: list[chess.Move] = []
    node = game
    while node.variations:
        node = node.variations[0]  # type: ignore[assignment]
        if node.move is not None:
            moves.append(node.move)
    return moves


def replay_moves(board: chess.Board, moves: list[chess.Move]) -> chess.Board:
    b = board.copy()
    for move in moves:
        if move in b.legal_moves:
            b.push(move)
        else:
            raise ValueError(f"Illegal move {move.uci()} in replay")
    return b
