from __future__ import annotations

import asyncio

import pytest
from aiohttp import ClientSession
from aioresponses import CallbackResult, aioresponses

from custom_components.classcharts.api import (
    AuthError,
    BEHAVIOUR_URL_TMPL,
    ClassChartsClient,
    ClassChartsError,
    LOGIN_URL,
)

EMAIL = "parent@example.com"
PASSWORD = "hunter2"


def _login_ok_payload(session_id: str = "sid-123"):
    return {"meta": {"session_id": session_id}}


async def test_login_success_sets_session_and_auth_header():
    with aioresponses() as m:
        m.post(LOGIN_URL, status=200, payload=_login_ok_payload("sid-123"))
        async with ClientSession() as session:
            client = ClassChartsClient(session, EMAIL, PASSWORD)
            await client.login()
            assert client._session_id == "sid-123"
            assert client._auth_header == {"Authorization": "Basic sid-123"}


async def test_login_failure_without_session_id_raises_autherror():
    with aioresponses() as m:
        m.post(LOGIN_URL, status=200, payload={"meta": {}})
        async with ClientSession() as session:
            client = ClassChartsClient(session, EMAIL, PASSWORD)
            with pytest.raises(AuthError):
                await client.login()


async def test_login_non_200_raises_autherror():
    with aioresponses() as m:
        m.post(LOGIN_URL, status=403, payload={"error": "forbidden"})
        async with ClientSession() as session:
            client = ClassChartsClient(session, EMAIL, PASSWORD)
            with pytest.raises(AuthError):
                await client.login()


async def test_request_timeout_raises_classcharts_error_not_raw_timeout():
    url = BEHAVIOUR_URL_TMPL.format(student_id=1)
    with aioresponses() as m:
        m.get(url, exception=asyncio.TimeoutError())
        async with ClientSession() as session:
            client = ClassChartsClient(session, EMAIL, PASSWORD)
            client._session_id = "sid-123"
            client._auth_header = {"Authorization": "Basic sid-123"}
            with pytest.raises(ClassChartsError):
                await client._request("GET", url)


async def test_request_non_json_body_raises_classcharts_error():
    url = BEHAVIOUR_URL_TMPL.format(student_id=1)
    with aioresponses() as m:
        m.get(url, status=200, body="<html>please enable javascript</html>", content_type="text/html")
        async with ClientSession() as session:
            client = ClassChartsClient(session, EMAIL, PASSWORD)
            client._session_id = "sid-123"
            client._auth_header = {"Authorization": "Basic sid-123"}
            with pytest.raises(ClassChartsError):
                await client._request("GET", url)


async def test_behaviour_relogs_in_once_on_401_then_succeeds():
    url = BEHAVIOUR_URL_TMPL.format(student_id=42)
    with aioresponses() as m:
        m.post(LOGIN_URL, status=200, payload=_login_ok_payload("sid-1"))
        m.get(url, status=401, payload={"success": False})
        m.post(LOGIN_URL, status=200, payload=_login_ok_payload("sid-2"))
        m.get(url, status=200, payload={"success": True, "data": {"positive_reasons": {}, "negative_reasons": {}}})

        async with ClientSession() as session:
            client = ClassChartsClient(session, EMAIL, PASSWORD)
            result = await client.behaviour(42)
            assert result["success"] is True
            assert client._session_id == "sid-2"


async def test_concurrent_ensure_auth_only_logs_in_once():
    call_count = 0

    async def login_callback(url, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return CallbackResult(status=200, payload=_login_ok_payload("sid-shared"))

    with aioresponses() as m:
        m.post(LOGIN_URL, callback=login_callback, repeat=True)
        async with ClientSession() as session:
            client = ClassChartsClient(session, EMAIL, PASSWORD)
            await asyncio.gather(client.ensure_auth(), client.ensure_auth())

    assert call_count == 1
    assert client._session_id == "sid-shared"
