"""PGN variation (RAV) tree helpers.

PGN variations are encoded as RAV (Recursive Annotation Variation) blocks,
surrounded by '(' and ')'. python-chess represents these as a tree of
`chess.pgn.GameNode` objects, where the mainline is the first child and
additional children are variations.

This module provides helpers to:
- iterate over a node's variations
- build a structured tree
- count variations per ply
- find the longest forced line
- search for a move across all variations
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Optional

import chess
import chess.pgn as pgn


@dataclass
class VariationNode:
    """Structured view of a PGN node + its variations."""

    move: Optional[chess.Move] = None
    san: Optional[str] = None
    comment: str = ""
    nags: List[int] = field(default_factory=list)
    variations: List["VariationNode"] = field(default_factory=list)


def collect_variations(node: pgn.GameNode) -> List[VariationNode]:
    """Convert a python-chess GameNode into a list of VariationNode children."""
    result: List[VariationNode] = []
    for child in node.variations:
        result.append(
            VariationNode(
                move=child.move,
                san=child.san() if child.move is not None else None,
                comment=node.comment if hasattr(node, "comment") else "",
                nags=list(node.nags) if hasattr(node, "nags") else [],
                variations=collect_variations(child),
            )
        )
    return result


def variation_count(node: pgn.GameNode) -> int:
    """Count total sub-variations (siblings of the mainline) under a node.

    Excludes the mainline itself — only counts alternate branches.
    """
    if not hasattr(node, "variations"):
        return 0
    total = 0
    children = list(node.variations)
    if not children:
        return 0
    # The first variation in a Game/Node is the mainline; only count siblings.
    for child in children[1:]:
        total += 1 + variation_count(child)
    # Recurse into the mainline to count nested variations
    total += variation_count(children[0])
    return total


def longest_forced_line(game: pgn.Game) -> List[chess.Move]:
    """Find the longest sequence of unique moves in the mainline (no variations)."""
    moves: List[chess.Move] = []
    node = game
    while node.variations:
        first = node.variations[0]
        if first.move is None:
            break
        moves.append(first.move)
        node = first
    return moves


def all_moves_in_variations(node: pgn.GameNode) -> Iterator[chess.Move]:
    """Yield every move in every variation tree under a node, depth-first."""
    if hasattr(node, "variations"):
        for child in node.variations:
            if child.move is not None:
                yield child.move
            yield from all_moves_in_variations(child)


def find_move_san(node: pgn.GameNode, target_san: str) -> Optional[pgn.GameNode]:
    """Find a node whose SAN equals target_san, searching depth-first from node."""
    if hasattr(node, "variations"):
        for child in node.variations:
            if child.move is not None and child.san() == target_san:
                return child
            found = find_move_san(child, target_san)
            if found is not None:
                return found
    return None


def find_move_uci(node: pgn.GameNode, target_uci: str) -> Optional[pgn.GameNode]:
    """Find a node whose UCI equals target_uci, searching depth-first from node."""
    if hasattr(node, "variations"):
        for child in node.variations:
            if child.move is not None and child.move.uci() == target_uci:
                return child
            found = find_move_uci(child, target_uci)
            if found is not None:
                return found
    return None


def ply_count(node: pgn.GameNode) -> int:
    """Count number of plies (half-moves) in the mainline from this node."""
    count = 0
    while hasattr(node, "variations") and node.variations:
        first = node.variations[0]
        if first.move is None:
            break
        count += 1
        node = first
    return count


def total_ply_count(game: pgn.Game) -> int:
    """Total plies in the mainline (start to end)."""
    return ply_count(game)


def has_variations(game: pgn.Game) -> bool:
    """True if any variation exists anywhere in the game tree."""
    return variation_count(game) > 0


def variation_depth_at(node: pgn.GameNode) -> int:
    """Minimum number of mainline plies from `node` to reach a sibling variation.

    0 if `node` itself has a sibling variation, 1 if its mainline child has
    one, etc. Returns 0 when no variations exist anywhere under the node.
    """
    if not hasattr(node, "variations") or not node.variations:
        return 0
    children = list(node.variations)
    # If this node has a sibling variation (more than one variation), return 0.
    if len(children) > 1:
        return 0
    # Otherwise, recurse into the mainline child and add 1.
    return 1 + variation_depth_at(children[0])


def mainline_with_indices(game: pgn.Game) -> List[tuple[int, chess.Move, str]]:
    """Return list of (ply_number, move, san) for the mainline only."""
    board = game.board()
    out: List[tuple[int, chess.Move, str]] = []
    for ply, node in enumerate(game.mainline()):
        move = node.move
        if move is None:
            continue
        san = board.san(move)
        out.append((ply, move, san))
        board.push(move)
    return out


def trim_to_ply(game: pgn.Game, max_ply: int) -> pgn.Game:
    """Return a new game truncated to at most max_ply half-moves on the mainline."""
    new_game = pgn.Game()
    new_game.headers.update(game.headers)
    board = new_game.board()
    node = new_game
    for ply, mv in enumerate(longest_forced_line(game)):
        if ply >= max_ply:
            break
        if mv not in board.legal_moves:
            break
        node = node.add_variation(mv)
        board.push(mv)
    return new_game


__all__ = [
    "VariationNode",
    "collect_variations",
    "variation_count",
    "longest_forced_line",
    "all_moves_in_variations",
    "find_move_san",
    "find_move_uci",
    "ply_count",
    "total_ply_count",
    "has_variations",
    "variation_depth_at",
    "mainline_with_indices",
    "trim_to_ply",
]
