from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN, PLATFORMS, CONF_USERNAME, CONF_PASSWORD, CONF_STUDENT_ID, CONF_STUDENT_NAME,
    CONF_MORNING_REFRESH_HOUR, DEFAULT_MORNING_REFRESH_HOUR
)
from .api import ClassChartsClient
from .coordinator import RewardsCoordinator, TimetableCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = ClassChartsClient(session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

    student_id = entry.data[CONF_STUDENT_ID]
    student_name = entry.data[CONF_STUDENT_NAME]
    morning_hour = entry.options.get(CONF_MORNING_REFRESH_HOUR, DEFAULT_MORNING_REFRESH_HOUR)

    rewards = RewardsCoordinator(hass, entry, client, student_id, student_name)
    timetable = TimetableCoordinator(hass, entry, client, student_id, student_name)

    await rewards.async_config_entry_first_refresh()
    await timetable.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "rewards": rewards,
        "timetable": timetable,
        "student_id": student_id,
        "student_name": student_name,
    }

    @callback
    def _morning_refresh(now=None):
        hass.async_create_task(timetable.async_request_refresh())

    remove = async_track_time_change(hass, _morning_refresh, hour=morning_hour, minute=0, second=0)
    entry.async_on_unload(remove)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

