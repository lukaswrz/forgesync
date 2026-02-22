# Forgesync

Forgesync automatically synchronizes all your Forgejo repositories to GitHub or any Forgejo instance (e.g. Codeberg).

While Forgejo supports periodic Git mirroring out of the box, it doesn't support syncing repository metadata, and setting these mirrors up manually can be a lot of work. Forgesync resolves this by:

- Automatically creating target repositories
- Syncing repository metadata (descriptions, topics, etc.)
- Enabling or disabling features like issues or pull requests on the destination
- Setting up mirrors directly within the source Forgejo instance
- Filtering out forks, mirrors, and private repositories

## ⬇️ Getting Forgesync

Forgesync is currently available as:

- ❄️ A Nix package and NixOS module provided as part of this Nix flake. See [usage via Nix](#usage-via-nix).
- 📦 A container. See [container usage](#container-usage).

## 💻 CLI usage

Here's how you would synchronize your Codeberg repositories to GitHub:

```bash
# Token for gathering source repository metadata and setting up mirrors.
export SOURCE_TOKEN=my_codeberg_token

# Token for creating and synchronizing repositories at the destination of your choosing.
export TARGET_TOKEN=my_github_token

# Token used within Forgejo for Git mirroring.
export MIRROR_TOKEN=my_github_mirror_token

# Run the sync:
forgesync https://codeberg.org/api/v1 github \
  --remirror \
  --feature issues \
  --feature pull-requests \
  --on-commit \
  --mirror-interval 8h0m0s \
  --exclude myrepo
```

Run `forgesync --help` to see what the example options do, and which ones you can add on top.

Check [required token scopes](#required-token-scopes) to find out what you need to specify when creating tokens.

## ⚠️ Back up your destination repositories!

> [!WARNING]
> Before running Forgesync, make sure you have backed up your repositories from the destination if you have any and plan to keep them. Forgesync will overwrite any repositories at the destination that share the same names as those on the source Forgejo instance. For more information, see [syncing by name](#syncing-by-name).

## Usage via Nix

To use Forgesync in an ephemeral shell, run this:

```bash
nix shell git+https://hack.moontide.ink/m64/forgesync.git
```

### NixOS module

First, add the flake input:

```nix
{
  inputs = {
    # ...

    forgesync.url = "git+https://hack.moontide.ink/m64/forgesync.git";
  };

  # ...
}
```

Then, configure Forgesync via the module:

```nix
{ inputs, ... }:
{
  # Either pass inputs via specialArgs and import the module here, or import it
  # via lib.nixosSystem.
  imports = [
    inputs.forgesync.nixosModules.default
  ];

  services.forgesync = {
    enable = true;
    jobs.github = {
      source = "https://codeberg.org/api/v1";
      target = "github";

      settings = {
        remirror = true;
        feature = [
          "issues"
          "pull-requests"
        ];
        sync-on-push = true;
        mirror-interval = "0h0m0s";
      };

      # Use whichever secret management you prefer, e.g. agenix.
      secretFile = "/path/to/secrets";

      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
      };
    };
  };
}
```

Take a look at the [module source](module.nix) for more details.

## Container usage

Alternatively, Forgesync can also be run in a container with Podman, Docker, Kubernetes, etc.

### Building the container

You can build the container with your favorite image building tool (Podman, Buildah, Docker, etc.).

Example with Podman:

```bash
podman build -t localhost/forgesync .
```

### Running the container

The `SOURCE_TOKEN`, `TARGET_TOKEN`, and `MIRROR_TOKEN` tokens must be passed to the container at runtime (`-e` for Podman/Docker, or as a Kubernetes secret).

Example with Podman:

```bash
podman run --rm -it \
  -e SOURCE_TOKEN=my_forgejo_token \
  -e TARGET_TOKEN=my_github_token \
  -e MIRROR_TOKEN=my_github_mirror_token \
  localhost/forgesync https://codeberg.org/api/v1 github \
    --remirror \
    --feature issues \
    --feature pull-requests \
    --on-commit \
    --mirror-interval 8h0m0s \
    --exclude myrepo
```

## Required token scopes

### Source token (Forgejo)

Your `SOURCE_TOKEN` must support:

- **Repository:** read + write
- **User data:** read + write

### Destination token (GitHub or Forgejo)

Your `TARGET_TOKEN` must support:

- **Repository:** read + write
- **User data:** read + write

### Mirror token

The `MIRROR_TOKEN` only needs to support:

- **Repository:** read + write

For GitHub fine-grained personal access tokens, this means that you will need to check "all repositories" under repository access and enable read and write permissions on repository contents.

## 🪞 Mirror management

### Re-mirroring

Forgejo stores a few bits of information as part of a push mirror, including:

- The mirror token
- The mirror interval
- The "on commit" toggle

There is currently no way to diff these fields via the Forgejo API, so if you want to change any of them, you need to use re-mirroring to recreate the push mirror with the desired configuration.

### Syncing by name

Forgesync synchronizes repositories by their names, so a typical setup would look like this:

- forgejo-user/repo-a → github-user/repo-a
- forgejo-user/repo-b → github-user/repo-b
- forgejo-user/repo-c → github-user/repo-c

If you rename repo-a to repo-a-ng, the old push mirror will remain in Forgejo, and it will keep mirroring to github-user/repo-a as well as github-user/repo-a-ng.
Forgesync does not track renames or maintain any state about repository history, so it won't detect that the destination no longer matches the source.
As a workaround, you can pass `--purge` to wipe all existing push mirrors from the source repository before creating any new ones.
