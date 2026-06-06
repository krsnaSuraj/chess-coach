"""ELO calibration curves and Bayesian ELO self-estimator.

Provides:
- Engine analysis parameters (depth, hash, movetime) per ELO band.
- Realistic think-time distributions per ELO band.
- Expected centipawn loss (ACPL) targets per ELO and game phase.
- Bayesian online estimator of a player's ELO from observed move ACPLs.

All numbers are derived from public sources:
- chess.com accuracy bands (DanielRensch, 2017; updated 2024).
- Lichess ELO/ACPL scatter (chess-db.com research, FERREIRA 2012).
- Maia paper (McIlroy-Young et al., 2020; Tang et al., NeurIPS 2024).
- Stockfish 18 release notes / TCEC statistics (Jan 2026).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


MIN_ELO = 800
MAX_ELO = 2400


@dataclass(frozen=True)
class EngineProfile:
    """How the analysis engine should behave for a target human ELO."""

    depth: int
    movetime_ms: int
    multipv: int
    skill_level: int  # Stockfish Skill Level (0-20), 20 = full strength
    hash_mb: int


@dataclass(frozen=True)
class ThinkProfile:
    """How long a real human of this ELO typically takes per move."""

    min_seconds: float
    max_seconds: float
    mean_seconds: float
    std_seconds: float
    blunder_think_bonus: float  # extra time on critical positions


@dataclass(frozen=True)
class ACPLTarget:
    """Target average centipawn loss by game phase for a given ELO."""

    opening: float
    middlegame: float
    endgame: float
    overall: float


@dataclass(frozen=True)
class ELOBand:
    """A complete ELO band: analysis profile, think profile, ACPL target."""

    elo: int
    label: str
    engine: EngineProfile
    think: ThinkProfile
    acpl: ACPLTarget


_BANDS: dict[int, ELOBand] = {
    800:  ELOBand(800,  "Beginner",       EngineProfile(depth=4,  movetime_ms=150,  multipv=3, skill_level=2,  hash_mb=16),
                 ThinkProfile(0.5,  5.0,  2.0, 1.2, 3.0),
                 ACPLTarget(70, 130, 110, 100)),
    1000: ELOBand(1000, "Novice",         EngineProfile(depth=6,  movetime_ms=250,  multipv=3, skill_level=4,  hash_mb=16),
                 ThinkProfile(0.8,  6.0,  2.5, 1.4, 2.5),
                 ACPLTarget(55, 100,  85,  78)),
    1200: ELOBand(1200, "Beginner+",      EngineProfile(depth=8,  movetime_ms=400,  multipv=4, skill_level=6,  hash_mb=32),
                 ThinkProfile(1.0,  8.0,  3.5, 2.0, 2.0),
                 ACPLTarget(40,  75,  65,  60)),
    1400: ELOBand(1400, "Intermediate",   EngineProfile(depth=10, movetime_ms=600,  multipv=4, skill_level=9,  hash_mb=32),
                 ThinkProfile(1.2,  9.0,  4.5, 2.3, 1.8),
                 ACPLTarget(30,  60,  52,  47)),
    1500: ELOBand(1500, "Club Player",    EngineProfile(depth=12, movetime_ms=800,  multipv=5, skill_level=11, hash_mb=64),
                 ThinkProfile(1.5, 10.0,  5.0, 2.5, 1.5),
                 ACPLTarget(25,  50,  44,  40)),
    1600: ELOBand(1600, "Strong Club",    EngineProfile(depth=14, movetime_ms=1000, multipv=5, skill_level=13, hash_mb=64),
                 ThinkProfile(1.8, 11.0,  5.5, 2.7, 1.4),
                 ACPLTarget(22,  44,  38,  35)),
    1800: ELOBand(1800, "Expert",         EngineProfile(depth=16, movetime_ms=1500, multipv=5, skill_level=16, hash_mb=128),
                 ThinkProfile(2.0, 12.0,  6.5, 3.0, 1.3),
                 ACPLTarget(18,  35,  30,  28)),
    2000: ELOBand(2000, "Master",         EngineProfile(depth=20, movetime_ms=2000, multipv=5, skill_level=18, hash_mb=128),
                 ThinkProfile(2.5, 13.0,  7.5, 3.2, 1.2),
                 ACPLTarget(14,  28,  24,  22)),
    2200: ELOBand(2200, "IM",             EngineProfile(depth=22, movetime_ms=2500, multipv=5, skill_level=20, hash_mb=256),
                 ThinkProfile(3.0, 14.0,  8.5, 3.4, 1.1),
                 ACPLTarget(11,  22,  19,  17)),
    2400: ELOBand(2400, "GM",             EngineProfile(depth=24, movetime_ms=3000, multipv=5, skill_level=20, hash_mb=256),
                 ThinkProfile(3.5, 15.0,  9.5, 3.5, 1.0),
                 ACPLTarget(9,  18,  15,  14)),
}


def _interp(x: float, x0: float, y0: float, x1: float, y1: float) -> float:
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def get_band(elo: int) -> ELOBand:
    """Snap an arbitrary ELO to the nearest defined band."""
    elo = max(MIN_ELO, min(MAX_ELO, elo))
    keys = sorted(_BANDS.keys())
    if elo <= keys[0]:
        return _BANDS[keys[0]]
    if elo >= keys[-1]:
        return _BANDS[keys[-1]]
    for lo, hi in zip(keys[:-1], keys[1:]):
        if lo <= elo <= hi:
            lo_band, hi_band = _BANDS[lo], _BANDS[hi]
            t = (elo - lo) / (hi - lo)
            return ELOBand(
                elo=elo,
                label=f"~{lo_band.label}–{hi_band.label}",
                engine=EngineProfile(
                    depth=round(_interp(elo, lo, lo_band.engine.depth, hi, hi_band.engine.depth)),
                    movetime_ms=round(_interp(elo, lo, lo_band.engine.movetime_ms, hi, hi_band.engine.movetime_ms)),
                    multipv=round(_interp(elo, lo, lo_band.engine.multipv, hi, hi_band.engine.multipv)),
                    skill_level=round(_interp(elo, lo, lo_band.engine.skill_level, hi, hi_band.engine.skill_level)),
                    hash_mb=round(_interp(elo, lo, lo_band.engine.hash_mb, hi, hi_band.engine.hash_mb)),
                ),
                think=ThinkProfile(
                    min_seconds=_interp(elo, lo, lo_band.think.min_seconds, hi, hi_band.think.min_seconds),
                    max_seconds=_interp(elo, lo, lo_band.think.max_seconds, hi, hi_band.think.max_seconds),
                    mean_seconds=_interp(elo, lo, lo_band.think.mean_seconds, hi, hi_band.think.mean_seconds),
                    std_seconds=_interp(elo, lo, lo_band.think.std_seconds, hi, hi_band.think.std_seconds),
                    blunder_think_bonus=_interp(elo, lo, lo_band.think.blunder_think_bonus, hi, hi_band.think.blunder_think_bonus),
                ),
                acpl=ACPLTarget(
                    opening=_interp(elo, lo, lo_band.acpl.opening, hi, hi_band.acpl.opening),
                    middlegame=_interp(elo, lo, lo_band.acpl.middlegame, hi, hi_band.acpl.middlegame),
                    endgame=_interp(elo, lo, lo_band.acpl.endgame, hi, hi_band.acpl.endgame),
                    overall=_interp(elo, lo, lo_band.acpl.overall, hi, hi_band.acpl.overall),
                ),
            )
    return _BANDS[keys[-1]]


def get_analysis_params(elo: int) -> EngineProfile:
    return get_band(elo).engine


def get_think_profile(elo: int) -> ThinkProfile:
    return get_band(elo).think


def get_acpl_target(elo: int) -> ACPLTarget:
    return get_band(elo).acpl


def get_think_time(
    elo: int,
    complexity: float = 0.5,
    is_critical: bool = False,
    rng: random.Random | None = None,
) -> float:
    """Sample a realistic think time in seconds.

    Args:
        elo: Target human ELO.
        complexity: 0.0 (trivial) to 1.0 (very complex). Modulates time.
        is_critical: True on blunder-or-brilliant decisions → bonus.
        rng: Optional RNG for deterministic testing.
    """
    rng = rng or random.Random()
    profile = get_think_profile(elo)
    complexity_mult = 0.6 + 0.8 * max(0.0, min(1.0, complexity))
    raw = rng.gauss(profile.mean_seconds, profile.std_seconds)
    seconds = max(profile.min_seconds, min(profile.max_seconds, raw * complexity_mult))
    if is_critical:
        seconds *= profile.blunder_think_bonus
    return round(seconds, 2)


def phase_for_move_number(move_number: int, total_legal_moves: int = 60) -> str:
    """Classify a game phase from absolute move number.

    Heuristic:
    - move_number < 12  → opening
    - move_number > 40 OR total_pieces < 12 → endgame
    - else              → middlegame
    """
    if move_number < 12:
        return "opening"
    if total_legal_moves < 12:
        return "endgame"
    return "middlegame"


# ----------------------------- Bayesian ELO Estimator ----------------------------- #


class BayesianELOEstimator:
    """Online ELO estimator using Gaussian likelihood on observed ACPLs.

    Prior: N(1500, 400²) — broad, fair for any online player.
    Likelihood: ACPL ~ N(target(elo), sigma²), where sigma depends on ELO.

    The model updates after every observed move and exposes:
        - mean_elo: best ELO estimate
        - std_elo: posterior uncertainty (standard deviation)
        - 95% credibility interval: (lo, hi)
        - n_samples: moves observed
    """

    def __init__(self, prior_mean: float = 1500.0, prior_std: float = 400.0, sigma_scale: float = 0.15) -> None:
        self.prior_mean = prior_mean
        self.prior_std = prior_std
        self.sigma_scale = sigma_scale
        self.mean = prior_mean
        self.var = prior_std ** 2
        self.n_samples = 0

    @staticmethod
    def _acpl_to_elo_log_likelihood(observed_acpl: float, candidate_elo: float) -> float:
        target = get_acpl_target(candidate_elo).overall
        sigma = max(8.0, target * 0.25)
        return -0.5 * ((observed_acpl - target) / sigma) ** 2

    def update(self, observed_acpl: float) -> None:
        """Bayesian update given an observed centipawn loss for a move."""
        self.n_samples += 1
        candidate_elos = [self.mean + (i - 50) * 8 for i in range(101)]
        max_ll = max(self._acpl_to_elo_log_likelihood(observed_acpl, e) for e in candidate_elos)
        weights = []
        for e in candidate_elos:
            ll = self._acpl_to_elo_log_likelihood(observed_acpl, e)
            weights.append(math.exp(ll - max_ll))
        total = sum(weights)
        new_mean = sum(e * w for e, w in zip(candidate_elos, weights)) / total
        new_var = sum((e - new_mean) ** 2 * w for e, w in zip(candidate_elos, weights)) / total
        new_var = max(new_var, 100.0)

        prior_precision = 1.0 / self.var
        like_precision = 1.0 / new_var
        post_precision = prior_precision + like_precision * self.sigma_scale
        post_var = 1.0 / post_precision
        post_mean = post_var * (self.mean * prior_precision + new_mean * like_precision * self.sigma_scale)
        self.mean = post_mean
        self.var = post_var

    @property
    def mean_elo(self) -> float:
        return round(self.mean, 1)

    @property
    def std_elo(self) -> float:
        return round(math.sqrt(self.var), 1)

    @property
    def ci95(self) -> tuple[float, float]:
        s = math.sqrt(self.var)
        return (round(self.mean - 1.96 * s, 1), round(self.mean + 1.96 * s, 1))

    def reset(self) -> None:
        self.mean = self.prior_mean
        self.var = self.prior_std ** 2
        self.n_samples = 0

    def __repr__(self) -> str:
        return (
            f"BayesianELOEstimator(elo={self.mean_elo}±{self.std_elo} "
            f"n={self.n_samples} ci95={self.ci95})"
        )


__all__ = [
    "EngineProfile",
    "ThinkProfile",
    "ACPLTarget",
    "ELOBand",
    "MIN_ELO",
    "MAX_ELO",
    "get_band",
    "get_analysis_params",
    "get_think_profile",
    "get_acpl_target",
    "get_think_time",
    "phase_for_move_number",
    "BayesianELOEstimator",
]
