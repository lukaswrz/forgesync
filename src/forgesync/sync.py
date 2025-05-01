from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Self
from pyforgejo import Repository as ForgejoRepository


class Destination(StrEnum):
    GITHUB = "github"
    FORGEJO = "forgejo"


@dataclass
class SyncedRepository:
    new_owner: str
    orig_owner: str
    name: str
    clone_url: str
    destination: Destination
    needs_mirror: bool


class Syncer(ABC):
    @abstractmethod
    def sync(
        self: Self, from_repo: ForgejoRepository, description: str
    ) -> SyncedRepository:
        pass


class SyncError(RuntimeError):
    pass
