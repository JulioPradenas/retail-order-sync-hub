"""MercadoLibre OAuth2 adapter.

Implements the authorization-code flow against the MercadoLibre sandbox, stores
the access/refresh tokens in ``app_db.oauth_tokens`` and refreshes the access
token automatically when it is close to expiry.

The token store and HTTP client are injectable so the refresh logic can be unit
tested without a real database or network.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
from sqlalchemy import select

from src.common.config import Settings, get_settings
from src.common.db import get_session_factory
from src.common.models import OAuthToken

PROVIDER = "mercadolibre"


@dataclass
class Token:
    access_token: str
    refresh_token: str | None
    expires_at: datetime


class TokenStore(Protocol):
    def load(self, provider: str) -> Token | None: ...
    def save(self, provider: str, token: Token) -> None: ...


class DbTokenStore:
    """Token store backed by ``app_db.oauth_tokens``."""

    def load(self, provider: str) -> Token | None:
        factory = get_session_factory()
        with factory() as session:
            row = session.scalar(select(OAuthToken).where(OAuthToken.provider == provider))
            if row is None or row.expires_at is None:
                return None
            return Token(row.access_token, row.refresh_token, row.expires_at)

    def save(self, provider: str, token: Token) -> None:
        factory = get_session_factory()
        with factory() as session:
            row = session.scalar(select(OAuthToken).where(OAuthToken.provider == provider))
            if row is None:
                row = OAuthToken(provider=provider)
                session.add(row)
            row.access_token = token.access_token
            row.refresh_token = token.refresh_token
            row.expires_at = token.expires_at
            session.commit()


class MercadoLibreOAuth:
    """OAuth2 client for the MercadoLibre sandbox."""

    def __init__(
        self,
        settings: Settings | None = None,
        store: TokenStore | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._store = store or DbTokenStore()
        self._http = http_client

    def _client(self) -> httpx.AsyncClient:
        if self._http is not None:
            return self._http
        return httpx.AsyncClient(base_url=self._settings.ml_api_base, timeout=10.0)

    def authorization_url(self, state: str | None = None) -> str:
        """Build the URL the user opens to grant access (start of the dance)."""
        params = {
            "response_type": "code",
            "client_id": self._settings.ml_client_id,
            "redirect_uri": self._settings.ml_redirect_uri,
        }
        if state:
            params["state"] = state
        return f"{self._settings.ml_auth_base}/authorization?{urlencode(params)}"

    async def exchange_code(self, code: str) -> Token:
        """Exchange an authorization code for tokens and persist them."""
        token = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.ml_redirect_uri,
            }
        )
        self._store.save(PROVIDER, token)
        return token

    async def refresh(self) -> Token:
        """Use the stored refresh token to obtain a fresh access token."""
        current = self._store.load(PROVIDER)
        if current is None or not current.refresh_token:
            raise RuntimeError("no refresh token stored — run the auth flow first")
        token = await self._token_request(
            {"grant_type": "refresh_token", "refresh_token": current.refresh_token}
        )
        self._store.save(PROVIDER, token)
        return token

    async def valid_access_token(self) -> str:
        """Return a non-expired access token, refreshing if near expiry."""
        current = self._store.load(PROVIDER)
        if current is None:
            raise RuntimeError("no token stored — run the auth flow first")
        skew = timedelta(seconds=self._settings.ml_refresh_skew_seconds)
        if datetime.now(UTC) >= current.expires_at - skew:
            current = await self.refresh()
        return current.access_token

    async def get_user(self) -> dict[str, Any]:
        """Fetch the authenticated sandbox user (``/users/me``)."""
        access_token = await self.valid_access_token()
        client = self._client()
        try:
            resp = await client.get(
                "/users/me", headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        finally:
            if self._http is None:
                await client.aclose()

    async def _token_request(self, payload: dict[str, str]) -> Token:
        body = {
            "client_id": self._settings.ml_client_id,
            "client_secret": self._settings.ml_client_secret,
            **payload,
        }
        client = self._client()
        try:
            resp = await client.post("/oauth/token", data=body)
            resp.raise_for_status()
            data = resp.json()
        finally:
            if self._http is None:
                await client.aclose()
        expires_at = datetime.now(UTC) + timedelta(seconds=int(data["expires_in"]))
        return Token(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
        )


async def _cmd_auth() -> int:
    """Interactive OAuth dance: open URL, paste back the redirect code."""
    oauth = MercadoLibreOAuth()
    if not oauth._settings.ml_client_id:
        print("ML_CLIENT_ID is empty — create a sandbox app and fill .env first.")
        return 1
    print("1) Open this URL, log in with your sandbox user and authorize:\n")
    print(f"   {oauth.authorization_url()}\n")
    print("2) You'll be redirected to your redirect_uri with ?code=... in the URL.")
    code = input("3) Paste the code here: ").strip()
    if not code:
        print("no code provided")
        return 1
    token = await oauth.exchange_code(code)
    print(f"ok — token stored, expires at {token.expires_at.isoformat()}")
    return 0


async def _cmd_get_user() -> int:
    import json

    user = await MercadoLibreOAuth().get_user()
    print(json.dumps(user, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(prog="python -m src.adapters.mercadolibre")
    parser.add_argument("command", choices=["auth", "get_user"])
    args = parser.parse_args()

    if args.command == "auth":
        return asyncio.run(_cmd_auth())
    return asyncio.run(_cmd_get_user())


if __name__ == "__main__":
    import sys

    sys.exit(main())
