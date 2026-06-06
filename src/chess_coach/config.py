from __future__ import annotations

import os
import socket
from typing import Any

import yaml


class ConfigError(Exception):
    pass


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "config.yaml"
)


def load_config(path: str | None = None) -> dict[str, Any]:
    target = path or DEFAULT_CONFIG_PATH
    if not os.path.exists(target):
        raise ConfigError(f"Config file not found at {target}")
    try:
        with open(target, "r") as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        raise ConfigError(f"Failed to load config: {e}") from e
    if not cfg:
        raise ConfigError(f"Config file is empty at {target}")
    if "engine" not in cfg:
        raise ConfigError("Missing 'engine' section in config")
    if "display" in cfg:
        disp = cfg["display"]
        for key in ("dark_square", "light_square", "arrow_color", "highlight_color",
                     "check_color", "dot_color", "capture_ring_color", "last_move_color"):
            val = disp.get(key)
            if val is not None and not isinstance(val, str):
                raise ConfigError(f"display.{key} must be a hex string, got {type(val).__name__}")
        opacity = disp.get("arrow_opacity")
        if opacity is not None and (isinstance(opacity, bool) or not isinstance(opacity, (int, float))):
            raise ConfigError(f"display.arrow_opacity must be a number, got {type(opacity).__name__}")
    _validate_humanizer(cfg)
    return cfg


def _validate_humanizer(cfg: dict) -> None:
    h = cfg.get("humanizer")
    if h is None:
        return
    if not isinstance(h, dict):
        raise ConfigError("humanizer section must be a mapping")
    personality = h.get("personality")
    if personality is not None:
        from chess_coach.personality import PersonalityType
        try:
            PersonalityType(personality.lower() if isinstance(personality, str) else personality)
        except ValueError as e:
            raise ConfigError(f"humanizer.personality invalid: {personality!r}") from e
    elo = h.get("target_elo")
    if elo is not None and (not isinstance(elo, int) or elo < 400 or elo > 2800):
        raise ConfigError(f"humanizer.target_elo must be int 400-2800, got {elo!r}")
    for key in ("maia_weight", "personality_weight", "engine_weight", "style_consistency", "simulated_think_time", "blend_top_n", "temperature"):
        val = h.get(key)
        if val is None:
            continue
        if key in ("simulated_think_time",):
            if not isinstance(val, bool):
                raise ConfigError(f"humanizer.{key} must be bool, got {type(val).__name__}")
        elif key == "blend_top_n":
            if not isinstance(val, int) or val < 2 or val > 20:
                raise ConfigError(f"humanizer.{key} must be int 2-20, got {val!r}")
        elif key == "temperature":
            if not isinstance(val, (int, float)) or val < 0.1 or val > 3.0:
                raise ConfigError(f"humanizer.{key} must be 0.1-3.0, got {val!r}")
        else:
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                raise ConfigError(f"humanizer.{key} must be 0.0-1.0, got {val!r}")
    maia = h.get("maia")
    if maia is not None:
        if not isinstance(maia, dict):
            raise ConfigError("humanizer.maia must be a mapping")
        for key in ("enabled", "auto_download"):
            if key in maia and not isinstance(maia[key], bool):
                raise ConfigError(f"humanizer.maia.{key} must be bool, got {type(maia[key]).__name__}")
        if "elo" in maia and (not isinstance(maia["elo"], int) or maia["elo"] < 600 or maia["elo"] > 2800):
            raise ConfigError(f"humanizer.maia.elo must be 600-2800, got {maia['elo']!r}")


def find_free_port(start: int = 8000) -> tuple["socket.socket", int]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", start))
        return sock, start
    except OSError:
        pass
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 0))
    port = sock.getsockname()[1]
    return sock, port


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
