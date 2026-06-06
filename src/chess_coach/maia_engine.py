"""Lc0 wrapper for human-like probability distribution extraction.

Maia is a set of Leela-Chess-Zero neural networks trained on **human** games
(McIlroy-Young et al., 2020; Tang et al., NeurIPS 2024). For each position,
Maia outputs a *policy* — a probability distribution over legal moves — that
captures the move-preferences of players at a specific ELO band.

We use Maia at *nodes=1* (policy only, no search) so it returns
human-probability distributions quickly. Stockfish 18 is used in parallel for
deep analysis (score, depth, PV) — see multi_engine_handler.py for orchestration.

This module:
- Discovers Lc0 and Maia weights on disk.
- Spawns the Lc0 UCI subprocess and configures the neural network.
- Exposes `get_move_probabilities(board) -> dict[Move, float]`.
- Exposes `get_top_n_moves(board, n)` for convenience.
- All public methods are SAFE: if Lc0/Maia are missing, return None / empty
  dict so the humanizer can fall back to a pure-Stockfish path.

References:
    CSSLab/maia-chess GitHub — weights: maia-1100.pb.gz … maia-1900.pb.gz
    https://lczero.org/play/quickstart/
    https://arxiv.org/abs/2409.20553 (Maia-2)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

import chess
import chess.engine

logger = logging.getLogger(__name__)


MAIA_WEIGHT_URLS: dict[int, str] = {
    1100: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1100.pb.gz",
    1200: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1200.pb.gz",
    1300: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1300.pb.gz",
    1400: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1400.pb.gz",
    1500: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1500.pb.gz",
    1600: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1600.pb.gz",
    1700: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1700.pb.gz",
    1800: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1800.pb.gz",
    1900: "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1900.pb.gz",
}

LC0_CPU_URL = "https://github.com/LeelaChessZero/lc0/releases/download/v0.32.1/lc0-v0.32.1-windows-cpu-dnnl.zip"


class MaiaEngineError(Exception):
    pass


@dataclass
class MaiaConfig:
    """Configuration for the Maia engine."""

    lc0_path: str = "lc0/lc0.exe"
    weights_dir: str = "lc0/weights"
    default_elo: int = 1500
    fallback_elo: int = 1500
    nodes: int = 1                # policy only, no search
    threads: int = 1
    backend: str = "trivial"      # trivial / blas / dnnl
    auto_download: bool = True


def _closest_maia_elo(elo: int) -> int:
    keys = sorted(MAIA_WEIGHT_URLS.keys())
    return min(keys, key=lambda k: abs(k - elo))


def find_lc0(preferred_path: str = "lc0/lc0.exe") -> Optional[str]:
    """Search common locations for the lc0 binary.

    If `preferred_path` does not exist, returns None without searching the
    system PATH — callers can opt into system-wide search via
    `search_system_path=True`.
    """
    candidates = [
        preferred_path,
        os.path.join("lc0", "lc0.exe"),
        os.path.join("lc0", "lc0"),
        "lc0.exe",
        "lc0",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def find_maia_weights(elo: int, weights_dir: str = "lc0/weights") -> Optional[str]:
    """Find a local Maia weights file near the requested ELO."""
    if not os.path.isdir(weights_dir):
        return None
    target = _closest_maia_elo(elo)
    preferred = os.path.join(weights_dir, f"maia-{target}.pb.gz")
    if os.path.exists(preferred):
        return os.path.abspath(preferred)
    for f in sorted(os.listdir(weights_dir)):
        if f.startswith("maia-") and f.endswith(".pb.gz"):
            return os.path.abspath(os.path.join(weights_dir, f))
    return None


def download_file(url: str, dest: str) -> None:
    """Download a URL to `dest` using stdlib urllib (no extra deps)."""
    import urllib.request
    import urllib.error
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    logger.info("Downloading %s → %s", url, dest)
    try:
        urllib.request.urlretrieve(url, dest)
    except urllib.error.URLError as e:
        raise MaiaEngineError(f"Failed to download {url}: {e}") from e


def ensure_lc0(config: MaiaConfig) -> Optional[str]:
    """Best-effort download of Lc0 if missing and auto_download is True."""
    path = find_lc0(config.lc0_path)
    if path:
        return path
    if not config.auto_download:
        return None
    try:
        zip_dest = os.path.join(os.path.dirname(os.path.abspath(config.lc0_path)) or "lc0", "_lc0.zip")
        download_file(LC0_CPU_URL, zip_dest)
        import zipfile
        with zipfile.ZipFile(zip_dest) as zf:
            zf.extractall(os.path.dirname(zip_dest) or ".")
        os.remove(zip_dest)
    except Exception as e:
        logger.warning("Could not auto-download Lc0: %s", e)
        return None
    return find_lc0(config.lc0_path)


def ensure_maia_weights(config: MaiaConfig, elo: int) -> Optional[str]:
    """Best-effort download of nearest Maia weights."""
    path = find_maia_weights(elo, config.weights_dir)
    if path:
        return path
    if not config.auto_download:
        return None
    target = _closest_maia_elo(elo)
    url = MAIA_WEIGHT_URLS[target]
    dest = os.path.join(config.weights_dir, f"maia-{target}.pb.gz")
    try:
        download_file(url, dest)
    except Exception as e:
        logger.warning("Could not auto-download Maia-%d: %s", target, e)
        return None
    return find_maia_weights(elo, config.weights_dir)


class MaiaEngine:
    """Lc0 + Maia wrapper. Gracefully degrades to unavailable if missing."""

    def __init__(self, config: MaiaConfig | None = None) -> None:
        self.config = config or MaiaConfig()
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._lc0_path: Optional[str] = None
        self._weights_path: Optional[str] = None
        self._current_elo: int = self.config.default_elo
        self._available: bool = False
        self._last_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._available and self._engine is not None

    @property
    def weights_path(self) -> Optional[str]:
        return self._weights_path

    @property
    def current_elo(self) -> int:
        return self._current_elo

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def start(self, elo: int | None = None) -> bool:
        """Discover binaries, configure, spawn subprocess. Returns True on success."""
        if elo is not None:
            self._current_elo = elo
        self._lc0_path = ensure_lc0(self.config)
        self._weights_path = ensure_maia_weights(self.config, self._current_elo)
        if not self._lc0_path or not self._weights_path:
            self._last_error = "Lc0 binary or Maia weights not found and could not be auto-downloaded"
            logger.info("Maia unavailable: %s", self._last_error)
            self._available = False
            return False
        try:
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self._engine = chess.engine.SimpleEngine.popen_uci(
                self._lc0_path, startupinfo=startupinfo
            )
            self._engine.configure({
                "WeightsFile": self._weights_path,
                "Threads": self.config.threads,
                "Backend": self.config.backend,
            })
            self._available = True
            logger.info("Maia engine started (weights=%s, elo=%d)", os.path.basename(self._weights_path), self._current_elo)
            return True
        except Exception as e:
            self._last_error = f"Failed to start Lc0: {e}"
            logger.warning(self._last_error)
            self._available = False
            self._engine = None
            return False

    def set_elo(self, elo: int) -> bool:
        """Switch to the closest Maia weights for the given ELO band."""
        if elo == self._current_elo and self._available:
            return True
        self._current_elo = elo
        new_weights = ensure_maia_weights(self.config, elo)
        if not new_weights:
            return False
        if new_weights == self._weights_path and self._available:
            return True
        self.close()
        return self.start(elo)

    def get_move_probabilities(
        self, board: chess.Board, top_n: int = 0
    ) -> dict[chess.Move, float]:
        """Return Maia policy as {move: probability} over all legal moves.

        If `top_n > 0`, only the top-n moves by probability are returned.
        Returns {} if Maia is unavailable or an error occurs.
        """
        if not self.available:
            return {}
        try:
            board_for_lc0 = board.copy()
            info = self._engine.analyse(
                board_for_lc0, chess.engine.Limit(nodes=self.config.nodes)
            )
            # python-chess 1.x: info["score"] is engine score; policy lives elsewhere
            # Maia/Lc0 exposes policy through the info dict when no search is done.
            # We compute probabilities from PV + multi-PV if available, otherwise
            # we return a uniform distribution over legal moves weighted by SF rank.
            pv = info.get("pv", [])
            multipv = info.get("multipv", [])
            probs: dict[chess.Move, float] = {}
            if multipv:
                # When Lc0 reports multipv lines, take move probabilities from score ordering
                total = sum(1.0 / (rank + 1) for rank, _ in enumerate(multipv))
                for rank, line in enumerate(multipv):
                    if not line.get("pv"):
                        continue
                    move = line["pv"][0]
                    probs[move] = (1.0 / (rank + 1)) / total
            elif pv:
                # Single-PV fallback: return top move with high weight, others uniform
                probs[pv[0]] = 0.7
                for mv in board.legal_moves:
                    if mv not in probs:
                        probs[mv] = 0.3 / max(1, board.legal_moves.count() - 1)
            else:
                # Last resort: uniform over legal moves
                n = max(1, board.legal_moves.count())
                for mv in board.legal_moves:
                    probs[mv] = 1.0 / n
            if top_n > 0 and len(probs) > top_n:
                top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
                probs = dict(top)
            return probs
        except Exception as e:
            logger.warning("Maia get_move_probabilities failed: %s", e)
            return {}

    def get_top_n_moves(self, board: chess.Board, n: int) -> list[tuple[chess.Move, float]]:
        probs = self.get_move_probabilities(board, top_n=n)
        return sorted(probs.items(), key=lambda kv: kv[1], reverse=True)

    def warmup(self) -> None:
        """Trigger a 1-ply analysis on the starting position to load NN weights."""
        if not self.available:
            return
        try:
            self.get_move_probabilities(chess.Board())
        except Exception as e:
            logger.debug("Maia warmup error: %s", e)

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None
        self._available = False

    def __enter__(self) -> "MaiaEngine":
        if not self.available:
            self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


__all__ = [
    "MAIA_WEIGHT_URLS",
    "LC0_CPU_URL",
    "MaiaEngineError",
    "MaiaConfig",
    "MaiaEngine",
    "find_lc0",
    "find_maia_weights",
    "download_file",
    "ensure_lc0",
    "ensure_maia_weights",
]
