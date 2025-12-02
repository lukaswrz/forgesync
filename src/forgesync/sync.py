from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from .source import SourceRepository
from .platform import Platform


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
    platform: Platform
    mirrored: bool


class Syncer(ABC):
    @abstractmethod
    def sync(
        self: Self,
        source_repo: SourceRepository,
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
