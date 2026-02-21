{
  description = "Automatically mirror all your Forgejo repositories to GitHub or any Forgejo instance";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;

      systems = nixpkgs.lib.systems.flakeExposed;

      forAllSystems =
        f:
        lib.genAttrs systems (
          system:
          f (
            let
              pkgs = nixpkgs.legacyPackages.${system};
              python = pkgs.python313;
            in
            {
              inherit system pkgs python;
              pythonSet =
                (pkgs.callPackage pyproject-nix.build.packages {
                  inherit python;
                }).overrideScope
                  (
                    lib.composeManyExtensions [
                      pyproject-build-systems.overlays.wheel
                      overlay
                    ]
                  );
            }
          )
        );

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };
    in
    {
      devShells = forAllSystems (
        { pkgs, python, ... }:
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.libffi
              pkgs.uv

              # Formatters
              pkgs.treefmt
              pkgs.nixfmt
              pkgs.prettier
              pkgs.taplo
              pkgs.ruff
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON_DOWNLOADS = "never";
              UV_PYTHON = python.interpreter;
            }
            // lib.optionalAttrs pkgs.stdenv.isLinux {
              LD_LIBRARY_PATH = lib.makeLibraryPath pkgs.pythonManylinuxPackages.manylinux1;
            };
            shellHook = ''
              unset PYTHONPATH
            '';
          };
        }
      );

      packages = forAllSystems (
        {
          system,
          pkgs,
          pythonSet,
          ...
        }:
        {
          venv = pythonSet.mkVirtualEnv "forgesync" workspace.deps.default;
          default =
            let
              inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;
            in
            mkApplication {
              venv = self.packages.${system}.venv;
              package = pythonSet.forgesync;
            };
        }
      );

      nixosModules.default = import ./module.nix self;

      formatter = forAllSystems ({ pkgs, ... }: pkgs.treefmt);
    };
}
