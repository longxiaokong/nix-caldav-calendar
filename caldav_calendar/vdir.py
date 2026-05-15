from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from icalendar import Calendar

from .errors import ConflictError, FilesystemWriteError, NotFoundError


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
        "path": str(item.path),
    }


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
