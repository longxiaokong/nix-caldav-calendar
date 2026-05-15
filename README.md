# nix-caldav-calendar

这是 CalDAV calendar and tasks tools 的 Nix-native OpenClaw wrapper。

这个仓库不保存任何日历凭据，也不实现新的 CalDAV 协议客户端。插件包会通过 Nix
提供一个稳定的 `caldav-calendar` CLI，并把 `vdirsyncer`、`khal` 和 `todoman` 放进
OpenClaw runtime PATH；本仓库保存 Nix 契约、skill 文档和少量 wrapper 文档。

## 插件信息

- 插件 id：`caldav-calendar`
- Runtime CLI：`caldav-calendar`
- 底层工具：`vdirsyncer`、`khal`、`todoman`
- 日历事件：用 `khal` 读写 `VEVENT`
- 任务：用 `todoman` 读写 `VTODO`，适合 Nextcloud Tasks 这类 CalDAV tasks
- 同步：事件和任务都通过 `vdirsyncer` 同步

## Nix 契约

这个 flake 导出：

- `packages.${system}.default`：包含 `caldav-calendar` wrapper CLI 的包。
- `openclawPlugin`：nix-openclaw 使用的插件契约，包含 `name`、`skills`、
  `packages` 和 `needs`。这个输出是 `system: { ... }` 形式，适合纯 flake 求值。
- `devShells.${system}.default`：带有 wrapper、`vdirsyncer`、`khal` 和 `todoman` 的本地开发环境。

`openclawPlugin.name` 是 `caldav-calendar`。

`openclawPlugin.needs` 声明：

```nix
{
  stateDirs = [
    ".config/caldav-calendar"
    ".local/share/vdirsyncer"
    ".local/share/khal"
    ".local/share/todoman"
  ];
  requiredEnv = [
    "CALDAV_CALENDAR_AUTH_FILE"
    "CALDAV_CALENDAR_CONFIG_DIR"
  ];
}
```

## 在 nix-openclaw 中启用

