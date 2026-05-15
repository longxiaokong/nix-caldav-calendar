from __future__ import annotations

import json
from types import SimpleNamespace

from caldav_calendar import remote
from caldav_calendar.cli import main


def _direct_config(configured_env):
    (configured_env["config_dir"] / "caldav-calendar.json").write_text(
        json.dumps(
            {
                "backend": "direct-caldav",
                "timezone": "Asia/Shanghai",
                "base_url": "https://cloud.example.com/remote.php/dav/calendars/user/",
                "username": "user",
                "event_collections": {"personal": "personal"},
                "task_collections": {"Inbox": "tasks"},
                "default_event_calendar": "personal",
                "default_task_list": "Inbox",
            }
        )
    )


def test_suggest_config_classifies_components_and_ignores_birthdays(configured_env, monkeypatch, capsys):
    _direct_config(configured_env)
    monkeypatch.setattr(
        remote,
        "discover",
        lambda config: [
            {"slug": "personal", "display_name": "Personal", "href": "https://example/personal/", "supports": ["VEVENT"]},
            {"slug": "tasks", "display_name": "Tasks", "href": "https://example/tasks/", "supports": ["VTODO"]},
            {"slug": "contact_birthdays", "display_name": "Contact birthdays", "href": "https://example/contact_birthdays/", "supports": ["VEVENT"]},
        ],
    )

    code = main(["caldav", "suggest-config", "--json"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert output["needs_user_choice"] is False
    assert output["recommended_config"]["event_collections"]["personal"] == "personal"
    assert output["recommended_config"]["task_collections"]["Inbox"] == "tasks"
    assert output["ignored"][0]["slug"] == "contact_birthdays"


def test_suggest_config_requires_choice_when_multiple_event_candidates(configured_env, monkeypatch, capsys):
    _direct_config(configured_env)
    monkeypatch.setattr(
        remote,
        "discover",
        lambda config: [
            {"slug": "personal", "display_name": "Personal", "href": "https://example/personal/", "supports": ["VEVENT"]},
            {"slug": "work", "display_name": "Work", "href": "https://example/work/", "supports": ["VEVENT"]},
            {"slug": "tasks", "display_name": "Tasks", "href": "https://example/tasks/", "supports": ["VTODO"]},
        ],
    )

    code = main(["caldav", "suggest-config", "--json"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["needs_user_choice"] is True
    assert output["recommended_config"]["event_collections"] == {}


def test_write_config_dry_run_does_not_write(configured_env, tmp_path, capsys):
    target = configured_env["config_dir"] / "caldav-calendar.json"
    original = target.read_text()
    input_path = tmp_path / "suggested.json"
    input_path.write_text(
        json.dumps(
            {
                "backend": "direct-caldav",
                "timezone": "Asia/Shanghai",
                "base_url": "https://cloud.example.com/remote.php/dav/calendars/user/",
                "username": "user",
                "event_collections": {"personal": "personal"},
                "task_collections": {"Inbox": "tasks"},
                "default_event_calendar": "personal",
                "default_task_list": "Inbox",
            }
        )
    )

    code = main(["caldav", "write-config", "--json-input", str(input_path), "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["would_write"] is True
    assert target.read_text() == original


def test_write_config_confirm_writes_file(configured_env, tmp_path, capsys):
    input_path = tmp_path / "suggested.json"
    input_path.write_text(
        json.dumps(
            {
                "backend": "direct-caldav",
                "timezone": "Asia/Shanghai",
                "base_url": "https://cloud.example.com/remote.php/dav/calendars/user/",
                "username": "user",
                "event_collections": {"personal": "personal"},
                "task_collections": {"Inbox": "tasks"},
                "default_event_calendar": "personal",
                "default_task_list": "Inbox",
            }
        )
    )

    code = main(["caldav", "write-config", "--json-input", str(input_path), "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["written"] is True
    written = json.loads((configured_env["config_dir"] / "caldav-calendar.json").read_text())
    assert written["backend"] == "direct-caldav"
    assert written["task_collections"]["Inbox"] == "tasks"
