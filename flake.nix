{
  description = "Nix-native OpenClaw plugin wrapper for CalDAV calendar access";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];

      forAllSystems = nixpkgs.lib.genAttrs systems;

      pluginName = "caldav-calendar";
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.writeShellApplication {
            name = pluginName;

            runtimeInputs = [
              pkgs.coreutils
              pkgs.khal
              pkgs.todoman
              pkgs.vdirsyncer
            ];

            text = ''
              set -euo pipefail

              usage() {
                cat <<'USAGE'
caldav-calendar: OpenClaw CalDAV wrapper around vdirsyncer, khal, and todoman

Required environment:
  CALDAV_CALENDAR_AUTH_FILE       Path to the CalDAV/app-password secret file.

Config environment:
  CALDAV_CALENDAR_CONFIG_DIR      Plugin-specific config directory.
  XDG_CONFIG_HOME                 Standard XDG config directory.

One of CALDAV_CALENDAR_CONFIG_DIR or XDG_CONFIG_HOME must be set.

Commands:
  sync                           Run vdirsyncer sync.
  discover                       Run vdirsyncer discover.
  list [args...]                 Run khal list.
  search [args...]               Run khal search.
  new [args...]                  Run khal new.
  edit [args...]                 Run khal edit.
  todo list [args...]            Run todoman list.
  todo new [args...]             Run todoman new.
  todo edit [args...]            Run todoman edit.
  todo done [args...]            Run todoman done.
  todo show [args...]            Run todoman show.
  vdirsyncer [args...]           Run vdirsyncer directly.
  khal [args...]                 Run khal directly.
  todoman [args...]              Run todoman directly.
USAGE
              }

              if [ "''${1:-}" = "--help" ] || [ "''${1:-}" = "-h" ]; then
                usage
                exit 0
              fi

              if [ -z "''${CALDAV_CALENDAR_AUTH_FILE:-}" ]; then
                echo "caldav-calendar: CALDAV_CALENDAR_AUTH_FILE is required" >&2
                exit 64
              fi

              if [ ! -r "$CALDAV_CALENDAR_AUTH_FILE" ]; then
                echo "caldav-calendar: CALDAV_CALENDAR_AUTH_FILE is not readable: $CALDAV_CALENDAR_AUTH_FILE" >&2
                exit 66
              fi

              if [ -n "''${CALDAV_CALENDAR_CONFIG_DIR:-}" ]; then
                export XDG_CONFIG_HOME="$CALDAV_CALENDAR_CONFIG_DIR"
              elif [ -z "''${XDG_CONFIG_HOME:-}" ]; then
                echo "caldav-calendar: set CALDAV_CALENDAR_CONFIG_DIR or XDG_CONFIG_HOME" >&2
                exit 64
              fi

              if [ "$#" -eq 0 ]; then
                usage >&2
                exit 64
              fi

              command="$1"
              shift

              case "$command" in
                sync)
                  exec vdirsyncer sync "$@"
                  ;;
                discover)
                  exec vdirsyncer discover "$@"
                  ;;
                list|search|new|edit)
                  exec khal "$command" "$@"
                  ;;
                todo)
                  if [ "$#" -eq 0 ]; then
                    echo "caldav-calendar: todo requires a todoman subcommand" >&2
                    usage >&2
                    exit 64
                  fi
                  exec todo "$@"
                  ;;
                vdirsyncer)
                  exec vdirsyncer "$@"
                  ;;
                khal)
                  exec khal "$@"
                  ;;
                todoman)
                  exec todo "$@"
                  ;;
                *)
                  echo "caldav-calendar: unknown command: $command" >&2
                  usage >&2
                  exit 64
                  ;;
              esac
            '';
          };
        });

      openclawPlugin = system: {
        name = pluginName;
        skills = [
          ./.
        ];
        packages = [
          self.packages.${system}.default
        ];
        needs = {
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
        };
      };

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            packages = [
              self.packages.${system}.default
              pkgs.khal
              pkgs.todoman
              pkgs.vdirsyncer
            ];
          };
        });
    };
}
