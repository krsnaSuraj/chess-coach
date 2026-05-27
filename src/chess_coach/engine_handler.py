from __future__ import annotations

import logging
import os
import subprocess
import chess
import chess.engine
from PyQt6.QtCore import QThread, pyqtSignal, QObject

logger = logging.getLogger(__name__)


class EngineHandler(QObject):
    analysis_update = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        self.engine_path: str = config.get("engine", {}).get("path", "stockfish.exe")
        self.engine: chess.engine.SimpleEngine | None = None
        self.analysis_thread: AnalysisThread | None = None
        self.pending_board: chess.Board | None = None

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

    def stop_engine(self) -> None:
        self._stop_current_thread_async()
        if self.engine:
            try:
                self.engine.quit()
            except Exception as e:
                logger.warning("Error stopping engine: %s", e)
            self.engine = None

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
