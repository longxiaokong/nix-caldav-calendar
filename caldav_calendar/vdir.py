from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from icalendar import Alarm, Calendar

from dateutil.rrule import rrulestr

from .errors import ConflictError, FilesystemWriteError, NotFoundError, ValidationError


@dataclass(frozen=True)
class VdirItem:
    path: Path
    component: Any


def iter_ics_files(directory: Path):
    if not directory.exists():
        return
    for path in sorted(directory.glob("*.ics")):
        if path.is_file():
            yield path


def read_calendar(path: Path) -> Calendar:
    return Calendar.from_ical(path.read_bytes())


def iter_components(directory: Path, component_name: str):
    for path in iter_ics_files(directory):
        calendar = read_calendar(path)
        for component in calendar.walk(component_name):
            yield VdirItem(path=path, component=component)


def _component_uid(component: Any) -> str:
    value = component.get("uid")
    return str(value) if value is not None else ""


def find_by_uid(directories: list[Path], component_name: str, uid: str) -> VdirItem:
    for directory in directories:
        for item in iter_components(directory, component_name):
            if _component_uid(item.component) == uid:
                return item
    raise NotFoundError(f"{component_name} not found for UID: {uid}")


def write_new_ics(directory: Path, uid: str, ics_bytes: bytes) -> Path:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uid}.ics"
        if path.exists():
            raise ConflictError(f"Refusing to overwrite existing item: {path}")
        path.write_bytes(ics_bytes)
        return path
    except ConflictError:
        raise
    except OSError as exc:
        raise FilesystemWriteError(f"Failed to write .ics file: {exc}") from exc


def overwrite_ics(path: Path, ics_bytes: bytes) -> None:
    try:
        path.write_bytes(ics_bytes)
    except OSError as exc:
        raise FilesystemWriteError(f"Failed to update .ics file: {exc}") from exc


def delete_ics(path: Path) -> None:
    try:
        path.unlink()
    except OSError as exc:
        raise FilesystemWriteError(f"Failed to delete .ics file: {exc}") from exc


def _prop_text(component: Any, key: str, default: str = "") -> str:
    value = component.get(key)
    return str(value) if value is not None else default


def _prop_dt(component: Any, key: str):
    value = component.get(key)
    if value is None:
        return None
    return value.dt


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _recurrence_summary(component: Any) -> str:
    value = component.get("rrule")
    if value is None:
        return ""
    to_ical = getattr(value, "to_ical", None)
    if callable(to_ical):
        return to_ical().decode("utf-8")
    return str(value)


