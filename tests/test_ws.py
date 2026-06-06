"""Tests for WebSocket layer (Phase K)."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from chess_coach.ws.protocol import (
    WsMessage,
    AnalysisUpdate,
    GameState,
    ToastMessage,
    SoundEvent,
    EvalLine,
    MessageType,
)
from chess_coach.ws.server import WsBroadcaster
from chess_coach.ws.client import WsClient, MockWsClient


class TestWsMessage:
    def test_construction(self) -> None:
        msg = WsMessage(type=MessageType.PING)
        assert msg.v == 1
        assert msg.type == MessageType.PING

    def test_to_json(self) -> None:
        msg = WsMessage(type=MessageType.PING, data={"a": 1})
        j = msg.to_json()
        d = json.loads(j)
        assert d["type"] == "ping"
        assert d["a"] == 1
        assert d["v"] == 1

    def test_from_json(self) -> None:
        raw = json.dumps({"type": "pong", "v": 1, "ts": 100, "echo": "hi"})
        msg = WsMessage.from_json(raw)
        assert msg.type == MessageType.PONG
        assert msg.data["echo"] == "hi"
        assert msg.ts == 100


class TestEvalLine:
    def test_to_dict(self) -> None:
        line = EvalLine(
            multipv=1, depth=20, score_cp=50, mate=None,
            pv=["e2e4", "e7e5"], wdl=(600, 200, 200), engine="SF18",
        )
        d = line.to_dict()
        assert d["multipv"] == 1
        assert d["depth"] == 20
        assert d["score_cp"] == 50
        assert d["pv"] == ["e2e4", "e7e5"]


class TestAnalysisUpdate:
    def test_to_message(self) -> None:
        au = AnalysisUpdate(
            fen="startpos", lines=[EvalLine(1, 20, 50, None, ["e2e4"])],
            best_move="e2e4", classification="best", accuracy=95.0, depth=20,
        )
        msg = au.to_message()
        assert msg.type == MessageType.ANALYSIS_UPDATE
        assert msg.data["fen"] == "startpos"
        assert msg.data["best_move"] == "e2e4"
        assert msg.data["accuracy"] == 95.0


class TestGameState:
    def test_to_message(self) -> None:
        gs = GameState(
            fen="startpos", turn="white", is_check=False, is_checkmate=False,
            is_stalemate=False, is_game_over=False, legal_moves=["e2e4"],
            ply=0, pgn_moves=[],
        )
        msg = gs.to_message()
        assert msg.type == MessageType.GAME_STATE
        assert msg.data["turn"] == "white"


class TestToastMessage:
    def test_to_message(self) -> None:
        t = ToastMessage(severity="info", title="Hi", body="World")
        msg = t.to_message()
        assert msg.type == MessageType.TOAST
        assert msg.data["severity"] == "info"


class TestSoundEvent:
    def test_to_message(self) -> None:
        s = SoundEvent(sfx="move", theme="midnight", pan=0.5)
        msg = s.to_message()
        assert msg.type == MessageType.SOUND
        assert msg.data["sfx"] == "move"


class TestWsBroadcaster:
    def test_register_unregister_sync(self) -> None:
        """Test the broadcaster using a synchronous wrapper.

        We avoid real asyncio here so the test works without pytest-asyncio.
        The async logic is exercised in test_broadcast_to_clients via asyncio.run.
        """
        import asyncio
        b = WsBroadcaster()
        assert b.client_count == 0
        fake_ws = _FakeWs()
        asyncio.run(b.register(fake_ws))
        assert b.client_count == 1
        asyncio.run(b.unregister(fake_ws))
        assert b.client_count == 0

    def test_broadcast_to_clients(self) -> None:
        import asyncio
        b = WsBroadcaster()
        ws1 = _FakeWs()
        ws2 = _FakeWs()
        asyncio.run(b.register(ws1))
        asyncio.run(b.register(ws2))
        msg = WsMessage(type=MessageType.PING, data={"hi": 1})
        asyncio.run(b.broadcast(msg))
        assert len(ws1.sent) == 1
        assert len(ws2.sent) == 1
        assert "ping" in ws1.sent[0]

    def test_broadcast_handles_dead_clients(self) -> None:
        import asyncio
        b = WsBroadcaster()
        good = _FakeWs()
        dead = _FakeWs(fail_on_send=True)
        asyncio.run(b.register(good))
        asyncio.run(b.register(dead))
        msg = WsMessage(type=MessageType.PING)
        asyncio.run(b.broadcast(msg))
        # Dead client should be unregistered
        assert b.client_count == 1
        assert good in b._clients


class TestMockWsClient:
    def test_connect_disconnect(self) -> None:
        c = MockWsClient()
        assert not c.connected
        c.connect()
        assert c.connected
        c.disconnect()
        assert not c.connected

    def test_send_when_disconnected(self) -> None:
        c = MockWsClient()
        assert c.send({"hi": 1}) is False

    def test_send_when_connected(self) -> None:
        c = MockWsClient()
        c.connect()
        assert c.send({"hi": 1}) is True
        assert c.sent == [{"hi": 1}]

    def test_deliver(self) -> None:
        c = MockWsClient()
        c.connect()
        c.deliver({"server": "ping"})
        assert c.received == [{"server": "ping"}]


class _FakeWs:
    """Minimal AsyncMock-compatible WebSocket for tests."""

    def __init__(self, fail_on_send: bool = False) -> None:
        self.sent: list[str] = []
        self.fail_on_send = fail_on_send

    async def send_text(self, text: str) -> None:
        if self.fail_on_send:
            raise RuntimeError("connection lost")
        self.sent.append(text)

    async def accept(self) -> None:
        pass

    async def receive_text(self) -> str:
        raise RuntimeError("not used in tests")
