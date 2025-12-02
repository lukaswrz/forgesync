from dataclasses import dataclass
from logging import Logger
from typing import Self
from pyforgejo import PushMirror, PyforgejoApi
from .sync import SyncedRepository


class MirrorError(RuntimeError):
    pass


@dataclass
class PushMirrorConfig:
    interval: str
    remirror: bool
    immediate: bool
    sync_on_push: bool


class PushMirrorer:
    client: PyforgejoApi
    mirror_token: str
    logger: Logger

    def __init__(
        self: Self,
        client: PyforgejoApi,
        mirror_token: str,
        logger: Logger,
    ) -> None:
        self.client = client
        self.mirror_token = mirror_token
        self.logger = logger

    def mirror_repo(
        self: Self,
        synced_repo: SyncedRepository,
        config: PushMirrorConfig,
    ) -> PushMirror | None:
        self.logger.info(
            "Setting up mirroring for %s to %s at %s",
            f"{synced_repo.orig_owner}/{synced_repo.name}",
            f"{synced_repo.new_owner}/{synced_repo.name}",
            synced_repo.clone_url,
        )

        new_push_mirror: PushMirror | None = None

        existing_push_mirrors = self.get_matching_mirrors(synced_repo=synced_repo)

        for push_mirror in existing_push_mirrors:
            if push_mirror.remote_name is None:
                raise MirrorError("Missing remote name")

            if config.remirror:
                self.client.repository.repo_delete_push_mirror(
                    owner=synced_repo.orig_owner,
                    repo=synced_repo.name,
                    name=push_mirror.remote_name,
                )

                self.logger.info("Removed old push mirror")

                new_push_mirror = self.add_push_mirror(
                    synced_repo=synced_repo, config=config
                )

        if not existing_push_mirrors:
            new_push_mirror = self.add_push_mirror(
                synced_repo=synced_repo, config=config
            )

        if new_push_mirror is not None:
            if config.immediate:
                self.client.repository.repo_push_mirror_sync(
                    owner=synced_repo.orig_owner,
                    repo=synced_repo.name,
                )
                self.logger.info("Triggered push mirror")

        self.logger.info("Finished mirror setup for %s", synced_repo.name)

        return new_push_mirror

    def get_matching_mirrors(
        self: Self,
        synced_repo: SyncedRepository,
    ) -> list[PushMirror]:
        repo_mirrors: list[PushMirror] = []

        push_mirrors = self.client.repository.repo_list_push_mirrors(
            owner=synced_repo.orig_owner,
            repo=synced_repo.name,
        )

        for push_mirror in push_mirrors:
            if push_mirror.remote_address == synced_repo.clone_url:
                repo_mirrors.append(push_mirror)

        return repo_mirrors

    def add_push_mirror(
        self: Self, synced_repo: SyncedRepository, config: PushMirrorConfig
    ) -> PushMirror:
        push_mirror = self.client.repository.repo_add_push_mirror(
            owner=synced_repo.orig_owner,
            repo=synced_repo.name,
            interval=config.interval,
            remote_address=synced_repo.clone_url,
            remote_username=synced_repo.new_owner,
            remote_password=self.mirror_token,
            sync_on_commit=config.sync_on_push,
            use_ssh=False,
        )

        self.logger.info("Created push mirror")

        return push_mirror
