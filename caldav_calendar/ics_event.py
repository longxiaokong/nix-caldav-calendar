from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from icalendar import Alarm, Calendar, Event

from .models import EventCreateInput

PRODID = "-//nix-caldav-calendar//agent-cli//EN"


def new_uid() -> str:
    return f"{uuid4()}@nix-caldav-calendar"


def build_event(input_data: EventCreateInput, uid: str | None = None) -> Calendar:
    event = Event()
    event.add("uid", uid or new_uid())
    event.add("dtstamp", datetime.now(timezone.utc))
    event.add("dtstart", input_data.start)
    event.add("dtend", input_data.end)
    event.add("summary", input_data.title)
    event.add("description", input_data.description)
    if input_data.location:
        event.add("location", input_data.location)
    if input_data.tags:
        event.add("categories", input_data.tags)
    if input_data.recurrence:
        event.add("rrule", input_data.recurrence)
    for reminder in input_data.reminders:
        alarm = Alarm()
        alarm.add("action", reminder["action"])
        alarm.add("description", reminder["description"])
        alarm.add("trigger", -timedelta(minutes=reminder["minutes_before"]))
        event.add_component(alarm)

    calendar = Calendar()
    calendar.add("prodid", PRODID)
    calendar.add("version", "2.0")
    calendar.add_component(event)
    return calendar


def event_to_bytes(calendar: Calendar) -> bytes:
    return calendar.to_ical()
