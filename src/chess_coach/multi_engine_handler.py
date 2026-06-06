"""Multi-engine handler — orchestrates Stockfish + Maia in parallel.

This is the *only* class the rest of the app should talk to. It wraps:
- Stockfish 18 (analytical engine, deep search, score, PV).
- Lc0 + Maia (probability distribution over legal moves).

Design:
- Both engines run in dedicated QThreads.
- Engine output is exposed through Qt signals so the UI and humanizer can
  listen without blocking.
- A single `start_analysis(board)` kicks off both engines; partial results
  are merged and emitted.
- All public methods are SAFE: if Maia is unavailable, only SF results are
  emitted (and the corresponding `maia_update` signal is never fired).

Backward compatibility:
- The original `EngineHandler` (engine_handler.py) is preserved as a thin
  alias that delegates to `MultiEngineHandler.start_analysis` and forwards
  `analysis_update` to its own `analysis_update` signal. Existing callers
  (server.py, main_window.py) work unchanged.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Optional

import chess
import chess.engine
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from chess_coach.maia_engine import MaiaEngine, MaiaConfig

logger = logging.getLogger(__name__)


@dataclass
class MultiEngineConfig:
    sf_path: str = "stockfish.exe"
    sf_threads: int = 2                # 0 = auto-detect (capped at 4 for safety)
    sf_hash_mb: int = 64               # 0 = auto = 25% of free RAM, capped 4096
    sf_movetime_ms: int = 2000
    sf_multipv: int = 3                # top-N principal variations
    sf_show_wdl: bool = True           # UCI_ShowWDL → win/draw/loss %
    sf_analyse_mode: bool = True       # UCI_AnalyseMode
    maia: MaiaConfig | None = None
    enable_maia: bool = True


def _auto_detect_threads() -> int:
    """Auto-detect safe thread count. Capped at 4 to keep SF responsive."""
    try:
        import os as _os
        n = _os.cpu_count() or 2
        return min(4, max(1, n))
    except Exception:
        return 2


def _auto_detect_hash_mb() -> int:
    """Use 25% of free RAM, capped at 4096 MB."""
    try:
        import psutil  # type: ignore
        free_mb = psutil.virtual_memory().available // (1024 * 1024)
        return max(64, min(4096, int(free_mb * 0.25)))
    except Exception:
        return 256


class StockfishAnalysisThread(QThread):
    info_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, engine: chess.engine.SimpleEngine, board: chess.Board, movetime_s: float = 2.0) -> None:
        super().__init__()
        self.engine = engine
        self.board = board
        self.movetime_s = movetime_s
        self.is_running = True

    def run(self) -> None:
        try:
            with self.engine.analysis(self.board) as analysis:
                for info in analysis:
                    if not self.is_running:
                        break
                    self.info_received.emit(dict(info))
        except Exception as e:
            logger.error("SF analysis error: %s", e)
            self.error_occurred.emit(f"SF analysis crashed: {e}")
        finally:
            self.is_running = False

    def stop(self) -> None:
        self.is_running = False


class MaiaAnalysisThread(QThread):
    maia_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, maia: MaiaEngine, board: chess.Board) -> None:
        super().__init__()
        self.maia = maia
        self.board = board
        self.is_running = True

    def run(self) -> None:
        try:
            probs = self.maia.get_move_probabilities(self.board, top_n=10)
            self.maia_received.emit({
                "board_fen": self.board.fen(),
                "probabilities": {m.uci(): p for m, p in probs.items()},
            })
        except Exception as e:
            logger.warning("Maia analysis error: %s", e)
            self.error_occurred.emit(f"Maia error: {e}")
        finally:
            self.is_running = False

    def stop(self) -> None:
        self.is_running = False


class MultiEngineHandler(QObject):
    """Coordinates Stockfish + Maia in parallel.

    Signals:
        analysis_update(dict): merged SF info + optional maia distribution
        maia_update(dict):     Maia-only distribution (when ready)
        error_occurred(str):   any error from either engine
    """

    analysis_update = pyqtSignal(dict)
    maia_update = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: MultiEngineConfig | None = None) -> None:
        super().__init__()
        self.config = config or MultiEngineConfig()
        # Resolve 0 = auto for threads/hash
        if self.config.sf_threads <= 0:
            self.config.sf_threads = _auto_detect_threads()
        if self.config.sf_hash_mb <= 0:
            self.config.sf_hash_mb = _auto_detect_hash_mb()
        self._sf_engine: chess.engine.SimpleEngine | None = None
        self._sf_thread: StockfishAnalysisThread | None = None
        self._maia_thread: MaiaAnalysisThread | None = None
        self._pending_board: chess.Board | None = None
        self._sf_path_resolved: str = self.config.sf_path
        self._maia: Optional[MaiaEngine] = None
        self._maia_available = False
        if self.config.enable_maia and self.config.maia is not None:
            self._maia = MaiaEngine(self.config.maia)
            self._maia_available = self._maia.start()
        self._last_maia: dict = {}
        self._last_wdl: dict = {}        # {"w": 33, "d": 50, "l": 17}
        self._last_pvs: list[dict] = []  # list of {multipv, score, pv, depth}

    @property
    def maia_available(self) -> bool:
        return self._maia_available

    @property
    def maia(self) -> Optional[MaiaEngine]:
        return self._maia

    @property
    def last_maia_distribution(self) -> dict:
        return self._last_maia

    @property
    def last_wdl(self) -> dict:
        """Most recent WDL: {w: int, d: int, l: int} in permille (0-1000)."""
        return self._last_wdl

    @property
    def last_pvs(self) -> list[dict]:
        """List of per-MultiPV entries: {multipv, depth, score_cp, pv: [uci,...]}."""
        return self._last_pvs

    def start_sf(self) -> None:
        try:
            if not os.path.exists(self.config.sf_path):
                cwd_path = os.path.join(os.getcwd(), self.config.sf_path)
                if os.path.exists(cwd_path):
                    self._sf_path_resolved = cwd_path
                else:
                    raise FileNotFoundError(f"Stockfish not found at {self.config.sf_path}")
            else:
                self._sf_path_resolved = self.config.sf_path
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self._sf_engine = chess.engine.SimpleEngine.popen_uci(
                self._sf_path_resolved, startupinfo=startupinfo
            )
            cfg: dict = {
                "Hash": self.config.sf_hash_mb,
                "Threads": self.config.sf_threads,
                "MultiPV": self.config.sf_multipv,
            }
            if self.config.sf_show_wdl:
                cfg["UCI_ShowWDL"] = True
            if self.config.sf_analyse_mode:
                cfg["UCI_AnalyseMode"] = True
            self._sf_engine.configure(cfg)
            logger.info("SF configured: threads=%d hash=%d multipv=%d wdl=%s",
                        self.config.sf_threads, self.config.sf_hash_mb,
                        self.config.sf_multipv, self.config.sf_show_wdl)
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._sf_engine = None

    def stop_sf(self) -> None:
        if self._sf_thread and self._sf_thread.isRunning():
            self._sf_thread.stop()
            self._sf_thread.wait(2000)
        if self._sf_engine:
            try:
                self._sf_engine.quit()
            except Exception as e:
                logger.warning("Error stopping SF: %s", e)
            self._sf_engine = None

    def _ensure_sf_alive(self) -> bool:
        if self._sf_engine is None:
            self.start_sf()
            return self._sf_engine is not None
        try:
            self._sf_engine.ping()
            return True
        except Exception:
            logger.warning("SF not responding, restarting")
            self.stop_sf()
            self.start_sf()
            return self._sf_engine is not None

    def start_analysis(self, board: chess.Board) -> None:
        if not self._ensure_sf_alive():
            self.error_occurred.emit("Stockfish not started")
            return
        snapshot = board.copy()
        self._pending_board = None

        if self._sf_thread and self._sf_thread.isRunning():
            self._pending_board = snapshot
            self._stop_sf_thread_async()
        else:
            self._launch_sf_thread(snapshot)

        if self._maia_available and self._maia is not None:
            self._launch_maia_thread(snapshot)

    def stop_analysis(self) -> None:
        self._pending_board = None
        self._stop_sf_thread_async()
        if self._maia_thread and self._maia_thread.isRunning():
            self._maia_thread.stop()

    def _stop_sf_thread_async(self) -> None:
        if self._sf_thread:
            try:
                self._sf_thread.info_received.disconnect()
            except TypeError:
                pass
            self._sf_thread.stop()
            self._sf_thread = None

    def _launch_sf_thread(self, board: chess.Board) -> None:
        if not self._sf_engine:
            return
        self._sf_thread = StockfishAnalysisThread(
            self._sf_engine, board, movetime_s=self.config.sf_movetime_ms / 1000.0
        )
        self._sf_thread.info_received.connect(self._on_sf_info)
        self._sf_thread.error_occurred.connect(self.error_occurred.emit)
        self._sf_thread.finished.connect(self._on_sf_finished)
        self._sf_thread.start()

    def _launch_maia_thread(self, board: chess.Board) -> None:
        if not self._maia:
            return
        if self._maia_thread and self._maia_thread.isRunning():
            return
        self._maia_thread = MaiaAnalysisThread(self._maia, board)
        self._maia_thread.maia_received.connect(self._on_maia_info)
        self._maia_thread.error_occurred.connect(self.error_occurred.emit)
        self._maia_thread.start()

    def _on_sf_info(self, info: dict) -> None:
        merged = dict(info)
        if self._last_maia:
            merged["maia_distribution"] = self._last_maia.get("probabilities", {})
        # Extract WDL if present
        wdl = info.get("wdl")
        if wdl is not None:
            try:
                self._last_wdl = {"w": int(wdl[0]), "d": int(wdl[1]), "l": int(wdl[2])}
                merged["wdl"] = self._last_wdl
            except Exception:
                pass
        # Collect per-PV info
        multipv = info.get("multipv", 1)
        pv = info.get("pv", [])
        score = info.get("score")
        depth = info.get("depth", 0)
        if pv:
            try:
                pv_moves = [m.uci() for m in pv]
            except Exception:
                pv_moves = []
            try:
                cp = score.white().score(mate_score=100000) if score else None
            except Exception:
                cp = None
            entry = {"multipv": multipv, "depth": depth, "score_cp": cp,
                     "pv": pv_moves}
            # Replace existing entry for this multipv index
            self._last_pvs = [e for e in self._last_pvs if e.get("multipv") != multipv]
            self._last_pvs.append(entry)
            self._last_pvs.sort(key=lambda e: e.get("multipv", 0))
            merged["pvs"] = list(self._last_pvs)
        self.analysis_update.emit(merged)

    def _on_sf_finished(self) -> None:
        if self._pending_board:
            nxt = self._pending_board
            self._pending_board = None
            self._launch_sf_thread(nxt)
            if self._maia_available and self._maia is not None:
                self._launch_maia_thread(nxt)

    def _on_maia_info(self, info: dict) -> None:
        self._last_maia = info
        self.maia_update.emit(info)

    def close(self) -> None:
        self.stop_analysis()
        self.stop_sf()
        if self._maia is not None:
            self._maia.close()


__all__ = ["MultiEngineConfig", "MultiEngineHandler", "StockfishAnalysisThread", "MaiaAnalysisThread"]
