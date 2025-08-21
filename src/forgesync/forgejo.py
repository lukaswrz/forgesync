from logging import Logger
from typing import Self, override
from pyforgejo import PyforgejoApi, Repository as ForgejoRepository, User as ForgejoUser

from .sync import (
    RepoError,
    RepoSkippedError,
    SyncError,
    SyncedRepository,
    Syncer,
    Destination,
)


class ForgejoSyncer(Syncer):
    client: PyforgejoApi
    user: ForgejoUser
    repos: dict[str, ForgejoRepository]
    logger: Logger

    def __init__(
        self: Self,
        instance: str,
        token: str,
        logger: Logger,
    ) -> None:
        self.client = PyforgejoApi(base_url=instance, api_key=token)

        self.user = self.client.user.get_current()

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
        from_repo: ForgejoRepository,
        description: str,
        topics: list[str],
    ) -> SyncedRepository:
        if self.user.login is None:
            raise SyncError("Cannot get username from Forgejo")

        if from_repo.name is None:
            raise RepoError("Cannot get Forgejo repository name")

        self.logger.info("Synchronizing %s/%s", self.user.login, from_repo.name)

        if from_repo.name in self.repos:
            existing_repo = self.repos[from_repo.name]

            if existing_repo.archived:
                raise RepoSkippedError("Destination repository is archived")

            if existing_repo.fork:
                raise RepoSkippedError("Destination repository is a fork")
        else:
            new_repo = self.client.repository.create_current_user_repo(
                name=from_repo.name,
                auto_init=False,
                default_branch=from_repo.default_branch,
                description=description,
                private=from_repo.private,
            )

            self.logger.info("Created new Forgejo repository %s", new_repo.full_name)

        edited_repo = self.client.repository.repo_edit(
            owner=self.user.login,
            repo=from_repo.name,
            archived=from_repo.archived,
            default_branch=from_repo.default_branch,
            description=description,
            external_tracker=None,
            external_wiki=None,
            globally_editable_wiki=None,
            has_actions=False,
            has_issues=False,
            has_packages=False,
            has_projects=False,
            has_pull_requests=False,
            has_releases=False,
            has_wiki=False,
            internal_tracker=None,
            name=from_repo.name,
            private=from_repo.private,
            template=from_repo.template,
            website=from_repo.website,
            wiki_branch=from_repo.wiki_branch,
        )

        if (
            edited_repo.owner is None
            or edited_repo.owner.login is None
            or from_repo.owner is None
            or from_repo.owner.login is None
            or edited_repo.name is None
            or edited_repo.clone_url is None
        ):
            raise RepoError("Received malformed Forgejo repository")

        self.client.repository.repo_update_topics(
            owner=edited_repo.owner.login,
            repo=edited_repo.name,
            topics=topics,
        )

        self.logger.info("Updated Forgejo repository %s", edited_repo.full_name)

        return SyncedRepository(
            new_owner=edited_repo.owner.login,
            orig_owner=from_repo.owner.login,
            name=edited_repo.name,
            clone_url=edited_repo.clone_url,
            destination=Destination.FORGEJO,
            mirrored=False,
        )
