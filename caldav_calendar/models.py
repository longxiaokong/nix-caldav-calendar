from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .errors import ValidationError


def load_json_file(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text())
    except FileNotFoundError as exc:
        raise ValidationError(f"JSON input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON input: {path}") from exc
    if not isinstance(data, dict):
        raise ValidationError("JSON input must be an object")
    return data


def _require_str(data: dict, field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Missing required field: {field_name}")
    return value


def _optional_str(data: dict, field_name: str, default: str = "") -> str:
    value = data.get(field_name, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValidationError(f"Field must be a string: {field_name}")
    return value


def _optional_tags(data: dict) -> list[str]:
    value = data.get("tags", [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError("Field must be a list of strings: tags")
    return value


def _parse_datetime(value: str, timezone: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid ISO datetime: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed


def parse_optional_datetime(data: dict, field_name: str, timezone: str) -> datetime | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Field must be a non-empty ISO datetime string: {field_name}")
    return _parse_datetime(value, timezone)


def validate_update_fields(data: dict, allowed: set[str]) -> dict:
    unknown = set(data) - allowed
    if unknown:
        raise ValidationError(f"Unknown update field(s): {', '.join(sorted(unknown))}")
    if not data:
        raise ValidationError("Update JSON must include at least one field")
    if set(data) == {"timezone"}:
        raise ValidationError("Update JSON must include at least one mutable field")
    return data


def validate_event_update(data: dict, default_timezone: str) -> dict:
    allowed = {"title", "start", "end", "timezone", "location", "description", "tags"}
    validate_update_fields(data, allowed)
    timezone = _optional_str(data, "timezone", default_timezone) or default_timezone
    output = dict(data)
    if "title" in output:
        output["title"] = _require_str(output, "title")
    if "start" in output:
        output["start"] = parse_optional_datetime(output, "start", timezone)
    if "end" in output:
        output["end"] = parse_optional_datetime(output, "end", timezone)
    if "start" in output and "end" in output and output["end"] <= output["start"]:
        raise ValidationError("Event end must be after start")
    if "location" in output:
        output["location"] = _optional_str(output, "location")
    if "description" in output:
        output["description"] = _optional_str(output, "description")
    if "tags" in output:
        output["tags"] = _optional_tags(output)
    output["timezone"] = timezone
    return output


def validate_task_update(data: dict, default_timezone: str) -> dict:
    allowed = {"title", "due", "timezone", "priority", "description", "tags"}
    validate_update_fields(data, allowed)
    timezone = _optional_str(data, "timezone", default_timezone) or default_timezone
    output = dict(data)
    if "title" in output:
        output["title"] = _require_str(output, "title")
    if "due" in output:
        due = _require_str(output, "due")
        try:
            datetime.fromisoformat(due)
        except ValueError as exc:
            raise ValidationError(f"Invalid ISO date or datetime: {due}") from exc
        output["due"] = due
    if "priority" in output:
        priority_raw = output["priority"]
        if not isinstance(priority_raw, int) or priority_raw < 0 or priority_raw > 9:
            raise ValidationError("Field priority must be an integer from 0 to 9")
    if "description" in output:
        output["description"] = _optional_str(output, "description")
    if "tags" in output:
        output["tags"] = _optional_tags(output)
    output["timezone"] = timezone
    return output


@dataclass(frozen=True)
class EventCreateInput:
    calendar: str | None
    title: str
    start: datetime
    end: datetime
    timezone: str
    location: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict, default_calendar: str, default_timezone: str) -> "EventCreateInput":
        timezone = _optional_str(data, "timezone", default_timezone) or default_timezone
        title = _require_str(data, "title")
        start = _parse_datetime(_require_str(data, "start"), timezone)
        end = _parse_datetime(_require_str(data, "end"), timezone)
        if end <= start:
            raise ValidationError("Event end must be after start")
        return cls(
            calendar=_optional_str(data, "calendar", default_calendar) or default_calendar,
            title=title,
            start=start,
            end=end,
            timezone=timezone,
            location=_optional_str(data, "location"),
            description=_optional_str(data, "description"),
            tags=_optional_tags(data),
        )


@dataclass(frozen=True)
class TaskCreateInput:
    list_name: str | None
    title: str
    due: str
    timezone: str
    priority: int = 0
    description: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict, default_list: str, default_timezone: str) -> "TaskCreateInput":
        timezone = _optional_str(data, "timezone", default_timezone) or default_timezone
        title = _require_str(data, "title")
        due = _require_str(data, "due")
        try:
            datetime.fromisoformat(due)
        except ValueError as exc:
            raise ValidationError(f"Invalid ISO date or datetime: {due}") from exc
        priority_raw = data.get("priority", 0)
        if not isinstance(priority_raw, int) or priority_raw < 0 or priority_raw > 9:
            raise ValidationError("Field priority must be an integer from 0 to 9")
        return cls(
            list_name=_optional_str(data, "list", default_list) or default_list,
            title=title,
            due=due,
            timezone=timezone,
            priority=priority_raw,
            description=_optional_str(data, "description"),
            tags=_optional_tags(data),
        )
