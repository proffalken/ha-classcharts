from __future__ import annotations

import asyncio
from typing import Any


class FakeResponse:
    """Duck-typed stand-in for aiohttp's request context manager + response.

    ClassChartsClient only ever uses `.status` and `await .json(...)`, entered
    via `async with session.post/request(...) as resp:` -- so this covers the
    full protocol it depends on without touching aiohttp internals at all.
    """

    def __init__(
        self,
        *,
        status: int = 200,
        json_data: Any = None,
        json_exc: Exception | None = None,
        enter_exc: Exception | None = None,
        delay: float = 0,
    ) -> None:
        self.status = status
        self._json_data = json_data
        self._json_exc = json_exc
        self._enter_exc = enter_exc
        self._delay = delay

    async def __aenter__(self) -> "FakeResponse":
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._enter_exc:
            raise self._enter_exc
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def json(self, content_type: Any = None) -> Any:
        if self._json_exc:
            raise self._json_exc
        return self._json_data


class FakeSession:
    """Duck-typed stand-in for aiohttp.ClientSession, queue-driven per call."""

    def __init__(self) -> None:
        self.post_calls: list[dict] = []
        self.request_calls: list[dict] = []
        self._post_queue: list[FakeResponse] = []
        self._request_queue: list[FakeResponse] = []

    def queue_post(self, response: FakeResponse) -> None:
        self._post_queue.append(response)

    def queue_request(self, response: FakeResponse) -> None:
        self._request_queue.append(response)

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.post_calls.append({"url": url, **kwargs})
        return self._post_queue.pop(0)

    def request(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.request_calls.append({"method": method, "url": url, **kwargs})
        return self._request_queue.pop(0)
