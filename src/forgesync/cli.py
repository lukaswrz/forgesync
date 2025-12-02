"""
Automatically mirror all your Forgejo repositories to GitHub or any Forgejo instance.
"""

from logging import Formatter, Logger, StreamHandler
from os import environ
from sys import stderr
from typing import Self, override
from tap import Tap
from pyforgejo import PyforgejoApi

from .source import SourceRepository
from .task import Task
from .dest import Destination
from .filter import RepositoryFilter
from .sync import (
    RepositoryError,
    RepositoryFeature,
    RepositorySkippedError,
    SyncError,
)
from .mirror import MirrorError, PushMirrorConfig, PushMirrorer


class ArgumentParser(Tap):
    source: str
    "base URL of the source instance"
    target: Destination
    "the destination, e.g. github, codeberg or forgejo=https://forgejo.example.com/api/v1"
    description_template: str = "{description} (Mirror of {url})"
    "the repository description template"
    remirror: bool = False
    "whether mirrors should be recreated"
    mirror_interval: str = "8h0m0s"
    "repository mirror interval"
    log: str = "INFO"
    "log level"
    include: list[str] = []
    "include repositories by these regular expressions"
    exclude: list[str] = []
    "exclude repositories by these regular expressions"
    skip_initial: bool = False
    "don't tell Forgejo to mirror Git repositories immediately after creating the push mirror"
    sync_on_push: bool = False
    "tell Forgejo to sync as soon as commits are pushed"
    feature: list[RepositoryFeature] = []
    "allow a repository feature"
    dry_run: bool = False
    "don't actually sync, just print what would be synced"

    @override
    def configure(self: Self):
        self.add_argument("source")  # pyright: ignore[reportUnknownMemberType]
        self.add_argument("target", type=Destination.parse)  # pyright: ignore[reportUnknownMemberType]
        self.add_argument("--include", action="append")  # pyright: ignore[reportUnknownMemberType]
        self.add_argument("--exclude", action="append")  # pyright: ignore[reportUnknownMemberType]
        self.add_argument("--feature", action="append")  # pyright: ignore[reportUnknownMemberType]


def make_logger(name: str, level: str) -> Logger:
    logger = Logger(name)
    logger.setLevel(level)
    formatter = Formatter(
        fmt="{asctime} [{levelname}] {name} ({filename}:{lineno}) - {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )
    handler = StreamHandler(stderr)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def get_args() -> ArgumentParser:
    parser = ArgumentParser(description=__doc__, underscores_to_dashes=True)
    return parser.parse_args()


def get_tokens() -> tuple[str, str, str]:
    try:
        source_token = environ["SOURCE_TOKEN"]
        target_token = environ["TARGET_TOKEN"]
        mirror_token = environ["MIRROR_TOKEN"]
    except KeyError as e:
        raise RuntimeError(f"Missing token: {e}")

    return source_token, target_token, mirror_token


def main() -> None:
    args = get_args()

    logger = make_logger(name="forgesync", level=args.log)

    try:
        source_token, target_token, mirror_token = get_tokens()
    except RuntimeError as e:
        logger.fatal(e)
        exit(1)

    source_client = PyforgejoApi(base_url=args.source, api_key=source_token)

    push_mirror_config = PushMirrorConfig(
        interval=args.mirror_interval,
        remirror=args.remirror,
        immediate=not args.skip_initial,
        sync_on_push=args.sync_on_push,
    )

    push_mirrorer = PushMirrorer(
        client=source_client,
        mirror_token=mirror_token,
        logger=logger,
    )

    syncer = args.target.make_syncer(
        token=target_token,
        features=args.feature,
        logger=logger,
        push_mirrorer=push_mirrorer,
        push_mirror_config=push_mirror_config,
    )

    source_user = source_client.user.get_current()
    if source_user.login is None:
        logger.fatal("Could not get username from Forgejo")
        exit(1)

    real_repos = source_client.user.list_repos(source_user.login)
    source_repos: list[SourceRepository] = []
    for real in real_repos:
        source_repos.append(SourceRepository(real=real))

    filter = RepositoryFilter(
        includes=args.include,
        excludes=args.exclude,
        logger=logger,
    )

    for source_repo in filter.filter(source_repos=source_repos):
        task = Task(
            syncer=syncer,
            source_client=source_client,
            description_template=args.description_template,
            source_repo=source_repo,
            push_mirrorer=push_mirrorer,
            push_mirror_config=push_mirror_config,
            destination=args.target,
        )

        if args.dry_run:
            logger.info("Would run task: %s", task)
            continue

        try:
            logger.info("Running task: %s", task)
            task.run()
        except MirrorError as error:
            logger.warning("Mirroring failed: %s", error)
            continue
        except RepositorySkippedError as error:
            logger.warning("Repository %s skipped: %s", source_repo.name, error)
            continue
        except RepositoryError as error:
            logger.warning("Syncing repository %s failed: %s", source_repo.name, error)
            continue
        except SyncError as error:
            logger.fatal("Syncing repository %s failed: %s", source_repo.name, error)
            exit(1)
