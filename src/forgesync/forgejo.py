from logging import Logger
from typing import Self, override
from pyforgejo import PyforgejoApi, Repository as ForgejoRepository, User as ForgejoUser

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
    ) -> None:
        self.client = PyforgejoApi(base_url=instance, api_key=token)

        self.user = self.client.user.get_current()

        self.features = features

        if self.user.login is None:
            raise SyncError("Could not get username from Forgejo")

        self.repos = {}
        for repo in self.client.user.list_repos(self.user.login):
            if repo.name is None:
                continue
            self.repos[repo.name] = repo

        self.logger = logger

    @override
    def sync(
        self: Self,
        source_repo: SourceRepository,
        description: str,
        topics: list[str],
    ) -> SyncedRepository:
        if self.user.login is None:
            raise SyncError("Cannot get username from Forgejo")

        self.logger.info("Synchronizing to %s/%s", self.user.login, source_repo.name)

        real = source_repo.real

        if source_repo.name in self.repos:
            existing_repo = self.repos[source_repo.name]

            if existing_repo.archived:
                raise RepositorySkippedError("Destination repository is archived")

            if existing_repo.fork:
                raise RepositorySkippedError("Destination repository is a fork")
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
            owner=self.user.login,
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
