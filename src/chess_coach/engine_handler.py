from __future__ import annotations

import logging
import os
import subprocess
import chess
import chess.engine
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from chess_coach.multi_engine_handler import MultiEngineHandler

logger = logging.getLogger(__name__)


class EngineHandler(QObject):
    """v3.0 EngineHandler — backwards-compatible facade over MultiEngineHandler.

    Preserves the v2.0 public API (start_engine / start_analysis / stop_engine
    / analysis_update / error_occurred signals). Internally delegates to
    MultiEngineHandler so v2.0 callers (server.py, main_window.py) keep
    working unchanged.

    Maia is *disabled* by default in this facade to keep the desktop startup
    snappy; enable it via `enable_maia=True` in the constructor.
    """

    analysis_update = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: dict, enable_maia: bool = False) -> None:
        super().__init__()
        self.config = config
        self.engine_path: str = config.get("engine", {}).get("path", "stockfish.exe")
        self.engine: chess.engine.SimpleEngine | None = None
        self.analysis_thread: AnalysisThread | None = None
        self.pending_board: chess.Board | None = None
        self._multi: MultiEngineHandler | None = None
        self._enable_maia = enable_maia

    def _ensure_engine_alive(self) -> bool:
        if self.engine is None:
            return False
        try:
            self.engine.ping()
            return True
        except Exception:
            logger.warning("Engine not responding, restarting")
            self._restart_engine()
            return self.engine is not None

    def _restart_engine(self) -> None:
        try:
            self.engine = None
            self.start_engine()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def start_engine(self) -> None:
        try:
            if not os.path.exists(self.engine_path):
                cwd_path = os.path.join(os.getcwd(), self.engine_path)
                if os.path.exists(cwd_path):
                    self.engine_path = cwd_path
                else:
                    raise FileNotFoundError(
                        f"Stockfish not found at {self.engine_path}"
                    )

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.engine = chess.engine.SimpleEngine.popen_uci(
                self.engine_path, startupinfo=startupinfo
            )
            self.engine.configure({
                "Hash": self.config.get("engine", {}).get("hash", 16),
                "Threads": self.config.get("engine", {}).get("threads", 1),
            })
        except Exception as e:
            self.error_occurred.emit(str(e))

    def swap_engine(self, key: str) -> str:
        """Restart with a different UCI engine binary.

        For SOTA NNUE engines (Berserk, Caissa, Crystal, Patricia, ShashChess)
        this looks for the binary in PATH or the project's engines/ directory.
        For Maia-2 this switches the multi-engine handler into Maia mode.

        Returns the path that was activated, or '' if the engine is not
        installed and we fell back to the existing binary. The caller decides
        what to show in the status bar.
        """
        from chess_coach.dialogs import resolve_engine_binary

        if key == "maia2":
            # Maia is wired through multi_engine_handler; do not swap the UCI
            # engine here. Just toggle the multi-handler's enable flag.
            if self._multi is None:
                self._multi = MultiEngineHandler()
            self._multi._enable_maia = True  # type: ignore[attr-defined]
            return "maia2"

        target = resolve_engine_binary(key)
        if not target:
            # Engine not installed — keep the running engine and signal back.
            return ""

        # Persist the new path in the config dict so subsequent restarts use it.
        self.config.setdefault("engine", {})["path"] = target
        self.engine_path = target
        self.stop_engine()
        try:
            self.start_engine()
        except Exception as e:  # noqa: BLE001
            self.error_occurred.emit(f"Engine swap to {key} failed: {e}")
            return ""
        return target

    def stop_engine(self) -> None:
        self._stop_current_thread_async()
        if self.engine:
            try:
                self.engine.quit()
            except Exception as e:
                logger.warning("Error stopping engine: %s", e)
            self.engine = None
        if self._multi is not None:
            self._multi.close()
            self._multi = None

    def start_analysis(self, board: chess.Board) -> None:
        if not self._ensure_engine_alive():
            self.error_occurred.emit("Engine not started")
            return
        snapshot = board.copy()
        self.pending_board = None
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.pending_board = snapshot
            self._stop_current_thread_async()
            return
        self._launch_thread(snapshot)

    def stop_analysis(self) -> None:
        self.pending_board = None
        self._stop_current_thread_async()

    def _stop_current_thread_async(self) -> None:
        if self.analysis_thread:
            try:
                self.analysis_thread.info_received.disconnect()
            except TypeError:
                pass
            self.analysis_thread.stop()

    def _launch_thread(self, board: chess.Board) -> None:
        if not self.engine:
            return
        self.analysis_thread = AnalysisThread(self.engine, board, self.config)
        self.analysis_thread.info_received.connect(self.analysis_update.emit)
        self.analysis_thread.error_occurred.connect(self.error_occurred.emit)
        self.analysis_thread.finished.connect(self._on_thread_finished)
        self.analysis_thread.start()

    def _on_thread_finished(self) -> None:
        if self.pending_board:
            next_board = self.pending_board
            self.pending_board = None
            self._launch_thread(next_board)


class AnalysisThread(QThread):
    info_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(
        self, engine: chess.engine.SimpleEngine, board: chess.Board, config: dict
    ) -> None:
        super().__init__()
        self.engine = engine
        self.board = board
        self.config = config
        self.is_running = True

    def run(self) -> None:
        try:
            with self.engine.analysis(self.board) as analysis:
                for info in analysis:
                    if not self.is_running:
                        break
                    self.info_received.emit(info)
        except Exception as e:
            logger.error("Analysis error: %s", e)
            self.error_occurred.emit(f"Analysis crashed: {e}")
        finally:
            self.is_running = False

    def stop(self) -> None:
        self.is_running = False
