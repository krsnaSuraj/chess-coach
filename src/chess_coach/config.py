from __future__ import annotations

import logging
import os
import re
import socket
from typing import Any

import yaml

logger = logging.getLogger(__name__)


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
    eng = cfg["engine"]
    if not isinstance(eng, dict):
        raise ConfigError("'engine' section must be a mapping")
    path = eng.get("path", "stockfish.exe")
    if not isinstance(path, str) or not path.strip() or len(path) > 512:
        raise ConfigError("engine.path must be a non-empty string")
    for key, lo, hi in (
        ("threads", 1, 64),
        ("hash", 1, 8192),
        ("multipv", 1, 10),
    ):
        val = eng.get(key)
        if val is not None and (
            isinstance(val, bool) or not isinstance(val, int) or not (lo <= val <= hi)
        ):
            raise ConfigError(f"engine.{key} must be int in {lo}..{hi}")
    wm = eng.get("web_movetime")
    if wm is not None and (
        isinstance(wm, bool) or not isinstance(wm, (int, float)) or not (0.05 <= wm <= 30)
    ):
        raise ConfigError("engine.web_movetime must be seconds in 0.05..30")
    hc = cfg.get("humanizer", {})
    if hc is not None:
        if not isinstance(hc, dict):
            raise ConfigError("'humanizer' section must be a mapping")
        enabled = hc.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError("humanizer.enabled must be true/false")
        elo = hc.get("target_elo", 1500)
        if isinstance(elo, bool) or not isinstance(elo, int) or not (400 <= elo <= 3000):
            raise ConfigError("humanizer.target_elo must be int in 400..3000")
        mode = hc.get("mode", "human")
        if mode not in ("human", "must_win", "safe"):
            raise ConfigError("humanizer.mode must be human|must_win|safe")
        ei = hc.get("error_injection", {})
        if ei is not None:
            if not isinstance(ei, dict):
                raise ConfigError("humanizer.error_injection must be a mapping")
            for key in ("inaccuracy_rate", "mistake_rate", "blunder_rate"):
                val = ei.get(key)
                if val is not None and (
                    isinstance(val, bool)
                    or not isinstance(val, (int, float))
                    or not (0.0 <= val <= 1.0)
                ):
                    raise ConfigError(f"humanizer.error_injection.{key} must be 0.0..1.0")
    if "display" in cfg:
        disp = cfg["display"]
        if not isinstance(disp, dict):
            raise ConfigError("'display' section must be a mapping")
        hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
        for key in (
            "dark_square",
            "light_square",
            "arrow_color",
            "highlight_color",
            "check_color",
            "dot_color",
            "capture_ring_color",
            "last_move_color",
        ):
            val = disp.get(key)
            if val is not None and (not isinstance(val, str) or not hex_re.match(val)):
                raise ConfigError(f"display.{key} must be a hex string like #RRGGBB")
        opacity = disp.get("arrow_opacity")
        if opacity is not None and (
            isinstance(opacity, bool)
            or not isinstance(opacity, (int, float))
            or not (0.0 <= opacity <= 1.0)
        ):
            raise ConfigError("display.arrow_opacity must be a number in 0.0..1.0")
    # Environment override (Docker): CHESS_COACH_ENGINE=/app/stockfish
    env_path = os.environ.get("CHESS_COACH_ENGINE")
    if env_path and env_path.strip():
        env_path = env_path.strip()
        if len(env_path) > 512:
            raise ConfigError("CHESS_COACH_ENGINE path too long")
        eng["path"] = env_path
        logger.info("Engine path overridden by CHESS_COACH_ENGINE")
    return cfg  # type: ignore[no-any-return]


def find_free_port(start: int = 8000) -> tuple["socket.socket", int]:
    if not isinstance(start, int) or isinstance(start, bool) or not 0 <= start <= 65535:
        raise OSError(f"Invalid port: {start!r}")
    if start != 0:
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
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip  # type: ignore[no-any-return]
    except Exception:
        return "127.0.0.1"
    finally:
        try:
            s.close()
        except Exception:
            pass
