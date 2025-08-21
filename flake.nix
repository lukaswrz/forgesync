{
  description = "forgesync";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    treefmt = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
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
      flake-parts,
      hooks,
      treefmt,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      ...
    }@inputs:
    let
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };
    in
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        hooks.flakeModule
        treefmt.flakeModule
      ];

      systems = nixpkgs.lib.systems.flakeExposed;

      perSystem =
        {
          config,
          pkgs,
          inputs',
          lib,
          ...
        }:
        let
          python = pkgs.python313;
          pythonSet =
            (pkgs.callPackage pyproject-nix.build.packages {
              inherit python;
            }).overrideScope
              (
                lib.composeManyExtensions [
                  pyproject-build-systems.overlays.default
                  overlay
                ]
              );
        in
        {
          treefmt = {
            projectRootFile = "flake.nix";

            programs.nixfmt = {
              enable = true;
              package = pkgs.nixfmt-rfc-style;
            };

            programs.ruff-check.enable = true;
            programs.ruff-format.enable = true;
          };

          pre-commit.settings.hooks = {
            treefmt.enable = true;
          };

          devShells.default = pkgs.mkShell {
            packages = [
              python
              pkgs.libffi
              pkgs.uv
            ];
            env = {
              UV_PYTHON_DOWNLOADS = "never";
              UV_PYTHON = python.interpreter;
            }
            // lib.optionalAttrs pkgs.stdenv.isLinux {
              LD_LIBRARY_PATH = lib.makeLibraryPath pkgs.pythonManylinuxPackages.manylinux1;
            };
            shellHook = ''
              ${config.pre-commit.installationScript}
              unset PYTHONPATH
            '';
          };

          packages.default = pythonSet.mkVirtualEnv "forgesync" workspace.deps.default;
        };

      flake.nixosModules.default = import ./module.nix self;
    };
}
