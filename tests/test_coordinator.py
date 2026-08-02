from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.classcharts.api import AuthError, ClassChartsError
from custom_components.classcharts.coordinator import RewardsCoordinator, TimetableCoordinator


def _fake_hass_and_entry():
    return MagicMock(), MagicMock()


async def test_rewards_coordinator_raises_update_failed_on_generic_error():
    hass, entry = _fake_hass_and_entry()
    client = MagicMock()
    client.behaviour = AsyncMock(side_effect=ClassChartsError("boom"))
    coordinator = RewardsCoordinator(hass, entry, client, 1, "Alex")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_rewards_coordinator_raises_config_entry_auth_failed_on_autherror():
    hass, entry = _fake_hass_and_entry()
    client = MagicMock()
    client.behaviour = AsyncMock(side_effect=AuthError("bad login"))
    coordinator = RewardsCoordinator(hass, entry, client, 1, "Alex")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_timetable_coordinator_raises_update_failed_on_generic_error():
    hass, entry = _fake_hass_and_entry()
    client = MagicMock()
    client.timetable_today = AsyncMock(side_effect=ClassChartsError("boom"))
    coordinator = TimetableCoordinator(hass, entry, client, 1, "Alex")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_timetable_coordinator_raises_config_entry_auth_failed_on_autherror():
    hass, entry = _fake_hass_and_entry()
    client = MagicMock()
    client.timetable_today = AsyncMock(side_effect=AuthError("bad login"))
    coordinator = TimetableCoordinator(hass, entry, client, 1, "Alex")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
