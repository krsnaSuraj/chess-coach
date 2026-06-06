"""Anti-cheat risk scoring.

Computes a 0-100 risk score indicating how likely the user's play is to be
flagged by chess.com's anti-cheat system, based on observable signals.

Signals tracked (with their estimated weight from the chess.com blog post
"Behind the Firewall" Feb 2026):
1. SF top-1 match rate            30%   (lower = safer)
2. Average centipawn loss         25%   (lower than ELO = suspicious)
3. Move time variance              15%   (too uniform = bot)
4. Style consistency               10%   (too perfect = engine, too erratic = not learned)
5. Tactical accuracy              10%   (too high = engine)
6. Blunder frequency               5%   (zero = engine)
7. Phase-conditional accuracy      5%   (too even across phases = engine)

The score is a soft indicator — it should NOT be exposed to the user as a
"you might get banned" warning. We use it internally to nudge the humanizer
toward more human-like play when risk exceeds 60.

References:
    https://www.chess.com/blog/shah-abbas-safavy/behind-the-firewall-...
    https://www.chess.com/blog/Jordi641/undetectable-by-design-...
    https://www.chess.com/blog/VNicolaisen/how-new-anti-cheating-technology-...
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    SAFE = "safe"            # 0-30
    LOW = "low"              # 30-50
    MODERATE = "moderate"    # 50-65
    HIGH = "high"            # 65-80
    CRITICAL = "critical"    # 80-100


RISK_LABELS: dict[RiskLevel, str] = {
    RiskLevel.SAFE:     "Safe",
    RiskLevel.LOW:      "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH:     "High",
    RiskLevel.CRITICAL: "Critical",
}


@dataclass
class RiskSignals:
    """All input signals to the risk scorer."""

    top1_match_rate: float = 0.0           # fraction of moves that are SF top-1
    avg_cpl: float = 50.0                  # average centipawn loss
    target_elo: int = 1500                 # the humanizer's target ELO
    move_time_variance: float = 5.0        # std dev of move times in seconds
    style_consistency: float = 0.5         # 0-1
    tactical_accuracy: float = 0.50        # 0-1
    blunder_frequency: float = 0.05        # 0-1
    phase_accuracy_variance: float = 0.10  # variance across opening/middle/end


@dataclass
class RiskResult:
    score: float
    level: RiskLevel
    label: str
    contributions: dict[str, float]
    recommendation: str


def _top1_risk(rate: float) -> float:
    """0% match = 0 risk, 90%+ = 100 risk."""
    return min(1.0, max(0.0, (rate - 0.20) / 0.70)) * 100


def _cpl_risk(avg_cpl: float, target_elo: int) -> float:
    """Lower than ELO target = higher risk."""
    from chess_coach.elo_calibrator import get_acpl_target
    target_cpl = get_acpl_target(target_elo).overall
    if avg_cpl <= 0:
        return 100.0
    ratio = target_cpl / max(1.0, avg_cpl)
    if ratio <= 1.0:
        return min(100.0, ratio * 30.0)  # avg CPL at or above target = 0-30 risk
    # avg CPL is below target — risky
    excess = ratio - 1.0
    return min(100.0, 30.0 + excess * 200.0)


def _time_variance_risk(std_seconds: float) -> float:
    """<1s variance = suspicious bot, 2-8s = human, >12s = novice."""
    if std_seconds < 0.5:
        return 100.0
    if std_seconds < 1.5:
        return 90.0
    if std_seconds < 2.5:
        return 60.0
    if std_seconds < 8.0:
        return 10.0
    if std_seconds < 12.0:
        return 25.0
    return 45.0


def _consistency_risk(score: float) -> float:
    """0.5 = balanced human, 0.0 or 1.0 = suspicious."""
    deviation = abs(score - 0.5)
    return min(100.0, deviation * 200.0)


def _tactical_accuracy_risk(acc: float) -> float:
    if acc < 0.30:
        return 5.0
    if acc < 0.55:
        return 10.0
    if acc < 0.75:
        return 25.0
    if acc < 0.90:
        return 55.0
    return 85.0


def _blunder_freq_risk(freq: float) -> float:
    if freq <= 0.005:
        return 100.0
    if freq < 0.03:
        return 80.0
    if freq < 0.10:
        return 40.0
    if freq < 0.30:
        return 10.0
    return 40.0


def _phase_variance_risk(variance: float) -> float:
    """Variance 0 = same accuracy across phases = suspicious."""
    return min(100.0, (1.0 - min(1.0, variance / 0.30)) * 100.0)


_WEIGHTS = {
    "top1_match": 0.30,
    "cpl": 0.25,
    "time_variance": 0.15,
    "consistency": 0.10,
    "tactical_accuracy": 0.10,
    "blunder_frequency": 0.05,
    "phase_variance": 0.05,
}


def compute_risk(signals: RiskSignals) -> RiskResult:
    """Return composite risk score [0, 100] with breakdown and recommendation."""
    contributions = {
        "top1_match": _top1_risk(signals.top1_match_rate) * _WEIGHTS["top1_match"],
        "cpl": _cpl_risk(signals.avg_cpl, signals.target_elo) * _WEIGHTS["cpl"],
        "time_variance": _time_variance_risk(signals.move_time_variance) * _WEIGHTS["time_variance"],
        "consistency": _consistency_risk(signals.style_consistency) * _WEIGHTS["consistency"],
        "tactical_accuracy": _tactical_accuracy_risk(signals.tactical_accuracy) * _WEIGHTS["tactical_accuracy"],
        "blunder_frequency": _blunder_freq_risk(signals.blunder_frequency) * _WEIGHTS["blunder_frequency"],
        "phase_variance": _phase_variance_risk(signals.phase_accuracy_variance) * _WEIGHTS["phase_variance"],
    }
    score = sum(contributions.values())
    score = max(0.0, min(100.0, score))
    if score < 30:
        level, label = RiskLevel.SAFE, RISK_LABELS[RiskLevel.SAFE]
    elif score < 50:
        level, label = RiskLevel.LOW, RISK_LABELS[RiskLevel.LOW]
    elif score < 65:
        level, label = RiskLevel.MODERATE, RISK_LABELS[RiskLevel.MODERATE]
    elif score < 80:
        level, label = RiskLevel.HIGH, RISK_LABELS[RiskLevel.HIGH]
    else:
        level, label = RiskLevel.CRITICAL, RISK_LABELS[RiskLevel.CRITICAL]
    recommendation = _recommend_for_level(level, contributions)
    return RiskResult(
        score=round(score, 1),
        level=level,
        label=label,
        contributions={k: round(v, 2) for k, v in contributions.items()},
        recommendation=recommendation,
    )


def _recommend_for_level(level: RiskLevel, contribs: dict[str, float]) -> str:
    if level == RiskLevel.SAFE:
        return "Current style looks safely human. Keep playing."
    top = max(contribs.items(), key=lambda kv: kv[1])[0]
    table = {
        "top1_match":         "Top-1 match rate too high. Increase sampling from Maia top-3.",
        "cpl":                "Average CPL too low for target ELO. Allow more humanizing mistakes.",
        "time_variance":      "Move timing too uniform. Vary think time more.",
        "consistency":        "Style too consistent. Loosen personality consistency.",
        "tactical_accuracy":  "Tactical solve rate too high. Drop tactics occasionally.",
        "blunder_frequency":  "Blunder frequency too low. Inject rare realistic blunders.",
        "phase_variance":     "Accuracy too even across phases. Vary by phase.",
    }
    return table.get(top, "Adjust humanizer parameters.")


def update_risk_from_history(
    history: list[dict],
    target_elo: int = 1500,
) -> RiskResult:
    """Compute risk from a history of move records.

    Each history item: {"move": Move, "cpl": float, "time_s": float,
                        "is_top1": bool, "phase": str}
    """
    if not history:
        signals = RiskSignals(target_elo=target_elo)
        return compute_risk(signals)
    cpls = [h.get("cpl", 50.0) for h in history]
    times = [h.get("time_s", 5.0) for h in history]
    top1_rate = sum(1 for h in history if h.get("is_top1")) / len(history)
    blunder_freq = sum(1 for c in cpls if c > 200) / len(cpls)
    phase_groups: dict[str, list[float]] = {}
    for h in history:
        phase_groups.setdefault(h.get("phase", "middlegame"), []).append(h.get("cpl", 50.0))
    phase_means = [sum(g) / len(g) for g in phase_groups.values() if g]
    if len(phase_means) >= 2:
        phase_var = statistics.pstdev(phase_means) / max(1.0, statistics.mean(phase_means))
    else:
        phase_var = 0.10
    time_var = statistics.pstdev(times) if len(times) >= 2 else 0.0
    signals = RiskSignals(
        top1_match_rate=top1_rate,
        avg_cpl=sum(cpls) / len(cpls),
        target_elo=target_elo,
        move_time_variance=time_var,
        style_consistency=0.6,
        tactical_accuracy=0.50,
        blunder_frequency=blunder_freq,
        phase_accuracy_variance=phase_var,
    )
    return compute_risk(signals)


__all__ = [
    "RiskLevel",
    "RISK_LABELS",
    "RiskSignals",
    "RiskResult",
    "compute_risk",
    "update_risk_from_history",
]
