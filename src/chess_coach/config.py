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
    return cfg


def find_free_port(start: int = 8000) -> tuple["socket.socket", int]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", start))
        return sock, start
    except OSError:
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
