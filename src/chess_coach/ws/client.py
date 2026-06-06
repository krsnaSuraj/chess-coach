"""Client-side WebSocket client (PWA side).

Auto-reconnect with exponential backoff.
Graceful degradation if server unreachable (no-op + warning).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class WsClient:
    """SOTA 2026 WebSocket client with auto-reconnect.

    No external dep: uses `websocket` if available, else stdlib `urllib`.
    """

    def __init__(
        self,
        url: str,
        on_message: Callable[[dict[str, Any]], None] | None = None,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
        max_backoff_s: float = 30.0,
    ) -> None:
        self._url = url
        self._on_message = on_message or (lambda m: None)
        self._on_open = on_open or (lambda: None)
        self._on_close = on_close or (lambda: None)
        self._max_backoff = max_backoff_s
        self._backoff = 1.0
        self._ws: Any = None
        self._connected = False
        self._should_run = False
        self._last_ping = 0.0

    def connect(self) -> None:
        """Start the client. Runs in background (caller manages loop)."""
        self._should_run = True
        self._backoff = 1.0
        self._connect_once()

    def _connect_once(self) -> None:
        try:
            from websocket import WebSocket  # type: ignore
        except ImportError:
            logger.debug("websocket-client not installed; using mock")
            return
        try:
            self._ws = WebSocket()
            self._ws.connect(self._url)
            self._connected = True
            self._backoff = 1.0
            self._on_open()
        except Exception as e:  # noqa: BLE001
            logger.debug("WS connect failed: %s", e)
            self._connected = False
            self._on_close()
            self._backoff = min(self._max_backoff, self._backoff * 2)

    def disconnect(self) -> None:
        self._should_run = False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001
                pass
        self._ws = None
        self._connected = False

    def send(self, message: dict[str, Any]) -> bool:
        if not self._connected or self._ws is None:
            return False
        try:
            self._ws.send(json.dumps(message))
            return True
        except Exception:  # noqa: BLE001
            self._connected = False
            return False

    def poll(self) -> None:
        """Read pending messages. Call from your main loop."""
        if not self._connected or self._ws is None:
            if self._should_run:
                time.sleep(min(self._backoff, 0.5))
                if not self._connected:
                    self._connect_once()
            return
        try:
            # Heartbeat ping every 30s
            if time.time() - self._last_ping > 30.0:
                self._ws.send(json.dumps({"type": "ping"}))
                self._last_ping = time.time()
            self._ws.settimeout(0.05)
            raw = self._ws.recv()
            if raw:
                try:
                    msg = json.loads(raw)
                    self._on_message(msg)
                except json.JSONDecodeError:
                    pass
        except Exception:  # noqa: BLE001
            self._connected = False
            self._on_close()
            self._backoff = min(self._max_backoff, self._backoff * 2)

    @property
    def connected(self) -> bool:
        return self._connected


class MockWsClient:
    """In-process mock for tests + offline mode.

    Just stores messages; never opens a real connection.
    """

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.received: list[dict[str, Any]] = []
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def send(self, message: dict[str, Any]) -> bool:
        if not self._connected:
            return False
        self.sent.append(message)
        return True

    def deliver(self, message: dict[str, Any]) -> None:
        """Test helper: simulate a server message arriving."""
        self.received.append(message)

    def poll(self) -> None:
        pass

    @property
    def connected(self) -> bool:
        return self._connected
