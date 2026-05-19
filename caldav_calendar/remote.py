from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

from icalendar import Calendar

from .errors import ConfigError, NotFoundError, SyncFailureError, ValidationError
from .vdir import (
    event_overlaps,
    event_summary,
    override_event_occurrence_calendar,
    task_summary,
    trim_recurrence_calendar,
    update_event_calendar,
    update_task_calendar,
)


@dataclass(frozen=True)
class RemoteItem:
    resource: Any
    component: Any
    collection_name: str | None = None

    @property
    def path(self):
        return getattr(self.resource, "url", "")


def _import_caldav():
    try:
        import caldav
    except ImportError as exc:
        raise ConfigError("python-caldav is not available in this runtime") from exc
    return caldav


def _password(config) -> str:
    if config.auth_file is None:
        raise ConfigError("CALDAV_CALENDAR_AUTH_FILE is required")
    return config.auth_file.read_text().strip()


def _client(config):
    caldav = _import_caldav()
    password = _password(config)
    if hasattr(caldav, "get_davclient"):
        return caldav.get_davclient(url=config.base_url, username=config.username, password=password)
    return caldav.DAVClient(url=config.base_url, username=config.username, password=password)


def _principal(config):
    return _client(config).principal()


def _calendars(config):
    return list(_principal(config).calendars())


def _slug(calendar) -> str:
    url = str(getattr(calendar, "url", ""))
    return urlparse(url).path.rstrip("/").split("/")[-1]


def _display_name(calendar) -> str:
    for attr in ("get_display_name", "name"):
        value = getattr(calendar, attr, None)
        if callable(value):
            try:
                result = value()
                if result:
                    return str(result)
            except Exception:
                pass
        elif value:
            return str(value)
    return _slug(calendar)


def _supported_components(calendar) -> list[str]:
    for attr in ("get_supported_components", "get_supported_component_set"):
        value = getattr(calendar, attr, None)
        if callable(value):
            try:
                result = value()
                if result:
                    return sorted({str(item).upper() for item in result})
            except Exception:
                pass
    return []


def discover(config) -> list[dict[str, Any]]:
    collections = []
    for calendar in _calendars(config):
        collections.append(
            {
                "href": str(getattr(calendar, "url", "")),
                "slug": _slug(calendar),
                "display_name": _display_name(calendar),
                "supports": _supported_components(calendar),
            }
        )
    return collections


def is_special_collection(collection: dict[str, Any]) -> bool:
    slug = collection.get("slug", "").lower()
    display_name = collection.get("display_name", "").lower()
    special_markers = [
        "birthday",
        "birthdays",
        "contact_birthdays",
        "contact birthdays",
    ]
    return any(marker in slug or marker in display_name for marker in special_markers)


def suggest_config(config) -> dict[str, Any]:
    collections = discover(config)
    ignored = []
    event_candidates = []
    task_candidates = []

    for collection in collections:
        supports = {component.upper() for component in collection.get("supports", [])}
        if is_special_collection(collection):
            ignored.append({**collection, "reason": "special/generated collection"})
            continue
        if "VEVENT" in supports:
            event_candidates.append(collection)
        if "VTODO" in supports:
            task_candidates.append(collection)
        if "VEVENT" not in supports and "VTODO" not in supports:
            ignored.append({**collection, "reason": "does not advertise VEVENT or VTODO"})

    recommended_event = event_candidates[0] if len(event_candidates) == 1 else None
    recommended_task = task_candidates[0] if len(task_candidates) == 1 else None
    needs_user_choice = len(event_candidates) != 1 or len(task_candidates) != 1
    recommended_config = {
        "backend": "direct-caldav",
        "timezone": config.timezone,
        "base_url": config.base_url,
        "username": config.username,
        "event_collections": {},
        "task_collections": {},
        "default_event_calendar": "personal",
        "default_task_list": "Inbox",
    }
    if recommended_event:
        recommended_config["event_collections"]["personal"] = recommended_event["slug"]
    if recommended_task:
        recommended_config["task_collections"]["Inbox"] = recommended_task["slug"]

    return {
        "collections": collections,
        "event_candidates": event_candidates,
        "task_candidates": task_candidates,
        "ignored": ignored,
        "needs_user_choice": needs_user_choice,
        "recommended_config": recommended_config,
    }


