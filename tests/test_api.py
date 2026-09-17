from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import quote

import pytest

from custom_components.classcharts.api import (
    AuthError,
    BEHAVIOUR_URL_TMPL,
    ClassChartsClient,
    ClassChartsError,
    HOMEWORK_URL_TMPL,
    PUPILS_URL,
    TIMETABLE_URL_TMPL,
)
from conftest import FakeResponse, FakeSession

EMAIL = "parent@example.com"
PASSWORD = "hunter2"


def _parent_session_credentials_cookie(session_id: str) -> str:
    return quote(json.dumps({"remember_me": False, "session_id": session_id}))


async def test_login_extracts_token_from_parent_session_credentials_cookie():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200))  # form login
    session.set_cookie("parent_session_credentials", _parent_session_credentials_cookie("sid-abc"))
    session.queue_post(FakeResponse(status=200))  # ping handshake

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    await client.login()

    assert client._session_id == "sid-abc"
    assert client._auth_header["Authorization"] == "Basic sid-abc"
    assert client._auth_header["X-Requested-With"] == "XMLHttpRequest"


async def test_login_falls_back_to_cc_session_cookie():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200))  # form login, no parent_session_credentials
    session.set_cookie("cc-session", "raw-cc-session-value")
    session.queue_post(FakeResponse(status=200))  # ping handshake

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    await client.login()

    assert client._session_id == "raw-cc-session-value"


async def test_login_raises_autherror_when_no_session_cookie_present():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200))  # form login sets no cookies at all

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    with pytest.raises(AuthError):
        await client.login()


async def test_login_raises_autherror_when_ping_handshake_fails():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200))  # form login
    session.set_cookie("cc-session", "sid-xyz")
    session.queue_post(FakeResponse(status=500))  # ping handshake fails

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    with pytest.raises(AuthError):
        await client.login()


async def test_pupils_posts_body_and_returns_parsed_list():
    session = FakeSession()
    session.queue_post(FakeResponse(status=200))  # form login
    session.set_cookie("cc-session", "sid-abc")
    session.queue_post(FakeResponse(status=200))  # ping handshake
    session.queue_request(
        FakeResponse(status=200, json_data={"success": 1, "data": [{"id": 1, "name": "Eve"}], "meta": []})
    )

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    result = await client.pupils()

    assert result == [{"id": 1, "name": "Eve"}]
    assert session.request_calls[-1]["method"] == "POST"
    assert session.request_calls[-1]["url"] == PUPILS_URL


async def test_pupils_relogs_in_once_on_401_then_succeeds():
    session = FakeSession()
    session.set_cookie("cc-session", "sid-1")
    session.queue_post(FakeResponse(status=200))  # form login
    session.queue_post(FakeResponse(status=200))  # ping
    session.queue_request(FakeResponse(status=401, json_data={"success": False}))
    session.queue_post(FakeResponse(status=200, sets_cookie=("cc-session", "sid-2")))  # form login (retry)
    session.queue_post(FakeResponse(status=200))  # ping (retry)
    session.queue_request(
        FakeResponse(status=200, json_data={"success": 1, "data": [{"id": 1, "name": "Eve"}], "meta": []})
    )

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    result = await client.pupils()

    assert result == [{"id": 1, "name": "Eve"}]
    assert len(session.post_calls) == 4  # two logins x (form login + ping)
    assert len(session.request_calls) == 2  # two pupils POSTs
    assert session.request_calls[-1]["headers"]["Authorization"] == "Basic sid-2"


