"""Tests for PGN advanced submodules: NAGs, variations, structured comments."""
from __future__ import annotations

import io
import textwrap

import chess
import chess.pgn as pgn
import pytest

from chess_coach.pgn import (
    NAG_BLUNDER,
    NAG_BRILLIANT_MOVE,
    NAG_CATALOG,
    NAG_GOOD_MOVE,
    NAG_MISTAKE,
    NAG_NULL,
    NagInfo,
    StructuredComment,
    VariationNode,
    classify_quality_nag,
    collect_variations,
    extract_plain_comment,
    find_move_san,
    find_move_uci,
    format_comment,
    has_variations,
    is_standard_nag,
    is_structured_comment,
    is_valid_nag,
    longest_forced_line,
    mainline_with_indices,
    nag_description,
    nag_short,
    nag_symbol,
    parse_all_comments,
    parse_comment,
    parse_mate,
    parse_nags,
    ply_count,
    quality_to_nag,
    total_ply_count,
    trim_to_ply,
    variation_count,
    variation_depth_at,
)


class TestNags:
    def test_catalog_has_31_entries(self):
        assert len(NAG_CATALOG) == 31  # 0..30

    def test_null_nag(self):
        assert NAG_CATALOG[0].description == "no annotation"
        assert NAG_CATALOG[0].symbol == ""

    def test_good_move(self):
        info = NAG_CATALOG[NAG_GOOD_MOVE]
        assert info.symbol == "!"
        assert info.description == "good move"

    def test_brilliant(self):
        info = NAG_CATALOG[NAG_BRILLIANT_MOVE]
        assert info.symbol == "!!"
        assert info.description == "brilliant move"

    def test_blunder(self):
        info = NAG_CATALOG[NAG_BLUNDER]
        assert info.symbol == "??"
        assert info.description == "blunder"

    def test_is_valid_nag(self):
        assert is_valid_nag(0)
        assert is_valid_nag(255)
        assert is_valid_nag(30)
        assert not is_valid_nag(-1)
        assert not is_valid_nag(256)

    def test_is_standard_nag(self):
        assert is_standard_nag(0)
        assert is_standard_nag(30)
        assert not is_standard_nag(31)
        assert not is_standard_nag(255)

    def test_nag_symbol(self):
        assert nag_symbol(1) == "!"
        assert nag_symbol(3) == "!!"
        assert nag_symbol(4) == "??"
        assert nag_symbol(31) == ""  # Unknown

    def test_nag_description(self):
        assert "brilliant" in nag_description(3)
        assert "blunder" in nag_description(4)

    def test_nag_short(self):
        assert nag_short(1) == "!"
        assert nag_short(99) == "$99"

    def test_classify_quality_nag(self):
        assert classify_quality_nag(3) == "brilliant"
        assert classify_quality_nag(1) == "good"
        assert classify_quality_nag(2) == "mistake"
        assert classify_quality_nag(4) == "blunder"
        assert classify_quality_nag(7) == "forced"
        assert classify_quality_nag(9) == "worst"
        assert classify_quality_nag(0) is None
        assert classify_quality_nag(99) is None

    def test_quality_to_nag(self):
        assert quality_to_nag("brilliant") == 3
        assert quality_to_nag("good") == 1
        assert quality_to_nag("mistake") == 2
        assert quality_to_nag("blunder") == 4
        assert quality_to_nag("forced") == 7
        assert quality_to_nag("unknown") == 0

    def test_quality_to_nag_case_insensitive(self):
        assert quality_to_nag("BRILLIANT") == 3
        assert quality_to_nag("Blunder") == 4

    def test_parse_nags_simple(self):
        assert parse_nags("1 2 3") == [1, 2, 3]

    def test_parse_nags_comma_separated(self):
        assert parse_nags("1,2,3") == [1, 2, 3]

    def test_parse_nags_invalid(self):
        assert parse_nags("1 foo 2 bar 3") == [1, 2, 3]

    def test_parse_nags_out_of_range(self):
        assert parse_nags("1 256 -1 2") == [1, 2]