def _collection(config, kind: str, name: str | None):
    mapping = config.event_collections if kind == "event" else config.task_collections
    default_name = config.default_event_calendar if kind == "event" else config.default_task_list
    selected = name or default_name
    try:
        target = mapping[selected]
    except KeyError as exc:
        raise ConfigError(f"Unknown {kind} collection: {selected}") from exc

    for calendar in _calendars(config):
        candidates = {
            _slug(calendar),
            _display_name(calendar),
            str(getattr(calendar, "url", "")),
        }
        if target in candidates or selected in candidates:
            return calendar, selected
    raise NotFoundError(f"Remote CalDAV collection not found: {target}")


def _resources(calendar, component: str):
    if component == "VEVENT":
        method_names = ["events", "objects"]
    else:
        method_names = ["todos", "objects"]
    for name in method_names:
        method = getattr(calendar, name, None)
        if callable(method):
            try:
                if component == "VTODO" and name == "todos":
                    return list(method(include_completed=True))
                return list(method())
            except TypeError:
                continue
    return []


def _calendar_from_resource(resource) -> Calendar:
    data = getattr(resource, "data", None)
    if data is None and hasattr(resource, "load"):
        resource.load()
        data = getattr(resource, "data", None)
    if data is None:
        raise SyncFailureError("Remote resource did not include iCalendar data")
    return Calendar.from_ical(data)


def _resource_components(resource, component: str):
    calendar = _calendar_from_resource(resource)
    return calendar.walk(component)


def list_events(config, start: date, end: date) -> list[dict[str, Any]]:
    output = []
    names = list(config.event_collections) or [config.default_event_calendar]
    for name in names:
        collection, collection_name = _collection(config, "event", name)
        for resource in _resources(collection, "VEVENT"):
            for component in _resource_components(resource, "VEVENT"):
                item = RemoteItem(resource=resource, component=component, collection_name=collection_name)
                if event_overlaps(item, start, end):
                    output.append(event_summary(item, collection_name))
    return output


def list_tasks(config, status: str) -> list[dict[str, Any]]:
    output = []
    names = list(config.task_collections) or [config.default_task_list]
    for name in names:
        collection, collection_name = _collection(config, "task", name)
        for resource in _resources(collection, "VTODO"):
            for component in _resource_components(resource, "VTODO"):
                item = RemoteItem(resource=resource, component=component, collection_name=collection_name)
                summary = task_summary(item, collection_name)
                is_done = summary["status"].upper() in {"COMPLETED", "CANCELLED"}
                if status == "all" or (status == "done" and is_done) or (status == "open" and not is_done):
                    output.append(summary)
    return output


def _find_remote_by_uid(config, kind: str, uid: str) -> RemoteItem:
    component_name = "VEVENT" if kind == "event" else "VTODO"
    mapping = config.event_collections if kind == "event" else config.task_collections
    names = list(mapping) or [config.default_event_calendar if kind == "event" else config.default_task_list]
    first_match: RemoteItem | None = None
    for name in names:
        collection, collection_name = _collection(config, kind, name)
        for resource in _resources(collection, component_name):
            for component in _resource_components(resource, component_name):
                if str(component.get("uid", "")) == uid:
                    item = RemoteItem(resource=resource, component=component, collection_name=collection_name)
                    if kind != "event" or component.get("recurrence-id") is None:
                        return item
                    if first_match is None:
                        first_match = item
    if first_match is not None:
        return first_match
    raise NotFoundError(f"{component_name} not found for UID: {uid}")


def get_event(config, uid: str) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "event", uid)
    return event_summary(item, item.collection_name)


def get_task(config, uid: str) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "task", uid)
    return task_summary(item, item.collection_name)


def create_event(config, calendar_name: str | None, ics_text: str):
    collection, _collection_name = _collection(config, "event", calendar_name)
    add_event = getattr(collection, "add_event", None)
    if not callable(add_event):
        raise SyncFailureError("python-caldav collection does not support add_event")
    return add_event(ics_text)


def create_task(config, list_name: str | None, ics_text: str):
    collection, _collection_name = _collection(config, "task", list_name)
    add_todo = getattr(collection, "add_todo", None)
    if not callable(add_todo):
        raise SyncFailureError("python-caldav collection does not support add_todo")
    return add_todo(ics_text)