推荐把这个仓库作为 `customPlugins` 加到 nix-openclaw 配置里，并显式传入 env 和
typed settings：

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
            CALDAV_CALENDAR_CONFIG_DIR = "/var/lib/openclaw/caldav-calendar/config";
          };
          settings = {
            provider = "nextcloud";
            baseUrl = "https://cloud.example.com";
            username = "user@example.com";

            events = {
              enabled = true;
              localPath = ".local/share/vdirsyncer/calendars";
              defaultCalendar = "personal";
            };

            tasks = {
              enabled = true;
              localPath = ".local/share/vdirsyncer/tasks";
              defaultList = "Inbox";
            };

            sync = {
              conflictResolution = "a wins";
            };
          };
        };
      }
    ];
  };
}
```

`config.env` 用于必需环境变量。`config.settings` 是普通 Nix typed config，
nix-openclaw 会把它渲染成第一个 state dir 里的 `config.json`，不需要内联 JSON
字符串。

重要：当前 wrapper 不会自动把 `config.json` 生成成 `vdirsyncer/config`、
`khal/config` 或 `todoman/config.py`。`settings` 是给 host、AI 和人类看的 typed
插件配置；实际 CLI 仍然读取下面这些文件：

- `$CALDAV_CALENDAR_CONFIG_DIR/vdirsyncer/config`
- `$CALDAV_CALENDAR_CONFIG_DIR/khal/config`
- `$CALDAV_CALENDAR_CONFIG_DIR/todoman/config.py`

## Runtime env

这个 wrapper 故意 fail-fast，不使用隐式 `~/.config` 默认值。需要配置：

- `CALDAV_CALENDAR_AUTH_FILE`：CalDAV 密码、app password 或 OAuth helper 所需的
  secret 文件路径。
- `CALDAV_CALENDAR_CONFIG_DIR`：包含 `vdirsyncer/config`、`khal/config` 和
  `todoman/config.py` 的配置目录。

凭据不应该提交到仓库，也不应该写进 Nix store。生产环境推荐使用 secret manager
暴露的机器本地路径，例如：

- `/run/agenix/caldav-calendar-auth`
- `/run/secrets/caldav-calendar-auth`

`vdirsyncer` 配置里可以这样读取凭据：

```ini
password.fetch = ["command", "sh", "-c", "cat \"$CALDAV_CALENDAR_AUTH_FILE\""]
```

## Settings schema

下面是 README 推荐的 `config.settings` 形状。它是 Nix-native typed config，不需要
JSON 字符串。

| Key | Type | Required | Meaning |
| --- | --- | --- | --- |
| `provider` | string | yes | `nextcloud`、`icloud`、`fastmail`、`generic-caldav`、`google` |
| `baseUrl` | string | provider-dependent | CalDAV server base URL。Nextcloud/Fastmail/generic 需要。 |
| `username` | string | yes | CalDAV 用户名或账号邮箱。 |
| `events.enabled` | bool | no | 是否配置日历事件。默认可以按 `true` 理解。 |
| `events.localPath` | string | no | 本地事件 `.ics` 目录，例如 `.local/share/vdirsyncer/calendars`。 |
| `events.defaultCalendar` | string | no | `khal` 默认日历名。 |
| `tasks.enabled` | bool | no | 是否配置 VTODO tasks。Nextcloud Tasks 推荐 `true`。 |
| `tasks.localPath` | string | no | 本地任务 `.ics` 目录，例如 `.local/share/vdirsyncer/tasks`。 |
| `tasks.defaultList` | string | no | `todoman` 默认任务列表名。 |
| `sync.conflictResolution` | string | no | vdirsyncer 冲突策略，常用 `"a wins"` 或 `"b wins"`。 |

### Provider matrix

| Provider | Events | Tasks / VTODO | Notes |
| --- | --- | --- | --- |
| `nextcloud` | yes | yes | 推荐用于 Nextcloud Calendar + Nextcloud Tasks。 |
| `icloud` | yes | maybe | iCloud CalDAV 适合日历；VTODO 支持取决于账号和 collection 暴露情况。 |
| `fastmail` | yes | yes | Fastmail 支持 CalDAV，task collection 可用性取决于账号配置。 |
| `generic-caldav` | yes | provider-dependent | 用于 Radicale、Baikal、SOGo 等通用 CalDAV 服务。 |
| `google` | yes | no | Google Calendar 可通过 `vdirsyncer` 的 `google_calendar` storage；Google Tasks 不是 CalDAV VTODO。 |

## Provider 配置建议

### Nextcloud

推荐 settings：

```nix
settings = {
  provider = "nextcloud";
  baseUrl = "https://cloud.example.com";
  username = "user@example.com";
  events = {
    enabled = true;
    localPath = ".local/share/vdirsyncer/calendars";
    defaultCalendar = "personal";
  };
  tasks = {
    enabled = true;
    localPath = ".local/share/vdirsyncer/tasks";
    defaultList = "Inbox";
  };
  sync.conflictResolution = "a wins";
};
```

Remote URL 通常是：

```text
https://cloud.example.com/remote.php/dav/calendars/USERNAME/
```

Nextcloud Tasks 使用同一个 CalDAV endpoint，但任务 list 是 VTODO collection。
先用 `caldav-calendar discover` 让 `vdirsyncer` 发现 collection，再同步。

### iCloud

推荐 settings：

```nix
settings = {
  provider = "icloud";
  username = "user@icloud.com";
  events = {
    enabled = true;
    localPath = ".local/share/vdirsyncer/calendars";
    defaultCalendar = "Home";
  };
  tasks.enabled = false;
  sync.conflictResolution = "a wins";
};
```

Remote URL：

```text
https://caldav.icloud.com/
```

使用 iCloud app-specific password，不要把密码写进 Nix 文件或 Nix store。

### Fastmail

推荐 settings：

```nix
settings = {
  provider = "fastmail";
  baseUrl = "https://caldav.fastmail.com";
  username = "user@example.com";
  events = {
    enabled = true;
    localPath = ".local/share/vdirsyncer/calendars";
    defaultCalendar = "Personal";
  };
  tasks = {
    enabled = true;
    localPath = ".local/share/vdirsyncer/tasks";
    defaultList = "Tasks";
  };
  sync.conflictResolution = "a wins";
};
```

Remote URL 通常是：

```text
https://caldav.fastmail.com/dav/calendars/user/EMAIL/
```

把 `EMAIL` 替换成账号邮箱。实际 collection 名称以 `discover` 结果为准。

### Generic CalDAV

用于 Radicale、Baikal、SOGo 或自建 CalDAV 服务：

```nix
settings = {
  provider = "generic-caldav";
  baseUrl = "https://dav.example.com/calendars/user/";
  username = "user";
  events.enabled = true;
  tasks.enabled = true;
  sync.conflictResolution = "a wins";
};
```

`baseUrl` 应该指向能让 `vdirsyncer discover` 找到 calendar/task collection 的
CalDAV collection 根路径。

### Google

Google Calendar events 可以用 `vdirsyncer` 的 `google_calendar` storage，但
Google Tasks 不是 CalDAV VTODO，所以这个 wrapper 的 `todoman` tasks flow 不适用于
Google Tasks。

推荐 settings：

```nix
settings = {
  provider = "google";
  username = "user@gmail.com";
  events = {
    enabled = true;
    localPath = ".local/share/vdirsyncer/calendars";
    defaultCalendar = "primary";
  };
  tasks.enabled = false;
  sync.conflictResolution = "a wins";
};
```

Google Calendar 通常需要 OAuth 配置。不要把 OAuth token 或 client secret 写入 Nix
store；如果需要 secret 文件，仍然放在 `/run/agenix/...` 或 `/run/secrets/...`。

## Config files

下面是实际客户端读取的配置文件模板。路径中的 `~` 在很多运行时里可能不是你想要的
OpenClaw state dir；生产配置里更推荐使用 host 渲染出的绝对 state 路径。

### vdirsyncer: events

`$CALDAV_CALENDAR_CONFIG_DIR/vdirsyncer/config`

```ini
[general]
status_path = "~/.local/share/vdirsyncer/status/"

