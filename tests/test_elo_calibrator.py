"""Tests for elo_calibrator module."""

from __future__ import annotations

import pytest

from chess_coach.elo_calibrator import (
    BayesianELOEstimator,
    ELOBand,
    EngineProfile,
    ThinkProfile,
    ACPLTarget,
    MIN_ELO,
    MAX_ELO,
    get_band,
    get_analysis_params,
    get_think_profile,
    get_acpl_target,
    get_think_time,
    phase_for_move_number,
)


class TestELOBand:
    def test_known_bands_exist(self) -> None:
        for elo in (800, 1000, 1200, 1500, 1800, 2200, 2400):
            band = get_band(elo)
            assert band.elo == elo
            assert band.label

    def test_band_monotonic_depth(self) -> None:
        depths = [get_band(elo).engine.depth for elo in (800, 1200, 1500, 1800, 2200, 2400)]
        assert depths == sorted(depths)

    def test_band_monotonic_acpl(self) -> None:
        # Higher ELO → lower ACPL (better play, fewer centipawns lost)
        acpls = [get_band(elo).acpl.overall for elo in (800, 1200, 1500, 1800, 2200, 2400)]
        assert acpls == sorted(acpls, reverse=True)

    def test_band_interpolation(self) -> None:
        b1 = get_band(1300)
        b2 = get_band(1500)
        bi = get_band(1400)
        assert b1.engine.depth < bi.engine.depth < b2.engine.depth

    def test_band_clamping(self) -> None:
        assert get_band(MIN_ELO - 1000).elo == MIN_ELO
        assert get_band(MAX_ELO + 1000).elo == MAX_ELO

    def test_think_profile_increases_with_elo(self) -> None:
        # Stronger players think longer on average
        means = [get_band(elo).think.mean_seconds for elo in (800, 1200, 1500, 1800, 2200, 2400)]
        assert means[0] < means[-1]

    def test_acpl_target_per_phase(self) -> None:
        for elo in (1500, 1800):
            t = get_acpl_target(elo)
            assert t.opening < t.overall or t.opening == t.overall
            assert t.middlegame > 0


class TestGetAnalysisParams:
    def test_returns_engine_profile(self) -> None:
        p = get_analysis_params(1500)
        assert isinstance(p, EngineProfile)
        assert p.depth >= 4
        assert p.movetime_ms >= 100

    def test_stronger_elo_more_depth(self) -> None:
        a = get_analysis_params(1200).depth
        b = get_analysis_params(2000).depth
        assert b > a


class TestGetThinkTime:
    def test_within_profile_bounds(self) -> None:
        import random
        rng = random.Random(0)
        for _ in range(20):
            t = get_think_time(1500, complexity=0.5, rng=rng)
            prof = get_think_profile(1500)
            assert prof.min_seconds <= t <= prof.max_seconds

    def test_complexity_increases_time(self) -> None:
        import random
        samples_simple = [get_think_time(1500, complexity=0.1, rng=random.Random(i)) for i in range(50)]
        samples_complex = [get_think_time(1500, complexity=0.9, rng=random.Random(i)) for i in range(50)]
        assert sum(samples_complex) > sum(samples_simple)

    def test_critical_boosts_time(self) -> None:
        import random
        normal = [get_think_time(1500, is_critical=False, rng=random.Random(i)) for i in range(50)]
        critical = [get_think_time(1500, is_critical=True, rng=random.Random(i)) for i in range(50)]
        assert sum(critical) > sum(normal)

    def test_higher_elo_slower_on_average(self) -> None:
        import random
        weak = [get_think_time(1000, rng=random.Random(i)) for i in range(100)]
        strong = [get_think_time(2200, rng=random.Random(i)) for i in range(100)]
        assert sum(strong) > sum(weak)


class TestPhaseForMoveNumber:
    def test_opening_phase(self) -> None:
        for n in (1, 5, 11):
            assert phase_for_move_number(n) == "opening"

    def test_middlegame_phase(self) -> None:
        for n in (15, 25, 35):
            assert phase_for_move_number(n) == "middlegame"

    def test_endgame_phase_low_pieces(self) -> None:
        assert phase_for_move_number(40, total_legal_moves=10) == "endgame"


class TestBayesianELOEstimator:
    def test_initial_state(self) -> None:
        e = BayesianELOEstimator()
        assert e.mean_elo == 1500.0
        assert e.n_samples == 0

    def test_low_acpl_increases_estimate(self) -> None:
        e = BayesianELOEstimator()
        for _ in range(20):
            e.update(20.0)  # way below 1500-target ~40
        assert e.mean_elo > 1500

    def test_high_acpl_decreases_estimate(self) -> None:
        e = BayesianELOEstimator()
        for _ in range(20):
            e.update(120.0)  # way above 1500-target ~40
        assert e.mean_elo < 1500

    def test_ci95_shrinks_with_data(self) -> None:
        e = BayesianELOEstimator()
        ci_initial = e.ci95
        for _ in range(50):
            e.update(40.0)
        ci_after = e.ci95
        assert (ci_after[1] - ci_after[0]) < (ci_initial[1] - ci_initial[0])

    def test_reset(self) -> None:
        e = BayesianELOEstimator()
        e.update(20.0)
        e.reset()
        assert e.n_samples == 0
        assert e.mean_elo == 1500.0

    def test_repr_contains_elo(self) -> None:
        e = BayesianELOEstimator()
        assert "elo=" in repr(e)
