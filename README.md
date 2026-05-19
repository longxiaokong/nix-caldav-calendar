# nix-caldav-calendar

Agent-friendly CalDAV Calendar + VTODO Tasks skill for Nix/OpenClaw.

The recommended backend is now `direct-caldav`, powered by `python-caldav`.
It talks to Nextcloud CalDAV directly instead of writing to local collection
directories and relying on `vdirsyncer` to upload them.

- calendar events are `VEVENT`
- tasks/todos are `VTODO`
- `caldav discover --json` classifies remote collections by supported component
- `khal`, `todoman`, and `vdirsyncer` remain available as manual/debug tools
- the older `backend = "vdir"` local `.ics` flow remains available as a fallback

No credentials, passwords, app tokens, or OAuth secrets are stored in the Nix
store.

## Status

This branch is an MVP focused on non-interactive automation:

- JSON output for agent-facing commands
- dry-run/confirm safety for writes
- direct CalDAV create/list/get/done flows through `python-caldav`
- UID-based update/delete for events and tasks
- structured recurrence (`RRULE`) and reminders (`VALARM`)
- one-off event overrides for recurring series (`RECURRENCE-ID`)
- remote collection discovery and classification
- legacy local vdir read/write still available with `backend = "vdir"`
- tests that use temporary local vdirs or mocks and do not require a real Nextcloud server

