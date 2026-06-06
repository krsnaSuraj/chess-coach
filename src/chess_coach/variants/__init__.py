"""Chess variants (Lichess set).

SOTA 2026 standard (Lichess supports all of these):
  - Standard
  - Chess960 (Fischer Random)
  - Atomic
  - Antichess
  - Horde
  - King of the Hill
  - Three-check
  - Crazyhouse
"""

from chess_coach.variants.standard import STANDARD, is_standard
from chess_coach.variants.chess960 import CHESS960, random_starting_position, is_chess960
from chess_coach.variants.atomic import ATOMIC, is_atomic
from chess_coach.variants.antichess import ANTICHESS, is_antichess
from chess_coach.variants.horde import HORDE, is_horde
from chess_coach.variants.king_of_the_hill import KOTH, is_koth
from chess_coach.variants.three_check import THREE_CHECK, is_three_check
from chess_coach.variants.crazyhouse import CRAZYHOUSE, is_crazyhouse
from chess_coach.variants.registry import (
    VARIANTS,
    get_variant,
    variant_names,
    variant_by_key,
)

__all__ = [
    "STANDARD",
    "is_standard",
    "CHESS960",
    "random_starting_position",
    "is_chess960",
    "ATOMIC",
    "is_atomic",
    "ANTICHESS",
    "is_antichess",
    "HORDE",
    "is_horde",
    "KOTH",
    "is_koth",
    "THREE_CHECK",
    "is_three_check",
    "CRAZYHOUSE",
    "is_crazyhouse",
    "VARIANTS",
    "get_variant",
    "variant_names",
    "variant_by_key",
]
