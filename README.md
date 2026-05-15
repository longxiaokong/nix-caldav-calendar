# nix-caldav-calendar

Agent-friendly CalDAV Calendar + VTODO Tasks skill for Nix/OpenClaw.

This repository provides a stable `caldav-calendar` CLI. The agent-facing path
is a Python JSON CLI that reads and writes local iCalendar `.ics` files:

- calendar events are `VEVENT`
- tasks/todos are `VTODO`
- local vdir directories are synced with Nextcloud through `vdirsyncer`
- `khal` and `todoman` remain available as manual/debug passthrough tools

No credentials, passwords, app tokens, or OAuth secrets are stored in the Nix
store.

## Status

This branch is an MVP focused on non-interactive automation:

- JSON output for agent-facing commands
- dry-run/confirm safety for writes
- VEVENT and VTODO generation
- local vdir read/write
- `vdirsyncer sync` after confirmed writes
- tests that use temporary local vdirs and do not require a real Nextcloud server

Advanced editing, deletion, recurrence, attendees, alarms, and provider-specific
config generation are intentionally out of scope for the first MVP.

## Nix Contract

The flake exports:

- `packages.${system}.default`: the `caldav-calendar` CLI package
- `openclawPlugin`: nix-openclaw plugin contract
- `devShells.${system}.default`: Python test/dev environment

`openclawPlugin.needs` declares:

```nix
{
  stateDirs = [
    ".config/caldav-calendar"
    ".local/share/caldav-calendar"
    ".local/share/vdirsyncer"
    ".local/share/khal"
    ".local/share/todoman"
  ];
  requiredEnv = [
    "CALDAV_CALENDAR_AUTH_FILE"
    "CALDAV_CALENDAR_CONFIG_DIR"
    "CALDAV_CALENDAR_DATA_DIR"
    "CALDAV_CALENDAR_DEFAULT_TIMEZONE"
  ];
}
```

## OpenClaw Configuration

Example:

```nix
{
  programs.openclaw = {
    enable = true;

    customPlugins = [
      {
        source = "github:OWNER/nix-caldav-calendar?rev=COMMIT&narHash=sha256-...";
        config = {
          env = {
            CALDAV_CALENDAR_CONFIG_DIR = "/var/lib/openclaw/caldav-calendar/config";
            CALDAV_CALENDAR_AUTH_FILE = "/run/agenix/caldav-calendar-auth";
            CALDAV_CALENDAR_DATA_DIR = "/var/lib/openclaw/caldav-calendar/data";
            CALDAV_CALENDAR_DEFAULT_TIMEZONE = "Asia/Shanghai";
          };
          settings = {
            provider = "nextcloud";
            baseUrl = "https://cloud.example.com";
            username = "user@example.com";
            default_event_calendar = "personal";
            default_task_list = "Inbox";
          };
        };
      }
    ];
  };
}
```

`config.settings` is Nix-native typed config. nix-openclaw may render it to
`config.json`, but this CLI needs a concrete Python config file with vdir paths,
described below.

## Environment Variables

- `CALDAV_CALENDAR_CONFIG_DIR`: directory containing `caldav-calendar.json` or
  `config.json`, and optionally `vdirsyncer`, `khal`, and `todoman` configs.
- `CALDAV_CALENDAR_AUTH_FILE`: runtime secret file path. This should point to
  something like `/run/agenix/caldav-calendar-auth` or
  `/run/secrets/caldav-calendar-auth`.
- `CALDAV_CALENDAR_DATA_DIR`: local data directory for vdirs and
  `audit.log.jsonl`.
- `CALDAV_CALENDAR_DEFAULT_TIMEZONE`: default timezone, for example
  `Asia/Shanghai`.

The CalDAV password/app token should be referenced by `vdirsyncer` at runtime:

```ini
password.fetch = ["command", "sh", "-c", "cat \"$CALDAV_CALENDAR_AUTH_FILE\""]
```

## Python CLI Config

Create `$CALDAV_CALENDAR_CONFIG_DIR/caldav-calendar.json`:

```json
{
  "timezone": "Asia/Shanghai",
  "event_calendars": {
    "personal": "/home/user/.local/share/caldav/personal-calendar"
  },
  "task_lists": {
    "Inbox": "/home/user/.local/share/caldav/tasks-inbox"
  },
  "default_event_calendar": "personal",
  "default_task_list": "Inbox"
}
```

The CLI also accepts `$CALDAV_CALENDAR_CONFIG_DIR/config.json`, which is useful
when the host renders typed settings to that filename.

Relative vdir paths are resolved under `CALDAV_CALENDAR_DATA_DIR`.

## Agent Commands

