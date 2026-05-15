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
- `caldav-calendar sync --json`
- `caldav-calendar event list --from YYYY-MM-DD --to YYYY-MM-DD --json`
- `caldav-calendar event get --uid UID --json`
- `caldav-calendar event create --json-input FILE --dry-run`
- `caldav-calendar event create --json-input FILE --confirm`
- `caldav-calendar task list --status open|done|all --json`
- `caldav-calendar task get --uid UID --json`
- `caldav-calendar task create --json-input FILE --dry-run`
- `caldav-calendar task create --json-input FILE --confirm`
- `caldav-calendar task done --uid UID --dry-run`
- `caldav-calendar task done --uid UID --confirm`

Write commands must use exactly one of `--dry-run` or `--confirm`. Without one,
the CLI returns JSON error code `CONFIRMATION_REQUIRED`.

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
