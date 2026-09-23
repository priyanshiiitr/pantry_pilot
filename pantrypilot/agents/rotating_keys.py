"""Failover across several Groq API keys when one is rate-limited.

Why this exists: Groq's free tier caps tokens per *minute* per key (8,000 at the
time of writing). One Coordinator turn re-sends its system prompt plus every
tool schema, so a full multi-agent run burns through a minute's budget in two or
three requests and then spends minutes in backoff. With more than one key
available, a 429 on the first is better answered by trying the next than by
waiting.

This works at the HTTP layer rather than by rebuilding the Strands model,
because a 429 can arrive part-way through an agent's event loop — swapping the
Authorization header underneath the OpenAI client keeps the agent's own
conversation completely untouched.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

RATE_LIMITED = 429


class RotatingKeyTransport(httpx.AsyncHTTPTransport):
    """An httpx transport that retries a rate-limited request with the next API key.

    Keys are tried in order starting from the last one that worked, so a run of
    requests doesn't re-hit a key that is already known to be exhausted. If every
    key is rate-limited, the final 429 is returned unchanged and the OpenAI
    client's own backoff takes over as usual.
    """

    def __init__(self, api_keys: list[str], **kwargs: object) -> None:
        super().__init__(**kwargs)
        if not api_keys:
            raise ValueError("RotatingKeyTransport needs at least one API key.")
        self._api_keys = api_keys
        self._current = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = None
        for _ in range(len(self._api_keys)):
            request.headers["authorization"] = f"Bearer {self._api_keys[self._current]}"
            response = await super().handle_async_request(request)
            if response.status_code != RATE_LIMITED:
                return response

            # The body must be drained before the connection can be reused for
            # the retry, and nothing here needs to read it.
            await response.aread()
            await response.aclose()
            previous = self._current
            self._current = (self._current + 1) % len(self._api_keys)
            logger.info(
                "Groq key %s of %s is rate-limited; trying key %s",
                previous + 1,
                len(self._api_keys),
                self._current + 1,
            )

        logger.warning("All %s Groq keys are rate-limited; backing off.", len(self._api_keys))
        return response


def build_rotating_http_client(api_keys: list[str]) -> httpx.AsyncClient:
    """Build the AsyncClient to hand to the OpenAI SDK via `client_args["http_client"]`."""
    return httpx.AsyncClient(transport=RotatingKeyTransport(api_keys), timeout=httpx.Timeout(120.0))
