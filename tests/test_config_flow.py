from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import SOURCE_REAUTH

from custom_components.classcharts.api import AuthError, ClassChartsError
from custom_components.classcharts.config_flow import ClassChartsConfigFlow
from custom_components.classcharts.const import CONF_PASSWORD, CONF_STUDENT_ID, CONF_USERNAME


def _flow_with_reauth_entry(entry_data: dict) -> ClassChartsConfigFlow:
    flow = ClassChartsConfigFlow()
    flow.hass = MagicMock()
    flow.context = {"source": SOURCE_REAUTH, "entry_id": "test-entry-id"}
    entry = MagicMock()
    entry.data = entry_data
    entry.entry_id = "test-entry-id"
    entry.update_listeners = []  # real ConfigEntry objects have none; MagicMock() would be truthy
    flow.hass.config_entries.async_get_known_entry.return_value = entry
    return flow


async def test_reauth_confirm_shows_form_when_no_input():
    flow = _flow_with_reauth_entry({CONF_USERNAME: "old@example.com", CONF_STUDENT_ID: 42})

    result = await flow.async_step_reauth_confirm()

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_confirm_success_updates_and_reloads_entry(monkeypatch):
    flow = _flow_with_reauth_entry({CONF_USERNAME: "old@example.com", CONF_STUDENT_ID: 42})

    async def fake_fetch_pupils(hass, email, password):
        return [{"id": 42, "name": "Eve"}]

    monkeypatch.setattr("custom_components.classcharts.config_flow._fetch_pupils", fake_fetch_pupils)

    result = await flow.async_step_reauth_confirm(
        {CONF_USERNAME: "new@example.com", CONF_PASSWORD: "newpass"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    flow.hass.config_entries.async_update_entry.assert_called_once()
    updated_data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
    assert updated_data[CONF_USERNAME] == "new@example.com"
    assert updated_data[CONF_PASSWORD] == "newpass"
    assert updated_data[CONF_STUDENT_ID] == 42  # untouched
    flow.hass.config_entries.async_schedule_reload.assert_called_once_with("test-entry-id")


async def test_reauth_confirm_auth_error_shows_error_and_does_not_update(monkeypatch):
    flow = _flow_with_reauth_entry({CONF_USERNAME: "old@example.com", CONF_STUDENT_ID: 42})

    async def fake_fetch_pupils(hass, email, password):
        raise AuthError("bad login")

    monkeypatch.setattr("custom_components.classcharts.config_flow._fetch_pupils", fake_fetch_pupils)

    result = await flow.async_step_reauth_confirm(
        {CONF_USERNAME: "old@example.com", CONF_PASSWORD: "wrong"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "auth"}
    flow.hass.config_entries.async_update_entry.assert_not_called()


async def test_reauth_confirm_cannot_connect_shows_error(monkeypatch):
    flow = _flow_with_reauth_entry({CONF_USERNAME: "old@example.com", CONF_STUDENT_ID: 42})

    async def fake_fetch_pupils(hass, email, password):
        raise ClassChartsError("network broke")

    monkeypatch.setattr("custom_components.classcharts.config_flow._fetch_pupils", fake_fetch_pupils)

    result = await flow.async_step_reauth_confirm(
        {CONF_USERNAME: "old@example.com", CONF_PASSWORD: "pw"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_confirm_student_no_longer_on_account_shows_error(monkeypatch):
    flow = _flow_with_reauth_entry({CONF_USERNAME: "old@example.com", CONF_STUDENT_ID: 42})

    async def fake_fetch_pupils(hass, email, password):
        return [{"id": 99, "name": "Someone Else"}]

    monkeypatch.setattr("custom_components.classcharts.config_flow._fetch_pupils", fake_fetch_pupils)

    result = await flow.async_step_reauth_confirm(
        {CONF_USERNAME: "old@example.com", CONF_PASSWORD: "pw"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "no_pupils"}
    flow.hass.config_entries.async_update_entry.assert_not_called()
