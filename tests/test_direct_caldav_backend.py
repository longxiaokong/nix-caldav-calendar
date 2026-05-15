from __future__ import annotations

import json

from caldav_calendar import cli, remote
from caldav_calendar.cli import main


def _direct_config(configured_env):
    config_path = configured_env["config_dir"] / "caldav-calendar.json"
    config_path.write_text(
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


def test_direct_sync_is_json_noop(configured_env, capsys):
    _direct_config(configured_env)

    code = main(["sync", "--json"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert output["sync"]["backend"] == "direct-caldav"
    assert output["sync"]["skipped"] is True


def test_direct_event_create_confirm_calls_remote(configured_env, event_input, monkeypatch, capsys):
    _direct_config(configured_env)
    calls = []

    def fake_create(config, calendar_name, ics_text):
        calls.append((calendar_name, ics_text))

    monkeypatch.setattr(remote, "create_event", fake_create)

    code = main(["event", "create", "--json-input", str(event_input), "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert output["path"] is None
    assert calls[0][0] == "personal"
    assert "BEGIN:VEVENT" in calls[0][1]
    assert list(configured_env["events"].glob("*.ics")) == []


def test_direct_task_done_confirm_calls_remote(configured_env, monkeypatch, capsys):
    _direct_config(configured_env)
    monkeypatch.setattr(remote, "get_task", lambda config, uid: {"uid": uid, "title": "Task", "status": "NEEDS-ACTION"})
    monkeypatch.setattr(remote, "complete_task", lambda config, uid: {"uid": uid, "title": "Task", "status": "COMPLETED"})

    code = main(["task", "done", "--uid", "abc", "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert output["item"]["status"] == "COMPLETED"