def _reminder_summary(component: Any) -> list[dict[str, Any]]:
    output = []
    for alarm in component.walk("VALARM"):
        trigger = alarm.get("trigger")
        trigger_value = getattr(trigger, "dt", None)
        minutes_before = None
        if isinstance(trigger_value, timedelta):
            minutes_before = int(abs(trigger_value.total_seconds()) // 60)
        output.append(
            {
                "action": _prop_text(alarm, "action", "DISPLAY"),
                "description": _prop_text(alarm, "description"),
                "minutes_before": minutes_before,
            }
        )
    return output


def event_summary(item: VdirItem, calendar_name: str | None = None) -> dict[str, Any]:
    component = item.component
    return {
        "kind": "event",
        "uid": _prop_text(component, "uid"),
        "calendar": calendar_name,
        "title": _prop_text(component, "summary"),
        "start": _iso(_prop_dt(component, "dtstart")),
        "end": _iso(_prop_dt(component, "dtend")),
        "location": _prop_text(component, "location"),
        "description": _prop_text(component, "description"),
        "recurrence": _recurrence_summary(component),
        "reminders": _reminder_summary(component),
        "path": str(item.path),
    }


def task_summary(item: VdirItem, list_name: str | None = None) -> dict[str, Any]:
    component = item.component
    return {
        "kind": "task",
        "uid": _prop_text(component, "uid"),
        "list": list_name,
        "title": _prop_text(component, "summary"),
        "due": _iso(_prop_dt(component, "due")),
        "status": _prop_text(component, "status", "NEEDS-ACTION"),
        "priority": int(component.get("priority", 0) or 0),
        "description": _prop_text(component, "description"),
        "recurrence": _recurrence_summary(component),
        "reminders": _reminder_summary(component),
        "path": str(item.path),
    }


def _replace_prop(component: Any, key: str, value: Any) -> None:
    if key in component:
        del component[key]
    component.add(key, value)


def _remove_or_replace_text(component: Any, key: str, value: str) -> None:
    if value == "":
        if key in component:
            del component[key]
        return
    _replace_prop(component, key, value)


def _replace_recurrence(component: Any, value: dict | None) -> None:
    if "rrule" in component:
        del component["rrule"]
    if value is not None:
        component.add("rrule", value)


def _rrule_to_update_dict(value: Any) -> dict[str, Any]:
    output: dict[str, Any] = {}
    key_map = {"FREQ": "freq", "INTERVAL": "interval", "COUNT": "count", "UNTIL": "until", "BYDAY": "byday"}
    for key, raw_value in value.items():
        output_key = key_map.get(str(key).upper())
        if output_key is None:
            output_key = str(key).lower()
        items = raw_value if isinstance(raw_value, list) else [raw_value]
        if len(items) == 1 and output_key != "byday":
            output[output_key] = items[0]
        else:
            output[output_key] = items
    return output


def _recurrence_anchor(component: Any, component_name: str) -> date | datetime:
    key = "dtstart" if component_name == "VEVENT" else "due"
    value = _prop_dt(component, key)
    if value is None and component_name == "VTODO":
        value = _prop_dt(component, "dtstart")
    if value is None:
        raise ValidationError(f"{component_name} recurrence trim requires DTSTART or DUE")
    return value


def _as_rule_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def trim_recurrence_calendar(calendar: Calendar, uid: str, component_name: str, before_date: date) -> Calendar:
    for component in calendar.walk(component_name):
        if _component_uid(component) != uid:
            continue
        rrule_value = component.get("rrule")
        if rrule_value is None:
            raise ValidationError(f"{component_name} has no recurrence rule to trim")
        anchor = _recurrence_anchor(component, component_name)
        dtstart = _as_rule_datetime(anchor)
        cutoff = datetime.combine(before_date, time.min, tzinfo=dtstart.tzinfo)
        rule_text = f"RRULE:{rrule_value.to_ical().decode('utf-8')}"
        rule = rrulestr(rule_text, dtstart=dtstart)
        kept = rule.between(dtstart - timedelta(seconds=1), cutoff, inc=False)
        keep_count = len(kept)
        if keep_count < 1:
            raise ValidationError("Trim date would remove every occurrence; use delete by UID instead")
        updates = _rrule_to_update_dict(rrule_value)
        updates.pop("until", None)
        updates["count"] = keep_count
        _replace_recurrence(component, updates)
        _replace_prop(component, "last-modified", datetime.now(timezone.utc))
        return calendar
    raise NotFoundError(f"{component_name} not found for UID: {uid}")


def trim_recurrence(item: VdirItem, component_name: str, before_date: date) -> Calendar:
    return trim_recurrence_calendar(read_calendar(item.path), _component_uid(item.component), component_name, before_date)


def _replace_reminders(component: Any, reminders: list[dict]) -> None:
    component.subcomponents = [sub for sub in component.subcomponents if sub.name != "VALARM"]
    for reminder in reminders:
        alarm = Alarm()
        alarm.add("action", reminder["action"])
        alarm.add("description", reminder["description"])
        alarm.add("trigger", -timedelta(minutes=reminder["minutes_before"]))
        component.add_component(alarm)


def event_overlaps(item: VdirItem, start: date, end: date) -> bool:
    event_start = _prop_dt(item.component, "dtstart")
    event_end = _prop_dt(item.component, "dtend") or event_start
    if isinstance(event_start, datetime):
        event_start_date = event_start.date()
    else:
        event_start_date = event_start
    if isinstance(event_end, datetime):
        event_end_date = event_end.date()
    else:
        event_end_date = event_end
    if event_start_date is None:
        return False
    return event_start_date <= end and event_end_date >= start


def mark_task_done(item: VdirItem) -> Calendar:
    calendar = read_calendar(item.path)
    for todo in calendar.walk("VTODO"):
        if _component_uid(todo) == _component_uid(item.component):
            todo["status"] = "COMPLETED"
            if "completed" in todo:
                del todo["completed"]
            todo.add("completed", datetime.now(timezone.utc))
            return calendar
    raise NotFoundError(f"VTODO not found for UID: {_component_uid(item.component)}")


def update_event_calendar(calendar: Calendar, uid: str, updates: dict[str, Any]) -> Calendar:
    for event in calendar.walk("VEVENT"):
        if _component_uid(event) == uid:
            if "title" in updates:
                _replace_prop(event, "summary", updates["title"])
            if "start" in updates:
                _replace_prop(event, "dtstart", updates["start"])
            if "end" in updates:
                _replace_prop(event, "dtend", updates["end"])
            if "location" in updates:
                _remove_or_replace_text(event, "location", updates["location"])
            if "description" in updates:
                _remove_or_replace_text(event, "description", updates["description"])
            if "tags" in updates:
                if updates["tags"]:
                    _replace_prop(event, "categories", updates["tags"])
                elif "categories" in event:
                    del event["categories"]
            if "recurrence" in updates:
                _replace_recurrence(event, updates["recurrence"])
            if "reminders" in updates:
                _replace_reminders(event, updates["reminders"])
            _replace_prop(event, "last-modified", datetime.now(timezone.utc))
            return calendar
    raise NotFoundError(f"VEVENT not found for UID: {uid}")


def update_event(item: VdirItem, updates: dict[str, Any]) -> Calendar:
    return update_event_calendar(read_calendar(item.path), _component_uid(item.component), updates)


def update_task_calendar(calendar: Calendar, uid: str, updates: dict[str, Any]) -> Calendar:
    for todo in calendar.walk("VTODO"):
        if _component_uid(todo) == uid:
            if "title" in updates:
                _replace_prop(todo, "summary", updates["title"])
            if "due" in updates:
                parsed_due = datetime.fromisoformat(updates["due"])
                value = parsed_due.date() if "T" not in updates["due"] else parsed_due
                _replace_prop(todo, "due", value)
            if "priority" in updates:
                _replace_prop(todo, "priority", updates["priority"])
            if "description" in updates:
                _remove_or_replace_text(todo, "description", updates["description"])
            if "tags" in updates:
                if updates["tags"]:
                    _replace_prop(todo, "categories", updates["tags"])
                elif "categories" in todo:
                    del todo["categories"]
            if "recurrence" in updates:
                _replace_recurrence(todo, updates["recurrence"])
            if "reminders" in updates:
                _replace_reminders(todo, updates["reminders"])
            _replace_prop(todo, "last-modified", datetime.now(timezone.utc))
            return calendar
    raise NotFoundError(f"VTODO not found for UID: {uid}")


def update_task(item: VdirItem, updates: dict[str, Any]) -> Calendar:
    return update_task_calendar(read_calendar(item.path), _component_uid(item.component), updates)
