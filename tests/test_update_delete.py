from __future__ import annotations

import json

from icalendar import Calendar

from caldav_calendar import cli, remote
from caldav_calendar.cli import main


def _write_json(path, data):
    path.write_text(json.dumps(data))
    return path


def test_task_update_dry_run_requires_uid_and_does_not_write(configured_env, task_input, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    main(["task", "create", "--json-input", str(task_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)
    update_input = _write_json(tmp_path / "task-update.json", {"due": "2026-05-19", "priority": 4})

    code = main(["task", "update", "--uid", created["uid"], "--json-input", str(update_input), "--dry-run"])
    output = json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["tasks"].glob("*.ics")).read_bytes())
    todo = calendar.walk("VTODO")[0]

    assert code == 0
    assert output["ok"] is True
    assert output["dry_run"] is True
    assert str(todo.get("due").dt) == "2026-05-18"


def test_task_update_confirm_changes_vtodo(configured_env, task_input, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    main(["task", "create", "--json-input", str(task_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)
    update_input = _write_json(tmp_path / "task-update.json", {"title": "Updated task", "due": "2026-05-19", "priority": 4})

    code = main(["task", "update", "--uid", created["uid"], "--json-input", str(update_input), "--confirm"])
    output = json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["tasks"].glob("*.ics")).read_bytes())
    todo = calendar.walk("VTODO")[0]

    assert code == 0
    assert output["ok"] is True
    assert str(todo.get("summary")) == "Updated task"
    assert str(todo.get("due").dt) == "2026-05-19"
    assert int(todo.get("priority")) == 4


def test_event_update_replaces_recurrence_and_reminders(configured_env, event_input, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    main(["event", "create", "--json-input", str(event_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)
    update_input = _write_json(
        tmp_path / "event-update.json",
        {
            "recurrence": {"frequency": "weekly", "count": 2, "by_day": ["SA"]},
            "reminders": [{"minutes_before": 15, "description": "Review"}],
        },
    )

    code = main(["event", "update", "--uid", created["uid"], "--json-input", str(update_input), "--confirm"])
    output = json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["events"].glob("*.ics")).read_bytes())
    event = calendar.walk("VEVENT")[0]

    assert code == 0
    assert output["item"]["recurrence"] == "FREQ=WEEKLY;COUNT=2;BYDAY=SA"
    assert output["item"]["reminders"][0]["minutes_before"] == 15
    assert event.get("rrule").to_ical().decode("utf-8") == "FREQ=WEEKLY;COUNT=2;BYDAY=SA"
    assert event.walk("VALARM")[0].get("trigger").to_ical().decode("utf-8") == "-PT15M"


def test_event_update_can_clear_recurrence_and_reminders(configured_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    event_input = _write_json(
        tmp_path / "event.json",
        {
            "calendar": "personal",
            "title": "Weekly review",
            "start": "2026-05-16T14:00:00",
            "end": "2026-05-16T16:00:00",
            "timezone": "Asia/Shanghai",
            "recurrence": {"frequency": "weekly", "count": 2},
            "reminders": [{"minutes_before": 15, "description": "Review"}],
        },
    )
    main(["event", "create", "--json-input", str(event_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)
    update_input = _write_json(tmp_path / "event-update.json", {"recurrence": None, "reminders": None})

    code = main(["event", "update", "--uid", created["uid"], "--json-input", str(update_input), "--confirm"])
    output = json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["events"].glob("*.ics")).read_bytes())
    event = calendar.walk("VEVENT")[0]

    assert code == 0
    assert output["item"]["recurrence"] == ""
    assert output["item"]["reminders"] == []
    assert event.get("rrule") is None
    assert event.walk("VALARM") == []


def test_event_recurrence_trim_keeps_occurrences_before_date(configured_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    event_input = _write_json(
        tmp_path / "event.json",
        {
            "calendar": "personal",
            "title": "Weekly review",
            "start": "2026-05-16T14:00:00",
            "end": "2026-05-16T16:00:00",
            "timezone": "Asia/Shanghai",
            "recurrence": {"frequency": "weekly", "count": 3, "by_day": ["SA"]},
        },
    )
    main(["event", "create", "--json-input", str(event_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)

    code = main(["event", "recurrence", "trim", "--uid", created["uid"], "--before-date", "2026-05-30", "--confirm"])
    output = json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["events"].glob("*.ics")).read_bytes())
    event = calendar.walk("VEVENT")[0]

    assert code == 0
    assert output["item"]["recurrence"] == "FREQ=WEEKLY;COUNT=2;BYDAY=SA"
    assert event.get("rrule").to_ical().decode("utf-8") == "FREQ=WEEKLY;COUNT=2;BYDAY=SA"


def test_event_recurrence_override_adds_exception_event(configured_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    event_input = _write_json(
        tmp_path / "event.json",
        {
            "calendar": "personal",
            "title": "Weekly review",
            "start": "2026-05-16T14:00:00",
            "end": "2026-05-16T16:00:00",
            "timezone": "Asia/Shanghai",
            "recurrence": {"frequency": "weekly", "count": 3, "by_day": ["SA"]},
        },
    )
    main(["event", "create", "--json-input", str(event_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)
    override_input = _write_json(
        tmp_path / "event-override.json",
        {
            "start": "2026-05-23T15:00:00",
            "end": "2026-05-23T17:00:00",
            "title": "Shifted weekly review",
            "location": "Library",
        },
    )

    code = main(
        [
            "event",
            "recurrence",
            "override",
            "--uid",
            created["uid"],
            "--occurrence-date",
            "2026-05-23",
            "--json-input",
            str(override_input),
            "--confirm",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["events"].glob("*.ics")).read_bytes())
    events = calendar.walk("VEVENT")
    overrides = [event for event in events if event.get("recurrence-id") is not None]

    assert code == 0
    assert output["ok"] is True
    assert len(events) == 2
    assert len(overrides) == 1
    assert str(overrides[0].get("summary")) == "Shifted weekly review"
    assert str(overrides[0].get("location")) == "Library"
    assert overrides[0].get("dtstart").dt.isoformat() == "2026-05-23T15:00:00+08:00"
    assert overrides[0].get("dtend").dt.isoformat() == "2026-05-23T17:00:00+08:00"
    assert overrides[0].get("recurrence-id").dt.isoformat() == "2026-05-23T14:00:00+08:00"


def test_event_recurrence_override_replaces_existing_exception(configured_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    event_input = _write_json(
        tmp_path / "event.json",
        {
            "calendar": "personal",
            "title": "Weekly review",
            "start": "2026-05-16T14:00:00",
            "end": "2026-05-16T16:00:00",
            "timezone": "Asia/Shanghai",
            "recurrence": {"frequency": "weekly", "count": 3, "by_day": ["SA"]},
        },
    )
    main(["event", "create", "--json-input", str(event_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)
    first_input = _write_json(tmp_path / "first.json", {"start": "2026-05-23T15:00:00", "end": "2026-05-23T17:00:00"})
    second_input = _write_json(tmp_path / "second.json", {"start": "2026-05-23T18:00:00", "end": "2026-05-23T19:00:00"})

    main(["event", "recurrence", "override", "--uid", created["uid"], "--occurrence-date", "2026-05-23", "--json-input", str(first_input), "--confirm"])
    json.loads(capsys.readouterr().out)
    code = main(["event", "recurrence", "override", "--uid", created["uid"], "--occurrence-date", "2026-05-23", "--json-input", str(second_input), "--confirm"])
    output = json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["events"].glob("*.ics")).read_bytes())
    overrides = [event for event in calendar.walk("VEVENT") if event.get("recurrence-id") is not None]

    assert code == 0
    assert output["ok"] is True
    assert len(overrides) == 1
    assert overrides[0].get("dtstart").dt.isoformat() == "2026-05-23T18:00:00+08:00"


def test_task_recurrence_trim_keeps_occurrences_before_date(configured_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    task_input = _write_json(
        tmp_path / "task.json",
        {
            "list": "Inbox",
            "title": "Weekly task",
            "due": "2026-05-16",
            "timezone": "Asia/Shanghai",
            "recurrence": {"frequency": "weekly", "count": 3, "by_day": ["SA"]},
        },
    )
    main(["task", "create", "--json-input", str(task_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)

    code = main(["task", "recurrence", "trim", "--uid", created["uid"], "--before-date", "2026-05-23", "--confirm"])
    output = json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["tasks"].glob("*.ics")).read_bytes())
    todo = calendar.walk("VTODO")[0]

    assert code == 0
    assert output["item"]["recurrence"] == "FREQ=WEEKLY;COUNT=1;BYDAY=SA"
    assert todo.get("rrule").to_ical().decode("utf-8") == "FREQ=WEEKLY;COUNT=1;BYDAY=SA"


def test_task_recurrence_trim_rejects_removing_every_occurrence(configured_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    task_input = _write_json(
        tmp_path / "task.json",
        {
            "list": "Inbox",
            "title": "Weekly task",
            "due": "2026-05-16",
            "timezone": "Asia/Shanghai",
            "recurrence": {"frequency": "weekly", "count": 3, "by_day": ["SA"]},
        },
    )
    main(["task", "create", "--json-input", str(task_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)

    code = main(["task", "recurrence", "trim", "--uid", created["uid"], "--before-date", "2026-05-16", "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["ok"] is False
    assert output["error"]["code"] == "VALIDATION_ERROR"


def test_task_update_without_mode_requires_confirmation(configured_env, task_input, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    main(["task", "create", "--json-input", str(task_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)
    update_input = _write_json(tmp_path / "task-update.json", {"due": "2026-05-19"})

    code = main(["task", "update", "--uid", created["uid"], "--json-input", str(update_input)])
    output = json.loads(capsys.readouterr().out)

    assert code == 6
    assert output["ok"] is False
    assert output["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_task_update_rejects_timezone_only(configured_env, task_input, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    main(["task", "create", "--json-input", str(task_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)
    update_input = _write_json(tmp_path / "task-update.json", {"timezone": "Asia/Shanghai"})

    code = main(["task", "update", "--uid", created["uid"], "--json-input", str(update_input), "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["ok"] is False
    assert output["error"]["code"] == "VALIDATION_ERROR"


def test_event_delete_confirm_removes_file(configured_env, event_input, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    main(["event", "create", "--json-input", str(event_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)

    code = main(["event", "delete", "--uid", created["uid"], "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert list(configured_env["events"].glob("*.ics")) == []


def test_event_delete_without_mode_requires_confirmation(configured_env, event_input, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    main(["event", "create", "--json-input", str(event_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)

    code = main(["event", "delete", "--uid", created["uid"]])
    output = json.loads(capsys.readouterr().out)

    assert code == 6
    assert output["ok"] is False
    assert output["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert len(list(configured_env["events"].glob("*.ics"))) == 1


def test_direct_task_update_calls_remote(configured_env, tmp_path, monkeypatch, capsys):
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
    update_input = _write_json(tmp_path / "task-update.json", {"due": "2026-05-19", "priority": 4})
    monkeypatch.setattr(remote, "get_task", lambda config, uid: {"uid": uid, "title": "Task", "status": "NEEDS-ACTION"})
    monkeypatch.setattr(
        remote,
        "update_remote_task",
        lambda config, uid, updates: {"uid": uid, "title": "Task", "due": updates["due"], "priority": updates["priority"]},
    )

    code = main(["task", "update", "--uid", "abc", "--json-input", str(update_input), "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert output["item"]["uid"] == "abc"
    assert output["item"]["due"] == "2026-05-19"


def test_direct_task_delete_calls_remote(configured_env, monkeypatch, capsys):
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
    monkeypatch.setattr(remote, "get_task", lambda config, uid: {"uid": uid, "title": "Task", "status": "NEEDS-ACTION"})
    monkeypatch.setattr(remote, "delete_remote_task", lambda config, uid: {"uid": uid, "title": "Task", "status": "NEEDS-ACTION"})

    code = main(["task", "delete", "--uid", "abc", "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert output["deleted"]["uid"] == "abc"
