---
name: caldav-calendar
description: Agent-friendly CalDAV calendar events and VTODO tasks for Nextcloud and compatible providers. Uses JSON commands, local .ics vdirs, and vdirsyncer sync.
metadata: {"clawdbot":{"emoji":"📅","os":["linux"],"requires":{"bins":["caldav-calendar"]},"install":[{"id":"nix-openclaw","kind":"nix","packages":["caldav-calendar"],"bins":["caldav-calendar"],"label":"Use the nix-openclaw caldav-calendar plugin"}]}}
---

# CalDAV Calendar + Tasks

Use `caldav-calendar` for non-interactive JSON automation. Prefer the
`direct-caldav` backend, which uses `python-caldav` to talk to Nextcloud
directly.

- Calendar events are `VEVENT`.
- Tasks/todos are `VTODO`.
- In direct mode, the CLI reads and writes remote CalDAV collections directly.
- In legacy vdir mode, local `.ics` files live in configured vdir directories
  and `vdirsyncer` syncs them.
- `khal` and `todoman` are available only as manual/debug passthrough tools.

## Agent Rules

Never use interactive edit commands for automation:

- Do not use `caldav-calendar edit ...` for agent workflows.
- Do not use `caldav-calendar todo edit ...` for agent workflows.
- Do not drive editors, TUIs, prompts, vim, nano, or keyboard interaction.

Use JSON-based commands only:

- Use `event` commands for calendar items with fixed start/end times.
- Use `task` commands for todos with due dates or completion state.
- Use `caldav suggest-config` and `caldav write-config` for setup.
- Use UID for get/done/update/delete style operations.
- Always run write operations with `--dry-run` first.
- Only run write operations with `--confirm` after user confirmation.
- After confirmed writes, sync and read back by UID.

## Required Env

The host must provide:

- `CALDAV_CALENDAR_CONFIG_DIR`
- `CALDAV_CALENDAR_AUTH_FILE`
- `CALDAV_CALENDAR_DATA_DIR`
- `CALDAV_CALENDAR_DEFAULT_TIMEZONE`

Credentials must live in runtime secret paths such as `/run/agenix/...` or
`/run/secrets/...`, never in the Nix store.

The Python CLI reads config from:

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

## Doctor

```bash
caldav-calendar doctor --json
```

Use this before other operations. It reports env presence, tool availability,
configured timezone, and whether vdir directories exist.

## Sync

```bash
caldav-calendar sync --json
```

In direct mode this returns a JSON no-op because writes go directly to the
server. In legacy vdir mode this runs `vdirsyncer sync`.

## Discover

```bash
caldav-calendar caldav discover --json
```

Use this to classify collections. Only use `VEVENT` collections for events and
`VTODO` collections for tasks. Do not write to contact birthdays or other
generated/special collections.

Suggest setup config:

```bash
caldav-calendar caldav suggest-config --json
```

If `needs_user_choice` is false, ask the user whether to write the recommended
config. If `needs_user_choice` is true, ask the user to choose from
`event_candidates` and `task_candidates`.

Write config only with dry-run/confirm:

```bash
caldav-calendar caldav write-config --json-input suggested.json --dry-run
caldav-calendar caldav write-config --json-input suggested.json --confirm
```

Never hand-edit `caldav-calendar.json` as an agent action when the setup helper
can write it.

## Events

List events:

```bash
caldav-calendar event list --from 2026-05-16 --to 2026-05-20 --json
```

Get one event:

```bash
caldav-calendar event get --uid UID --json
```

Dry-run create:

```bash
caldav-calendar event create --json-input examples/event-create.json --dry-run
```

Confirmed create:

```bash
caldav-calendar event create --json-input examples/event-create.json --confirm
caldav-calendar event get --uid UID --json
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

## Tasks

List tasks:

```bash
caldav-calendar task list --status open --json
caldav-calendar task list --status done --json
caldav-calendar task list --status all --json
```

Get one task:

```bash
caldav-calendar task get --uid UID --json
```

Dry-run create:

```bash
caldav-calendar task create --json-input examples/task-create.json --dry-run
```

Confirmed create:

```bash
caldav-calendar task create --json-input examples/task-create.json --confirm
caldav-calendar task get --uid UID --json
```

Dry-run done:

```bash
caldav-calendar task done --uid UID --dry-run
```

Confirmed done:

```bash
caldav-calendar task done --uid UID --confirm
caldav-calendar task get --uid UID --json
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

## Manual Debug Passthrough

These remain available for humans, not agent automation:

```bash
caldav-calendar khal ...
caldav-calendar todoman ...
caldav-calendar vdirsyncer ...
caldav-calendar list ...
caldav-calendar todo ...
```

Do not use passthrough edit commands in automated workflows.
