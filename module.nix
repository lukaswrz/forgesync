self:
{
  lib,
  pkgs,
  utils,
  config,
  ...
}:
let
  cfg = config.services.forgesync;
  inherit (lib) types;
  inherit (utils.systemdUtils.unitOptions) unitOption;
in
{
  options.services.forgesync = {
    enable = lib.mkEnableOption "Forgesync";

    package = lib.mkPackageOption self.packages.${pkgs.system} "default" { };

    jobs = lib.mkOption {
      description = ''
        Synchronization jobs to run.
      '';
      default = { };
      type = types.attrsOf (
        types.submodule {
          options = {
            source = lib.mkOption {
              example = "https://codeberg.org/api/v1";
              description = ''
                The base URL of the source instance.
              '';
              type = types.str;
            };

            target = lib.mkOption {
              example = "github";
              description = ''
                The destination, e.g. github, codeberg or forgejo=https://forgejo.example.com/api/v1.
              '';
              type = types.str;
            };

            settings = lib.mkOption {
              default = { };
              example = {
                remirror = true;
                description-template = "{description} (Mirror of {url})";
                mirror-interval = "8h0m0s";
                log = "INFO";
              };
              description = ''
                Settings for this Forgesync job.
              '';
              type =
                let
                  simples = [
                    types.bool
                    types.str
                    types.int
                    types.float
                  ];
                in
                types.attrsOf (
                  types.oneOf (
                    simples
                    ++ [
                      (types.listOf (types.oneOf simples))
                    ]
                  )
                );
            };

            secretFile = lib.mkOption {
              type = types.path;
              description = ''
                The EnvironmentFile for the required tokens: `SOURCE_TOKEN`, `TARGET_TOKEN` and `MIRROR_TOKEN`.
              '';
            };

            timerConfig = lib.mkOption {
              type = types.nullOr (types.attrsOf unitOption);
              default = {
                OnCalendar = "daily";
                Persistent = true;
              };
              description = ''
                When to run the job.
              '';
            };
          };
        }
      );
    };
  };

  config = lib.mkIf cfg.enable {
    systemd = lib.mkMerge (
      lib.mapAttrsToList (
        jobName: job:
        let
          unitName = "forgesync-job-${jobName}";
          description = "Forgesync job ${jobName}";
        in
        {
          timers.${unitName} = {
            wantedBy = [ "timers.target" ];
            inherit description;
            inherit (job) timerConfig;
          };

          services.${unitName} = {
            after = [ "network.target" ];
            inherit description;

            serviceConfig = {
              Type = "oneshot";

              DynamicUser = true;

              ExecStart =
                let
                  args = [
                    (lib.getExe cfg.package)
                  ]
                  ++ (lib.cli.toCommandLineGNU { isLong = _: true; } job.settings)
                  ++ [
                    "--"
                    job.source
                    job.target
                  ];
                in
                utils.escapeSystemdExecArgs args;

              EnvironmentFile = job.secretFile;

              NoNewPrivileges = true;
              PrivateDevices = true;
              ProtectKernelTunables = true;
              ProtectKernelModules = true;
              ProtectControlGroups = true;
              MemoryDenyWriteExecute = true;
              LockPersonality = true;
              RestrictAddressFamilies = [
                "AF_INET"
                "AF_INET6"
              ];
              DevicePolicy = "closed";
              RestrictNamespaces = true;
              RestrictRealtime = true;
              RestrictSUIDSGID = true;
            };
          };
        }
      ) cfg.jobs
    );
  };
}
