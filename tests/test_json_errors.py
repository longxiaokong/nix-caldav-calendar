from __future__ import annotations

import json

from caldav_calendar.cli import main


def test_missing_required_field_returns_json(configured_env, tmp_path, capsys):
    path = tmp_path / "event.json"
    path.write_text(json.dumps({"start": "2026-05-16T14:00:00", "end": "2026-05-16T16:00:00"}))

    code = main(["event", "create", "--json-input", str(path), "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["ok"] is False
    assert output["error"]["code"] == "VALIDATION_ERROR"


def test_write_without_mode_requires_confirmation(configured_env, task_input, capsys):
    code = main(["task", "create", "--json-input", str(task_input)])
    output = json.loads(capsys.readouterr().out)

    assert code == 6
    assert output["ok"] is False
    assert output["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_invalid_recurrence_returns_json(configured_env, tmp_path, capsys):
    path = tmp_path / "event.json"
    path.write_text(
        json.dumps(
            {
                "title": "Review",
                "start": "2026-05-16T14:00:00",
                "end": "2026-05-16T16:00:00",
                "recurrence": {"frequency": "hourly"},
            }
        )
    )

    code = main(["event", "create", "--json-input", str(path), "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["ok"] is False
    assert output["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_reminder_returns_json(configured_env, tmp_path, capsys):
    path = tmp_path / "task.json"
    path.write_text(json.dumps({"title": "Prepare", "due": "2026-05-18", "reminders": [{"minutes_before": -1}]}))

    code = main(["task", "create", "--json-input", str(path), "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["ok"] is False
    assert output["error"]["code"] == "VALIDATION_ERROR"


def test_task_done_unknown_uid_returns_not_found(configured_env, capsys):
    code = main(["task", "done", "--uid", "missing", "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 4
    assert output["ok"] is False
    assert output["error"]["code"] == "NOT_FOUND"
