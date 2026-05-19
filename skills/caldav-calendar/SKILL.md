---
name: caldav-calendar
description: Agent-friendly CalDAV calendar events and VTODO tasks for Nextcloud and compatible providers. Uses JSON commands, local .ics vdirs, and vdirsyncer sync.
metadata: {"clawdbot":{"emoji":"📅","os":["linux","macos"],"requires":{"bins":["caldav-calendar"]},"install":[{"id":"nix-openclaw","kind":"nix","packages":["caldav-calendar"],"bins":["caldav-calendar"],"label":"Use the nix-openclaw caldav-calendar plugin"}]}}
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
- Use structured `recurrence` and `reminders` fields; do not hand-compose raw
  `.ics` text.
- To handle requests by title, list relevant items, match the likely item, then
  use its UID. If multiple items match, ask the user to choose.
- Always run write operations with `--dry-run` first.
- Only run write operations with `--confirm` after user confirmation.
- After confirmed writes, sync and read back by UID.

## Plugin Config

The host must provide this env var:

- `CALDAV_CALENDAR_AUTH_FILE`

Credentials must live in runtime secret paths such as `/run/agenix/...` or
`/run/secrets/...`, never in the Nix store.

Use OpenClaw `settings` for typed config such as `backend`, `timezone`,
`base_url`, `username`, `event_collections`, and `task_collections`. OpenClaw
renders settings to `.config/caldav-calendar/config.json`.

The Python CLI reads config from:

- `$XDG_CONFIG_HOME/caldav-calendar/config.json`
- `$CALDAV_CALENDAR_CONFIG_DIR/config.json` when that override is set
- legacy `$CALDAV_CALENDAR_CONFIG_DIR/caldav-calendar.json`

The host must set either `XDG_CONFIG_HOME` or `CALDAV_CALENDAR_CONFIG_DIR`, and
either `XDG_DATA_HOME` or `CALDAV_CALENDAR_DATA_DIR`.

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

`discover` and `suggest-config` intentionally work before
`event_collections` and `task_collections` are configured. They only require
`backend`, `timezone`, `base_url`, `username`, and `CALDAV_CALENDAR_AUTH_FILE`.
Normal event/task operations still require collection mappings.

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

Never hand-edit CalDAV config files as an agent action when the setup helper
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

Dry-run update/delete by UID:

```bash
caldav-calendar event update --uid UID --json-input examples/event-update.json --dry-run
caldav-calendar event delete --uid UID --dry-run
caldav-calendar event recurrence trim --uid UID --before-date 2026-05-30 --dry-run
caldav-calendar event recurrence override --uid UID --occurrence-date 2026-05-23 --json-input examples/event-override.json --dry-run
```

Confirmed update/delete by UID:

```bash
caldav-calendar event update --uid UID --json-input examples/event-update.json --confirm
caldav-calendar event delete --uid UID --confirm
caldav-calendar event recurrence trim --uid UID --before-date 2026-05-30 --confirm
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

Set `"recurrence": null` in update JSON to remove an existing repeat rule. Set
`"reminders": null` in update JSON to remove all alarms.
Use `event recurrence trim --before-date YYYY-MM-DD` to delete instances on
that date and after it while keeping earlier instances. Use `event delete --uid`
to delete the entire recurring series.
Use `event recurrence override --occurrence-date YYYY-MM-DD` to change one
instance in a recurring series. The override JSON must include the new `start`
and `end`; it may also include `title`, `location`, `description`, `tags`, and
`reminders`.

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

Dry-run update/delete by UID:

```bash
caldav-calendar task update --uid UID --json-input examples/task-update.json --dry-run
caldav-calendar task delete --uid UID --dry-run
caldav-calendar task recurrence trim --uid UID --before-date 2026-05-30 --dry-run
```

Confirmed update/delete by UID:

```bash
caldav-calendar task update --uid UID --json-input examples/task-update.json --confirm
caldav-calendar task delete --uid UID --confirm
caldav-calendar task recurrence trim --uid UID --before-date 2026-05-30 --confirm
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
Use `task recurrence trim --before-date YYYY-MM-DD` to delete recurring task
instances on that date and after it while keeping earlier instances. Use
`task delete --uid` to delete the entire recurring task series.

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
