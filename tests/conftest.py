from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def configured_env(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    events = data_dir / "personal-calendar"
    tasks = data_dir / "tasks-inbox"
    config_dir.mkdir()
    events.mkdir(parents=True)
    tasks.mkdir(parents=True)
    auth_file = tmp_path / "auth"
    auth_file.write_text("secret-placeholder")
    (config_dir / "caldav-calendar.json").write_text(
        json.dumps(
            {
                "timezone": "Asia/Shanghai",
                "event_calendars": {"personal": str(events)},
                "task_lists": {"Inbox": str(tasks)},
                "default_event_calendar": "personal",
                "default_task_list": "Inbox",
            }
        )
    )
    monkeypatch.setenv("CALDAV_CALENDAR_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("CALDAV_CALENDAR_AUTH_FILE", str(auth_file))
    monkeypatch.setenv("CALDAV_CALENDAR_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CALDAV_CALENDAR_DEFAULT_TIMEZONE", "Asia/Shanghai")
    return {
        "config_dir": config_dir,
        "data_dir": data_dir,
        "events": events,
        "tasks": tasks,
        "auth_file": auth_file,
    }


@pytest.fixture
def event_input(tmp_path):
    path = tmp_path / "event.json"
    path.write_text(
        json.dumps(
            {
                "calendar": "personal",
                "title": "Review summer camp materials",
                "start": "2026-05-16T14:00:00",
                "end": "2026-05-16T16:00:00",
                "timezone": "Asia/Shanghai",
                "description": "Review summer camp knowledge points",
            }
        )
    )
    return path


@pytest.fixture
def task_input(tmp_path):
    path = tmp_path / "task.json"
    path.write_text(
        json.dumps(
            {
                "list": "Inbox",
                "title": "Prepare summer camp application materials",
                "due": "2026-05-18",
                "timezone": "Asia/Shanghai",
                "priority": 5,
                "description": "Collect materials",
            }
        )
    )
    return path
