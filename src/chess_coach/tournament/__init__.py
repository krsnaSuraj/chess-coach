"""Tournament schedulers: arena, swiss, bracket."""
from __future__ import annotations

from .arena import (
    ArenaPairing,
    ArenaPlayer,
    ArenaRound,
    ArenaTournament,
    simulate_arena,
)
from .swiss import (
    SwissPairing,
    SwissPlayer,
    SwissRound,
    SwissTournament,
    simulate_swiss,
)
from .bracket import (
    Bracket,
    BracketMatch,
    BracketPlayer,
    build_double_elim,
    build_single_elim,
)

__all__ = [
    # arena
    "ArenaPairing",
    "ArenaPlayer",
    "ArenaRound",
    "ArenaTournament",
    "simulate_arena",
    # swiss
    "SwissPairing",
    "SwissPlayer",
    "SwissRound",
    "SwissTournament",
    "simulate_swiss",
    # bracket
    "Bracket",
    "BracketMatch",
    "BracketPlayer",
    "build_double_elim",
    "build_single_elim",
]
