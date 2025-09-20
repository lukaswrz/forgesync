from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Self
from pyforgejo import Repository as ForgejoRepository


class Destination(StrEnum):
    GITHUB = "github"
    FORGEJO = "forgejo"


class RepositoryFeature(StrEnum):
    ACTIONS = "actions"
    DISCUSSIONS = "discussions"
    ISSUES = "issues"
    PACKAGES = "packages"
    PROJECTS = "projects"
    PULL_REQUESTS = "pull-requests"
    RELEASES = "releases"
    WIKI = "wiki"


@dataclass
class SyncedRepository:
    new_owner: str
    orig_owner: str
    name: str
    clone_url: str
    destination: Destination
    mirrored: bool


class Syncer(ABC):
    @abstractmethod
    def sync(
        self: Self,
        from_repo: ForgejoRepository,
        description: str,
        topics: list[str],
    ) -> SyncedRepository:
        pass


class SyncError(RuntimeError):
    pass


class RepositoryError(SyncError):
    pass


class RepositorySkippedError(RepositoryError):
    pass
