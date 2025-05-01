from logging import Logger
from typing import Self, override
from github.AuthenticatedUser import AuthenticatedUser
from github.GithubObject import NotSet
from github.Repository import Repository as GithubRepository
from github import Github, Auth as GithubAuth
from pyforgejo import Repository as ForgejoRepository
from .sync import SyncError, SyncedRepository, Syncer


class GithubSyncer(Syncer):
    client: Github
    user: AuthenticatedUser
    repos: dict[str, GithubRepository]
    logger: Logger

    def __init__(self: Self, instance: str, token: str, logger: Logger) -> None:
        auth = GithubAuth.Token(token)

        self.client = Github(
            base_url=instance,
            auth=auth,
            user_agent="forgesync",
        )

        user = self.client.get_user()
        if not isinstance(user, AuthenticatedUser):
            raise SyncError("user must be authenticated")

        self.user = user

        self.repos = {}
        for repo in self.user.get_repos():
            self.repos[repo.name] = repo

        self.logger = logger

    @override
    def sync(
        self: Self, from_repo: ForgejoRepository, description: str
    ) -> SyncedRepository:
        if from_repo.name is None:
            raise SyncError("could not get Forgejo repository name")

        self.logger.info("Synchronizing %s", from_repo.name)

        if from_repo.name in self.repos:
            repo = self.repos[from_repo.name]
        else:
            repo = self.user.create_repo(
                auto_init=False,
                has_downloads=False,
                name=from_repo.name,
                description=description,
                homepage=from_repo.website if from_repo.website is not None else NotSet,
                private=from_repo.private if from_repo.private is not None else NotSet,
                has_issues=False,
                has_projects=False,
                has_wiki=False,
                has_discussions=False,
            )
            self.logger.info("Created new GitHub repository %s", repo.full_name)

        repo.edit(
            name=from_repo.name,
            description=description,
            homepage=from_repo.website if from_repo.website is not None else NotSet,
            private=from_repo.private if from_repo.private is not None else NotSet,
            has_issues=False,
            has_projects=False,
            has_wiki=False,
            has_discussions=False,
            is_template=from_repo.template
            if from_repo.template is not None
            else NotSet,
            default_branch=from_repo.default_branch
            if from_repo.default_branch is not None
            else NotSet,
            archived=from_repo.archived if from_repo.archived is not None else NotSet,
            allow_forking=False,
        )

        self.logger.info("Updated GitHub repository %s", repo.full_name)

        repo.replace_topics(from_repo.topics if from_repo.topics is not None else [])

        self.logger.info("Replaced topics on GitHub repository %s", repo.full_name)

        if (
            repo.owner.name is None
            or from_repo.owner is None
            or from_repo.owner.login is None
        ):
            raise SyncError("received malformed repository")

        return SyncedRepository(
            new_owner=repo.owner.name,
            orig_owner=from_repo.owner.login,
            name=repo.name,
            clone_url=repo.clone_url,
        )
