from dataclasses import dataclass
from logging import Logger
from typing import Self
from enum import StrEnum
from pyforgejo import PushMirror, PyforgejoApi
from .sync import SyncedRepository


class MirrorError(RuntimeError):
    pass


class Remirror(StrEnum):
    NO = "no"
    YES = "yes"
    PURGE = "purge"


@dataclass
class PushMirrorConfig:
    interval: str
    remirror: Remirror
    immediate: bool
    on_commit: bool


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

        push_mirrors_to_delete: list[PushMirror] = []

        make_mirror = False

        match config.remirror:
            case Remirror.PURGE:
                push_mirrors_to_delete = self.client.repository.repo_list_push_mirrors(
                    owner=synced_repo.orig_owner,
                    repo=synced_repo.name,
                )
                make_mirror = True
            case Remirror.YES:
                push_mirrors_to_delete = self.get_matching_mirrors(
                    synced_repo=synced_repo
                )
                make_mirror = True
            case Remirror.NO:
                matching_mirrors = self.get_matching_mirrors(synced_repo=synced_repo)
                if not matching_mirrors:
                    make_mirror = True

        for push_mirror in push_mirrors_to_delete:
            if push_mirror.remote_name is None:
                raise MirrorError("Missing remote name")

            self.client.repository.repo_delete_push_mirror(
                owner=synced_repo.orig_owner,
                repo=synced_repo.name,
                name=push_mirror.remote_name,
            )

            if push_mirror.remote_address is not None:
                self.logger.info(
                    "Removed old push mirror to %s", push_mirror.remote_address
                )

        if make_mirror:
            new_push_mirror = self.add_push_mirror(
                synced_repo=synced_repo,
                config=config,
            )

        if new_push_mirror is not None and config.immediate:
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
            sync_on_commit=config.on_commit,
            use_ssh=False,
        )

        self.logger.info("Created push mirror")

        return push_mirror