class TestVariations:
    def _make_game_with_variations(self) -> pgn.Game:
        pgn_text = textwrap.dedent("""
        1. e4 e5 (1... c5 {Sicilian}) 2. Nf3 Nc6 (2... d6) 3. Bb5 *
        """)
        return pgn.read_game(io.StringIO(pgn_text))

    def test_collect_variations_returns_list(self):
        game = self._make_game_with_variations()
        var = collect_variations(game)
        # First level: 1. e4
        assert len(var) == 1
        # e4 move
        assert var[0].san == "e4"
        # The response has a variation
        assert var[0].variations  # 1... c5

    def test_variation_count(self):
        game = self._make_game_with_variations()
        # Sub-variations: c5 (sibling of e5), d6 (sibling of Nc6) = 2
        assert variation_count(game) == 2

    def test_longest_forced_line(self):
        game = self._make_game_with_variations()
        forced = longest_forced_line(game)
        # Mainline: e4, e5, Nf3, Nc6, Bb5
        assert len(forced) == 5
        assert forced[0].uci() == "e2e4"
        assert forced[-1].uci() == "f1b5"

    def test_ply_count(self):
        game = self._make_game_with_variations()
        assert ply_count(game) == 5

    def test_total_ply_count(self):
        game = self._make_game_with_variations()
        assert total_ply_count(game) == 5

    def test_has_variations_true(self):
        game = self._make_game_with_variations()
        assert has_variations(game) is True

    def test_has_variations_false(self):
        game = pgn.read_game(io.StringIO("1. e4 e5 1/2-1/2"))
        assert has_variations(game) is False

    def test_find_move_san(self):
        game = self._make_game_with_variations()
        # Find Nf3 in mainline
        node = find_move_san(game, "Nf3")
        assert node is not None
        assert node.move.uci() == "g1f3"

    def test_find_move_san_missing(self):
        game = self._make_game_with_variations()
        node = find_move_san(game, "Qxd5")
        assert node is None

    def test_find_move_uci(self):
        game = self._make_game_with_variations()
        node = find_move_uci(game, "g1f3")
        assert node is not None
        assert node.san() == "Nf3"

    def test_mainline_with_indices(self):
        game = pgn.read_game(io.StringIO("1. e4 e5 2. Nf3 1/2-1/2"))
        moves = mainline_with_indices(game)
        assert len(moves) == 3
        assert moves[0] == (0, chess.Move.from_uci("e2e4"), "e4")
        assert moves[1][2] == "e5"
        assert moves[2][2] == "Nf3"

    def test_trim_to_ply(self):
        game = pgn.read_game(io.StringIO("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *"))
        trimmed = trim_to_ply(game, 3)
        assert total_ply_count(trimmed) == 3
        # First three plies: e4, e5, Nf3
        forced = longest_forced_line(trimmed)
        assert len(forced) == 3

    def test_collect_variations_empty_game(self):
        game = pgn.Game()
        var = collect_variations(game)
        assert var == []


