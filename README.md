# Forgesync

Forgesync automatically synchronizes all your Forgejo repositories to GitHub and any Forgejo instance such as Codeberg.

While Forgejo supports periodic Git mirroring out of the box, setting these mirrors up can be a lot of manual work. Forgesync resolves this by:

* Automatically creating target repositories  
* Syncing repository metadata (descriptions, topics, etc.)  
* Disabling issues and pull requests on the destination  
* Setting up mirrors directly within the source Forgejo instance  
* Filtering out forks, mirrors, and private repositories (only syncing what matters)

## 💻 CLI usage

Here's how you would synchronize your Codeberg repositories to GitHub:

```bash
# Token for gathering source repository metadata and setting up mirrors.
export FROM_TOKEN=my_forgejo_token

# Token for creating and synchronizing repositories at the destination of your choosing.
export TO_TOKEN=my_github_token

# Token used within Forgejo for Git mirroring.
export MIRROR_TOKEN=my_github_mirror_token

# Run the sync:
forgesync \
  --from-instance https://codeberg.org/api/v1 \
  --to github \
  --to-instance https://api.github.com \
  --remirror \
  --mirror-interval 8h0m0s \
  --immediate \
  --log INFO
```

## ❄️ Usage as a NixOS module

Not yet.

## ⚠️ Be careful with your data!

> [!WARNING]
> Before running Forgesync, ensure you have backups. The tool will overwrite any repositories at the destination that share the same names as those on the source Forgejo instance. Proceed with caution.

## 🔑 Required token scopes

### Source (Forgejo)
Your `FROM_TOKEN` must have:
* **Repository:** read + write
* **User data:** read

### Destination (GitHub or Forgejo)
Your `TO_TOKEN` must have:
* **Repository:** read + write  
* **User data:** read

### Mirror Token
The mirror token only needs:
- **Repository:** read + write
