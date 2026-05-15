from __future__ import annotations

import json

from caldav_calendar.cli import main


def test_task_create_dry_run_does_not_write(configured_env, task_input, capsys):
    code = main(["task", "create", "--json-input", str(task_input), "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert output["dry_run"] is True
    assert output["would_create"]["kind"] == "task"
    assert "VTODO" in output["ical"]
    assert list(configured_env["tasks"].glob("*.ics")) == []