def complete_task(config, uid: str) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "task", uid)
    before = task_summary(item, item.collection_name)
    calendar = _calendar_from_resource(item.resource)
    for todo in calendar.walk("VTODO"):
        if str(todo.get("uid", "")) == uid:
            todo["status"] = "COMPLETED"
            if "completed" in todo:
                del todo["completed"]
            from datetime import datetime, timezone

            todo.add("completed", datetime.now(timezone.utc))
            break
    else:
        raise NotFoundError(f"VTODO not found for UID: {uid}")
    item.resource.data = calendar.to_ical().decode("utf-8")
    save = getattr(item.resource, "save", None)
    if not callable(save):
        raise SyncFailureError("python-caldav resource does not support save")
    save()
    return {**before, "status": "COMPLETED"}


def update_remote_event(config, uid: str, updates: dict[str, Any]) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "event", uid)
    calendar = _calendar_from_resource(item.resource)
    updated_calendar = update_event_calendar(calendar, uid, updates)
    item.resource.data = updated_calendar.to_ical().decode("utf-8")
    save = getattr(item.resource, "save", None)
    if not callable(save):
        raise SyncFailureError("python-caldav resource does not support save")
    save()
    refreshed = _find_remote_by_uid(config, "event", uid)
    return event_summary(refreshed, refreshed.collection_name)


def trim_remote_event_recurrence(config, uid: str, before_date: date) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "event", uid)
    calendar = _calendar_from_resource(item.resource)
    updated_calendar = trim_recurrence_calendar(calendar, uid, "VEVENT", before_date)
    item.resource.data = updated_calendar.to_ical().decode("utf-8")
    save = getattr(item.resource, "save", None)
    if not callable(save):
        raise SyncFailureError("python-caldav resource does not support save")
    save()
    refreshed = _find_remote_by_uid(config, "event", uid)
    return event_summary(refreshed, refreshed.collection_name)


def override_remote_event_occurrence(config, uid: str, occurrence_date: date, updates: dict[str, Any]) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "event", uid)
    calendar = _calendar_from_resource(item.resource)
    updated_calendar = override_event_occurrence_calendar(calendar, uid, occurrence_date, updates)
    item.resource.data = updated_calendar.to_ical().decode("utf-8")
    save = getattr(item.resource, "save", None)
    if not callable(save):
        raise SyncFailureError("python-caldav resource does not support save")
    save()
    refreshed = _find_remote_by_uid(config, "event", uid)
    return event_summary(refreshed, refreshed.collection_name)


def update_remote_task(config, uid: str, updates: dict[str, Any]) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "task", uid)
    calendar = _calendar_from_resource(item.resource)
    updated_calendar = update_task_calendar(calendar, uid, updates)
    item.resource.data = updated_calendar.to_ical().decode("utf-8")
    save = getattr(item.resource, "save", None)
    if not callable(save):
        raise SyncFailureError("python-caldav resource does not support save")
    save()
    refreshed = _find_remote_by_uid(config, "task", uid)
    return task_summary(refreshed, refreshed.collection_name)


def trim_remote_task_recurrence(config, uid: str, before_date: date) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "task", uid)
    calendar = _calendar_from_resource(item.resource)
    updated_calendar = trim_recurrence_calendar(calendar, uid, "VTODO", before_date)
    item.resource.data = updated_calendar.to_ical().decode("utf-8")
    save = getattr(item.resource, "save", None)
    if not callable(save):
        raise SyncFailureError("python-caldav resource does not support save")
    save()
    refreshed = _find_remote_by_uid(config, "task", uid)
    return task_summary(refreshed, refreshed.collection_name)


def delete_remote_event(config, uid: str) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "event", uid)
    before = event_summary(item, item.collection_name)
    delete = getattr(item.resource, "delete", None)
    if not callable(delete):
        raise SyncFailureError("python-caldav resource does not support delete")
    delete()
    return before


def delete_remote_task(config, uid: str) -> dict[str, Any]:
    item = _find_remote_by_uid(config, "task", uid)
    before = task_summary(item, item.collection_name)
    delete = getattr(item.resource, "delete", None)
    if not callable(delete):
        raise SyncFailureError("python-caldav resource does not support delete")
    delete()
    return before
