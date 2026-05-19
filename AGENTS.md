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

## Plugin config

Use `customPlugins.<plugin>.config.env` only for secret/runtime paths:

- `CALDAV_CALENDAR_AUTH_FILE`: runtime secret file path. Do not put this file
  in the Nix store.

Use `customPlugins.<plugin>.config.settings` for typed CalDAV configuration.
OpenClaw renders these settings to `config.json` in the first state directory,
`.config/caldav-calendar`.

Example placeholder:

```nix
customPlugins = [
  {
    source = "github:owner/nix-caldav-calendar?rev=<commit>&narHash=<narHash>";
    config = {
      env = {
        CALDAV_CALENDAR_AUTH_FILE = "/run/agenix/caldav-calendar-auth";
      };
      settings = {
        backend = "direct-caldav";
        provider = "nextcloud";
        timezone = "Asia/Shanghai";
        base_url = "https://cloud.example.com/remote.php/dav/calendars/USERNAME/";
        username = "USERNAME";
        event_collections = {
          personal = "personal";
        };
        task_collections = {
          Inbox = "tasks";
        };
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

The CLI reads config from:

- `$XDG_CONFIG_HOME/caldav-calendar/config.json`
- `$CALDAV_CALENDAR_CONFIG_DIR/config.json` when that override is set
- legacy `$CALDAV_CALENDAR_CONFIG_DIR/caldav-calendar.json`

`CALDAV_CALENDAR_DATA_DIR` is optional. Without it, `XDG_DATA_HOME` must be set,
and audit logs plus legacy vdir relative paths use
`$XDG_DATA_HOME/caldav-calendar`.

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
- `caldav-calendar event recurrence override --uid UID --occurrence-date YYYY-MM-DD --json-input FILE --dry-run`
- `caldav-calendar event recurrence override --uid UID --occurrence-date YYYY-MM-DD --json-input FILE --confirm`
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

Agents must not hand-edit CalDAV config files. Use `suggest-config` to
classify collections and `write-config` to write the selected config. If
`needs_user_choice` is true, ask the user which event/task collection to use.
`caldav discover` and `caldav suggest-config` are allowed to run before
`event_collections` and `task_collections` are configured; they only need
`backend`, `timezone`, `base_url`, `username`, and `CALDAV_CALENDAR_AUTH_FILE`.
Normal event/task operations still require collection mappings.

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

To change one event instance in a recurring series, use `event recurrence
override`. Its JSON input must include the new `start` and `end`, and may include
`title`, `location`, `description`, `tags`, and `reminders`. The CLI writes a
same-UID exception event with `RECURRENCE-ID`. Recurring task instance overrides
are not supported.

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
$XDG_DATA_HOME/caldav-calendar/audit.log.jsonl
```

If `CALDAV_CALENDAR_DATA_DIR` is set, it overrides that data directory.

## CI

Run:

```sh
nix develop -c pytest
nix build .#default
```
