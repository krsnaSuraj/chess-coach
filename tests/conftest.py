from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import chess
import chess.engine
import pytest
import yaml
from fastapi.testclient import TestClient

from chess_coach import server
from chess_coach.game_controller import GameController


@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {
        "engine": {
            "path": "stockfish.exe",
            "threads": 2,
            "hash": 64,
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
def mock_engine() -> MagicMock:
    """Fake Stockfish: fast Cp(39) startpos-like analysis, no binary needed."""
    engine = MagicMock()
    engine.analyse.return_value = [
        {
            "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
            "score": chess.engine.PovScore(chess.engine.Cp(39), chess.WHITE),
            "depth": 18,
        },
        {
            "pv": [chess.Move.from_uci("d2d4")],
            "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            "depth": 18,
        },
    ]
    return engine


@pytest.fixture
def client(mock_engine: MagicMock):
    """TestClient with fresh global server state per test."""
    server.game_controller = GameController()
    server._move_history = []
    server._reset_for_tests()
    with patch.object(server, "get_engine", return_value=mock_engine):
        with TestClient(server.app) as c:
            yield c
