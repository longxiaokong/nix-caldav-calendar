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
          python = pkgs.python3.override {
            packageOverrides = final: prev: {
              niquests = prev.niquests.overridePythonAttrs (_old: {
                doCheck = false;
              });
              caldav = prev.caldav.overridePythonAttrs (_old: {
                doCheck = false;
              });
            };
          };
          pythonEnv = python.withPackages (ps: [
            ps.caldav
            ps.icalendar
          ]);
        in
        {
          default = pkgs.writeShellApplication {
            name = pluginName;

            runtimeInputs = [
              pkgs.coreutils
              pkgs.khal
              pkgs.todoman
              pkgs.vdirsyncer
              pythonEnv
            ];

            text = ''
              export PYTHONPATH="${./.}''${PYTHONPATH:+:$PYTHONPATH}"
              exec python -m caldav_calendar.cli "$@"
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
        };
      };

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.override {
            packageOverrides = final: prev: {
              niquests = prev.niquests.overridePythonAttrs (_old: {
                doCheck = false;
              });
              caldav = prev.caldav.overridePythonAttrs (_old: {
                doCheck = false;
              });
            };
          };
          pythonEnv = python.withPackages (ps: [
            ps.caldav
            ps.icalendar
            ps.pytest
          ]);
        in
        {
          default = pkgs.mkShell {
            packages = [
              self.packages.${system}.default
              pkgs.khal
              pkgs.todoman
              pkgs.vdirsyncer
              pythonEnv
            ];
          };
        });
    };
}
