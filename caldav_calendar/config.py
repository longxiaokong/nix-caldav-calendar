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
    backend: str
    base_url: str | None
    username: str | None
    event_calendars: dict[str, Path]
    task_lists: dict[str, Path]
    event_collections: dict[str, str]
    task_collections: dict[str, str]
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
        config_dir / "config.json",
        config_dir / "caldav-calendar.json",
    ]


def _config_dir_from_env() -> Path:
    config_dir_raw = os.environ.get("CALDAV_CALENDAR_CONFIG_DIR")
    if config_dir_raw:
        return Path(config_dir_raw).expanduser()
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home).expanduser() / "caldav-calendar"
    raise ConfigError("CALDAV_CALENDAR_CONFIG_DIR or XDG_CONFIG_HOME is required")


def _data_dir_from_env() -> Path:
    data_dir_raw = os.environ.get("CALDAV_CALENDAR_DATA_DIR")
    if data_dir_raw:
        return Path(data_dir_raw).expanduser()
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "caldav-calendar"
    raise ConfigError("CALDAV_CALENDAR_DATA_DIR or XDG_DATA_HOME is required")


def load_config(require_files: bool = True, collections_required: bool = True) -> RuntimeConfig:
    config_dir = _config_dir_from_env()
    data_dir = _data_dir_from_env()
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
        raise ConfigError("Config setting timezone is required")

    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"Unknown timezone: {timezone}") from exc

    raw_event_calendars = file_data.get("event_calendars") or {}
    raw_task_lists = file_data.get("task_lists") or {}
    backend = file_data.get("backend") or "vdir"
    if backend not in {"vdir", "direct-caldav"}:
        raise ConfigError(f"Unsupported backend: {backend}")

    base_url = file_data.get("base_url") or file_data.get("baseUrl")
    username = file_data.get("username")
    raw_event_collections = file_data.get("event_collections") or {}
    raw_task_collections = file_data.get("task_collections") or {}

    if require_files and backend == "vdir" and not raw_event_calendars:
        raise ConfigError("Config must define at least one event_calendars entry")
    if require_files and backend == "vdir" and not raw_task_lists:
        raise ConfigError("Config must define at least one task_lists entry")
    if require_files and backend == "direct-caldav":
        if not base_url:
            raise ConfigError("Direct CalDAV backend requires base_url")
        if not username:
            raise ConfigError("Direct CalDAV backend requires username")
        if collections_required and not raw_event_collections:
            raise ConfigError("Direct CalDAV backend requires event_collections")
        if collections_required and not raw_task_collections:
            raise ConfigError("Direct CalDAV backend requires task_collections")

    event_calendars = {
        name: _resolve_data_path(path, data_dir)
        for name, path in raw_event_calendars.items()
    }
    task_lists = {
        name: _resolve_data_path(path, data_dir)
        for name, path in raw_task_lists.items()
    }

    default_event_calendar = (
        file_data.get("default_event_calendar")
        or next(iter(event_calendars), "")
        or next(iter(raw_event_collections), "")
    )
    default_task_list = (
        file_data.get("default_task_list")
        or next(iter(task_lists), "")
        or next(iter(raw_task_collections), "")
    )

    return RuntimeConfig(
        config_dir=config_dir,
        auth_file=auth_file,
        data_dir=data_dir,
        timezone=timezone,
        backend=backend,
        base_url=base_url,
        username=username,
        event_calendars=event_calendars,
        task_lists=task_lists,
        event_collections={name: str(value) for name, value in raw_event_collections.items()},
        task_collections={name: str(value) for name, value in raw_task_collections.items()},
        default_event_calendar=default_event_calendar,
        default_task_list=default_task_list,
        config_file=selected_file,
    )
