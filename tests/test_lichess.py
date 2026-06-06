"""Tests for Lichess integration (Phase M)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from chess_coach.lichess.explorer import (
    LichessExplorer,
    ExplorerResponse,
    MoveStats,
    ExplorerSource,
)
from chess_coach.lichess.puzzles import (
    LichessPuzzles,
    Puzzle,
    PuzzleTheme,
    curated_puzzles,
)
from chess_coach.lichess.cache import LichessCache, default_cache_path
from chess_coach.lichess.oauth import (
    LichessOAuth,
    OAuthToken,
    _generate_pkce,
    LICHESS_OAUTH_AUTHORIZE,
)
from chess_coach.lichess.study_sync import StudySync, _split_pgn_chapters
from chess_coach.lichess.game_sync import GameSync, GameSummary


# ===== MoveStats =====

class TestMoveStats:
    def test_basic(self) -> None:
        m = MoveStats(
            uci="e2e4", san="e4", white_wins=100, draws=50, black_wins=50,
            average_rating=1600,
        )
        assert m.total == 200
        assert m.white_winrate == 0.5
        assert m.drawrate == 0.25
        assert m.black_winrate == 0.25

    def test_zero_total(self) -> None:
        m = MoveStats(uci="", san="", white_wins=0, draws=0, black_wins=0,
                      average_rating=1500)
        assert m.white_winrate == 0.0
        assert m.drawrate == 0.0


class TestExplorerResponse:
    def test_best_move(self) -> None:
        moves = [
            MoveStats("e2e4", "e4", 50, 20, 30, 1500),
            MoveStats("d2d4", "d4", 100, 40, 60, 1500),
        ]
        resp = ExplorerResponse(fen="x", moves=moves)
        best = resp.best_move()
        assert best is not None
        assert best.uci == "d2d4"  # higher total

    def test_empty(self) -> None:
        resp = ExplorerResponse(fen="x", moves=[])
        assert resp.best_move() is None
        assert resp.best_by_winrate() is None


# ===== LichessExplorer (with mocked HTTP) =====

class TestLichessExplorer:
    def test_query_requires_player_for_player_source(self) -> None:
        cache = LichessCache(":memory:")
        ex = LichessExplorer(cache=cache)
        # No player specified for source=player -> should raise
        with pytest.raises(ValueError):
            ex.query("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                     source=ExplorerSource.PLAYER)

    def test_query_handles_network_error(self) -> None:
        """If network fails, return empty response (graceful)."""
        cache = LichessCache(":memory:")
        ex = LichessExplorer(cache=cache)
        with patch("chess_coach.lichess.explorer.urlopen", side_effect=URLError("no network")):
            resp = ex.query("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        assert resp.moves == []
        assert resp.fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    def test_query_parses_response(self) -> None:
        cache = LichessCache(":memory:")
        ex = LichessExplorer(cache=cache)
        mock_data = {
            "moves": [
                {"uci": "e2e4", "san": "e4", "white": 100, "draws": 50, "black": 50,
                 "averageRating": 1600},
            ]
        }

        import contextlib

        class _H:
            def get(self, key: str, default: str = "") -> str:
                return "20"

        @contextlib.contextmanager
        def fake_urlopen(req, timeout=None):  # noqa: ARG001
            class _Resp:
                def read(self_inner) -> bytes:
                    return json.dumps(mock_data).encode()

                headers = _H()

                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *args):
                    return False
            yield _Resp()

        with patch("chess_coach.lichess.explorer.urlopen", fake_urlopen):
            resp = ex.query("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        assert len(resp.moves) == 1
        assert resp.moves[0].san == "e4"
        assert resp.moves[0].total == 200


# ===== Cache =====

class TestLichessCache:
    def test_set_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = LichessCache(Path(tmp) / "test.sqlite")
            cache.set("key1", {"hello": "world"})
            v = cache.get("key1")
            assert v == {"hello": "world"}

    def test_get_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = LichessCache(Path(tmp) / "test.sqlite")
            assert cache.get("nonexistent") is None

    def test_ttl_expiry(self) -> None:
        import gc
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "test.sqlite"
            cache = LichessCache(db_path)
            cache.set("key1", "value", ttl_s=1)
            assert cache.get("key1") == "value"
            # Manually expire via raw sqlite, close immediately
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            conn.execute("UPDATE cache SET expires_at = 0")
            conn.commit()
            conn.close()
            del cache
            gc.collect()
            new_cache = LichessCache(db_path)
            assert new_cache.get("key1") is None

    def test_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = LichessCache(Path(tmp) / "test.sqlite")
            cache.set("a", 1)
            cache.set("b", 2)
            stats = cache.stats()
            assert stats["total"] == 2
            assert stats["valid"] == 2

    def test_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = LichessCache(Path(tmp) / "test.sqlite")
            cache.set("a", 1)
            cache.clear()
            assert cache.get("a") is None


# ===== Puzzles =====

class TestPuzzle:
    def test_to_from_dict(self) -> None:
        d = {
            "id": "abc", "fen": "startpos", "moves": ["e2e4"],
            "rating": 1500, "ratingDeviation": 75, "popularity": 90,
            "nbPlays": 1000, "themes": ["fork"], "openingTags": ["Italian"],
        }
        p = Puzzle.from_dict(d)
        assert p.id == "abc"
        assert p.rating == 1500
        assert "fork" in p.themes
        d2 = p.to_dict()
        assert d2["id"] == "abc"

    def test_primary_theme(self) -> None:
        p = Puzzle(id="x", fen="x", moves=[], rating=1500, rating_deviation=75,
                   popularity=0, nb_plays=0, themes=["fork", "pin"])
        assert p.primary_theme == "fork"

    def test_no_themes(self) -> None:
        p = Puzzle(id="x", fen="x", moves=[], rating=1500, rating_deviation=75,
                   popularity=0, nb_plays=0, themes=[])
        assert p.primary_theme == "unknown"


class TestLichessPuzzles:
    def test_fetch_next_no_token(self) -> None:
        p = LichessPuzzles(oauth_token=None)
        assert p.fetch_next() is None

    def test_list_themes(self) -> None:
        p = LichessPuzzles()
        themes = p.list_themes()
        assert "fork" in themes
        assert "mateIn1" in themes
        assert "pin" in themes

    def test_theme_description(self) -> None:
        p = LichessPuzzles()
        assert p.theme_description("fork") == "Knight fork"
        assert p.theme_description("mateIn1") == "Mate in 1"
        # Unknown theme returns title-cased
        assert "Discovered" in p.theme_description("discoveredAttack")


class TestCuratedPuzzles:
    def test_returns_at_least_three(self) -> None:
        p = curated_puzzles()
        assert len(p) >= 3
        for puzzle in p:
            assert puzzle.fen
            assert puzzle.rating > 0
            assert puzzle.themes


# ===== OAuth =====

class TestPkce:
    def test_generate(self) -> None:
        v, c = _generate_pkce()
        assert len(v) > 40
        assert len(c) > 40
        assert v != c  # verifier and challenge should differ


class TestOAuthToken:
    def test_construction(self) -> None:
        t = OAuthToken(
            access_token="abc", token_type="Bearer",
            expires_at=int(time.time()) + 3600, scope="preference:read",
        )
        assert not t.is_expired

    def test_expired(self) -> None:
        t = OAuthToken(
            access_token="x", token_type="Bearer",
            expires_at=0, scope="",
        )
        assert t.is_expired

    def test_json_roundtrip(self) -> None:
        t = OAuthToken(
            access_token="x", token_type="Bearer",
            expires_at=12345, scope="read", user_id="alice",
        )
        s = t.to_json()
        t2 = OAuthToken.from_json(s)
        assert t2.access_token == "x"
        assert t2.user_id == "alice"


class TestLichessOAuth:
    def test_authorize_url(self) -> None:
        oauth = LichessOAuth()
        url = oauth.authorize_url()
        assert url.startswith(LICHESS_OAUTH_AUTHORIZE)
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "response_type=code" in url

    def test_is_authenticated_no_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            oauth = LichessOAuth()
            oauth._token_path = Path(tmp) / "nonexistent.json"
            assert not oauth.is_authenticated()

    def test_revoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            oauth = LichessOAuth()
            oauth._token_path = Path(tmp) / "token.json"
            oauth._token_path.write_text('{"access_token": "x"}')
            oauth.revoke()
            assert not oauth._token_path.exists()

    def test_exchange_code_state_mismatch(self) -> None:
        oauth = LichessOAuth()
        oauth.authorize_url()  # sets up verifier + state
        with pytest.raises(ValueError):
            oauth.exchange_code("some_code", "wrong_state")


# ===== Study Sync =====

class TestSplitPgnChapters:
    def test_single_chapter(self) -> None:
        pgn = "[Event \"A\"]\n\n1. e4 e5\n"
        chapters = _split_pgn_chapters(pgn)
        assert len(chapters) == 1
        assert "e4" in chapters[0]

    def test_multi_chapter(self) -> None:
        pgn = '[Event "A"]\n\n1. e4\n\n[Event "B"]\n\n1. d4\n'
        chapters = _split_pgn_chapters(pgn)
        assert len(chapters) == 2


class TestStudySync:
    def test_fetch_no_token(self) -> None:
        s = StudySync(oauth_token=None)
        with patch("urllib.request.urlopen", side_effect=URLError("offline")):
            result = s.fetch("abc123")
        assert result is None


# ===== Game Sync =====

class TestGameSync:
    def test_stream_no_token(self) -> None:
        g = GameSync(oauth_token=None)
        # No token -> no games
        games = list(g.stream_user_games("alice"))
        assert games == []