async def test_pupils_relogs_in_once_on_expired_body_with_200_status_then_succeeds():
    """ClassCharts signals an expired session with HTTP 200 and success=0/expired=1
    in the body, not a 401 -- this must be treated as an auth failure too, or the
    session degrades silently and never recovers on its own (only a reload of the
    integration would fix it, since that recreates the client and force-logs-in)."""
    session = FakeSession()
    session.set_cookie("cc-session", "sid-1")
    session.queue_post(FakeResponse(status=200))  # form login
    session.queue_post(FakeResponse(status=200))  # ping
    session.queue_request(
        FakeResponse(
            status=200,
            json_data={"success": 0, "expired": 1, "error": "You are not logged in. [1]", "meta": []},
        )
    )
    session.queue_post(FakeResponse(status=200, sets_cookie=("cc-session", "sid-2")))  # form login (retry)
    session.queue_post(FakeResponse(status=200))  # ping (retry)
    session.queue_request(
        FakeResponse(status=200, json_data={"success": 1, "data": [{"id": 1, "name": "Eve"}], "meta": []})
    )

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    result = await client.pupils()

    assert result == [{"id": 1, "name": "Eve"}]
    assert len(session.post_calls) == 4  # two logins x (form login + ping)
    assert len(session.request_calls) == 2  # two pupils POSTs
    assert session.request_calls[-1]["headers"]["Authorization"] == "Basic sid-2"


async def test_timetable_without_date_omits_date_param():
    url = TIMETABLE_URL_TMPL.format(student_id=42)
    session = FakeSession()
    session.queue_request(FakeResponse(status=200, json_data={"success": 1, "data": [], "meta": {}}))
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    client._session_id = "sid-123"
    client._auth_header = {"Authorization": "Basic sid-123"}

    await client.timetable(42)

    call = session.request_calls[-1]
    assert call["method"] == "GET"
    assert call["url"] == url
    assert call.get("params") is None


async def test_timetable_with_date_passes_date_param():
    url = TIMETABLE_URL_TMPL.format(student_id=42)
    session = FakeSession()
    session.queue_request(FakeResponse(status=200, json_data={"success": 1, "data": [], "meta": {}}))
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    client._session_id = "sid-123"
    client._auth_header = {"Authorization": "Basic sid-123"}

    await client.timetable(42, date="2026-06-10")

    call = session.request_calls[-1]
    assert call["url"] == url
    assert call["params"] == {"date": "2026-06-10"}


async def test_homework_passes_display_date_and_range_params():
    url = HOMEWORK_URL_TMPL.format(student_id=42)
    session = FakeSession()
    session.queue_request(FakeResponse(status=200, json_data={"success": 1, "data": []}))
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    client._session_id = "sid-123"
    client._auth_header = {"Authorization": "Basic sid-123"}

    await client.homework(42, "2026-06-01", "2026-06-14")

    call = session.request_calls[-1]
    assert call["method"] == "GET"
    assert call["url"] == url
    assert call["params"] == {"display_date": "due_date", "from": "2026-06-01", "to": "2026-06-14"}


async def test_homework_relogs_in_once_on_401_then_succeeds():
    url = HOMEWORK_URL_TMPL.format(student_id=42)
    session = FakeSession()
    session.set_cookie("cc-session", "sid-1")
    session.queue_post(FakeResponse(status=200))  # form login
    session.queue_post(FakeResponse(status=200))  # ping
    session.queue_request(FakeResponse(status=401, json_data={"success": False}))
    session.queue_post(FakeResponse(status=200, sets_cookie=("cc-session", "sid-2")))  # form login (retry)
    session.queue_post(FakeResponse(status=200))  # ping (retry)
    session.queue_request(FakeResponse(status=200, json_data={"success": 1, "data": [{"id": 1}]}))

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    result = await client.homework(42, "2026-06-01", "2026-06-14")

    assert result["data"] == [{"id": 1}]
    assert len(session.request_calls) == 2
    assert session.request_calls[-1]["headers"]["Authorization"] == "Basic sid-2"


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
    url = BEHAVIOUR_URL_TMPL.format(student_id=42)
    session = FakeSession()
    session.set_cookie("cc-session", "sid-1")
    # first login (via ensure_auth)
    session.queue_post(FakeResponse(status=200))  # form login
    session.queue_post(FakeResponse(status=200))  # ping
    session.queue_request(FakeResponse(status=401, json_data={"success": False}))
    # second login (explicit retry after 401)
    session.queue_post(FakeResponse(status=200, sets_cookie=("cc-session", "sid-2")))  # form login
    session.queue_post(FakeResponse(status=200))  # ping
    session.queue_request(
        FakeResponse(
            status=200,
            json_data={"success": True, "data": {"positive_reasons": {}, "negative_reasons": {}}},
        )
    )

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    result = await client.behaviour(42)

    assert result["success"] is True
    assert len(session.post_calls) == 4  # two logins x (form login + ping)
    assert len(session.request_calls) == 2  # two behaviour GETs
    assert session.request_calls[-1]["headers"]["Authorization"] == "Basic sid-2"


