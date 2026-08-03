from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from homeassistant.util import dt as dt_util

from custom_components.classcharts.calendar import (
    ClassChartsHomeworkCalendar,
    ClassChartsTimetableCalendar,
    _homework_to_event,
    _lesson_to_event,
)


def _lesson(**overrides):
    base = {
        "teacher_name": "Mrs R Williams",
        "lesson_id": 8931972,
        "lesson_name": "07R/Rg",
        "subject_name": "Registration",
        "period_name": "2We:Reg",
        "room_name": "S2",
        "date": "2026-06-10",
        "start_time": "2026-06-10T08:45:00+01:00",
        "end_time": "2026-06-10T09:15:00+01:00",
        "key": 1157054133,
    }
    base.update(overrides)
    return base


def _homework(**overrides):
    base = {
        "id": 25171144,
        "title": "Knowledge test",
        "subject": "RE",
        "teacher": "Mrs S Hunter",
        "lesson": "07R/Re",
        "homework_type": "Homework",
        "description": "Please revise using the knowledge organisers.",
        "issue_date": "2026-05-22",
        "due_date": "2026-06-01",
    }
    base.update(overrides)
    return base


class _StubCoordinator:
    def __init__(self, data):
        self.data = data


def test_lesson_to_event_maps_real_fields():
    event = _lesson_to_event(_lesson())
    assert event is not None
    assert event.summary == "Registration"
    assert event.location == "S2"
    assert "Mrs R Williams" in event.description
    assert "2We:Reg" in event.description
    assert event.uid == "classcharts-1157054133"
    assert event.start.hour == 8
    assert event.start.minute == 45


def test_lesson_to_event_falls_back_to_lesson_name_when_subject_blank():
    event = _lesson_to_event(_lesson(subject_name=""))
    assert event.summary == "07R/Rg"


def test_lesson_to_event_handles_missing_room():
    event = _lesson_to_event(_lesson(room_name=""))
    assert event.location is None


def test_lesson_to_event_returns_none_for_missing_times():
    assert _lesson_to_event(_lesson(start_time="")) is None
    assert _lesson_to_event({}) is None


def test_event_property_returns_current_or_next_upcoming_lesson(monkeypatch):
    fixed_now = datetime(2026, 6, 10, 9, 0, tzinfo=timezone(timedelta(hours=1)))
    monkeypatch.setattr(dt_util, "now", lambda: fixed_now)

    past = _lesson(key=1, start_time="2026-06-10T08:00:00+01:00", end_time="2026-06-10T08:30:00+01:00")
    current = _lesson(
        key=2, subject_name="Maths",
        start_time="2026-06-10T08:45:00+01:00", end_time="2026-06-10T09:15:00+01:00",
    )
    future = _lesson(
        key=3, subject_name="English",
        start_time="2026-06-10T10:00:00+01:00", end_time="2026-06-10T11:00:00+01:00",
    )

    coordinator = _StubCoordinator({"days": {"2026-06-10": {"lessons": [past, current, future]}}})
    entity = ClassChartsTimetableCalendar(coordinator, 1, "Eve")

    assert entity.event.summary == "Maths"


def test_event_property_returns_none_when_no_upcoming_lessons(monkeypatch):
    fixed_now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone(timedelta(hours=1)))
    monkeypatch.setattr(dt_util, "now", lambda: fixed_now)

    past = _lesson(start_time="2026-06-10T08:00:00+01:00", end_time="2026-06-10T08:30:00+01:00")
    coordinator = _StubCoordinator({"days": {"2026-06-10": {"lessons": [past]}}})
    entity = ClassChartsTimetableCalendar(coordinator, 1, "Eve")

    assert entity.event is None


async def test_async_get_events_filters_to_requested_range():
    in_range = _lesson(key=1, date="2026-06-10")
    out_of_range = _lesson(
        key=2, subject_name="Outside range", date="2026-06-11",
        start_time="2026-06-11T08:45:00+01:00", end_time="2026-06-11T09:15:00+01:00",
    )
    coordinator = _StubCoordinator(
        {"days": {"2026-06-10": {"lessons": [in_range]}, "2026-06-11": {"lessons": [out_of_range]}}}
    )
    entity = ClassChartsTimetableCalendar(coordinator, 1, "Eve")

    start = datetime(2026, 6, 10, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 10, 23, 59, tzinfo=timezone.utc)
    events = await entity.async_get_events(None, start, end)

    assert [e.summary for e in events] == ["Registration"]


def test_homework_to_event_maps_real_fields():
    event = _homework_to_event(_homework())
    assert event is not None
    assert event.summary == "Knowledge test"
    assert event.all_day is True
    assert event.location is None
    assert "RE" in event.description
    assert "Mrs S Hunter" in event.description
    assert "Homework" in event.description
    assert "revise" in event.description
    assert event.uid == "classcharts-homework-25171144"
    assert event.start == date(2026, 6, 1)
    assert event.end == date(2026, 6, 2)


def test_homework_to_event_falls_back_to_subject_when_title_blank():
    event = _homework_to_event(_homework(title=""))
    assert event.summary == "RE"


def test_homework_to_event_returns_none_for_missing_due_date():
    assert _homework_to_event(_homework(due_date="")) is None
    assert _homework_to_event({}) is None


def test_homework_event_property_returns_next_due_item(monkeypatch):
    fixed_now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone(timedelta(hours=1)))
    monkeypatch.setattr(dt_util, "now", lambda: fixed_now)

    overdue = _homework(id=1, due_date="2026-05-20")
    upcoming = _homework(id=2, title="Essay", due_date="2026-06-01")
    coordinator = _StubCoordinator({"items": [overdue, upcoming]})
    entity = ClassChartsHomeworkCalendar(coordinator, 1, "Eve")

    assert entity.event.summary == "Essay"


async def test_homework_async_get_events_filters_to_range():
    in_range = _homework(id=1, due_date="2026-06-01")
    out_of_range = _homework(id=2, title="Later", due_date="2026-06-20")
    coordinator = _StubCoordinator({"items": [in_range, out_of_range]})
    entity = ClassChartsHomeworkCalendar(coordinator, 1, "Eve")

    start = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
    events = await entity.async_get_events(None, start, end)

    assert [e.summary for e in events] == ["Knowledge test"]
