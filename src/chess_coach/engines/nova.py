"""Nova chess engine adapter - pure policy transformer, 35ms inference."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Optional

import numpy as np
import chess

from chess_coach.engines.base import Engine, EngineInfo, Evaluation

logger = logging.getLogger(__name__)

# Nova move index encoding
PIECE_MAP = {"P": 0, "N": 1, "B": 2, "R": 3, "Q": 4, "K": 5,
             "p": 6, "n": 7, "b": 8, "r": 9, "q": 10, "k": 11}


class NovaConfig:
    """Nova engine configuration."""

    def __init__(
        self,
        model_dir: str = "engines/nova",
        rating: int = 1500,
        classical: float = 0.5,
        aggression: float = 0.5,
        temperature: float = 0.5,
        auto_download: bool = True,
    ):
        self.model_dir = model_dir
        self.rating = rating
        self.classical = classical
        self.aggression = aggression
        self.temperature = temperature
        self.auto_download = auto_download


class NovaEngine(Engine):
    """Nova chess engine - pure policy transformer with 35ms inference."""

    def __init__(self, config: Optional[NovaConfig] = None):
        self.config = config or NovaConfig()
        self.session = None
        self._ensure_model()

    def _ensure_model(self):
        """Auto-download model if not present."""
        model_dir = Path(self.config.model_dir)
        onnx_path = model_dir / "nova_v3b.onnx"

        if not onnx_path.exists():
            if self.config.auto_download:
                self._download_model(model_dir)
            else:
                raise FileNotFoundError(
                    f"Nova model not found at {onnx_path} and auto_download is False. "
                    "Set auto_download=True or download the model manually."
                )

        import onnxruntime as ort
        self.session = ort.InferenceSession(
            str(onnx_path),
            providers=["CPUExecutionProvider"],
        )

    def _download_model(self, model_dir: Path):
        """Download Nova model from HuggingFace."""
        from huggingface_hub import hf_hub_download

        model_dir.mkdir(parents=True, exist_ok=True)

        hf_hub_download(
            repo_id="novachess/novachess-engine",
            filename="nova_v3b.onnx",
            local_dir=str(model_dir),
        )
        hf_hub_download(
            repo_id="novachess/novachess-engine",
            filename="nova_v3b.onnx.data",
            local_dir=str(model_dir),
        )

    def fen_to_planes(self, fen: str) -> np.ndarray:
        """Convert FEN to 18-plane encoding for Nova."""
        planes = np.zeros((18, 8, 8), dtype=np.float32)
        parts = fen.split()
        board_part, turn, castling, ep = parts[0], parts[1], parts[2], parts[3]

        for ri, rank_str in enumerate(board_part.split("/")):
            rank_idx = 7 - ri
            file_idx = 0
            for ch in rank_str:
                if ch.isdigit():
                    file_idx += int(ch)
                else:
                    planes[PIECE_MAP[ch], rank_idx, file_idx] = 1.0
                    file_idx += 1

        if turn == "w":
            planes[12].fill(1.0)
        if "K" in castling:
            planes[13].fill(1.0)
        if "Q" in castling:
            planes[14].fill(1.0)
        if "k" in castling:
            planes[15].fill(1.0)
        if "q" in castling:
            planes[16].fill(1.0)
        if ep != "-" and len(ep) == 2:
            planes[17, 0, ord(ep[0]) - ord("a")] = 1.0

        return planes

    def decode_move_idx(self, idx: int) -> chess.Move:
        """Decode move index to chess.Move."""
        promo = None
        raw = int(idx)
        if raw >= 4096 * 3:
            promo = chess.QUEEN
            raw -= 4096 * 3
        elif raw >= 4096 * 2:
            promo = chess.BISHOP
            raw -= 4096 * 2
        elif raw >= 4096:
            promo = chess.KNIGHT
            raw -= 4096

        from_sq = raw // 64
        to_sq = raw % 64
        return chess.Move(from_sq, to_sq, promotion=promo)

    # -- helpers to reduce duplication ----------------------------------------

    def _build_legal_mask(self, board: chess.Board) -> np.ndarray:
        """Build a 16384-element boolean mask of legal moves.

        Rook promotions are intentionally omitted: Nova's move-index space
        only encodes queen / bishop / knight promotions, so a queen promotion
        covers all practical endgames. Rook promotions are therefore mapped to
        the queen-promotion slot to avoid leaving them unreachable.
        """
        mask = np.zeros(16384, dtype=bool)
        for mv in board.legal_moves:
            idx = mv.from_square * 64 + mv.to_square
            if mv.promotion == chess.KNIGHT:
                idx += 4096
            elif mv.promotion == chess.BISHOP:
                idx += 4096 * 2
            elif mv.promotion == chess.ROOK:
                # Rook promotions map to queen-promotion slot.
                # Queen promotion covers all practical cases.
                logger.debug(
                    "Rook promotion %s mapped to queen-promotion slot", mv
                )
                idx += 4096 * 3
            elif mv.promotion == chess.QUEEN:
                idx += 4096 * 3
            mask[idx] = True
        return mask

    def _run_inference(
        self, positions: np.ndarray, conditioning: np.ndarray
    ) -> np.ndarray:
        """Run a single forward pass and return raw logits."""
        return self.session.run(None, {
            "positions": positions,
            "conditioning": conditioning,
        })[0][0]

    def _build_conditioning(
        self,
        rating: int,
        classical: float,
        aggression: float,
    ) -> np.ndarray:
        """Build the conditioning vector for the model."""
        r = max(800, min(2700, rating))
        return np.array(
            [[(r - 800) / (2700 - 800), classical, aggression]],
            dtype=np.float32,
        )

    # -- Engine ABC interface --------------------------------------------------

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="Nova",
            version="v3b",
            author="Novachess",
            elo_ceiling=2400,
            elo_floor=800,
            type="neural",
            requires=["onnxruntime"],
            url="https://huggingface.co/novachess/novachess-engine",
        )

    def start(self) -> None:
        if self.session is None:
            self._ensure_model()

    def stop(self) -> None:
        if self.session is not None:
            self.session = None

    def is_ready(self) -> bool:
        return self.session is not None

    def evaluate(
        self, fen: str, depth: int = 20, multipv: int = 1
    ) -> Evaluation:
        board = chess.Board(fen)
        positions = self.fen_to_planes(fen)[np.newaxis]
        conditioning = self._build_conditioning(
            self.config.rating, self.config.classical, self.config.aggression
        )
        logits = self._run_inference(positions, conditioning)

        legal_mask = self._build_legal_mask(board)
        masked = np.where(legal_mask, logits, -1e9)

        # Probability distribution over legal moves (no temperature)
        probs = np.exp(masked - masked.max())
        probs *= legal_mask
        total = probs.sum()

        score_cp = 0
        if total > 0:
            probs_normalized = probs / total
            sorted_probs = np.sort(probs_normalized)[::-1]
            p_best = float(sorted_probs[0])
            p_second = float(sorted_probs[1]) if len(sorted_probs) > 1 else 1e-12
            p_second = max(p_second, 1e-12)
            score_cp = int(200 * math.log(p_best / p_second))

        return Evaluation(
            score_cp=score_cp,
            depth=depth,
            source_engine="Nova",
        )

    def set_option(self, name: str, value: Any) -> None:
        if name == "rating":
            self.config.rating = int(value)
        elif name == "classical":
            self.config.classical = float(value)
        elif name == "aggression":
            self.config.aggression = float(value)
        elif name == "temperature":
            self.config.temperature = float(value)
        else:
            raise ValueError(f"Unknown Nova option: {name}")

    def get_options(self) -> dict[str, Any]:
        return {
            "rating": self.config.rating,
            "classical": self.config.classical,
            "aggression": self.config.aggression,
            "temperature": self.config.temperature,
        }

    # -- public move API -------------------------------------------------------

    def get_move(
        self,
        board: chess.Board,
        rating: Optional[int] = None,
        classical: Optional[float] = None,
        aggression: Optional[float] = None,
        temperature: Optional[float] = None,
    ) -> chess.Move:
        """Get best move from Nova engine."""
        rating = rating or self.config.rating
        classical = classical if classical is not None else self.config.classical
        aggression = aggression if aggression is not None else self.config.aggression
        temperature = temperature if temperature is not None else self.config.temperature

        positions = self.fen_to_planes(board.fen())[np.newaxis]
        conditioning = self._build_conditioning(rating, classical, aggression)
        logits = self._run_inference(positions, conditioning)

        legal_mask = self._build_legal_mask(board)
        masked = np.where(legal_mask, logits, -1e9)

        # Temperature sampling
        probs = np.exp((masked - masked.max()) / temperature)
        probs *= legal_mask
        total = probs.sum()
        if total == 0:
            return chess.Move.null()
        probs /= total

        top_idx = np.random.choice(16384, p=probs)
        return self.decode_move_idx(top_idx)

    def get_top_moves(
        self,
        board: chess.Board,
        n: int = 3,
        rating: Optional[int] = None,
        classical: Optional[float] = None,
        aggression: Optional[float] = None,
    ) -> list[tuple[chess.Move, float]]:
        """Get top N moves with probabilities."""
        rating = rating or self.config.rating
        classical = classical if classical is not None else self.config.classical
        aggression = aggression if aggression is not None else self.config.aggression

        positions = self.fen_to_planes(board.fen())[np.newaxis]
        conditioning = self._build_conditioning(rating, classical, aggression)
        logits = self._run_inference(positions, conditioning)

        legal_mask = self._build_legal_mask(board)
        masked = np.where(legal_mask, logits, -1e9)
        probs = np.exp(masked - masked.max())
        probs *= legal_mask
        total = probs.sum()
        if total == 0:
            return []
        probs /= total

        top_indices = np.argsort(probs)[::-1][:n]
        return [(self.decode_move_idx(i), float(probs[i])) for i in top_indices]
