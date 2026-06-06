"""Lichess SQL cache with TTL.

Stores Opening Explorer responses in a local SQLite DB keyed by query.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def default_cache_path() -> Path:
    return Path(os.environ.get("CHESS_COACH_CACHE", str(Path.home() / ".chess_coach" / "lichess_cache.sqlite")))


class LichessCache:
    """SQLite-backed TTL cache for Lichess responses."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else default_cache_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with a short timeout to avoid file lock issues on Windows."""
        # 5s timeout if file is locked by another connection
        conn = sqlite3.connect(self._path, timeout=5.0)
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")
            conn.commit()

    def get(self, key: str) -> Any | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
                ).fetchone()
                if row is None:
                    return None
                value_json, expires_at = row
                if expires_at < time.time():
                    conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                    conn.commit()
                    return None
                return json.loads(value_json)
        except sqlite3.Error as e:
            logger.debug("Cache get failed: %s", e)
            return None

    def set(self, key: str, value: Any, ttl_s: int = 259200) -> None:
        try:
            data = json.dumps(value, default=_default_json)
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                    (key, data, int(time.time()) + ttl_s),
                )
                conn.commit()
        except (sqlite3.Error, TypeError) as e:
            logger.debug("Cache set failed: %s", e)

    def clear(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM cache")
                conn.commit()
        except sqlite3.Error as e:
            logger.debug("Cache clear failed: %s", e)

    def stats(self) -> dict[str, int]:
        try:
            with self._connect() as conn:
                total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                expired = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE expires_at < ?", (int(time.time()),)
                ).fetchone()[0]
                return {"total": total, "expired": expired, "valid": total - expired}
        except sqlite3.Error:
            return {"total": 0, "expired": 0, "valid": 0}


def _default_json(obj: Any) -> Any:
    """JSON encoder for dataclass + enum support."""
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def cached(ttl_s: int = 86400) -> Callable:
    """Decorator: cache function results in LichessCache.

    Usage:
        @cached(ttl_s=3600)
        def fetch_lichess_data(fen): ...
    """
    def decorator(func: Callable) -> Callable:
        cache = LichessCache()

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"{func.__module__}.{func.__name__}:{args}:{sorted(kwargs.items())}"
            cached_val = cache.get(key)
            if cached_val is not None:
                return cached_val
            result = func(*args, **kwargs)
            try:
                cache.set(key, result, ttl_s=ttl_s)
            except Exception:  # noqa: BLE001
                pass
            return result
        return wrapper
    return decorator
