"""Opening book support.

Two submodules:
- polyglot: Binary .bin book reading (uses python-chess built-in)
- eco: ECO (Encyclopaedia of Chess Openings) code database
"""
from __future__ import annotations

from .polyglot import (
    PolyglotBook,
    PolyglotEntry,
    PolyglotMove,
    read_polyglot_book,
    find_book_move,
    COMMON_OPENING_BOOKS,
    is_polyglot_book,
)
from .eco import (
    ECODatabase,
    ECOEntry,
    COMMON_ECO_CODES,
    lookup_eco,
    is_eco_line,
    ECO_CODES_BY_PREFIX,
)

__all__ = [
    "PolyglotBook",
    "PolyglotEntry",
    "PolyglotMove",
    "read_polyglot_book",
    "find_book_move",
    "COMMON_OPENING_BOOKS",
    "is_polyglot_book",
    "ECODatabase",
    "ECOEntry",
    "COMMON_ECO_CODES",
    "lookup_eco",
    "is_eco_line",
    "ECO_CODES_BY_PREFIX",
]
