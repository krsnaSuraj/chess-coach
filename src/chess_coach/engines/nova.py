"""Nova chess engine adapter - pure policy transformer, 35ms inference."""

from __future__ import annotations

import numpy as np
import chess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Nova move index encoding
PIECE_MAP = {"P": 0, "N": 1, "B": 2, "R": 3, "Q": 4, "K": 5,
             "p": 6, "n": 7, "b": 8, "r": 9, "q": 10, "k": 11}


@dataclass
class NovaConfig:
    """Nova engine configuration."""
    model_dir: str = "engines/nova"
    rating: int = 1500
    classical: float = 0.5
    aggression: float = 0.5
    temperature: float = 0.5
    auto_download: bool = True


class NovaEngine:
    """Nova chess engine - pure policy transformer with 35ms inference."""
    
    def __init__(self, config: Optional[NovaConfig] = None):
        self.config = config or NovaConfig()
        self.session = None
        self._ensure_model()
    
    def _ensure_model(self):
        """Auto-download model if not present."""
        from huggingface_hub import hf_hub_download
        
        model_dir = Path(self.config.model_dir)
        onnx_path = model_dir / "nova_v3b.onnx"
        
        if not onnx_path.exists() and self.config.auto_download:
            self._download_model(model_dir)
        
        import onnxruntime as ort
        self.session = ort.InferenceSession(
            str(onnx_path),
            providers=["CPUExecutionProvider"]
        )
    
    def _download_model(self, model_dir: Path):
        """Download Nova model from HuggingFace."""
        from huggingface_hub import hf_hub_download
        
        model_dir.mkdir(parents=True, exist_ok=True)
        
        hf_hub_download(
            repo_id="novachess/novachess-engine",
            filename="nova_v3b.onnx",
            local_dir=str(model_dir)
        )
        hf_hub_download(
            repo_id="novachess/novachess-engine",
            filename="nova_v3b.onnx.data",
            local_dir=str(model_dir)
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
            promo = chess.ROOK
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
    
    def get_move(self, board: chess.Board, rating: Optional[int] = None,
                 classical: Optional[float] = None,
                 aggression: Optional[float] = None,
                 temperature: Optional[float] = None) -> chess.Move:
        """Get best move from Nova engine."""
        rating = rating or self.config.rating
        classical = classical if classical is not None else self.config.classical
        aggression = aggression if aggression is not None else self.config.aggression
        temperature = temperature or self.config.temperature
        
        # Encode position
        positions = self.fen_to_planes(board.fen())[np.newaxis]
        
        # Normalize rating
        r = max(800, min(2700, rating))
        conditioning = np.array([[(r - 800) / (2700 - 800), classical, aggression]],
                               dtype=np.float32)
        
        # Single forward pass (35-50ms)
        logits = self.session.run(None, {
            "positions": positions,
            "conditioning": conditioning
        })[0][0]
        
        # Mask illegal moves
        legal_mask = np.zeros(16384, dtype=bool)
        for mv in board.legal_moves:
            idx = mv.from_square * 64 + mv.to_square
            if mv.promotion == chess.KNIGHT:
                idx += 4096
            elif mv.promotion == chess.BISHOP:
                idx += 4096 * 2
            elif mv.promotion == chess.ROOK:
                idx += 4096 * 3
            legal_mask[idx] = True
        
        masked = np.where(legal_mask, logits, -1e9)
        
        # Temperature sampling
        probs = np.exp(masked - masked.max()) / temperature
        probs *= legal_mask
        probs /= probs.sum()
        
        # Sample from distribution
        top_idx = np.random.choice(16384, p=probs)
        return self.decode_move_idx(top_idx)
    
    def get_top_moves(self, board: chess.Board, n: int = 3,
                      rating: Optional[int] = None,
                      classical: Optional[float] = None,
                      aggression: Optional[float] = None) -> list[tuple[chess.Move, float]]:
        """Get top N moves with probabilities."""
        rating = rating or self.config.rating
        classical = classical if classical is not None else self.config.classical
        aggression = aggression if aggression is not None else self.config.aggression
        
        positions = self.fen_to_planes(board.fen())[np.newaxis]
        r = max(800, min(2700, rating))
        conditioning = np.array([[(r - 800) / (2700 - 800), classical, aggression]],
                               dtype=np.float32)
        
        logits = self.session.run(None, {
            "positions": positions,
            "conditioning": conditioning
        })[0][0]
        
        legal_mask = np.zeros(16384, dtype=bool)
        for mv in board.legal_moves:
            idx = mv.from_square * 64 + mv.to_square
            if mv.promotion == chess.KNIGHT:
                idx += 4096
            elif mv.promotion == chess.BISHOP:
                idx += 4096 * 2
            elif mv.promotion == chess.ROOK:
                idx += 4096 * 3
            legal_mask[idx] = True
        
        masked = np.where(legal_mask, logits, -1e9)
        probs = np.exp(masked - masked.max())
        probs *= legal_mask
        probs /= probs.sum()
        
        top_indices = np.argsort(probs)[::-1][:n]
        return [(self.decode_move_idx(i), float(probs[i])) for i in top_indices]
