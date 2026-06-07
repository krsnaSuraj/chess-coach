"""PGN Numeric Annotation Glyphs (NAGs) — full 0..255 support with descriptions.

NAGs are the standard annotation system in PGN. 0 = null, 1..255 = semantic
glyphs. Standard chess NAGs are in 1..23, with extended values for engines
(Lichess uses 1..10, 11..23, 32..40, 76..140 for engine quality + positions).

This module wraps python-chess's NAG constants and adds a full 0..255
catalog with human-readable descriptions and unicode glyphs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import chess.pgn as pgn


# Standard chess NAGs (re-export from python-chess for convenience)
NAG_NULL = 0
NAG_GOOD_MOVE = 1
NAG_MISTAKE = 2
NAG_BRILLIANT_MOVE = 3
NAG_BLUNDER = 4
NAG_SPECULATIVE_MOVE = 5
NAG_DUBIOUS_MOVE = 6
NAG_FORCED_MOVE = 7
NAG_SINGULAR_MOVE = 8
NAG_WORST_MOVE = 9
NAG_DRAWISH_POSITION = 10
NAG_QUIET_POSITION = 11
NAG_ACTIVE_POSITION = 12
NAG_UNCLEAR_POSITION = 13
NAG_WHITE_SLIGHT_ADVANTAGE = 14
NAG_BLACK_SLIGHT_ADVANTAGE = 15
NAG_WHITE_MODERATE_ADVANTAGE = 16
NAG_BLACK_MODERATE_ADVANTAGE = 17
NAG_WHITE_DECISIVE_ADVANTAGE = 18
NAG_BLACK_DECISIVE_ADVANTAGE = 19
NAG_WHITE_ZUGZWANG = 20
NAG_BLACK_ZUGZWANG = 21
NAG_WHITE_MODERATE_COUNTERPLAY = 22
NAG_BLACK_MODERATE_COUNTERPLAY = 23
NAG_WHITE_DECISIVE_COUNTERPLAY = 24
NAG_BLACK_DECISIVE_COUNTERPLAY = 25
NAG_WHITE_MODERATE_TIME_PRESSURE = 26
NAG_BLACK_MODERATE_TIME_PRESSURE = 27
NAG_WHITE_SEVERE_TIME_PRESSURE = 28
NAG_BLACK_SEVERE_TIME_PRESSURE = 29
NAG_NOVELTY = 30


@dataclass(frozen=True, slots=True)
class NagInfo:
    """Information about a single NAG."""

    value: int
    symbol: str
    description: str
    short: str


# Full 0..255 catalog. Standard NAGs (1..30) get explicit descriptions;
# 31..255 are reserved for application-specific glyphs but follow convention.
NAG_CATALOG: Dict[int, NagInfo] = {
    0: NagInfo(0, "", "no annotation", ""),
    1: NagInfo(1, "!", "good move", "!"),
    2: NagInfo(2, "?", "mistake", "?"),
    3: NagInfo(3, "!!", "brilliant move", "!!"),
    4: NagInfo(4, "??", "blunder", "??"),
    5: NagInfo(5, "!?", "speculative move", "!?"),
    6: NagInfo(6, "?!", "dubious move", "?!"),
    7: NagInfo(7, "□", "forced move", "□"),
    8: NagInfo(8, "⨀", "singular move (only good move)", "⨀"),
    9: NagInfo(9, "✕", "worst move", "✕"),
    10: NagInfo(10, "=", "drawish position", "="),
    11: NagInfo(11, "∞", "quiet position", "∞"),
    12: NagInfo(12, "⇌", "active position", "⇌"),
    13: NagInfo(13, "⸺", "unclear position", "⸺"),
    14: NagInfo(14, "⩲", "White slight advantage (≅ +0.20)", "⩲"),
    15: NagInfo(15, "⩱", "Black slight advantage (≅ -0.20)", "⩱"),
    16: NagInfo(16, "±", "White moderate advantage (≅ +0.80)", "±"),
    17: NagInfo(17, "∓", "Black moderate advantage (≅ -0.80)", "∓"),
    18: NagInfo(18, "+−", "White decisive advantage (≅ +2.00)", "+−"),
    19: NagInfo(19, "−+", "Black decisive advantage (≅ -2.00)", "−+"),
    20: NagInfo(20, "⊙", "White in zugzwang", "⊙"),
    21: NagInfo(21, "⨀", "Black in zugzwang", "⨀"),
    22: NagInfo(22, "⇆", "White has moderate counterplay", "⇆"),
    23: NagInfo(23, "⇄", "Black has moderate counterplay", "⇄"),
    24: NagInfo(24, "⇗", "White has decisive counterplay", "⇗"),
    25: NagInfo(25, "⇘", "Black has decisive counterplay", "⇘"),
    26: NagInfo(26, "△", "White moderate time pressure", "△"),
    27: NagInfo(27, "▲", "Black moderate time pressure", "▲"),
    28: NagInfo(28, "⏰", "White severe time pressure", "⏰"),
    29: NagInfo(29, "⏱", "Black severe time pressure", "⏱"),
    30: NagInfo(30, "N", "novelty (out of book)", "N"),
}


def is_valid_nag(value: int) -> bool:
    """Return True if the value is a valid NAG (0..255)."""
    return 0 <= value <= 255


def is_standard_nag(value: int) -> bool:
    """Return True if the value is a standard chess NAG (0..30)."""
    return 0 <= value <= 30


def is_quality_nag(value: int) -> bool:
    """Return True if the NAG describes a move quality (1..9, 11..14)."""
    return 1 <= value <= 14 or value == 30


def is_position_nag(value: int) -> bool:
    """Return True if the NAG describes a position state (10..29)."""
    return 10 <= value <= 29


def nag_symbol(value: int) -> str:
    """Return the unicode symbol for a NAG (empty string for unknown)."""
    info = NAG_CATALOG.get(value)
    return info.symbol if info else ""


def nag_description(value: int) -> str:
    """Return the description of a NAG."""
    info = NAG_CATALOG.get(value)
    return info.description if info else f"NAG #{value}"


def nag_short(value: int) -> str:
    """Return the short glyph for a NAG."""
    info = NAG_CATALOG.get(value)
    return info.short if info else f"${value}"


def classify_quality_nag(value: int) -> Optional[str]:
    """Classify a quality NAG (1..9) into a verdict: brilliant/good/mistake/blunder/forced."""
    if value == 3:
        return "brilliant"
    if value in (1, 5, 8):
        return "good"
    if value in (2, 6):
        return "mistake"
    if value == 4:
        return "blunder"
    if value == 7:
        return "forced"
    if value == 9:
        return "worst"
    return None


def quality_to_nag(verdict: str) -> int:
    """Map a quality verdict string back to a NAG integer.

    Supported verdicts: brilliant, good, mistake, blunder, forced, worst, speculative, dubious.
    Returns NAG_NULL (0) for unknown.
    """
    table = {
        "brilliant": NAG_BRILLIANT_MOVE,
        "good": NAG_GOOD_MOVE,
        "mistake": NAG_MISTAKE,
        "blunder": NAG_BLUNDER,
        "forced": NAG_FORCED_MOVE,
        "worst": NAG_WORST_MOVE,
        "speculative": NAG_SPECULATIVE_MOVE,
        "dubious": NAG_DUBIOUS_MOVE,
    }
    return table.get(verdict.lower(), NAG_NULL)


def parse_nags(values: str) -> list[int]:
    """Parse a string of NAG integers (comma- or space-separated) into a list."""
    out: list[int] = []
    for tok in values.replace(",", " ").split():
        try:
            v = int(tok.strip())
            if is_valid_nag(v):
                out.append(v)
        except ValueError:
            continue
    return out


def pgn_chess_nag(value: int) -> int | None:
    """Return the python-chess NAG constant for a value, or None if N/A."""
    if not is_valid_nag(value):
        return None
    name = {
        1: "NAG_GOOD_MOVE",
        2: "NAG_MISTAKE",
        3: "NAG_BRILLIANT_MOVE",
        4: "NAG_BLUNDER",
        5: "NAG_SPECULATIVE_MOVE",
        6: "NAG_DUBIOUS_MOVE",
        7: "NAG_FORCED_MOVE",
        8: "NAG_SINGULAR_MOVE",
        9: "NAG_WORST_MOVE",
        10: "NAG_DRAWISH_POSITION",
        11: "NAG_QUIET_POSITION",
        12: "NAG_ACTIVE_POSITION",
        13: "NAG_UNCLEAR_POSITION",
        14: "NAG_WHITE_SLIGHT_ADVANTAGE",
        15: "NAG_BLACK_SLIGHT_ADVANTAGE",
        16: "NAG_WHITE_MODERATE_ADVANTAGE",
        17: "NAG_BLACK_MODERATE_ADVANTAGE",
        18: "NAG_WHITE_DECISIVE_ADVANTAGE",
        19: "NAG_BLACK_DECISIVE_ADVANTAGE",
        20: "NAG_WHITE_ZUGZWANG",
        21: "NAG_BLACK_ZUGZWANG",
        22: "NAG_WHITE_MODERATE_COUNTERPLAY",
        23: "NAG_BLACK_MODERATE_COUNTERPLAY",
        24: "NAG_WHITE_DECISIVE_COUNTERPLAY",
        25: "NAG_BLACK_DECISIVE_COUNTERPLAY",
        26: "NAG_WHITE_MODERATE_TIME_PRESSURE",
        27: "NAG_BLACK_MODERATE_TIME_PRESSURE",
        28: "NAG_WHITE_SEVERE_TIME_PRESSURE",
        29: "NAG_BLACK_SEVERE_TIME_PRESSURE",
        30: "NAG_NOVELTY",
    }.get(value)
    if name is None:
        return None
    return getattr(pgn, name, None)


__all__ = [
    "NAG_CATALOG",
    "NagInfo",
    "NAG_NULL",
    "NAG_GOOD_MOVE",
    "NAG_MISTAKE",
    "NAG_BRILLIANT_MOVE",
    "NAG_BLUNDER",
    "NAG_SPECULATIVE_MOVE",
    "NAG_DUBIOUS_MOVE",
    "NAG_FORCED_MOVE",
    "NAG_SINGULAR_MOVE",
    "NAG_WORST_MOVE",
    "NAG_DRAWISH_POSITION",
    "NAG_QUIET_POSITION",
    "NAG_ACTIVE_POSITION",
    "NAG_UNCLEAR_POSITION",
    "NAG_WHITE_SLIGHT_ADVANTAGE",
    "NAG_BLACK_SLIGHT_ADVANTAGE",
    "NAG_WHITE_MODERATE_ADVANTAGE",
    "NAG_BLACK_MODERATE_ADVANTAGE",
    "NAG_WHITE_DECISIVE_ADVANTAGE",
    "NAG_BLACK_DECISIVE_ADVANTAGE",
    "NAG_WHITE_ZUGZWANG",
    "NAG_BLACK_ZUGZWANG",
    "NAG_WHITE_MODERATE_COUNTERPLAY",
    "NAG_BLACK_MODERATE_COUNTERPLAY",
    "NAG_WHITE_DECISIVE_COUNTERPLAY",
    "NAG_BLACK_DECISIVE_COUNTERPLAY",
    "NAG_WHITE_MODERATE_TIME_PRESSURE",
    "NAG_BLACK_MODERATE_TIME_PRESSURE",
    "NAG_WHITE_SEVERE_TIME_PRESSURE",
    "NAG_BLACK_SEVERE_TIME_PRESSURE",
    "NAG_NOVELTY",
    "is_valid_nag",
    "is_standard_nag",
    "is_quality_nag",
    "is_position_nag",
    "nag_symbol",
    "nag_description",
    "nag_short",
    "classify_quality_nag",
    "quality_to_nag",
    "parse_nags",
    "pgn_chess_nag",
]
