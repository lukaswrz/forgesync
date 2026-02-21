from dataclasses import replace
from logging import Logger
from typing import Self, override
from github.AuthenticatedUser import AuthenticatedUser
from github.GithubException import GithubException
from github.GithubObject import NotSet
from github.Repository import Repository as GithubRepository
from github import Github, Auth as GithubAuth

from .source import SourceRepository
from .platform import Platform
from .mirror import PushMirrorConfig, PushMirrorer, Remirror
from .sync import (
    RepositoryError,
    RepositoryFeature,
    SyncError,
    RepositorySkippedError,
    SyncedRepository,
    Syncer,
)


class GithubSyncer(Syncer):
    client: Github
    user: AuthenticatedUser
    repos: dict[str, GithubRepository]
    logger: Logger
    features: list[RepositoryFeature]
    push_mirrorer: PushMirrorer
    push_mirror_config: PushMirrorConfig

    def __init__(
        self: Self,
        instance: str,
        token: str,
        features: list[RepositoryFeature],
        logger: Logger,
        push_mirrorer: PushMirrorer,
        push_mirror_config: PushMirrorConfig,
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

        self.features = features

        self.repos = {}
        for repo in self.user.get_repos():
            self.repos[repo.name] = repo

        self.push_mirrorer = push_mirrorer
        self.push_mirror_config = push_mirror_config

        self.logger = logger

    @override
    def sync(
        self: Self,
        source_repo: SourceRepository,
        description: str,
        topics: list[str],
    ) -> SyncedRepository:
        self.logger.info("Synchronizing to %s/%s", self.user.login, source_repo.name)

        real = source_repo.real

        mirrored = False

        if source_repo.name in self.repos:
            repo = self.repos[source_repo.name]

            if repo.archived:
                raise RepositorySkippedError("Destination repository is archived")

            if repo.fork:
                raise RepositorySkippedError("Destination repository is a fork")
        else:
            repo = self.user.create_repo(
                auto_init=False,
                name=source_repo.name,
                description=description,
                homepage=real.website if real.website is not None else NotSet,
                private=real.private if real.private is not None else NotSet,
                has_issues=RepositoryFeature.ISSUES in self.features,
                has_projects=RepositoryFeature.PROJECTS in self.features,
                has_wiki=RepositoryFeature.WIKI in self.features,
                has_discussions=RepositoryFeature.DISCUSSIONS in self.features,
                has_downloads=False,
            )

            self.logger.info("Created new GitHub repository %s", repo.full_name)

        try:
            _ = repo.get_contents("/")
        except GithubException:
            self.logger.warning(
                "Could not fetch contents of %s, continuing assuming the repo is empty",
                repo.name,
            )

            synced_repo = self.make_synced(source_repo=source_repo, repo=repo)

            push_mirror = self.push_mirrorer.mirror_repo(
                synced_repo=synced_repo,
                config=replace(
                    self.push_mirror_config,
                    remirror=Remirror.YES,
                    immediate=True,
                ),
            )
            if push_mirror is None:
                raise RepositoryError(
                    f"Could not mirror new repository {repo.full_name}"
                )

            mirrored = True

        repo.edit(
            name=source_repo.name,
            description=description,
            homepage=real.website if real.website is not None else NotSet,
            private=real.private if real.private is not None else NotSet,
            has_issues=RepositoryFeature.ISSUES in self.features,
            has_projects=RepositoryFeature.PROJECTS in self.features,
            has_wiki=RepositoryFeature.WIKI in self.features,
            has_discussions=RepositoryFeature.DISCUSSIONS in self.features,
            is_template=real.template if real.template is not None else NotSet,
            default_branch=real.default_branch
            if real.default_branch is not None
            else NotSet,
            archived=real.archived if real.archived is not None else NotSet,
        )

        self.logger.info("Updated GitHub repository %s", repo.full_name)

        repo.replace_topics(topics=topics)

        self.logger.info("Replaced topics on GitHub repository %s", repo.full_name)

        synced_repo = self.make_synced(source_repo=source_repo, repo=repo)

        synced_repo.mirrored = mirrored

        return synced_repo

    def make_synced(
        self: Self, source_repo: SourceRepository, repo: GithubRepository
    ) -> SyncedRepository:
        return SyncedRepository(
            new_owner=repo.owner.login,
            orig_owner=source_repo.owner,
            name=repo.name,
            clone_url=repo.clone_url,
            platform=Platform.GITHUB,
            mirrored=False,
        )
