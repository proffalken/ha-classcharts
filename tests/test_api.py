from __future__ import annotations

import asyncio
import json

import pytest

from custom_components.classcharts.api import (
    AuthError,
    BEHAVIOUR_URL_TMPL,
    ClassChartsClient,
    ClassChartsError,
)
from conftest import FakeResponse, FakeSession

EMAIL = "parent@example.com"
PASSWORD = "hunter2"


def _login_ok_payload(session_id: str = "sid-123"):
    return {"meta": {"session_id": session_id}}


async def test_login_success_sets_session_and_auth_header():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200, json_data=_login_ok_payload("sid-123")))
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    await client.login()
    assert client._session_id == "sid-123"
    assert client._auth_header == {"Authorization": "Basic sid-123"}


async def test_login_failure_without_session_id_raises_autherror():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200, json_data={"meta": {}}))
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    with pytest.raises(AuthError):
        await client.login()


async def test_login_non_200_raises_autherror():
    session = FakeSession()
    session.queue_post(FakeResponse(status=403, json_data={"error": "forbidden"}))
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    with pytest.raises(AuthError):
        await client.login()


async def test_request_timeout_raises_classcharts_error_not_raw_timeout():
    url = BEHAVIOUR_URL_TMPL.format(student_id=1)
    session = FakeSession()
    session.queue_request(FakeResponse(enter_exc=asyncio.TimeoutError()))
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    client._session_id = "sid-123"
    client._auth_header = {"Authorization": "Basic sid-123"}
    with pytest.raises(ClassChartsError):
        await client._request("GET", url)


async def test_request_non_json_body_raises_classcharts_error():
    url = BEHAVIOUR_URL_TMPL.format(student_id=1)
    session = FakeSession()
    session.queue_request(
        FakeResponse(
            status=200,
            json_exc=json.JSONDecodeError("Expecting value", "<html>...</html>", 0),
        )
    )
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    client._session_id = "sid-123"
    client._auth_header = {"Authorization": "Basic sid-123"}
    with pytest.raises(ClassChartsError):
        await client._request("GET", url)


async def test_behaviour_relogs_in_once_on_401_then_succeeds():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200, json_data=_login_ok_payload("sid-1")))
    session.queue_request(FakeResponse(status=401, json_data={"success": False}))
    session.queue_post(FakeResponse(status=200, json_data=_login_ok_payload("sid-2")))
    session.queue_request(
        FakeResponse(
            status=200,
            json_data={"success": True, "data": {"positive_reasons": {}, "negative_reasons": {}}},
        )
    )

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    result = await client.behaviour(42)
    assert result["success"] is True
    assert client._session_id == "sid-2"


async def test_concurrent_ensure_auth_only_logs_in_once():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200, json_data=_login_ok_payload("sid-shared"), delay=0.05))
    session.queue_post(FakeResponse(status=200, json_data=_login_ok_payload("sid-shared"), delay=0.05))

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    await asyncio.gather(client.ensure_auth(), client.ensure_auth())

    assert len(session.post_calls) == 1
    assert client._session_id == "sid-shared"
