"""Variant registry + metadata for the SOTA 2026 Lichess variant set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VariantInfo:
    key: str
    name: str
    description: str
    icon: str
    supported_by_engine: bool = True
    lichess_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "supported_by_engine": self.supported_by_engine,
            "lichess_url": self.lichess_url,
        }


VARIANTS: list[VariantInfo] = [
    VariantInfo(
        key="standard",
        name="Standard",
        description="Classical chess. The default for tournaments and ratings.",
        icon="♔",
        lichess_url="https://lichess.org/variant/standard",
    ),
    VariantInfo(
        key="chess960",
        name="Chess960 (Fischer Random)",
        description="Random starting position from 960 legal setups. Castling rules adapt.",
        icon="🎲",
        lichess_url="https://lichess.org/variant/chess960",
    ),
    VariantInfo(
        key="atomic",
        name="Atomic",
        description="Captures explode; surrounding non-pawn pieces are removed.",
        icon="💥",
        supported_by_engine=False,
        lichess_url="https://lichess.org/variant/atomic",
    ),
    VariantInfo(
        key="antichess",
        name="Antichess",
        description="Goal: lose all your pieces. Forced captures apply.",
        icon="🃏",
        supported_by_engine=False,
        lichess_url="https://lichess.org/variant/antichess",
    ),
    VariantInfo(
        key="horde",
        name="Horde",
        description="White has 36 pieces vs Black's 16. Asymmetric warfare.",
        icon="🏰",
        supported_by_engine=False,
        lichess_url="https://lichess.org/variant/horde",
    ),
    VariantInfo(
        key="kingOfTheHill",
        name="King of the Hill",
        description="Get your king to the center 4 squares to win instantly.",
        icon="⛰️",
        supported_by_engine=False,
        lichess_url="https://lichess.org/variant/kingOfTheHill",
    ),
    VariantInfo(
        key="threeCheck",
        name="Three-Check",
        description="Receive 3 checks and you lose.",
        icon="✓",
        supported_by_engine=False,
        lichess_url="https://lichess.org/variant/threeCheck",
    ),
    VariantInfo(
        key="crazyhouse",
        name="Crazyhouse",
        description="Captured pieces go to your pocket; drop them on your turn.",
        icon="🌀",
        supported_by_engine=False,
        lichess_url="https://lichess.org/variant/crazyhouse",
    ),
]


def get_variant(key: str) -> VariantInfo | None:
    for v in VARIANTS:
        if v.key == key:
            return v
    return None


def variant_by_key(key: str) -> VariantInfo | None:
    return get_variant(key)


def variant_names() -> list[str]:
    return [v.name for v in VARIANTS]
