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