All agent-facing commands are non-interactive and emit JSON.

### Doctor

```sh
caldav-calendar doctor --json
```

Checks env presence, vdir directory existence, tool availability, config file,
and default timezone.

### Sync

```sh
caldav-calendar sync --json
```

Runs `vdirsyncer sync`. Confirmed writes automatically run sync afterward.

### Events

```sh
caldav-calendar event list --from 2026-05-16 --to 2026-05-20 --json
caldav-calendar event get --uid UID --json
caldav-calendar event create --json-input examples/event-create.json --dry-run
caldav-calendar event create --json-input examples/event-create.json --confirm
```

Event input:

```json
{
  "calendar": "personal",
  "title": "Review summer camp materials",
  "start": "2026-05-16T14:00:00",
  "end": "2026-05-16T16:00:00",
  "timezone": "Asia/Shanghai",
  "location": "",
  "description": "Review summer camp knowledge points",
  "tags": ["summer-camp", "study"]
}
```

Generated events include `VCALENDAR`, `VERSION:2.0`, `PRODID`, `VEVENT`,
`UID`, `DTSTAMP`, `DTSTART`, `DTEND`, `SUMMARY`, and `DESCRIPTION`.

### Tasks

```sh
caldav-calendar task list --status open --json
caldav-calendar task list --status done --json
caldav-calendar task list --status all --json
caldav-calendar task get --uid UID --json
caldav-calendar task create --json-input examples/task-create.json --dry-run
caldav-calendar task create --json-input examples/task-create.json --confirm
caldav-calendar task done --uid UID --dry-run
caldav-calendar task done --uid UID --confirm
```

Task input:

```json
{
  "list": "Inbox",
  "title": "Prepare summer camp application materials",
  "due": "2026-05-18",
  "timezone": "Asia/Shanghai",
  "priority": 5,
  "description": "Collect transcript, CV, personal statement, project experience, and recommendation letter materials",
  "tags": ["summer-camp", "application"]
}
```

Generated tasks include `VCALENDAR`, `VERSION:2.0`, `PRODID`, `VTODO`, `UID`,
`DTSTAMP`, `SUMMARY`, `DUE`, `STATUS:NEEDS-ACTION`, `PRIORITY`, and
`DESCRIPTION`.

## Safety Rules

- Read-only commands may run directly.
- Write commands require exactly one of `--dry-run` or `--confirm`.
- Without either flag, the CLI returns JSON error code `CONFIRMATION_REQUIRED`.
- `--dry-run` validates and returns the item that would be written; it writes no
  files and does not sync.
- `--confirm` writes the `.ics` file or update, runs `vdirsyncer sync`, and
  returns structured JSON.
- Update/done operations use UID only. Do not modify by title.
- If sync fails, the CLI returns JSON error code `SYNC_FAILURE`.

Exit codes:

- `0`: ok
- `1`: general error
- `2`: validation error
- `3`: config error
- `4`: not found
- `5`: conflict detected
- `6`: confirmation required
- `7`: sync failure
- `8`: filesystem write failure

## Audit Log

Confirmed writes append JSON lines to:

```text
$CALDAV_CALENDAR_DATA_DIR/audit.log.jsonl
```

Example:

```json
{
  "timestamp": "2026-05-16T10:00:00+08:00",
  "operation": "task.create",
  "uid": "generated-uid",
  "title": "Prepare summer camp application materials",
  "dry_run": false,
  "result": "ok"
}
```

## Nextcloud vdirsyncer Notes

The Python CLI does not replace `vdirsyncer` config. Configure
`$CALDAV_CALENDAR_CONFIG_DIR/vdirsyncer/config` so events and tasks sync into
the same vdir directories referenced by `caldav-calendar.json`.

For Nextcloud, the remote URL is usually:

```text
https://cloud.example.com/remote.php/dav/calendars/USERNAME/
```

Events and tasks can use separate `pair` sections with separate local filesystem
storages. Both should read the password through `CALDAV_CALENDAR_AUTH_FILE`.

## Manual Debug Passthrough

These commands remain available for humans:

```sh
caldav-calendar khal ...
caldav-calendar todoman ...
caldav-calendar vdirsyncer ...
caldav-calendar list ...
caldav-calendar todo ...
```

Do not use interactive passthrough commands for agent automation. In particular,
avoid `caldav-calendar edit ...` and `caldav-calendar todo edit ...`.

## Development

Use Nix for the development environment:

```sh
nix develop -c pytest
nix build .#default
nix eval --json --impure --expr '(let flake = builtins.getFlake (toString ./.); system = builtins.currentSystem; in flake.openclawPlugin system)'
```
