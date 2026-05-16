# AGENTS.md

This repository is a Nix-native OpenClaw skill wrapper for agent-friendly
CalDAV calendar events and VTODO tasks.

## Plugin id

Use `caldav-calendar`.

## Runtime model

Agent automation uses the Python CLI. Prefer `backend = "direct-caldav"`:

- `VEVENT` calendar events are read/written through `python-caldav`.
- `VTODO` tasks are read/written through `python-caldav`.
- `caldav discover --json` classifies remote collections by supported component.
- `caldav suggest-config --json` creates a deterministic recommended config.
- `caldav write-config --json-input FILE --dry-run|--confirm` is the only
  agent-safe way to write setup config.
- Legacy `backend = "vdir"` remains available for local `.ics` files and
  `vdirsyncer sync`.
- `khal` and `todoman` remain installed for human/manual debugging only.

Do not automate interactive editors or TUI screens.

## Required environment

Set these values through `customPlugins.<plugin>.config.env`:

- `CALDAV_CALENDAR_CONFIG_DIR`: directory containing `caldav-calendar.json`
  or `config.json`, plus optional `vdirsyncer`, `khal`, and `todoman` configs.
- `CALDAV_CALENDAR_AUTH_FILE`: runtime secret file path. Do not put this file
  in the Nix store.
- `CALDAV_CALENDAR_DATA_DIR`: local data directory for vdirs and audit logs.
- `CALDAV_CALENDAR_DEFAULT_TIMEZONE`: default timezone, such as
  `Asia/Shanghai`.

Example placeholder:

```nix
customPlugins = [
  {
    source = "github:owner/nix-caldav-calendar?rev=<commit>&narHash=<narHash>";
    config = {
      env = {
        CALDAV_CALENDAR_CONFIG_DIR = "/var/lib/openclaw/caldav-calendar/config";
        CALDAV_CALENDAR_AUTH_FILE = "/run/agenix/caldav-calendar-auth";
        CALDAV_CALENDAR_DATA_DIR = "/var/lib/openclaw/caldav-calendar/data";
        CALDAV_CALENDAR_DEFAULT_TIMEZONE = "Asia/Shanghai";
      };
      settings = {
        backend = "direct-caldav";
        provider = "nextcloud";
        base_url = "https://cloud.example.com/remote.php/dav/calendars/USERNAME/";
        username = "USERNAME";
        default_event_calendar = "personal";
        default_task_list = "Inbox";
      };
    };
  }
];
```

No real credentials belong in this repository. In production, keep credentials
under secret-managed paths such as `/run/agenix/...` or `/run/secrets/...`.

## Python config

The CLI reads:

- `$CALDAV_CALENDAR_CONFIG_DIR/caldav-calendar.json`
- `$CALDAV_CALENDAR_CONFIG_DIR/config.json`

Example:

```json
{
  "backend": "direct-caldav",
  "timezone": "Asia/Shanghai",
  "base_url": "https://cloud.example.com/remote.php/dav/calendars/USERNAME/",
  "username": "USERNAME",
  "event_collections": {
    "personal": "personal"
  },
  "task_collections": {
    "Inbox": "tasks"
  },
  "default_event_calendar": "personal",
  "default_task_list": "Inbox"
}
```

## Agent-facing commands

All agent-facing commands are non-interactive and emit JSON:

- `caldav-calendar doctor --json`
- `caldav-calendar caldav discover --json`
- `caldav-calendar caldav suggest-config --json`
- `caldav-calendar caldav write-config --json-input FILE --dry-run`
- `caldav-calendar caldav write-config --json-input FILE --confirm`
- `caldav-calendar sync --json`
- `caldav-calendar event list --from YYYY-MM-DD --to YYYY-MM-DD --json`
- `caldav-calendar event get --uid UID --json`
- `caldav-calendar event create --json-input FILE --dry-run`
- `caldav-calendar event create --json-input FILE --confirm`
- `caldav-calendar event update --uid UID --json-input FILE --dry-run`
- `caldav-calendar event update --uid UID --json-input FILE --confirm`
- `caldav-calendar event delete --uid UID --dry-run`
- `caldav-calendar event delete --uid UID --confirm`
- `caldav-calendar event recurrence trim --uid UID --before-date YYYY-MM-DD --dry-run`
- `caldav-calendar event recurrence trim --uid UID --before-date YYYY-MM-DD --confirm`
- `caldav-calendar task list --status open|done|all --json`
- `caldav-calendar task get --uid UID --json`
- `caldav-calendar task create --json-input FILE --dry-run`
- `caldav-calendar task create --json-input FILE --confirm`
- `caldav-calendar task update --uid UID --json-input FILE --dry-run`
- `caldav-calendar task update --uid UID --json-input FILE --confirm`
- `caldav-calendar task done --uid UID --dry-run`
- `caldav-calendar task done --uid UID --confirm`
- `caldav-calendar task delete --uid UID --dry-run`
- `caldav-calendar task delete --uid UID --confirm`
- `caldav-calendar task recurrence trim --uid UID --before-date YYYY-MM-DD --dry-run`
- `caldav-calendar task recurrence trim --uid UID --before-date YYYY-MM-DD --confirm`

Write commands must use exactly one of `--dry-run` or `--confirm`. Without one,
the CLI returns JSON error code `CONFIRMATION_REQUIRED`.

Agents must not hand-edit `caldav-calendar.json`. Use `suggest-config` to
classify collections and `write-config` to write the selected config. If
`needs_user_choice` is true, ask the user which event/task collection to use.

For natural-language requests like "move the review task" or "delete the summer
camp task", agents should list the relevant date/status range, identify the
probable item, and then use UID-based update/delete. If more than one item
matches, ask the user to choose. Never update or delete by title alone.

Use structured JSON for repeat rules and alarms. `recurrence` maps to `RRULE`
and supports `frequency`, `interval`, `count`, `until`, and `by_day`.
`reminders` maps to `VALARM` and uses `minutes_before` plus optional
`description`; only display alarms are supported. In update JSON,
`"recurrence": null` clears an existing repeat rule and `"reminders": null`
clears all alarms.

To delete part of a recurring series, use `recurrence trim`. Its `--before-date`
keeps instances before that date and deletes instances on that date and after it
by rewriting the repeat rule to a shorter `COUNT`. To delete the whole recurring
series, use `event delete --uid` or `task delete --uid`.

## Manual passthrough

These commands are available for humans and debugging, not agent automation:

- `caldav-calendar khal ...`
- `caldav-calendar todoman ...`
- `caldav-calendar vdirsyncer ...`
- `caldav-calendar edit ...`
- `caldav-calendar todo edit ...`

Agents must not drive editors, TUIs, or interactive prompts.

## Audit log

Confirmed writes append JSON lines to:

```text
$CALDAV_CALENDAR_DATA_DIR/audit.log.jsonl
```

## CI

Run:

```sh
nix develop -c pytest
nix build .#default
```