[pair nextcloud_calendar]
a = "nextcloud_calendar_remote"
b = "nextcloud_calendar_local"
collections = ["from a", "from b"]
conflict_resolution = "a wins"

[storage nextcloud_calendar_remote]
type = "caldav"
url = "https://cloud.example.com/remote.php/dav/calendars/USERNAME/"
username = "USERNAME"
password.fetch = ["command", "sh", "-c", "cat \"$CALDAV_CALENDAR_AUTH_FILE\""]

[storage nextcloud_calendar_local]
type = "filesystem"
path = "~/.local/share/vdirsyncer/calendars/"
fileext = ".ics"
```

### vdirsyncer: tasks / VTODO

同一个 `vdirsyncer/config` 可以继续追加 task pair：

```ini
[pair nextcloud_tasks]
a = "nextcloud_tasks_remote"
b = "nextcloud_tasks_local"
collections = ["from a", "from b"]
conflict_resolution = "a wins"

[storage nextcloud_tasks_remote]
type = "caldav"
url = "https://cloud.example.com/remote.php/dav/calendars/USERNAME/"
username = "USERNAME"
password.fetch = ["command", "sh", "-c", "cat \"$CALDAV_CALENDAR_AUTH_FILE\""]

[storage nextcloud_tasks_local]
type = "filesystem"
path = "~/.local/share/vdirsyncer/tasks/"
fileext = ".ics"
```

### khal

`$CALDAV_CALENDAR_CONFIG_DIR/khal/config`

```ini
[calendars]
[[my_calendars]]
path = ~/.local/share/vdirsyncer/calendars/*
type = discover

[default]
default_calendar = Personal
highlight_event_days = True

[locale]
timeformat = %H:%M
dateformat = %Y-%m-%d
```

### todoman

`$CALDAV_CALENDAR_CONFIG_DIR/todoman/config.py`

```python
path = "~/.local/share/vdirsyncer/tasks/*"
default_list = "Inbox"
date_format = "%Y-%m-%d"
time_format = "%H:%M"
```

## 使用方式

日常流程通常是先同步，再查询或修改事件/任务，最后再次同步：

```sh
caldav-calendar sync
caldav-calendar list today 7d
caldav-calendar new tomorrow 14:00 15:00 "Meeting"
caldav-calendar todo list
caldav-calendar todo new --due tomorrow "Submit report"
caldav-calendar sync
```

日历事件使用 `khal`：

```sh
caldav-calendar discover
caldav-calendar sync
caldav-calendar list today 7d
caldav-calendar search "meeting"
caldav-calendar new 2026-01-15 10:00 11:00 "Meeting title"
caldav-calendar edit "Meeting title"
```

`caldav-calendar edit` 是交互式命令，需要 TTY。

VTODO 任务使用 `todoman`，适合 Nextcloud Tasks：

```sh
caldav-calendar todo list
caldav-calendar todo new "Buy milk"
caldav-calendar todo new --due tomorrow "Submit report"
caldav-calendar todo show 123
caldav-calendar todo edit 123
caldav-calendar todo done 123
```

事件和任务都通过 `vdirsyncer` 同步：

```sh
caldav-calendar sync
```

## 本地验证

```sh
nix build .#default
nix flake show --all-systems
nix eval --json --impure --expr '(let flake = builtins.getFlake (toString ./.); system = builtins.currentSystem; in flake.openclawPlugin system)'
./result/bin/caldav-calendar --help
```

## CI

这个仓库目前没有 Garnix 配置。如果之后加入 Garnix，至少应验证：

- `nix build .#default`
- `openclawPlugin` 输出可求值
