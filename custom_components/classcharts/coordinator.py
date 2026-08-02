from __future__ import annotations
from datetime import timedelta
import logging
from typing import Any, Dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from .api import AuthError, ClassChartsClient, ClassChartsError
from .const import REWARDS_REFRESH_MINUTES, TIMETABLE_DAY_CACHE_SECONDS

_LOGGER = logging.getLogger(__name__)

class RewardsCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: ClassChartsClient,
        student_id: int,
        student_name: str,
    ):
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"classcharts_rewards_{student_id}",
            update_interval=timedelta(minutes=REWARDS_REFRESH_MINUTES),
        )
        self._client = client
        self.student_id = student_id
        self.student_name = student_name

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            raw = await self._client.behaviour(self.student_id)
        except AuthError as e:
            raise ConfigEntryAuthFailed(str(e)) from e
        except ClassChartsError as e:
            raise UpdateFailed(str(e)) from e

        data = raw.get("data", {}) or {}
        pos: dict = data.get("positive_reasons", {}) or {}
        neg: dict = data.get("negative_reasons", {}) or {}
        return {
            "positive_reasons": pos,
            "negative_reasons": neg,
            "total_positive": sum(v for v in pos.values() if isinstance(v, (int, float))),
            "total_negative": sum(v for v in neg.values() if isinstance(v, (int, float))),
            "last_updated": dt_util.utcnow().isoformat(),
        }

class TimetableCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: ClassChartsClient,
        student_id: int,
        student_name: str,
    ):
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"classcharts_timetable_{student_id}",
            update_interval=timedelta(seconds=TIMETABLE_DAY_CACHE_SECONDS),
        )
        self._client = client
        self.student_id = student_id
        self.student_name = student_name

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            raw = await self._client.timetable_today(self.student_id)
        except AuthError as e:
            raise ConfigEntryAuthFailed(str(e)) from e
        except ClassChartsError as e:
            raise UpdateFailed(str(e)) from e
        lessons = raw.get("data", []) or []
        meta = raw.get("meta", {}) or {}
        return {"lessons": lessons, "meta": meta, "count": len(lessons)}
