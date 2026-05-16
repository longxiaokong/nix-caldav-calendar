from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from icalendar import Alarm, Calendar, Todo

from .models import TaskCreateInput

PRODID = "-//nix-caldav-calendar//agent-cli//EN"


def new_uid() -> str:
    return f"{uuid4()}@nix-caldav-calendar"


def _parse_due(value: str) -> date | datetime:
    parsed = datetime.fromisoformat(value)
    if "T" not in value:
        return parsed.date()
    return parsed


def build_task(input_data: TaskCreateInput, uid: str | None = None) -> Calendar:
    todo = Todo()
    todo.add("uid", uid or new_uid())
    todo.add("dtstamp", datetime.now(timezone.utc))
    todo.add("summary", input_data.title)
    todo.add("due", _parse_due(input_data.due))
    todo.add("status", "NEEDS-ACTION")
    todo.add("priority", input_data.priority)
    todo.add("description", input_data.description)
    if input_data.tags:
        todo.add("categories", input_data.tags)
    if input_data.recurrence:
        todo.add("rrule", input_data.recurrence)
    for reminder in input_data.reminders:
        alarm = Alarm()
        alarm.add("action", reminder["action"])
        alarm.add("description", reminder["description"])
        alarm.add("trigger", -timedelta(minutes=reminder["minutes_before"]))
        todo.add_component(alarm)

    calendar = Calendar()
    calendar.add("prodid", PRODID)
    calendar.add("version", "2.0")
    calendar.add_component(todo)
    return calendar


def task_to_bytes(calendar: Calendar) -> bytes:
    return calendar.to_ical()
