from __future__ import annotations
from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import RewardsCoordinator, TimetableCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    rewards: RewardsCoordinator = data["rewards"]
    timetable: TimetableCoordinator = data["timetable"]
    student_id = data["student_id"]
    student_name = data["student_name"]

    entities: list[SensorEntity] = [
        RewardsTotalSensor(rewards, student_id, student_name, positive=True),
        RewardsTotalSensor(rewards, student_id, student_name, positive=False),
        TimetableTodaySensor(timetable, student_id, student_name),
    ]

    snap = rewards.data or {}
    for key in (snap.get("positive_reasons") or {}).keys():
        entities.append(ReasonSensor(rewards, student_id, student_name, key, positive=True))
    for key in (snap.get("negative_reasons") or {}).keys():
        entities.append(ReasonSensor(rewards, student_id, student_name, key, positive=False))

    async_add_entities(entities)

class BaseClassChartsEntity(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, student_id: int, student_name: str) -> None:
        self._student_id = student_id
        self._student_name = student_name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"student_{self._student_id}")},
            name=f"{self._student_name} · ClassCharts",
            manufacturer="ClassCharts (Unofficial)",
            model="Parent API",
        )

class RewardsTotalSensor(BaseClassChartsEntity):
    def __init__(self, coordinator: RewardsCoordinator, student_id: int, student_name: str, *, positive: bool):
        super().__init__(student_id, student_name)
        self.coordinator = coordinator
        self._positive = positive
        kind = "positive" if positive else "negative"
        self._attr_name = f"{student_name} Rewards ({kind})"
        self._attr_unique_id = f"classcharts_rewards_total_{student_id}_{kind}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get("total_positive" if self._positive else "total_negative", 0)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "positive_reasons": data.get("positive_reasons", {}),
            "negative_reasons": data.get("negative_reasons", {}),
            "last_updated": data.get("last_updated"),
        }

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self._handle))

    @callback
    def _handle(self) -> None:
        self.async_write_ha_state()

class ReasonSensor(BaseClassChartsEntity):
    def __init__(self, coordinator: RewardsCoordinator, student_id: int, student_name: str, reason_key: str, *, positive: bool):
        super().__init__(student_id, student_name)
        self.coordinator = coordinator
        self._positive = positive
        self._reason_key = reason_key
        side = "pos" if positive else "neg"
        self._attr_name = f"{student_name} Reward {reason_key}"
        self._attr_unique_id = f"classcharts_rewards_reason_{student_id}_{side}_{reason_key.lower()}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        bucket = data.get("positive_reasons" if self._positive else "negative_reasons", {})
        try:
            return int(bucket.get(self._reason_key, 0))
        except (ValueError, TypeError):
            return 0

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self._handle))

    @callback
    def _handle(self) -> None:
        self.async_write_ha_state()

class TimetableTodaySensor(BaseClassChartsEntity):
    def __init__(self, coordinator: TimetableCoordinator, student_id: int, student_name: str):
        super().__init__(student_id, student_name)
        self.coordinator = coordinator
        self._attr_name = f"{student_name} Timetable (Today)"
        self._attr_unique_id = f"classcharts_timetable_today_{student_id}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get("count", 0)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {"lessons": data.get("lessons", []), "meta": data.get("meta", {})}

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self._handle))

    @callback
    def _handle(self) -> None:
        self.async_write_ha_state()

