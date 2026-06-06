"""Lc0 (Leela Chess Zero) v0.32.2 engine adapter.

Lc0 is the open-source reimplementation of AlphaZero, using NN evaluation.
Supports both best-play (with strong networks) and Maia-2 (human-policy) weights.

We implement only the UCI interface here. The actual binary + weights are
downloaded on first use by `chess_coach/scripts/install_deps.py`.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from chess_coach.engines.base import Engine, EngineError, EngineInfo, Evaluation

logger = logging.getLogger(__name__)

LC0_DEFAULT_OPTIONS: dict[str, Any] = {
    "Backend": "trivial",
    "Threads": 1,
    "NNCacheSize": 200000,
    "MultiPV": 1,
}


class Lc0Engine(Engine):
    """Lc0 v0.32.2 adapter. Supports all Lc0 backends (blas, cuda, dx, etc.)."""

    def __init__(self, binary: str = "lc0/lc0.exe", weights: str | None = None,
                 options: dict[str, Any] | None = None) -> None:
        self._binary = binary
        self._weights = weights
        self._options: dict[str, Any] = {**LC0_DEFAULT_OPTIONS, **(options or {})}
        if weights:
            self._options["WeightsFile"] = weights
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.RLock()
        self._ready = False
        self._version_str = "0.32.2"

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="Lc0",
            version=self._version_str,
            author="Leela Chess Zero community",
            elo_ceiling=3500,
            elo_floor=1400,
            type="lc0",
            requires=["lc0.exe", "*.pb.gz weights"],
        )

    def start(self) -> None:
        with self._lock:
            if self._proc is not None:
                return
            try:
                self._proc = subprocess.Popen(
                    [str(Path(self._binary))],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
            except FileNotFoundError as e:
                raise EngineError(f"Lc0 binary not found at {self._binary}") from e
            self._send("uci")
            self._wait_for("uciok", timeout=10.0)
            for name, value in self._options.items():
                self._send(f"setoption name {name} value {value}")
            self._send("isready")
            self._wait_for("readyok", timeout=10.0)
            self._send("ucinewgame")
            self._ready = True
            logger.info("Lc0 %s ready (weights=%s)", self._version_str, self._weights)

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
            return self._collect_best(depth)

    def _send(self, cmd: str) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write((cmd + "\n").encode())
        self._proc.stdin.flush()

    def _read_line(self, timeout: float = 30.0) -> str:
        assert self._proc is not None and self._proc.stdout is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self._proc.stdout.readline()
            if line:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    return decoded
            time.sleep(0.005)
        raise EngineError("Lc0 read timeout")

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
        raise EngineError(f"Lc0 did not respond with '{token}' within {timeout}s")

    def _collect_best(self, depth: int) -> Evaluation:
        best = Evaluation(score_cp=0, depth=depth, source_engine="Lc0")
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            line = self._read_line(timeout=0.5)
            if line.startswith("info") and "score cp" in line:
                m = re.search(r"score cp (-?\d+)", line)
                if m:
                    best.score_cp = int(m.group(1))
                m = re.search(r"score mate (-?\d+)", line)
                if m:
                    best.mate = int(m.group(1))
                m = re.search(r"depth (\d+)", line)
                if m:
                    best.depth = int(m.group(1))
                m = re.search(r"nodes (\d+)", line)
                if m:
                    best.nodes = int(m.group(1))
                m = re.search(r"nps (\d+)", line)
                if m:
                    best.nps = int(m.group(1))
                m = re.search(r"pv (.+)$", line)
                if m:
                    best.pv = m.group(1).split()
            elif line.startswith("bestmove"):
                return best
        raise EngineError("Lc0 did not produce bestmove")
