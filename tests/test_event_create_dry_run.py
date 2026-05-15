from __future__ import annotations

import json

from caldav_calendar.cli import main


def test_event_create_dry_run_does_not_write(configured_env, event_input, capsys):
    code = main(["event", "create", "--json-input", str(event_input), "--dry-run"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["ok"] is True
    assert output["dry_run"] is True
    assert output["would_create"]["kind"] == "event"
    assert "VEVENT" in output["ical"]
    assert list(configured_env["events"].glob("*.ics")) == []
