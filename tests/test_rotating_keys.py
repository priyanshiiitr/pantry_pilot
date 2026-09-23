"""Tests for agents/rotating_keys.py — Groq API key failover on a 429.

These never reach the network. The transport's one real network call
(httpx.AsyncHTTPTransport.handle_async_request, reached via super()) is replaced
with a scripted one that records which key each attempt carried, so the rotation
logic itself is what's under test.

They drive the coroutine with asyncio.run() rather than pulling in
pytest-asyncio, since this is the only async code in the project.
"""

import asyncio

import httpx
import pytest

from pantrypilot.agents.rotating_keys import RotatingKeyTransport, SharedAsyncClient
from pantrypilot.config import Settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def script_responses(monkeypatch: pytest.MonkeyPatch, statuses: list[int]) -> list[str]:
    """Make the underlying network call return `statuses` in order.

    Returns the list that each attempt's API key is appended to.
    """
    keys_tried: list[str] = []
    remaining = list(statuses)

    async def fake_send(_self: httpx.AsyncHTTPTransport, request: httpx.Request) -> httpx.Response:
        keys_tried.append(request.headers["authorization"].removeprefix("Bearer "))
        status = remaining.pop(0) if remaining else 200
        return httpx.Response(status, content=b"{}", request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_send)
    return keys_tried


def send(transport: RotatingKeyTransport) -> httpx.Response:
    """Send one request through the transport, the way httpx would."""
    request = httpx.Request("POST", GROQ_URL, json={"model": "x"})
    return asyncio.run(transport.handle_async_request(request))


def test_first_key_is_used_when_it_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no rate limit there is no rotation — one attempt, on the primary key."""
    keys_tried = script_responses(monkeypatch, [200])
    transport = RotatingKeyTransport(["key-a", "key-b"])

    response = send(transport)

    assert response.status_code == 200
    assert keys_tried == ["key-a"]


def test_a_rate_limited_key_falls_through_to_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 on the first key is retried on the second rather than waited out.

    This is the whole point: three keys at 8,000 tokens/minute each beats one
    key at 8,000 followed by a 30-second backoff.
    """
    keys_tried = script_responses(monkeypatch, [429, 200])
    transport = RotatingKeyTransport(["key-a", "key-b"])

    response = send(transport)

    assert response.status_code == 200
    assert keys_tried == ["key-a", "key-b"]


def test_rotation_starts_from_the_last_working_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Later requests start at the key that worked, not back at the exhausted one.

    Otherwise every request would waste a round trip re-discovering a 429 it
    already knows about.
    """
    keys_tried = script_responses(monkeypatch, [429, 200, 200])
    transport = RotatingKeyTransport(["key-a", "key-b"])

    send(transport)
    keys_tried.clear()
    send(transport)

    assert keys_tried == ["key-b"]


def test_rotation_wraps_around_all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """With three keys, a 429 on the first two still finds the third."""
    keys_tried = script_responses(monkeypatch, [429, 429, 200])
    transport = RotatingKeyTransport(["key-a", "key-b", "key-c"])

    response = send(transport)

    assert response.status_code == 200
    assert keys_tried == ["key-a", "key-b", "key-c"]


def test_all_keys_limited_returns_the_last_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """When every key is exhausted, hand the 429 back for the SDK to back off on.

    Retrying forever here would hide a real outage behind a hung agent run.
    """
    keys_tried = script_responses(monkeypatch, [429, 429])
    transport = RotatingKeyTransport(["key-a", "key-b"])

    response = send(transport)

    assert response.status_code == 429
    assert keys_tried == ["key-a", "key-b"]


def test_a_single_key_is_tried_once_and_not_looped(monkeypatch: pytest.MonkeyPatch) -> None:
    """One key configured means the old behaviour: one attempt, then back off."""
    keys_tried = script_responses(monkeypatch, [429])
    transport = RotatingKeyTransport(["key-a"])

    response = send(transport)

    assert response.status_code == 429
    assert keys_tried == ["key-a"]


def test_a_non_rate_limit_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 401 means the key is wrong, not busy — rotating would just mask it."""
    keys_tried = script_responses(monkeypatch, [401, 200])
    transport = RotatingKeyTransport(["key-a", "key-b"])

    response = send(transport)

    assert response.status_code == 401
    assert keys_tried == ["key-a"]


def test_at_least_one_key_is_required() -> None:
    """An empty key list is a configuration mistake worth failing loudly on."""
    with pytest.raises(ValueError, match="at least one API key"):
        RotatingKeyTransport([])


def test_duplicate_keys_are_collapsed() -> None:
    """The same key listed twice shares one rate-limit budget, so retrying it is pointless."""
    settings = Settings(groq_api_key="key-a", groq_fallback_api_keys="key-a, key-b ,key-a")

    assert settings.groq_api_keys == ["key-a", "key-b"]


def test_blank_fallbacks_are_ignored() -> None:
    """Trailing commas and empty entries shouldn't produce empty keys."""
    settings = Settings(groq_api_key="key-a", groq_fallback_api_keys=" , ,")

    assert settings.groq_api_keys == ["key-a"]


def test_the_shared_client_survives_being_closed_by_the_sdk() -> None:
    """The OpenAI SDK closes whatever http_client it is handed when it's done.

    That client is shared by every agent in the process, so honouring the close
    left later agents with "Cannot send a request, as the client has been
    closed" mid-run — which surfaced only as an opaque "Connection error".
    """
    client = SharedAsyncClient(transport=RotatingKeyTransport(["key-a"]))

    asyncio.run(client.aclose())

    assert not client.is_closed


def test_the_shared_client_survives_an_async_with_block() -> None:
    """`async with client:` must not close it either."""

    async def use_and_exit() -> None:
        async with client:
            pass

    client = SharedAsyncClient(transport=RotatingKeyTransport(["key-a"]))
    asyncio.run(use_and_exit())

    assert not client.is_closed


def test_every_agent_shares_one_client_and_its_rotation_position(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each agent builds its own model; they must not each re-discover a dead key.

    A per-model client would make every new specialist start again at key 1 and
    burn a 429 finding out what the process already knew.
    """
    import pantrypilot.agents.rotating_keys as module

    monkeypatch.setattr(module, "_shared_client", None)

    first = module.build_rotating_http_client(["key-a", "key-b"])
    second = module.build_rotating_http_client(["key-a", "key-b"])

    assert first is second
