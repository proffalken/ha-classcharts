from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TimetableCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    timetable: TimetableCoordinator = data["timetable"]
    student_id = data["student_id"]
    student_name = data["student_name"]

    async_add_entities([ClassChartsTimetableCalendar(timetable, student_id, student_name)])


def _lesson_to_event(lesson: dict) -> Optional[CalendarEvent]:
    start_raw = lesson.get("start_time")
    end_raw = lesson.get("end_time")
    if not start_raw or not end_raw:
        return None
    try:
        start = datetime.fromisoformat(start_raw)
        end = datetime.fromisoformat(end_raw)
    except ValueError:
        return None

    summary = lesson.get("subject_name") or lesson.get("lesson_name") or "Lesson"
    teacher = lesson.get("teacher_name") or ""
    period = lesson.get("period_name") or ""
    description = " · ".join(part for part in (teacher, period) if part) or None
    location = lesson.get("room_name") or None
    key = lesson.get("key")
    uid = f"classcharts-{key}" if key is not None else None

    return CalendarEvent(
        start=start,
        end=end,
        summary=summary,
        description=description,
        location=location,
        uid=uid,
    )


class ClassChartsTimetableCalendar(CalendarEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TimetableCoordinator, student_id: int, student_name: str) -> None:
        self.coordinator = coordinator
        self._student_id = student_id
        self._student_name = student_name
        self._attr_name = f"{student_name} Timetable"
        self._attr_unique_id = f"classcharts_timetable_calendar_{student_id}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"student_{self._student_id}")},
            name=f"{self._student_name} · ClassCharts",
            manufacturer="ClassCharts (Unofficial)",
            model="Parent API",
        )

    def _all_events(self) -> list[CalendarEvent]:
        days = (self.coordinator.data or {}).get("days", {})
        events = []
        for day in days.values():
            for lesson in day.get("lessons", []):
                event = _lesson_to_event(lesson)
                if event is not None:
                    events.append(event)
        events.sort(key=lambda e: e.start)
        return events

    @property
    def event(self) -> Optional[CalendarEvent]:
        now = dt_util.now()
        for event in self._all_events():
            if event.end > now:
                return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [e for e in self._all_events() if e.start < end_date and e.end > start_date]

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self._handle))

    @callback
    def _handle(self) -> None:
        self.async_write_ha_state()
