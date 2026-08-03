from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector, SelectOptionDict

from .const import (
    DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_STUDENT_ID, CONF_STUDENT_NAME,
    CONF_MORNING_REFRESH_HOUR, DEFAULT_MORNING_REFRESH_HOUR
)
from .api import ClassChartsClient, AuthError, ClassChartsError

# --- Step 1 form (email + password) ---
STEP_USER = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})

async def _fetch_pupils(hass: HomeAssistant, email: str, password: str):
    client = ClassChartsClient(async_get_clientsession(hass), email, password)
    await client.login()
    return await client.pupils()

class ClassChartsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            try:
                pupils = await _fetch_pupils(self.hass, email, password)
                if not pupils:
                    errors["base"] = "no_pupils"
                else:
                    # Save creds & pupils between steps
                    self._creds = (email, password, pupils)
                    return await self.async_step_student()
            except AuthError:
                errors["base"] = "auth"
            except ClassChartsError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

    async def async_step_student(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        email, password, pupils = self._creds

        # Build nice dropdown showing names but storing ids
        options = [
            SelectOptionDict(label=p["name"], value=str(p["id"]))
            for p in pupils
        ]
        id_to_name = {str(p["id"]): p["name"] for p in pupils}

        schema = vol.Schema({
            vol.Required(CONF_STUDENT_ID): selector({
                "select": {
                    "options": options,
                    "mode": "dropdown",
                    "sort": True
                }
            }),
            # Use a time selector; we'll keep only the hour
            vol.Optional(CONF_MORNING_REFRESH_HOUR, default="05:00:00"): selector({
                "time": {}
            }),
        })

        if user_input is not None:
            student_id_str = user_input[CONF_STUDENT_ID]
            student_id = int(student_id_str)
            student_name = id_to_name[student_id_str]

            time_str = user_input.get(CONF_MORNING_REFRESH_HOUR, "05:00:00")
            # Expect "HH:MM" or "HH:MM:SS"
            hour = int(time_str.split(":")[0])

            await self.async_set_unique_id(f"{email}:{student_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{student_name}",
                data={
                    CONF_USERNAME: email,
                    CONF_PASSWORD: password,
                    CONF_STUDENT_ID: student_id,
                    CONF_STUDENT_NAME: student_name,
                },
                options={
                    CONF_MORNING_REFRESH_HOUR: hour,
                }
            )

        return self.async_show_form(step_id="student", data_schema=schema)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            email = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            try:
                pupils = await _fetch_pupils(self.hass, email, password)
                student_id = reauth_entry.data[CONF_STUDENT_ID]
                if not any(p.get("id") == student_id for p in pupils):
                    errors["base"] = "no_pupils"
                else:
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data_updates={CONF_USERNAME: email, CONF_PASSWORD: password},
                    )
            except AuthError:
                errors["base"] = "auth"
            except ClassChartsError:
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=reauth_entry.data.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)

