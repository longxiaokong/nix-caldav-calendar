# nix-caldav-calendar

这是 CalDAV calendar and tasks tools 的 Nix-native OpenClaw wrapper。

这个仓库不保存任何日历凭据，也不实现新的 CalDAV 协议客户端。插件包会通过 Nix
提供一个稳定的 `caldav-calendar` CLI，并把 `vdirsyncer`、`khal` 和 `todoman` 放进
OpenClaw runtime PATH；本仓库保存 Nix 契约、skill 文档和少量 wrapper 文档。

## 插件信息

- 插件 id：`caldav-calendar`
- Runtime CLI：`caldav-calendar`
- 底层工具：`vdirsyncer`、`khal`、`todoman`
- 作用：为 OpenClaw 提供 CalDAV 日历事件和 VTODO 任务的同步、查询、创建和编辑能力。

## Nix 契约

这个 flake 导出：

- `packages.${system}.default`：包含 `caldav-calendar` wrapper CLI 的包。
- `openclawPlugin`：nix-openclaw 使用的插件契约，包含 `name`、`skills`、
  `packages` 和 `needs`。这个输出是 `system: { ... }` 形式，适合纯 flake 求值。
- `devShells.${system}.default`：带有 wrapper、`vdirsyncer`、`khal` 和 `todoman` 的本地开发环境。

`openclawPlugin.name` 是 `caldav-calendar`。

## 在 nix-openclaw 中启用

这个插件是 OpenClaw native CLI/skill plugin。Nix 会把 `caldav-calendar` 放到
OpenClaw runtime PATH，skill 会指导 AI 通过这个命令操作日历事件和 VTODO 任务。

推荐把这个仓库作为 `customPlugins` 加到 nix-openclaw 配置里，并显式传入 env：

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
            provider = "icloud";
            username = "user@example.com";
            calendar = "Home";
            syncDays = 30;
            enabled = true;
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

## Runtime env

这个 wrapper 故意 fail-fast，不使用隐式 `~/.config` 默认值。需要配置：

- `CALDAV_CALENDAR_AUTH_FILE`：CalDAV 密码或 app password 文件路径。
- `CALDAV_CALENDAR_CONFIG_DIR`：包含 `vdirsyncer/config`、`khal/config` 和
  `todoman/config.py` 的配置目录。

凭据不应该提交到仓库。生产环境推荐使用 secret manager 暴露的机器本地路径，例如：

- `/run/agenix/caldav-calendar-auth`
- `/run/secrets/caldav-calendar-auth`

`vdirsyncer` 配置里可以这样读取凭据：

```ini
password.fetch = ["command", "sh", "-c", "cat \"$CALDAV_CALENDAR_AUTH_FILE\""]
```

## State dirs

`openclawPlugin.needs.stateDirs` 声明：

- `.config/caldav-calendar`
- `.local/share/vdirsyncer`
- `.local/share/khal`
- `.local/share/todoman`

第一项用于 nix-openclaw 渲染 typed `config.settings`。后几项用于同步状态、本地
`.ics` 文件、`khal` cache 和 `todoman` 数据。

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
