"""Lichess OAuth 2.0 with PKCE (no client secret needed for public apps).

Flow:
  1. Generate code_verifier + code_challenge
  2. Redirect user to https://lichess.org/oauth/authorize?...
  3. User logs in, approves, gets redirected to redirect_uri with code
  4. Exchange code + verifier for access token
  5. Use token in Authorization: Bearer <token> header

SOTA 2026 standard: PKCE (RFC 7636) for public clients.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_OAUTH_AUTHORIZE = "https://lichess.org/oauth/authorize"
LICHESS_OAUTH_TOKEN = "https://lichess.org/api/token"
DEFAULT_REDIRECT_URI = "http://localhost:8080/oauth/callback"
DEFAULT_SCOPES = [
    "preference:read",
    "puzzle:read",
    "study:read",
    "study:write",
    "game:read",
]


@dataclass
class OAuthToken:
    """An OAuth access token + metadata."""
    access_token: str
    token_type: str
    expires_at: int  # unix seconds
    scope: str
    user_id: str | None = None

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_json(self) -> str:
        return json.dumps({
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "user_id": self.user_id,
        })

    @classmethod
    def from_json(cls, raw: str) -> "OAuthToken":
        d = json.loads(raw)
        return cls(**d)


def _generate_pkce() -> tuple[str, str]:
    """Generate a (code_verifier, code_challenge) pair per RFC 7636."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


class LichessOAuth:
    """Lichess OAuth 2.0 with PKCE."""

    def __init__(self, redirect_uri: str = DEFAULT_REDIRECT_URI, scopes: list[str] | None = None) -> None:
        self._redirect_uri = redirect_uri
        self._scopes = scopes or DEFAULT_SCOPES
        self._verifier: str | None = None
        self._state: str | None = None
        self._token_path = Path(os.environ.get(
            "CHESS_COACH_OAUTH",
            str(Path.home() / ".chess_coach" / "oauth_token.json"),
        ))

    def authorize_url(self) -> str:
        """Generate the URL the user should be redirected to."""
        self._verifier, challenge = _generate_pkce()
        self._state = secrets.token_urlsafe(16)
        params = [
            "response_type=code",
            f"redirect_uri={quote(self._redirect_uri)}",
            f"scope={quote(' '.join(self._scopes))}",
            f"state={quote(self._state)}",
            f"code_challenge={quote(challenge)}",
            "code_challenge_method=S256",
        ]
        return f"{LICHESS_OAUTH_AUTHORIZE}?{'&'.join(params)}"

    def exchange_code(self, code: str, state: str) -> OAuthToken:
        """Exchange the authorization code for an access token."""
        if self._verifier is None or self._state is None:
            raise RuntimeError("authorize_url() must be called first")
        if state != self._state:
            raise ValueError("OAuth state mismatch (possible CSRF)")
        data = (
            f"grant_type=authorization_code&code={quote(code)}"
            f"&code_verifier={quote(self._verifier)}"
            f"&redirect_uri={quote(self._redirect_uri)}"
        ).encode("utf-8")
        req = Request(
            LICHESS_OAUTH_TOKEN,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        # Lichess tokens don't expire, but we set a large expires_at for safety
        token = OAuthToken(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "Bearer"),
            expires_at=int(time.time()) + 365 * 24 * 3600,
            scope=payload.get("scope", " ".join(self._scopes)),
        )
        self._save_token(token)
        return token

    def _save_token(self, token: OAuthToken) -> None:
        try:
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(token.to_json())
        except OSError as e:
            logger.debug("Save token failed: %s", e)

    def load_token(self) -> OAuthToken | None:
        try:
            if not self._token_path.exists():
                return None
            return OAuthToken.from_json(self._token_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Load token failed: %s", e)
            return None

    def is_authenticated(self) -> bool:
        token = self.load_token()
        return token is not None and not token.is_expired

    def revoke(self) -> None:
        try:
            self._token_path.unlink(missing_ok=True)
        except OSError as e:
            logger.debug("Revoke failed: %s", e)
