from logging import Logger
from typing import Self, override, Callable, Iterator, TypeVar, Any, Sequence
from pyforgejo import PyforgejoApi, Repository as ForgejoRepository, User as ForgejoUser
from itertools import count

from .source import SourceRepository
from .platform import Platform
from .sync import (
    RepositoryError,
    RepositoryFeature,
    RepositorySkippedError,
    SyncError,
    SyncedRepository,
    Syncer,
)

T = TypeVar("T")
R = TypeVar("R")


def depaginate(
    func: Callable[..., R],
    *args: Any,
    convert: Callable[[R], Sequence[T] | None] = lambda item: item,
    limit: int = 50,
    **kwargs: Any,
) -> Iterator[T]:
    for page in count(1):
        result = func(*args, page=page, limit=limit, **kwargs)

        items = convert(result) or []

        if not items:
            break

        yield from items

        if len(items) < limit:
            break


class ForgejoSyncer(Syncer):
    client: PyforgejoApi
    user: ForgejoUser
    repos: dict[str, ForgejoRepository]
    features: list[RepositoryFeature]
    logger: Logger

    def __init__(
        self: Self,
        instance: str,
        token: str,
        features: list[RepositoryFeature],
        logger: Logger,
        org: str | None = None
    ) -> None:

        self.client = PyforgejoApi(base_url=instance, api_key=token)

        self.features = features

        self.logger = logger

        self.is_org = bool(org)

        self.repos = {}
        if self.is_org:
            self.target_owner = org
            self.user = None
            for repo in depaginate(self.client.organization.org_list_repos, self.target_owner):
                if repo.name is None:
                    continue
                self.repos[repo.name] = repo
        else:
            self.user = self.client.user.get_current()
            if self.user.login is None:
                raise SyncError("Could not get username from Forgejo")
            self.target_owner = self.user.login
            for repo in depaginate(self.client.user.list_repos, self.target_owner):
                if repo.name is None:
                    continue
                self.repos[repo.name] = repo

    @override
    def sync(
        self: Self,
        source_repo: SourceRepository,
        description: str,
        topics: list[str],
    ) -> SyncedRepository:
        self.logger.info("Synchronizing to %s/%s", self.target_owner, source_repo.name)

        real = source_repo.real

        if source_repo.name in self.repos:
            existing_repo = self.repos[source_repo.name]

            if existing_repo.archived:
                raise RepositorySkippedError("Destination repository is archived")

            if existing_repo.fork:
                raise RepositorySkippedError("Destination repository is a fork")
        else:
            if self.is_org:
                new_repo = self.client.organization.create_org_repo(
                    org=self.target_owner,
                    name=source_repo.name,
                    auto_init=False,
                    default_branch=real.default_branch,
                    description=description,
                    private=real.private,
                )
            else:
                new_repo = self.client.repository.create_current_user_repo(
                    name=source_repo.name,
                    auto_init=False,
                    default_branch=real.default_branch,
                    description=description,
                    private=real.private,
                )

            self.logger.info("Created new Forgejo repository %s", new_repo.full_name)

        edited_repo = self.client.repository.repo_edit(
            owner=self.target_owner,
            repo=source_repo.name,
            archived=real.archived,
            default_branch=real.default_branch,
            description=description,
            external_tracker=None,
            external_wiki=None,
            globally_editable_wiki=None,
            has_actions=RepositoryFeature.ACTIONS in self.features,
            has_issues=RepositoryFeature.ISSUES in self.features,
            has_packages=RepositoryFeature.PACKAGES in self.features,
            has_projects=RepositoryFeature.PROJECTS in self.features,
            has_pull_requests=RepositoryFeature.PULL_REQUESTS in self.features,
            has_releases=RepositoryFeature.RELEASES in self.features,
            has_wiki=RepositoryFeature.WIKI in self.features,
            internal_tracker=None,
            name=real.name,
            private=real.private,
            template=real.template,
            website=real.website,
            wiki_branch=real.wiki_branch,
        )

        if (
            edited_repo.owner is None
            or edited_repo.owner.login is None
            or edited_repo.name is None
            or edited_repo.clone_url is None
        ):
            raise RepositoryError("Received malformed target repository from Forgejo")

        self.client.repository.repo_update_topics(
            owner=edited_repo.owner.login,
            repo=edited_repo.name,
            topics=topics,
        )

        self.logger.info("Updated Forgejo repository %s", edited_repo.full_name)

        return SyncedRepository(
            new_owner=edited_repo.owner.login,
            orig_owner=source_repo.owner,
            name=edited_repo.name,
            clone_url=edited_repo.clone_url,
            platform=Platform.FORGEJO,
            mirrored=False,
        )
