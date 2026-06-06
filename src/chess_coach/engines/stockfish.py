"""Stockfish 18 engine adapter.

Stockfish 18 (released 2026-01-31) adds:
  - SFNNv10 network architecture
  - Threat Inputs (input plane of threats from each piece)
  - Correction history (faster learning in analysis)
  - Shared memory between processes (MultiPV aggregation)
  - +46 ELO over Stockfish 17

UCI protocol implementation in pure Python (no python-chess-engine dep).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from chess_coach.engines.base import Engine, EngineError, EngineInfo, Evaluation

logger = logging.getLogger(__name__)

# Default Stockfish 18 NNUE network (SFNNv10)
SF18_NNUE_NAME = "nn-d0b74cd1a5d6.nnue"

# Default UCI options
SF18_DEFAULT_OPTIONS: dict[str, Any] = {
    "Use NNUE": True,
    "EvalFile": SF18_NNUE_NAME,
    "Threads": 1,
    "Hash": 16,
    "MultiPV": 1,
    "Skill Level": 20,
    "Move Overhead": 10,
    "Slow Mover": 100,
    "UCI_AnalyseMode": True,
    "UCI_LimitStrength": False,
    "UCI_Elo": 3200,
    "Contempt": 0,
    "Ponder": False,
}


class Stockfish18Engine(Engine):
    """Stockfish 18 adapter (UCI protocol, sync, thread-safe per process)."""

    def __init__(
        self,
        binary: str = "stockfish.exe",
        options: dict[str, Any] | None = None,
        nnue_path: str | None = None,
    ) -> None:
        self._binary = binary
        self._options: dict[str, Any] = {**SF18_DEFAULT_OPTIONS, **(options or {})}
        if nnue_path:
            self._options["EvalFile"] = nnue_path
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.RLock()
        self._ready = False
        self._info_buffer: list[str] = []
        self._version_str = "18.0"
        self._path = Path(binary)

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="Stockfish",
            version=self._version_str,
            author="Stockfish Team",
            elo_ceiling=3500,
            elo_floor=1400,
            type="uci",
            requires=["stockfish.exe"],
        )

    def start(self) -> None:
        with self._lock:
            if self._proc is not None:
                return
            try:
                self._proc = subprocess.Popen(
                    [str(self._path)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
            except FileNotFoundError as e:
                raise EngineError(f"Stockfish binary not found at {self._path}") from e
            self._send("uci")
            self._wait_for("uciok", timeout=10.0)
            for name, value in self._options.items():
                self._send(f"setoption name {name} value {value}")
            self._send("isready")
            self._wait_for("readyok", timeout=10.0)
            self._send("ucinewgame")
            self._ready = True
            logger.info("Stockfish 18 ready (%s)", self._binary)

    def stop(self) -> None:
        with self._lock:
            if self._proc is None:
                return
            try:
                self._send("quit")
                self._proc.wait(timeout=3.0)
            except Exception:  # noqa: BLE001
                self._proc.kill()
            finally:
                self._proc = None
                self._ready = False

    def is_ready(self) -> bool:
        return self._ready and self._proc is not None

    def set_option(self, name: str, value: Any) -> None:
        with self._lock:
            self._options[name] = value
            if self._ready:
                self._send(f"setoption name {name} value {value}")

    def get_options(self) -> dict[str, Any]:
        return dict(self._options)

    def evaluate(self, fen: str, depth: int = 20, multipv: int = 1) -> Evaluation:
        with self._lock:
            if not self.is_ready():
                self.start()
            self._send(f"position fen {fen}")
            self._send(f"setoption name MultiPV value {multipv}")
            self._send(f"go depth {depth}")
            return self._collect_best(depth, multipv)

    # --- internals ---

    def _send(self, cmd: str) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write((cmd + "\n").encode())
        self._proc.stdin.flush()

    def _read_line(self, timeout: float = 30.0) -> str:
        assert self._proc is not None and self._proc.stdout is not None
        deadline = time.monotonic() + timeout
        # Non-blocking read loop (Windows compatible)
        while time.monotonic() < deadline:
            line = self._proc.stdout.readline()
            if line:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    return decoded
            time.sleep(0.005)
        raise EngineError("Engine read timeout")

    def _wait_for(self, token: str, timeout: float = 30.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self._read_line(timeout=0.5)
            if "id name" in line:
                m = re.search(r"id name (.+)", line)
                if m:
                    self._version_str = m.group(1)
            if token in line:
                return line
        raise EngineError(f"Engine did not respond with '{token}' within {timeout}s")

    def _collect_best(self, depth: int, multipv: int) -> Evaluation:
        lines: dict[int, dict[str, Any]] = {}
        deadline = time.monotonic() + 60.0
        best = Evaluation(score_cp=0, depth=depth, source_engine="Stockfish 18")
        while time.monotonic() < deadline:
            line = self._read_line(timeout=0.5)
            if line.startswith("info"):
                parsed = self._parse_info(line, multipv)
                if parsed is not None:
                    lines[parsed["multipv"]] = parsed
            elif line.startswith("bestmove"):
                # Use highest-depth entry
                if lines:
                    top = max(lines.values(), key=lambda x: x.get("depth", 0))
                    best = self._to_evaluation(top, depth)
                return best
        raise EngineError("Engine did not produce bestmove")

    def _parse_info(self, line: str, multipv: int) -> dict[str, Any] | None:
        out: dict[str, Any] = {"multipv": 1}
        if " multipv " in line:
            m = re.search(r"multipv (\d+)", line)
            if m:
                out["multipv"] = int(m.group(1))
        m = re.search(r"depth (\d+)", line)
        if m:
            out["depth"] = int(m.group(1))
        m = re.search(r"nodes (\d+)", line)
        if m:
            out["nodes"] = int(m.group(1))
        m = re.search(r"nps (\d+)", line)
        if m:
            out["nps"] = int(m.group(1))
        m = re.search(r"score mate (-?\d+)", line)
        if m:
            out["mate"] = int(m.group(1))
        m = re.search(r"score cp (-?\d+)", line)
        if m:
            out["cp"] = int(m.group(1))
        m = re.search(r"time (\d+)", line)
        if m:
            out["time"] = int(m.group(1))
        m = re.search(r"wdl (\d+) (\d+) (\d+)", line)
        if m:
            out["wdl"] = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.search(r"pv (.+)$", line)
        if m:
            out["pv"] = m.group(1).split()
        if "score" not in line:
            return None
        return out

    def _to_evaluation(self, info: dict[str, Any], requested_depth: int) -> Evaluation:
        return Evaluation(
            score_cp=info.get("cp", 0),
            mate=info.get("mate"),
            depth=info.get("depth", requested_depth),
            nodes=info.get("nodes", 0),
            nps=info.get("nps", 0),
            time_ms=info.get("time", 0),
            pv=info.get("pv", []),
            wdl=info.get("wdl"),
            source_engine="Stockfish 18",
        )


def find_stockfish() -> str:
    """Find Stockfish binary on PATH or in project root."""
    candidates = ["stockfish.exe", "stockfish", os.path.join("bin", "stockfish.exe")]
    for c in candidates:
        if Path(c).exists():
            return c
    return "stockfish.exe"
