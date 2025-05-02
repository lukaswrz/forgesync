from collections.abc import Iterable
from dataclasses import dataclass, fields
from logging import Logger
from typing import Self
from pyforgejo import PushMirror, PyforgejoApi
from .sync import SyncedRepository


class MirrorError(RuntimeError):
    pass


@dataclass
class PushMirrorConfig:
    interval: str | None = None
    remirror: bool | None = None
    immediate: bool | None = None
    sync_on_commit: bool | None = None

    def overlay(self: Self, other: Self) -> Self:
        result = type(self)()
        for f in fields(self):
            value = (  # pyright: ignore[reportAny]
                getattr(other, f.name)
                if getattr(other, f.name) is not None
                else getattr(self, f.name)
            )
            setattr(result, f.name, value)
        return result

    def is_valid(self: Self) -> bool:
        for f in fields(self):
            if getattr(self, f.name) is None:
                return False

        return True


class PushMirrorer:
    client: PyforgejoApi
    config: PushMirrorConfig
    mirror_token: str
    logger: Logger

    def __init__(
        self: Self,
        client: PyforgejoApi,
        config: PushMirrorConfig,
        mirror_token: str,
        logger: Logger,
    ) -> None:
        self.client = client
        self.config = config
        self.mirror_token = mirror_token
        self.logger = logger

    def get_matching_mirrors(
        self: Self,
        repos: Iterable[SyncedRepository],
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
        config: PushMirrorConfig,
    ) -> PushMirror | None:
        self.logger.info(
            f"Setting up mirrors for {repo.orig_owner}/{repo.name} to {repo.new_owner}/{repo.name} at {repo.clone_url}"
        )

        if not repo.needs_mirror:
            self.logger.info("Skipping mirrors")
            return None

        final_config = self.config.overlay(config)

        if not final_config.is_valid():
            raise MirrorError("config is invalid")

        def add_push_mirror() -> PushMirror:
            push_mirror = self.client.repository.repo_add_push_mirror(
                owner=repo.orig_owner,
                repo=repo.name,
                interval=final_config.interval,
                remote_address=repo.clone_url,
                remote_username=repo.new_owner,
                remote_password=self.mirror_token,
                sync_on_commit=final_config.sync_on_commit,
                use_ssh=False,
            )

            self.logger.info("Created push mirror")

            return push_mirror

        new_push_mirror: PushMirror | None = None

        for push_mirror in existing_push_mirrors:
            if push_mirror.remote_name is None:
                raise MirrorError("missing remote name")

            if final_config.remirror:
                self.client.repository.repo_delete_push_mirror(
                    owner=repo.orig_owner,
                    repo=repo.name,
                    name=push_mirror.remote_name,
                )

                self.logger.info("Removed old push mirror")

                new_push_mirror = add_push_mirror()

        if not existing_push_mirrors:
            new_push_mirror = add_push_mirror()

        if new_push_mirror is not None:
            if final_config.immediate:
                self.client.repository.repo_push_mirror_sync(
                    owner=repo.orig_owner,
                    repo=repo.name,
                )

        self.logger.info("Finished mirrors")

        return new_push_mirror

    def mirror_repos(
        self: Self,
        synced_repos: Iterable[SyncedRepository],
        config: PushMirrorConfig,
    ) -> list[PushMirror]:
        new_push_mirrors: list[PushMirror] = []

        matching_mirrors = self.get_matching_mirrors(repos=synced_repos)

        for synced_repo in synced_repos:
            new_push_mirror = self.mirror_repo(
                repo=synced_repo,
                existing_push_mirrors=matching_mirrors[synced_repo.name],
                config=config,
            )

            if new_push_mirror is not None:
                new_push_mirrors.append(new_push_mirror)

        return new_push_mirrors
