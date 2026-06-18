from datetime import UTC, datetime, timedelta

import httpx
from src.adapters.mercadolibre import PROVIDER, MercadoLibreOAuth, Token
from src.common.config import Settings


class MemoryStore:
    def __init__(self) -> None:
        self._tokens: dict[str, Token] = {}

    def load(self, provider: str) -> Token | None:
        return self._tokens.get(provider)

    def save(self, provider: str, token: Token) -> None:
        self._tokens[provider] = token


def _settings() -> Settings:
    return Settings(
        ml_client_id="cid",
        ml_client_secret="sec",
        ml_api_base="https://api.test",
        ml_auth_base="https://auth.test",
        ml_refresh_skew_seconds=300,
    )


def _oauth(handler, store: MemoryStore | None = None) -> MercadoLibreOAuth:  # type: ignore[no-untyped-def]
    settings = _settings()
    client = httpx.AsyncClient(
        base_url=settings.ml_api_base, transport=httpx.MockTransport(handler)
    )
    return MercadoLibreOAuth(settings=settings, store=store or MemoryStore(), http_client=client)


async def test_exchange_code_stores_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/token"
        return httpx.Response(
            200, json={"access_token": "AT", "refresh_token": "RT", "expires_in": 21600}
        )

    store = MemoryStore()
    token = await _oauth(handler, store).exchange_code("the-code")
    assert token.access_token == "AT"
    stored = store.load(PROVIDER)
    assert stored is not None and stored.refresh_token == "RT"


async def test_valid_access_token_refreshes_when_expired() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200, json={"access_token": "NEW", "refresh_token": "RT2", "expires_in": 21600}
        )

    store = MemoryStore()
    store.save(PROVIDER, Token("OLD", "RT", datetime.now(UTC) - timedelta(seconds=10)))
    token = await _oauth(handler, store).valid_access_token()
    assert token == "NEW"
    assert calls["n"] == 1
    assert store.load(PROVIDER).access_token == "NEW"  # type: ignore[union-attr]


async def test_valid_access_token_skips_refresh_when_fresh() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("token endpoint must not be called for a fresh token")

    store = MemoryStore()
    store.save(PROVIDER, Token("FRESH", "RT", datetime.now(UTC) + timedelta(hours=2)))
    assert await _oauth(handler, store).valid_access_token() == "FRESH"


async def test_get_user_sends_bearer_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/me"
        assert request.headers["Authorization"] == "Bearer FRESH"
        return httpx.Response(200, json={"id": 123, "nickname": "TESTUSER"})

    store = MemoryStore()
    store.save(PROVIDER, Token("FRESH", "RT", datetime.now(UTC) + timedelta(hours=2)))
    user = await _oauth(handler, store).get_user()
    assert user["nickname"] == "TESTUSER"


def test_authorization_url_contains_expected_params() -> None:
    url = _oauth(lambda r: httpx.Response(200, json={})).authorization_url(state="xyz")
    assert url.startswith("https://auth.test/authorization?")
    assert "client_id=cid" in url
    assert "response_type=code" in url
    assert "state=xyz" in url
