from collections.abc import Generator, Iterable
from dataclasses import dataclass
from logging import Logger
from re import fullmatch

from .source import SourceRepository


@dataclass
class RepositoryFilter:
    includes: list[str]
    excludes: list[str]
    logger: Logger

    @staticmethod
    def matches(name: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if fullmatch(pattern, name) is not None:
                return True

        return False

    def filter(
        self, source_repos: Iterable[SourceRepository]
    ) -> Generator[SourceRepository]:
        for source_repo in source_repos:
            if (
                source_repo.real.fork
                or source_repo.real.mirror
                or source_repo.real.private
            ):
                continue

            if self.includes != [] and not self.matches(
                source_repo.name, self.includes
            ):
                self.logger.info(
                    "Repository %s does not match includes, skipping", source_repo
                )
                continue

            if self.matches(source_repo.name, self.excludes):
                self.logger.info(
                    "Repository %s matches excludes, skipping", source_repo
                )
                continue

            yield source_repo
