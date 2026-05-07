# AGENTS.md

This repository is a Nix-native OpenClaw plugin wrapper for CalDAV calendar
access through `vdirsyncer` and `khal`.

## Plugin id

Use `caldav-calendar`.

## Runtime command

OpenClaw should call the `caldav-calendar` command from the plugin runtime PATH.
The wrapper exposes these subcommands:

- `caldav-calendar sync`
- `caldav-calendar discover`
- `caldav-calendar list ...`
- `caldav-calendar search ...`
- `caldav-calendar new ...`
- `caldav-calendar edit ...`
- `caldav-calendar vdirsyncer ...`
- `caldav-calendar khal ...`

## Required environment

Set these values through `customPlugins.<plugin>.config.env`:

- `CALDAV_CALENDAR_AUTH_FILE`: path to a machine-local secret file containing
  the CalDAV password or app password.
- `CALDAV_CALENDAR_CONFIG_DIR`: plugin-specific config directory containing
  the `vdirsyncer` and `khal` config files.

Example placeholder:

```nix
customPlugins = [
  {
    source = "github:owner/caldav-calendar?rev=<commit>&narHash=<narHash>";
    config = {
      env = {
        CALDAV_CALENDAR_AUTH_FILE = "/run/agenix/caldav-calendar-auth";
        CALDAV_CALENDAR_CONFIG_DIR = "/var/lib/openclaw/caldav-calendar/config";
      };
      settings = {
        provider = "icloud";
        username = "user@example.com";
        calendar = "Home";
        syncDays = 30;
        enabled = true;
      };
    };
  }
];
```

No real credentials belong in this repository. In production, keep credentials
under a secret-managed path such as `/run/agenix/caldav-calendar-auth`,
`/run/secrets/caldav-calendar-auth`, or another host-local equivalent.

## Config directories

The wrapper honors config locations explicitly:

- `CALDAV_CALENDAR_CONFIG_DIR`: plugin-specific config directory. When set, the
  wrapper exports it as `XDG_CONFIG_HOME` for `vdirsyncer` and `khal`.
- `XDG_CONFIG_HOME`: standard XDG config directory. Used when
  `CALDAV_CALENDAR_CONFIG_DIR` is unset.

One of these must be set. The wrapper intentionally does not fall back to
`~/.config`.

The OpenClaw host renders typed `config.settings` to `config.json` in the first
declared state directory:

- `.config/caldav-calendar`

`vdirsyncer` and `khal` still expect their normal config files below the active
config home:

- `$XDG_CONFIG_HOME/vdirsyncer/config`
- `$XDG_CONFIG_HOME/khal/config`

Use `CALDAV_CALENDAR_AUTH_FILE` from the `vdirsyncer` config through a command
password fetch, for example:

```ini
password.fetch = ["command", "sh", "-c", "cat \"$CALDAV_CALENDAR_AUTH_FILE\""]
```

## Runtime state

The wrapper declares these OpenClaw state directories:

- `.config/caldav-calendar`
- `.local/share/vdirsyncer`
- `.local/share/khal`

`vdirsyncer` stores sync status and local calendar files under its configured
paths. `khal` may store its event cache in `.local/share/khal` when the runtime
uses XDG state/data locations.

## CI

This repository does not currently include Garnix configuration. If Garnix is
added later, include checks that build `packages.<system>.default` and evaluate
`openclawPlugin`.
