from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self
from pyforgejo import Repository as ForgejoRepository


@dataclass
class SyncedRepository:
    new_owner: str
    orig_owner: str
    name: str
    clone_url: str


class Syncer(ABC):
    @abstractmethod
    def sync(
        self: Self, from_repo: ForgejoRepository, description: str
    ) -> SyncedRepository:
        pass


class SyncError(RuntimeError):
    pass