Attendees, recurring task exceptions, and full provider config generation are
intentionally out of scope for this MVP.

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
  };
}
```

OpenClaw renders `config.settings` to `config.json` in the first state
directory, `.config/caldav-calendar`. Keep normal typed values in `settings`;
keep only the secret file path in `env`.

## Environment Variables

- `CALDAV_CALENDAR_AUTH_FILE`: runtime secret file path. This should point to
  something like `/run/agenix/caldav-calendar-auth` or
  `/run/secrets/caldav-calendar-auth`.
- `CALDAV_CALENDAR_CONFIG_DIR`: optional override for the config directory.
  Without it, `XDG_CONFIG_HOME` must be set and the CLI reads
  `$XDG_CONFIG_HOME/caldav-calendar/config.json`.
- `CALDAV_CALENDAR_DATA_DIR`: optional override for audit logs and legacy vdir
  state. Without it, `XDG_DATA_HOME` must be set and the CLI uses
  `$XDG_DATA_HOME/caldav-calendar`.
- `CALDAV_CALENDAR_DEFAULT_TIMEZONE`: optional local override. Prefer the
  `timezone` setting in plugin config.

## Direct CalDAV Config

OpenClaw normally creates `.config/caldav-calendar/config.json` from
`config.settings`. For local/manual testing, create `config.json` in the
directory selected by `CALDAV_CALENDAR_CONFIG_DIR` or
`$XDG_CONFIG_HOME/caldav-calendar`:

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

The values inside `event_collections` and `task_collections` may be collection
slugs, display names, or full collection URLs. Use discovery first to find the
right values:

```sh
caldav-calendar caldav discover --json
```

Bootstrap note: `caldav discover` and `caldav suggest-config` only require
`backend`, `timezone`, `base_url`, `username`, and `CALDAV_CALENDAR_AUTH_FILE`.
They intentionally work before `event_collections` and `task_collections` are
configured. Event/task read-write commands still require those collection
mappings.

Use only collections that advertise the matching component:

- `VEVENT` collections are valid event calendars
- `VTODO` collections are valid task lists
- generated collections such as contact birthdays should not be agent write targets

For agent setup, prefer deterministic helpers:

```sh
caldav-calendar caldav suggest-config --json
```

This returns `event_candidates`, `task_candidates`, `ignored`,
`needs_user_choice`, and `recommended_config`. If there is exactly one event
candidate and one task candidate, `recommended_config` is complete. If
`needs_user_choice` is true, the agent should ask the user which event/task
collection to use.

Write config only through the explicit writer:

```sh
caldav-calendar caldav write-config --json-input suggested.json --dry-run
caldav-calendar caldav write-config --json-input suggested.json --confirm
```

Agents should not hand-edit CalDAV config files.

## Legacy vdir Config

The previous vdirsyncer-backed mode is still available:

```json
{
  "backend": "vdir",
  "timezone": "Asia/Shanghai",
  "event_calendars": {
    "personal": "/home/user/.local/share/caldav/personal-calendar/personal"
  },
  "task_lists": {
    "Inbox": "/home/user/.local/share/caldav/tasks-inbox/tasks"
  },
  "default_event_calendar": "personal",
  "default_task_list": "Inbox"
}
```

In vdir mode, confirmed writes create local `.ics` files and then run
`vdirsyncer sync`. This mode requires the JSON paths to point to the actual
collection subdirectories, not the storage root.

## Agent Commands

All agent-facing commands are non-interactive and emit JSON.

### Doctor

```sh
caldav-calendar doctor --json
```

Checks env presence, tool availability, config file, backend, and timezone.

### Discover

```sh
caldav-calendar caldav discover --json
```

Lists remote collections with slug, display name, href, and supported CalDAV
components. Use this to choose event/task collections safely.

### Suggest / Write Config

```sh
caldav-calendar caldav suggest-config --json
caldav-calendar caldav write-config --json-input suggested.json --dry-run
caldav-calendar caldav write-config --json-input suggested.json --confirm
```

Use `suggest-config` to classify collections and produce a recommended config.
Use `write-config` to write the selected config. `write-config` also requires
dry-run/confirm safety.

### Sync

```sh
caldav-calendar sync --json
```

In `direct-caldav` mode this is a JSON no-op because writes go directly to the
remote server. In `vdir` mode it runs `vdirsyncer sync`.

### Events

```sh
caldav-calendar event list --from 2026-05-16 --to 2026-05-20 --json
caldav-calendar event get --uid UID --json
caldav-calendar event create --json-input examples/event-create.json --dry-run
caldav-calendar event create --json-input examples/event-create.json --confirm
caldav-calendar event update --uid UID --json-input examples/event-update.json --dry-run
caldav-calendar event update --uid UID --json-input examples/event-update.json --confirm
caldav-calendar event delete --uid UID --dry-run
caldav-calendar event delete --uid UID --confirm
caldav-calendar event recurrence trim --uid UID --before-date 2026-05-30 --dry-run
caldav-calendar event recurrence trim --uid UID --before-date 2026-05-30 --confirm
caldav-calendar event recurrence override --uid UID --occurrence-date 2026-05-23 --json-input examples/event-override.json --dry-run
caldav-calendar event recurrence override --uid UID --occurrence-date 2026-05-23 --json-input examples/event-override.json --confirm
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
  "tags": ["summer-camp", "study"],
  "recurrence": {
    "frequency": "weekly",
    "interval": 1,
    "count": 4,
    "by_day": ["SA"]
  },
  "reminders": [
    {
      "minutes_before": 30,
      "description": "Review summer camp materials"
    }
  ]
}
```

For update JSON, set `"recurrence": null` to remove an existing repeat rule and
`"reminders": null` to remove all alarms.

Use `event recurrence trim --before-date YYYY-MM-DD` to delete instances on
that date and after it while keeping earlier instances. For example, a weekly
event on May 16, 23, and 30 trimmed with `--before-date 2026-05-30` keeps May
16 and May 23. Use `event delete --uid UID` to delete the entire recurring
series.

Use `event recurrence override --occurrence-date YYYY-MM-DD` to change one
instance in a recurring series. The override JSON must include the new `start`
and `end`; it may also include `title`, `location`, `description`, `tags`, and
`reminders`. The CLI writes a same-UID exception event with `RECURRENCE-ID`.

### Tasks

```sh
caldav-calendar task list --status open --json
caldav-calendar task list --status done --json
caldav-calendar task list --status all --json
caldav-calendar task get --uid UID --json
caldav-calendar task create --json-input examples/task-create.json --dry-run
caldav-calendar task create --json-input examples/task-create.json --confirm
caldav-calendar task update --uid UID --json-input examples/task-update.json --dry-run
caldav-calendar task update --uid UID --json-input examples/task-update.json --confirm
caldav-calendar task done --uid UID --dry-run
caldav-calendar task done --uid UID --confirm
caldav-calendar task delete --uid UID --dry-run
caldav-calendar task delete --uid UID --confirm
caldav-calendar task recurrence trim --uid UID --before-date 2026-05-30 --dry-run
caldav-calendar task recurrence trim --uid UID --before-date 2026-05-30 --confirm
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
  "tags": ["summer-camp", "application"],
  "reminders": [
    {
      "minutes_before": 1440,
      "description": "Prepare summer camp application materials"
    }
  ]
}
```

Tasks support the same optional `recurrence` and `reminders` fields as events.
Reminder triggers are relative and use `minutes_before`.

Use `task recurrence trim --before-date YYYY-MM-DD` to delete recurring task
instances on that date and after it while keeping earlier instances. Use
`task delete --uid UID` to delete the entire recurring task series.

## Safety Rules

- Read-only commands may run directly.
- Write commands require exactly one of `--dry-run` or `--confirm`.
- Without either flag, the CLI returns JSON error code `CONFIRMATION_REQUIRED`.
- `--dry-run` validates and returns the item that would be written.
- `--confirm` performs the actual write.
- Update/done/delete operations use UID only. Do not modify by title.
- Config writes must use `caldav write-config --dry-run` before `--confirm`.
- Credentials are read from `CALDAV_CALENDAR_AUTH_FILE` at runtime.

When the user says "move the review task" or "delete the summer camp task", the
agent should first use `task list` or `event list` to find plausible matches,
ask for confirmation when ambiguous, and then call update/delete by UID. The CLI
intentionally does not update or delete by title.

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
$XDG_DATA_HOME/caldav-calendar/audit.log.jsonl
```

If `CALDAV_CALENDAR_DATA_DIR` is set, it overrides that data directory.

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
nix eval --json --impure --expr '(let flake = builtins.getFlake (toString ./.) ; system = builtins.currentSystem; in flake.openclawPlugin system)'
```
