from collections.abc import Iterable
from logging import Logger
from typing import Self
from pyforgejo import PushMirror, PyforgejoApi
from .sync import SyncedRepository


class MirrorError(RuntimeError):
    pass


class PushMirrorer:
    client: PyforgejoApi
    logger: Logger

    def __init__(
        self: Self,
        client: PyforgejoApi,
        logger: Logger,
    ) -> None:
        self.client = client
        self.logger = logger

    def get_matching_mirrors(
        self: Self, repos: Iterable[SyncedRepository]
    ) -> dict[str, list[PushMirror]]:
        repo_mirrors: dict[str, list[PushMirror]] = {}

        for repo in repos:
            if repo.name in repo_mirrors:
                raise MirrorError("duplicate repositories")

            repo_mirrors[repo.name] = []

            push_mirrors = self.client.repository.repo_list_push_mirrors(
                owner=repo.orig_owner,
                repo=repo.name,
            )

            for push_mirror in push_mirrors:
                if push_mirror.remote_address == repo.clone_url:
                    repo_mirrors[repo.name].append(push_mirror)

        return repo_mirrors

    def mirror_repo(
        self: Self,
        repo: SyncedRepository,
        existing_push_mirrors: list[PushMirror],
        interval: str,
        remirror: bool,
        immediate: bool,
        sync_on_commit: bool,
        mirror_token: str,
    ) -> PushMirror | None:
        def add_push_mirror() -> PushMirror:
            push_mirror = self.client.repository.repo_add_push_mirror(
                owner=repo.orig_owner,
                repo=repo.name,
                interval=interval,
                remote_address=repo.clone_url,
                remote_username=repo.new_owner,
                remote_password=mirror_token,
                sync_on_commit=sync_on_commit,
                use_ssh=False,
            )

            self.logger.info(
                f"Created push mirror for {repo.orig_owner}/{repo.name} to {repo.new_owner}/{repo.name} at {repo.clone_url}"
            )

            return push_mirror

        new_push_mirror: PushMirror | None = None

        for push_mirror in existing_push_mirrors:
            if push_mirror.remote_name is None:
                raise MirrorError("missing remote name")

            if remirror:
                self.client.repository.repo_delete_push_mirror(
                    owner=repo.orig_owner,
                    repo=repo.name,
                    name=push_mirror.remote_name,
                )

                self.logger.info(
                    f"Removed old push mirror for {repo.orig_owner}/{repo.name} to {repo.new_owner}/{repo.name} at {repo.clone_url}"
                )

                new_push_mirror = add_push_mirror()

        if not existing_push_mirrors:
            new_push_mirror = add_push_mirror()

        if new_push_mirror is not None:
            if immediate:
                self.client.repository.repo_push_mirror_sync(
                    owner=repo.orig_owner,
                    repo=repo.name,
                )

        return new_push_mirror

    def mirror_repos(
        self: Self,
        synced_repos: Iterable[SyncedRepository],
        interval: str,
        remirror: bool,
        immediate: bool,
        sync_on_commit: bool,
        mirror_token: str,
    ) -> list[PushMirror]:
        new_push_mirrors: list[PushMirror] = []

        matching_mirrors = self.get_matching_mirrors(repos=synced_repos)

        for synced_repo in synced_repos:
            new_push_mirror = self.mirror_repo(
                repo=synced_repo,
                existing_push_mirrors=matching_mirrors[synced_repo.name],
                interval=interval,
                remirror=remirror,
                immediate=immediate,
                sync_on_commit=sync_on_commit,
                mirror_token=mirror_token,
            )

            if new_push_mirror is not None:
                new_push_mirrors.append(new_push_mirror)

        return new_push_mirrors