class TestStructuredComments:
    def test_parse_empty_comment(self):
        sc = parse_comment("")
        assert sc.text == ""
        assert not sc.has_eval
        assert not sc.has_clock

    def test_parse_plain_comment(self):
        sc = parse_comment("This is a good move.")
        assert sc.text == "This is a good move."
        assert not sc.has_eval

    def test_parse_eval_cp(self):
        sc = parse_comment("{[%eval 0.34]} good position")
        assert sc.eval_cp == pytest.approx(0.34)
        assert sc.has_eval
        assert sc.mate_in is None

    def test_parse_eval_negative(self):
        sc = parse_comment("[%eval -1.25]")
        assert sc.eval_cp == pytest.approx(-1.25)

    def test_parse_eval_mate(self):
        sc = parse_comment("[%eval #5]")
        assert sc.mate_in == 5
        assert sc.eval_cp is None

    def test_parse_eval_negative_mate(self):
        sc = parse_comment("[%eval #-3]")
        assert sc.mate_in == -3

    def test_parse_clock(self):
        sc = parse_comment("[%clk 0:01:23.45]")
        assert sc.clock_seconds == pytest.approx(83.45)

    def test_parse_clock_short(self):
        sc = parse_comment("[%clk 0:05:00]")
        assert sc.clock_seconds == 300.0

    def test_parse_csl(self):
        sc = parse_comment("[%csl Ra1,Rb2,Yg3]")
        assert sc.squares_colored == ["Ra1", "Rb2", "Yg3"]

    def test_parse_cal(self):
        sc = parse_comment("[%cal Ge2e4,Re2e4]")
        assert sc.arrows_colored == ["Ge2e4", "Re2e4"]

    def test_parse_mdt(self):
        sc = parse_comment("[%mdt 0:00:42]")
        assert sc.move_duration == pytest.approx(42.0)

    def test_parse_combined(self):
        text = "[%eval 0.34][%clk 0:01:23][%csl Ra1]"
        sc = parse_comment(text)
        assert sc.eval_cp == pytest.approx(0.34)
        assert sc.clock_seconds == pytest.approx(83.0)
        assert sc.squares_colored == ["Ra1"]

    def test_is_structured_comment(self):
        assert is_structured_comment("[%eval 0.5]") is True
        assert is_structured_comment("[%clk 0:01:00]") is True
        assert is_structured_comment("plain text") is False
        assert is_structured_comment("") is False

    def test_extract_plain_comment(self):
        cleaned = extract_plain_comment("good move [%eval 0.34] here")
        assert "good move" in cleaned
        assert "here" in cleaned
        assert "[%eval" not in cleaned

    def test_format_comment_roundtrip(self):
        sc = StructuredComment(
            text="Nice",
            eval_cp=0.5,
            clock_seconds=120.0,
            squares_colored=["Ra1"],
        )
        formatted = format_comment(sc)
        assert "{ Nice" in formatted
        assert "[%eval +0.50]" in formatted
        # PGN standard clock format is H:MM:SS.d — 120s = 0:02:00.00
        assert "[%clk 0:02:00.00]" in formatted
        # Round-trip
        sc2 = parse_comment(formatted)
        assert sc2.eval_cp == pytest.approx(0.5)
        assert sc2.clock_seconds == pytest.approx(120.0)

    def test_format_comment_empty(self):
        assert format_comment(StructuredComment()) == ""

    def test_eval_string(self):
        sc = StructuredComment(eval_cp=0.5)
        assert sc.eval_string == "+0.50"
        sc2 = StructuredComment(mate_in=3)
        assert sc2.eval_string == "#3"

    def test_clock_string(self):
        # PGN standard [%clk H:MM:SS.d] — always 3 components
        sc = StructuredComment(clock_seconds=83.45)
        assert sc.clock_string == "0:01:23.45"
        sc2 = StructuredComment(clock_seconds=3725.0)
        assert sc2.clock_string == "1:02:05.00"

    def test_parse_mate_helper(self):
        assert parse_mate("#5") == 5
        assert parse_mate("#-3") == -3
        assert parse_mate("0.34") is None

    def test_parse_all_comments(self):
        out = parse_all_comments(["[%eval 0.5]", "plain", "[%clk 0:01:00]"])
        assert out[0].eval_cp == pytest.approx(0.5)
        assert out[1].text == "plain"
        assert out[2].clock_seconds == pytest.approx(60.0)


class TestVariationDepth:
    def test_variation_depth_at_root(self):
        game = pgn.read_game(io.StringIO("1. e4 e5 (1... c5) 2. Nf3 *"))
        # Root has 1 variation (e4), sibling c5 appears 1 ply into mainline
        assert variation_depth_at(game) == 1


class TestPgnIntegration:
    def test_round_trip_nag_in_pgn(self):
        """Test that NAG constants match python-chess's NAG constants."""
        import chess.pgn as pgn
        # Sanity: our constants match python-chess
        assert NAG_GOOD_MOVE == pgn.NAG_GOOD_MOVE
        assert NAG_BRILLIANT_MOVE == pgn.NAG_BRILLIANT_MOVE
        assert NAG_BLUNDER == pgn.NAG_BLUNDER
        assert NAG_NULL == 0
