from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.classcharts.api import AuthError, ClassChartsError
from custom_components.classcharts.const import CALENDAR_DAYS_AHEAD
from custom_components.classcharts.coordinator import RewardsCoordinator, TimetableCoordinator


def _fake_hass_and_entry():
    return MagicMock(), MagicMock()


def _dates(n: int) -> list[str]:
    today = dt_util.now().date()
    return [(today + timedelta(days=i)).isoformat() for i in range(n)]


def _day_response(lesson_name: str) -> dict:
    return {"success": 1, "data": [{"subject_name": lesson_name}], "meta": {"dates": []}}


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


async def test_timetable_coordinator_builds_days_dict_across_window():
    hass, entry = _fake_hass_and_entry()
    dates = _dates(CALENDAR_DAYS_AHEAD)
    responses = [_day_response(f"Lesson {i}") for i in range(CALENDAR_DAYS_AHEAD)]
    client = MagicMock()
    client.timetable = AsyncMock(side_effect=responses)
    coordinator = TimetableCoordinator(hass, entry, client, 1, "Alex")

    result = await coordinator._async_update_data()

    assert len(result["days"]) == CALENDAR_DAYS_AHEAD
    assert set(result["days"].keys()) == set(dates)
    assert result["days"][dates[0]]["lessons"] == responses[0]["data"]
    # today's data is still exposed at the top level (TimetableTodaySensor regression guard)
    assert result["lessons"] == responses[0]["data"]
    assert result["meta"] == responses[0]["meta"]
    assert result["count"] == 1


async def test_timetable_coordinator_skips_failing_day_but_keeps_others():
    hass, entry = _fake_hass_and_entry()
    dates = _dates(CALENDAR_DAYS_AHEAD)
    responses = [_day_response(f"Lesson {i}") for i in range(CALENDAR_DAYS_AHEAD)]
    side_effects = list(responses)
    side_effects[1] = ClassChartsError("transient")  # tomorrow fails
    client = MagicMock()
    client.timetable = AsyncMock(side_effect=side_effects)
    coordinator = TimetableCoordinator(hass, entry, client, 1, "Alex")

    result = await coordinator._async_update_data()

    assert len(result["days"]) == CALENDAR_DAYS_AHEAD - 1
    assert dates[1] not in result["days"]
    assert dates[0] in result["days"]  # today unaffected
    assert result["count"] == 1  # today's data still correct


async def test_timetable_coordinator_raises_update_failed_when_today_fails():
    hass, entry = _fake_hass_and_entry()
    client = MagicMock()
    client.timetable = AsyncMock(side_effect=ClassChartsError("boom"))
    coordinator = TimetableCoordinator(hass, entry, client, 1, "Alex")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_timetable_coordinator_raises_config_entry_auth_failed_when_today_fails_auth():
    hass, entry = _fake_hass_and_entry()
    client = MagicMock()
    client.timetable = AsyncMock(side_effect=AuthError("bad login"))
    coordinator = TimetableCoordinator(hass, entry, client, 1, "Alex")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_timetable_coordinator_raises_config_entry_auth_failed_when_later_day_fails_auth():
    hass, entry = _fake_hass_and_entry()
    client = MagicMock()
    client.timetable = AsyncMock(side_effect=[_day_response("Today"), AuthError("bad login")])
    coordinator = TimetableCoordinator(hass, entry, client, 1, "Alex")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
