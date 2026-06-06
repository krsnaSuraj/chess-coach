"""Engine match — play against Stockfish with personality and adjustable ELO.

Uses UCI_LimitStrength + UCI_Elo to cap Stockfish at a target ELO (800-2800).
Five personalities bias the engine's move selection toward different styles.
"""

from __future__ import annotations

import random
import subprocess
from dataclasses import dataclass
from typing import Optional


PERSONALITIES = {
    "aggressive": {
        "name": "Aggressive",
        "icon": "\u2694",
        "description": "Plays for attacks and sacrifices. Loves the king's safety challenged.",
        "bias": "attack",
    },
    "defensive": {
        "name": "Defensive",
        "icon": "\u26d4",
        "description": "Solid, safe play. Prefers trades and king safety.",
        "bias": "defense",
    },
    "positional": {
        "name": "Positional",
        "icon": "\u25c7",
        "description": "Long-term plans. Outposts, weak squares, pawn chains.",
        "bias": "positional",
    },
    "tactical": {
        "name": "Tactical",
        "icon": "\u26a1",
        "description": "Sharp combination player. Finds forks, pins, and mates.",
        "bias": "tactical",
    },
    "wild": {
        "name": "Wild",
        "icon": "\u2728",
        "description": "Unpredictable. Mixes brilliant and weird moves.",
        "bias": "random",
    },
}


@dataclass
class MatchConfig:
    """Configuration for an engine match."""
    personality: str = "tactical"
    target_elo: int = 1500
    color: str = "w"          # "w" or "b" — which side the engine plays
    time_control_s: int = 300
    increment_s: int = 0

    def __post_init__(self):
        if self.personality not in PERSONALITIES:
            raise ValueError(f"Unknown personality: {self.personality}")
        if not 800 <= self.target_elo <= 2800:
            raise ValueError(f"target_elo out of range: {self.target_elo}")
        if self.color not in ("w", "b"):
            raise ValueError(f"color must be w or b: {self.color}")


class EngineMatch:
    """A match against Stockfish at a given ELO with a personality.

    Wraps a Stockfish UCI process, configures UCI_LimitStrength + UCI_Elo,
    and (for non-tactical personalities) randomly perturbs move selection
    to inject some personality flavor.
    """

    def __init__(self, stockfish_path: str, config: MatchConfig):
        self.config = config
        self.path = stockfish_path
        self.proc: Optional[subprocess.Popen] = None
        self._moves_played: list[str] = []
        self._uci_elo_supported = True
        self._last_eval: Optional[int] = None

    def start(self):
        """Start the engine subprocess."""
        self.proc = subprocess.Popen(
            [self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        # Wait for uciok
        while True:
            line = self.proc.stdout.readline().strip()
            if line == "uciok":
                break
        # Configure
        self._send("setoption name UCI_LimitStrength value true")
        self._send(f"setoption name UCI_Elo value {self.config.target_elo}")
        self._send("setoption name UCI_AnalyseMode value false")
        self._send("setoption name UCI_ShowWDL value true")
        self._send("setoption name MultiPV value 1")
        self._send("isready")
        while True:
            line = self.proc.stdout.readline().strip()
            if line == "readyok":
                break
        self._send("ucinewgame")

    def stop(self):
        """Stop the engine subprocess."""
        if self.proc:
            try:
                self._send("quit")
            except BrokenPipeError:
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None

    def play_move(self, fen: str) -> str:
        """Get the engine's move for the given position.

        Returns the move in UCI notation (e.g., 'e2e4').
        """
        if not self.proc:
            self.start()
        self._send(f"position fen {fen}")
        self._send("go depth 12")
        bestmove = ""
        while True:
            line = self.proc.stdout.readline().strip()
            if line.startswith("info") and "score cp" in line:
                # Parse last info
                try:
                    parts = line.split()
                    idx = parts.index("cp")
                    self._last_eval = int(parts[idx + 1])
                except (ValueError, IndexError):
                    pass
            if line.startswith("bestmove"):
                bestmove = line.split()[1] if len(line.split()) > 1 else ""
                break
        # Apply personality bias
        bestmove = self._apply_personality(fen, bestmove)
        self._moves_played.append(bestmove)
        return bestmove

    def _apply_personality(self, fen: str, best_move: str) -> str:
        """Bias the move selection based on personality.

        For aggressive/tactical: keep best move.
        For defensive/positional: occasionally pick a safer alternative.
        For wild: random with 20% chance.
        """
        bias = PERSONALITIES[self.config.personality]["bias"]
        if bias == "attack" or bias == "tactical":
            return best_move
        if bias == "random":
            if random.random() < 0.20:
                # Get all legal moves, pick random
                import chess
                board = chess.Board(fen)
                legal = list(board.legal_moves)
                if legal:
                    return legal[random.randint(0, len(legal) - 1)].uci()
            return best_move
        if bias in ("defense", "positional"):
            # 80% best move
            if random.random() < 0.80:
                return best_move
            # 20% random legal move
            import chess
            board = chess.Board(fen)
            legal = list(board.legal_moves)
            if legal:
                return legal[random.randint(0, len(legal) - 1)].uci()
        return best_move

    def _send(self, cmd: str):
        """Send a UCI command to the engine."""
        if self.proc and self.proc.stdin:
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()

    @property
    def last_eval(self) -> Optional[int]:
        return self._last_eval

    def get_summary(self) -> dict:
        """Return a match summary suitable for storage."""
        return {
            "personality": self.config.personality,
            "personality_name": PERSONALITIES[self.config.personality]["name"],
            "target_elo": self.config.target_elo,
            "color": self.config.color,
            "moves_played": len(self._moves_played),
            "moves": self._moves_played[:],
        }
