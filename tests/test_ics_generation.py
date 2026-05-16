from __future__ import annotations

import json

from icalendar import Calendar

from caldav_calendar import cli
from caldav_calendar.cli import main


def test_event_create_confirm_writes_valid_vevent(configured_env, event_input, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})

    code = main(["event", "create", "--json-input", str(event_input), "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    files = list(configured_env["events"].glob("*.ics"))
    assert len(files) == 1
    calendar = Calendar.from_ical(files[0].read_bytes())
    assert len(calendar.walk("VEVENT")) == 1


def test_event_create_writes_recurrence_and_reminders(configured_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    event_input = tmp_path / "event.json"
    event_input.write_text(
        json.dumps(
            {
                "calendar": "personal",
                "title": "Weekly review",
                "start": "2026-05-16T14:00:00",
                "end": "2026-05-16T16:00:00",
                "timezone": "Asia/Shanghai",
                "recurrence": {"frequency": "weekly", "interval": 1, "count": 4, "by_day": ["SA"]},
                "reminders": [{"minutes_before": 30, "description": "Weekly review"}],
            }
        )
    )

    code = main(["event", "create", "--json-input", str(event_input), "--confirm"])
    json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["events"].glob("*.ics")).read_bytes())
    event = calendar.walk("VEVENT")[0]
    alarm = event.walk("VALARM")[0]

    assert code == 0
    assert event.get("rrule").to_ical().decode("utf-8") == "FREQ=WEEKLY;COUNT=4;INTERVAL=1;BYDAY=SA"
    assert alarm.get("trigger").to_ical().decode("utf-8") == "-PT30M"


def test_task_create_confirm_writes_valid_vtodo(configured_env, task_input, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})

    code = main(["task", "create", "--json-input", str(task_input), "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    files = list(configured_env["tasks"].glob("*.ics"))
    assert len(files) == 1
    calendar = Calendar.from_ical(files[0].read_bytes())
    todos = calendar.walk("VTODO")
    assert len(todos) == 1
    assert str(todos[0].get("status")) == "NEEDS-ACTION"


def test_task_create_writes_reminder(configured_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    task_input = tmp_path / "task.json"
    task_input.write_text(
        json.dumps(
            {
                "list": "Inbox",
                "title": "Prepare materials",
                "due": "2026-05-18",
                "timezone": "Asia/Shanghai",
                "reminders": [{"minutes_before": 1440, "description": "Prepare materials"}],
            }
        )
    )

    code = main(["task", "create", "--json-input", str(task_input), "--confirm"])
    json.loads(capsys.readouterr().out)
    calendar = Calendar.from_ical(next(configured_env["tasks"].glob("*.ics")).read_bytes())
    alarm = calendar.walk("VTODO")[0].walk("VALARM")[0]

    assert code == 0
    assert alarm.get("trigger").to_ical().decode("utf-8") == "-P1D"


def test_task_done_confirm_marks_completed(configured_env, task_input, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_sync", lambda: {"returncode": 0, "stdout": "", "stderr": ""})
    main(["task", "create", "--json-input", str(task_input), "--confirm"])
    created = json.loads(capsys.readouterr().out)

    code = main(["task", "done", "--uid", created["uid"], "--confirm"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    calendar = Calendar.from_ical(next(configured_env["tasks"].glob("*.ics")).read_bytes())
    todos = calendar.walk("VTODO")
    assert str(todos[0].get("status")) == "COMPLETED"
