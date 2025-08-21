from dataclasses import replace
from logging import Logger
from typing import Self, override
from github.AuthenticatedUser import AuthenticatedUser
from github.GithubException import GithubException
from github.GithubObject import NotSet
from github.Repository import Repository as GithubRepository
from github import Github, Auth as GithubAuth
from pyforgejo import Repository as ForgejoRepository

from .mirror import PushMirrorConfig, PushMirrorer
from .sync import (
    RepoError,
    SyncError,
    RepoSkippedError,
    SyncedRepository,
    Syncer,
    Destination,
)


class GithubSyncer(Syncer):
    client: Github
    user: AuthenticatedUser
    repos: dict[str, GithubRepository]
    push_mirrorer: PushMirrorer
    push_mirror_config: PushMirrorConfig
    logger: Logger

    def __init__(
        self: Self,
        instance: str,
        token: str,
        push_mirrorer: PushMirrorer,
        push_mirror_config: PushMirrorConfig,
        logger: Logger,
    ) -> None:
        auth = GithubAuth.Token(token)

        self.client = Github(
            base_url=instance,
            auth=auth,
            user_agent="forgesync",
        )

        user = self.client.get_user()
        if not isinstance(user, AuthenticatedUser):
            raise SyncError("User must be authenticated")

        self.user = user

        self.repos = {}
        for repo in self.user.get_repos():
            self.repos[repo.name] = repo

        self.push_mirrorer = push_mirrorer
        self.push_mirror_config = push_mirror_config

        self.logger = logger

    @override
    def sync(
        self: Self,
        from_repo: ForgejoRepository,
        description: str,
        topics: list[str],
    ) -> SyncedRepository:
        if from_repo.name is None:
            raise RepoError("Cannot get source repository name")

        self.logger.info("Synchronizing %s/%s", self.user.login, from_repo.name)

        mirrored = False

        if from_repo.name in self.repos:
            repo = self.repos[from_repo.name]

            if repo.archived:
                raise RepoSkippedError("Destination repository is archived")

            if repo.fork:
                raise RepoSkippedError("Destination repository is a fork")
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

        try:
            _ = repo.get_contents("/")
        except GithubException:
            self.logger.warning(
                "Could not fetch contents of %s, continuing assuming the repo is empty",
                repo.name,
            )

            synced_repo = self.make_synced(from_repo=from_repo, repo=repo)

            push_mirror = self.push_mirrorer.mirror_repo(
                synced_repo=synced_repo,
                config=replace(
                    self.push_mirror_config,
                    remirror=True,
                    immediate=True,
                ),
            )
            if push_mirror is None:
                raise RepoError(f"Could not mirror new repository {repo.full_name}")

            mirrored = True

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
        )

        self.logger.info("Updated GitHub repository %s", repo.full_name)

        repo.replace_topics(topics=topics)

        self.logger.info("Replaced topics on GitHub repository %s", repo.full_name)

        synced_repo = self.make_synced(from_repo=from_repo, repo=repo)

        synced_repo.mirrored = mirrored

        return synced_repo

    def make_synced(
        self: Self, from_repo: ForgejoRepository, repo: GithubRepository
    ) -> SyncedRepository:
        if from_repo.owner is None or from_repo.owner.login is None:
            raise RepoError("Cannot get GitHub reposiory owner")

        return SyncedRepository(
            new_owner=repo.owner.login,
            orig_owner=from_repo.owner.login,
            name=repo.name,
            clone_url=repo.clone_url,
            destination=Destination.GITHUB,
            mirrored=False,
        )
