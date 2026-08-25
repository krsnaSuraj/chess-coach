from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from chess_coach.game_controller import GameController


@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {
        "engine": {
            "path": "stockfish.exe",
            "threads": 2,
            "hash": 64,
            "movetime": 2000,
            "web_movetime": 0.15,
        },
        "display": {
            "dark_square": "#B58863",
            "light_square": "#F0D9B5",
            "arrow_color": "#00FF00",
            "arrow_opacity": 0.6,
            "highlight_color": "#FFFF64",
            "check_color": "#FF3232",
            "dot_color": "#646464",
            "capture_ring_color": "#323232",
            "last_move_color": "#FFFF64",
        },
    }


@pytest.fixture
def temp_config(tmp_path: Path, sample_config: dict[str, Any]) -> Path:
    p = tmp_path / "config.yaml"
    with open(p, "w") as f:
        yaml.dump(sample_config, f)
    return p


@pytest.fixture
def game_controller() -> GameController:
    return GameController()


@pytest.fixture
def sample_pgn() -> str:
    return (
        '[Event "Test Game"]\n'
        '[Site "?"]\n'
        '[Date "2026.05.27"]\n'
        '[Round "?"]\n'
        '[White "?"]\n'
        '[Black "?"]\n'
        '[Result "*"]\n'
        "\n"
        "1. e4 e5 2. Nf3 Nc6 3. Bb5 *\n"
    )
