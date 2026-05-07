---
name: caldav-calendar
description: Sync and query CalDAV calendars (iCloud, Google, Fastmail, Nextcloud, etc.) using vdirsyncer + khal. Works on Linux.
metadata: {"clawdbot":{"emoji":"📅","os":["linux"],"requires":{"bins":["caldav-calendar"]},"install":[{"id":"nix-openclaw","kind":"nix","packages":["caldav-calendar"],"bins":["caldav-calendar"],"label":"Use the nix-openclaw caldav-calendar plugin"}]}}
---

# CalDAV Calendar (vdirsyncer + khal)

**vdirsyncer** syncs CalDAV calendars to local `.ics` files. **khal** reads and writes them. In OpenClaw, call them through the `caldav-calendar` wrapper on PATH.

## Required Runtime Env

`caldav-calendar` fails fast unless these are configured by the host:

- `CALDAV_CALENDAR_AUTH_FILE`: readable file containing the CalDAV/app-password secret.
- `CALDAV_CALENDAR_CONFIG_DIR`: explicit plugin config directory. The wrapper also honors `XDG_CONFIG_HOME` when used outside OpenClaw.

## Sync First

Always sync before querying or after making changes:
```bash
caldav-calendar sync
```

## View Events

```bash
caldav-calendar list                        # Today
caldav-calendar list today 7d               # Next 7 days
caldav-calendar list tomorrow               # Tomorrow
caldav-calendar list 2026-01-15 2026-01-20  # Date range
caldav-calendar list -a Work today          # Specific calendar
```

## Search

```bash
caldav-calendar search "meeting"
caldav-calendar search "dentist" --format "{start-date} {title}"
```

## Create Events

```bash
caldav-calendar new 2026-01-15 10:00 11:00 "Meeting title"
caldav-calendar new 2026-01-15 "All day event"
caldav-calendar new tomorrow 14:00 15:30 "Call" -a Work
caldav-calendar new 2026-01-15 10:00 11:00 "With notes" :: Description goes here
```

After creating, sync to push changes:
```bash
caldav-calendar sync
```

## Edit Events (interactive)

`caldav-calendar edit` is interactive — requires a TTY. Use tmux if automating:

```bash
caldav-calendar edit "search term"
caldav-calendar edit -a CalendarName "search term"
caldav-calendar edit --show-past "old event"
```

Menu options:
- `s` → edit summary
- `d` → edit description
- `t` → edit datetime range
- `l` → edit location
- `D` → delete event
- `n` → skip (save changes, next match)
- `q` → quit

After editing, sync:
```bash
caldav-calendar sync
```

## Delete Events

Use `caldav-calendar edit`, then press `D` to delete.

## Output Formats

For scripting:
```bash
caldav-calendar list --format "{start-date} {start-time}-{end-time} {title}" today 7d
caldav-calendar list --format "{uid} | {title} | {calendar}" today
```

Placeholders: `{title}`, `{description}`, `{start}`, `{end}`, `{start-date}`, `{start-time}`, `{end-date}`, `{end-time}`, `{location}`, `{calendar}`, `{uid}`

## Caching

khal caches events in its XDG data directory. If data looks stale after syncing:
```bash
rm "$XDG_DATA_HOME/khal/khal.db"
```

## Initial Setup

### 1. Configure vdirsyncer (`$XDG_CONFIG_HOME/vdirsyncer/config`)

Example for iCloud:
```ini
[general]
status_path = "~/.local/share/vdirsyncer/status/"

[pair icloud_calendar]
a = "icloud_remote"
b = "icloud_local"
collections = ["from a", "from b"]
conflict_resolution = "a wins"

[storage icloud_remote]
type = "caldav"
url = "https://caldav.icloud.com/"
username = "your@icloud.com"
password.fetch = ["command", "sh", "-c", "cat \"$CALDAV_CALENDAR_AUTH_FILE\""]

[storage icloud_local]
type = "filesystem"
path = "~/.local/share/vdirsyncer/calendars/"
fileext = ".ics"
```

Provider URLs:
- iCloud: `https://caldav.icloud.com/`
- Google: Use `google_calendar` storage type
- Fastmail: `https://caldav.fastmail.com/dav/calendars/user/EMAIL/`
- Nextcloud: `https://YOUR.CLOUD/remote.php/dav/calendars/USERNAME/`

### 2. Configure khal (`$XDG_CONFIG_HOME/khal/config`)

```ini
[calendars]
[[my_calendars]]
path = ~/.local/share/vdirsyncer/calendars/*
type = discover

[default]
default_calendar = Home
highlight_event_days = True

[locale]
timeformat = %H:%M
dateformat = %Y-%m-%d
```

### 3. Discover and sync

```bash
caldav-calendar discover   # First time only
caldav-calendar sync
```