async def test_concurrent_ensure_auth_only_logs_in_once():
    session = FakeSession()
    session.set_cookie("cc-session", "sid-shared")
    # queue enough for two full login+ping cycles in case the lock fails,
    # so a bug shows up as a clean call-count mismatch, not an IndexError
    session.queue_post(FakeResponse(status=200, delay=0.05))
    session.queue_post(FakeResponse(status=200))
    session.queue_post(FakeResponse(status=200))
    session.queue_post(FakeResponse(status=200))

    client = ClassChartsClient(session, EMAIL, PASSWORD)
    await asyncio.gather(client.ensure_auth(), client.ensure_auth())

    assert len(session.post_calls) == 2  # one form login + one ping, not two of each
    assert client._session_id == "sid-shared"


def _authed_client(session: FakeSession) -> ClassChartsClient:
    client = ClassChartsClient(session, EMAIL, PASSWORD)
    client._session_id = "sid-123"
    client._auth_header = {"Authorization": "Basic sid-123"}
    return client


async def test_pupils_logs_warning_on_empty_response(caplog):
    session = FakeSession()
    session.queue_request(FakeResponse(status=200, json_data={"success": 1, "data": [], "meta": []}))
    client = _authed_client(session)

    with caplog.at_level(logging.WARNING, logger="custom_components.classcharts.api"):
        await client.pupils()

    assert any("empty" in r.message.lower() for r in caplog.records)


async def test_timetable_logs_warning_on_empty_response(caplog):
    session = FakeSession()
    session.queue_request(FakeResponse(status=200, json_data={"success": 1, "data": [], "meta": {}}))
    client = _authed_client(session)

    with caplog.at_level(logging.WARNING, logger="custom_components.classcharts.api"):
        await client.timetable(42, date="2026-06-10")

    assert any("empty" in r.message.lower() for r in caplog.records)


async def test_timetable_warn_if_empty_false_suppresses_warning(caplog):
    session = FakeSession()
    session.queue_request(FakeResponse(status=200, json_data={"success": 1, "data": [], "meta": {}}))
    client = _authed_client(session)

    with caplog.at_level(logging.WARNING, logger="custom_components.classcharts.api"):
        await client.timetable(42, date="2026-06-10", warn_if_empty=False)

    assert caplog.records == []


async def test_timetable_does_not_warn_when_data_present(caplog):
    session = FakeSession()
    session.queue_request(
        FakeResponse(status=200, json_data={"success": 1, "data": [{"subject_name": "Maths"}], "meta": {}})
    )
    client = _authed_client(session)

    with caplog.at_level(logging.WARNING, logger="custom_components.classcharts.api"):
        await client.timetable(42, date="2026-06-10")

    assert caplog.records == []


async def test_homework_logs_warning_on_empty_response(caplog):
    session = FakeSession()
    session.queue_request(FakeResponse(status=200, json_data={"success": 1, "data": []}))
    client = _authed_client(session)

    with caplog.at_level(logging.WARNING, logger="custom_components.classcharts.api"):
        await client.homework(42, "2026-06-01", "2026-06-14")

    assert any("empty" in r.message.lower() for r in caplog.records)


async def test_behaviour_logs_warning_on_empty_response(caplog):
    session = FakeSession()
    session.queue_request(FakeResponse(status=200, json_data={"success": True, "data": {}}))
    client = _authed_client(session)

    with caplog.at_level(logging.WARNING, logger="custom_components.classcharts.api"):
        await client.behaviour(42)

    assert any("empty" in r.message.lower() for r in caplog.records)
