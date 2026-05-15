from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ConfigError


@dataclass(frozen=True)
class RuntimeConfig:
    config_dir: Path
    auth_file: Path | None
    data_dir: Path
    timezone: str
    event_calendars: dict[str, Path]
    task_lists: dict[str, Path]
    default_event_calendar: str
    default_task_list: str
    config_file: Path | None

    def event_dir(self, name: str | None) -> Path:
        selected = name or self.default_event_calendar
        try:
            return self.event_calendars[selected]
        except KeyError as exc:
            raise ConfigError(f"Unknown event calendar: {selected}") from exc

    def task_dir(self, name: str | None) -> Path:
        selected = name or self.default_task_list
        try:
            return self.task_lists[selected]
        except KeyError as exc:
            raise ConfigError(f"Unknown task list: {selected}") from exc


def _resolve_data_path(raw: str, data_dir: Path) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return data_dir / path


def _config_candidates(config_dir: Path) -> list[Path]:
    return [
        config_dir / "caldav-calendar.json",
        config_dir / "config.json",
    ]


def load_config(require_files: bool = True) -> RuntimeConfig:
    config_dir_raw = os.environ.get("CALDAV_CALENDAR_CONFIG_DIR")
    if not config_dir_raw:
        raise ConfigError("CALDAV_CALENDAR_CONFIG_DIR is required")

    data_dir_raw = os.environ.get("CALDAV_CALENDAR_DATA_DIR")
    if not data_dir_raw:
        raise ConfigError("CALDAV_CALENDAR_DATA_DIR is required")

    config_dir = Path(config_dir_raw).expanduser()
    data_dir = Path(data_dir_raw).expanduser()
    auth_raw = os.environ.get("CALDAV_CALENDAR_AUTH_FILE")
    if not auth_raw:
        raise ConfigError("CALDAV_CALENDAR_AUTH_FILE is required")
    auth_file = Path(auth_raw).expanduser() if auth_raw else None
    if not auth_file.is_file():
        raise ConfigError(f"CALDAV_CALENDAR_AUTH_FILE is not readable: {auth_file}")

    selected_file = next((path for path in _config_candidates(config_dir) if path.exists()), None)
    if require_files and selected_file is None:
        names = ", ".join(str(path) for path in _config_candidates(config_dir))
        raise ConfigError(f"No caldav-calendar config file found; tried {names}")

    file_data: dict = {}
    if selected_file is not None:
        try:
            file_data = json.loads(selected_file.read_text())
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON config file: {selected_file}") from exc

    timezone = (
        os.environ.get("CALDAV_CALENDAR_DEFAULT_TIMEZONE")
        or file_data.get("timezone")
        or ""
    )
    if not timezone:
        raise ConfigError("CALDAV_CALENDAR_DEFAULT_TIMEZONE or config timezone is required")

    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"Unknown timezone: {timezone}") from exc

    raw_event_calendars = file_data.get("event_calendars") or {}
    raw_task_lists = file_data.get("task_lists") or {}

    if require_files and not raw_event_calendars:
        raise ConfigError("Config must define at least one event_calendars entry")
    if require_files and not raw_task_lists:
        raise ConfigError("Config must define at least one task_lists entry")

    event_calendars = {
        name: _resolve_data_path(path, data_dir)
        for name, path in raw_event_calendars.items()
    }
    task_lists = {
        name: _resolve_data_path(path, data_dir)
        for name, path in raw_task_lists.items()
    }

    default_event_calendar = file_data.get("default_event_calendar") or next(iter(event_calendars), "")
    default_task_list = file_data.get("default_task_list") or next(iter(task_lists), "")

    return RuntimeConfig(
        config_dir=config_dir,
        auth_file=auth_file,
        data_dir=data_dir,
        timezone=timezone,
        event_calendars=event_calendars,
        task_lists=task_lists,
        default_event_calendar=default_event_calendar,
        default_task_list=default_task_list,
        config_file=selected_file,
    )
