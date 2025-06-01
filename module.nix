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
            settings = lib.mkOption {
              default = { };
              example = {
                from-instance = "https://codeberg.org/api/v1";
                to = "github";
                to-instance = "https://api.github.com";
                remirror = true;
                description-template = "{description} (Mirror of {url})";
                mirror-interval = "8h0m0s";
                immediate = true;
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
                The EnvironmentFile for secrets required for Forgesync: `FROM_TOKEN`, `TO_TOKEN` and `MIRROR_TOKEN`.
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

            inhibit = lib.mkOption {
              default = [ ];
              type = types.listOf (types.strMatching "^[^:]+$");
              example = [
                "sleep"
              ];
              description = ''
                Run the Forgesync process with an inhibition lock taken;
                see {manpage}`systemd-inhibit(1)` for a list of possible operations.
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
                  inhibitArgs = [
                    (lib.getExe' config.systemd.package "systemd-inhibit")
                    "--mode"
                    "block"
                    "--who"
                    description
                    "--what"
                    (lib.concatStringsSep ":" job.inhibit)
                    "--why"
                    "Scheduled Forgesync job ${jobName}"
                    "--"
                  ];

                  args =
                    (lib.optionals (job.inhibit != [ ]) inhibitArgs)
                    ++ [ (lib.getExe cfg.package) ]
                    ++ (lib.cli.toGNUCommandLine { mkOptionName = k: "--${k}"; } job.settings);
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
