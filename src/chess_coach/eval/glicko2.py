"""Glicko-2 rating system.

Glicko-2 (Mark Glickman, 2013) improves on Glicko by using a volatility
parameter to model rating reliability. The scale is also smaller (rating +
RD + volatility, with PI=3.14159...). This implementation is
self-contained and pure stdlib.

Reference: http://www.glicko.net/glicko/glicko2.pdf
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

PI_SQUARED = math.pi ** 2
SCALE = 173.7178  # Conversion between Glicko-2 and Elo scale
INITIAL_RATING = 1500.0
INITIAL_RD = 350.0
INITIAL_VOLATILITY = 0.06
TAU = 0.5  # System constant (0.3..1.2, smaller = less volatile change)
EPSILON = 1e-6


@dataclass
class Glicko2Result:
    """Outcome of a single game from a player's perspective."""

    opponent_rating: float
    opponent_rd: float
    score: float  # 1.0 = win, 0.5 = draw, 0.0 = loss
    opponent_volatility: Optional[float] = None


@dataclass
class Glicko2Player:
    """Player with Glicko-2 state (rating on original Glicko scale)."""

    rating: float = INITIAL_RATING
    rd: float = INITIAL_RD
    volatility: float = INITIAL_VOLATILITY

    def to_glicko2(self) -> Tuple[float, float, float]:
        """Convert to Glicko-2 internal scale (mu, phi)."""
        mu = (self.rating - 1500.0) / SCALE
        phi = self.rd / SCALE
        return mu, phi, self.volatility

    @classmethod
    def from_glicko2(cls, mu: float, phi: float, volatility: float) -> "Glicko2Player":
        """Construct a player from Glicko-2 (mu, phi, sigma)."""
        rating = mu * SCALE + 1500.0
        rd = phi * SCALE
        return cls(rating=rating, rd=rd, volatility=volatility)


def _g(phi: float) -> float:
    """g(phi) = 1 / sqrt(1 + 3*phi^2 / pi^2)."""
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / PI_SQUARED)


def _e(mu: float, mu_j: float, phi_j: float) -> float:
    """Expected score against opponent j."""
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _compute_variance(mu: float, opponents: Sequence[Glicko2Player]) -> float:
    """v = 1 / sum(g(phi_j)^2 * E * (1 - E))."""
    total = 0.0
    for opp in opponents:
        mu_j = (opp.rating - 1500.0) / SCALE
        phi_j = opp.rd / SCALE
        g_phi = _g(phi_j)
        e = _e(mu, mu_j, phi_j)
        total += g_phi * g_phi * e * (1.0 - e)
    if total < EPSILON:
        return 1e10
    return 1.0 / total


def _compute_delta(mu: float, opponents: Sequence[Glicko2Player], scores: Sequence[float]) -> float:
    """delta = v * sum(g(phi_j) * (s_j - E_j))."""
    v = _compute_variance(mu, opponents)
    total = 0.0
    for opp, s in zip(opponents, scores):
        mu_j = (opp.rating - 1500.0) / SCALE
        phi_j = opp.rd / SCALE
        g_phi = _g(phi_j)
        e = _e(mu, mu_j, phi_j)
        total += g_phi * (s - e)
    return v * total


def _compute_new_volatility(sigma: float, phi: float, v: float, delta: float, tau: float) -> float:
    """Find new volatility via Illinois algorithm."""
    a = math.log(sigma * sigma)

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta * delta - phi * phi - v - ex)
        den = 2.0 * (phi * phi + v + ex) ** 2
        return num / den - (x - a) / (tau * tau)

    # a_bound is a hint for the Illinois algorithm; if not finite, ignore.
    try:
        ratio = (delta * delta - phi * phi - v) / max(tau * tau - phi * phi - v, 1e-10)
        if ratio > 0:
            a_bound = math.log(ratio) / 2.0
        else:
            a_bound = a
        if math.isnan(a_bound) or math.isinf(a_bound):
            a_bound = a
    except (ValueError, OverflowError):
        a_bound = a
    A = a
    if delta * delta > phi * phi + v:
        try:
            B = math.log(delta * delta - phi * phi - v)
        except (ValueError, OverflowError):
            k = 1
            while f(a - k * tau) < 0 and k < 100:
                k += 1
            B = a - k * tau
    else:
        k = 1
        while f(a - k * tau) < 0 and k < 100:
            k += 1
        B = a - k * tau

    fA = f(A)
    fB = f(B)
    iterations = 0
    while abs(B - A) > EPSILON and iterations < 100:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A = B
            fA = fB
        else:
            fA = fA / 2.0
        B = C
        fB = fC
        iterations += 1
    return math.exp(A / 2.0)


def update_player(player: Glicko2Player, results: Iterable[Glicko2Result]) -> Glicko2Player:
    """Update a player given a list of game results and return the new state.

    Results with opponent_volatility=None are treated as standard opponents.
    """
    results_list = list(results)
    if not results_list:
        # No games: RD increases toward sqrt(rd^2 + sigma^2) per period
        new_rd = math.sqrt(player.rd * player.rd + player.volatility * player.volatility)
        return Glicko2Player(rating=player.rating, rd=min(new_rd, INITIAL_RD), volatility=player.volatility)

    opponents: List[Glicko2Player] = []
    scores: List[float] = []
    for r in results_list:
        opp = Glicko2Player(
            rating=r.opponent_rating,
            rd=r.opponent_rd,
            volatility=r.opponent_volatility if r.opponent_volatility is not None else INITIAL_VOLATILITY,
        )
        opponents.append(opp)
        scores.append(r.score)

    mu, phi, sigma = player.to_glicko2()
    v = _compute_variance(mu, opponents)
    delta = _compute_delta(mu, opponents, scores)
    new_sigma = _compute_new_volatility(sigma, phi, v, delta, TAU)
    new_phi_star = math.sqrt(phi * phi + new_sigma * new_sigma)
    new_phi = 1.0 / math.sqrt(1.0 / (new_phi_star * new_phi_star) + 1.0 / v)
    new_mu = mu + new_phi * new_phi * sum(
        _g(opp.rd / SCALE) * (s - _e(mu, (opp.rating - 1500.0) / SCALE, opp.rd / SCALE))
        for opp, s in zip(opponents, scores)
    )

    new_player = Glicko2Player.from_glicko2(new_mu, new_phi, new_sigma)
    new_player.rd = min(new_player.rd, INITIAL_RD)
    return new_player


def rating_to_elo(rating: float) -> float:
    """Glicko-2 is on a different scale; this is a no-op since we already store Elo-ish values."""
    return rating


def elo_to_glicko2_rating(elo: float) -> float:
    """No-op conversion (our storage is on the Glicko-2 display scale)."""
    return elo


__all__ = [
    "Glicko2Player",
    "Glicko2Result",
    "INITIAL_RATING",
    "INITIAL_RD",
    "INITIAL_VOLATILITY",
    "TAU",
    "SCALE",
    "update_player",
    "rating_to_elo",
    "elo_to_glicko2_rating",
]
