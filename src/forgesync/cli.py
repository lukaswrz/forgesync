"""
Automatically synchronize all your Forgejo repositories to GitHub as well as any Forgejo instance.
"""

from logging import Formatter, Logger, StreamHandler
from os import environ, PathLike
from sys import stderr
from tap import Tap
from xdg_base_dirs import xdg_config_home
from pyforgejo import PyforgejoApi, Repository as ForgejoRepository

from .sync import SyncError, SyncedRepository, Destination
from .github import GithubSyncer
from .forgejo import ForgejoSyncer
from .mirror import MirrorError, PushMirrorConfig, PushMirrorer
from re import compile


class ArgumentParser(Tap):
    from_instance: str
    "base URL of the source instance"
    to: Destination
    "what kind of destination to sync to, e.g. 'forgejo' or 'github'"
    to_instance: str
    "base URL of the destination instance"
    description_template: str = "{description} (Mirror of {url})"
    "the repository description template"
    remirror: bool = False
    "whether mirrors should be recreated"
    mirror_interval: str = "8h0m0s"
    "repository mirror interval"
    log: str = "WARNING"
    "log level"
    filter: str | None = None
    "filter repositories by this regular expression"
    immediate: bool = False
    "tell Forgejo to mirror Git repositories immediately"
    sync_on_commit: bool = False
    "tell Forgejo to sync as soon as commits are pushed"


def get_config_files() -> list[str | PathLike[str]]:
    app = "forgesync"
    config_path = xdg_config_home() / app / f"{app}.conf"
    config_files: list[str | PathLike[str]] = (
        [config_path] if config_path.exists() else []
    )

    return config_files


def make_description(template: str, repo: ForgejoRepository) -> str:
    return template.format(
        description=repo.description,
        url=repo.html_url,
        website=repo.website,
        full_name=repo.full_name,
        clone_url=repo.clone_url,
    )


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
    parser = ArgumentParser(
        config_files=get_config_files(), description=__doc__, underscores_to_dashes=True
    )
    return parser.parse_args()


def main() -> None:
    try:
        from_token = environ["FROM_TOKEN"]
        to_token = environ["TO_TOKEN"]
        mirror_token = environ["MIRROR_TOKEN"]
    except KeyError as e:
        print(f"Missing token: {e}", file=stderr)
        exit(1)

    args = get_args()

    logger = make_logger(name="forgesync", level=args.log)

    from_client = PyforgejoApi(base_url=args.from_instance, api_key=from_token)

    push_mirror_config = PushMirrorConfig(
        interval=args.mirror_interval,
        remirror=args.remirror,
        immediate=args.immediate,
        sync_on_commit=args.sync_on_commit,
    )

    push_mirrorer = PushMirrorer(
        client=from_client,
        config=push_mirror_config,
        mirror_token=mirror_token,
        logger=logger,
    )

    match args.to:
        case Destination.GITHUB:
            syncer = GithubSyncer(
                instance=args.to_instance,
                token=to_token,
                push_mirrorer=push_mirrorer,
                logger=logger,
            )
        case Destination.FORGEJO:
            syncer = ForgejoSyncer(
                instance=args.to_instance,
                token=to_token,
                logger=logger,
            )

    from_user = from_client.user.get_current()
    if from_user.login is None:
        logger.fatal("Could not get username from Forgejo")
        exit(1)

    from_repos = from_client.user.list_repos(from_user.login)
    synced_repos: list[SyncedRepository] = []
    for repo in from_repos:
        if repo.fork or repo.mirror or repo.private:
            continue

        if repo.name is None:
            logger.fatal("Could not get name of Forgejo repository")
            exit(1)

        if args.filter is not None:
            pattern = compile(args.filter)
            if pattern.search(repo.name) is not None:
                continue

        description = make_description(
            template=args.description_template,
            repo=repo,
        )

        try:
            synced_repo = syncer.sync(from_repo=repo, description=description)
        except SyncError as error:
            logger.fatal("Syncing failed: %s", error)
            exit(2)

        synced_repos.append(synced_repo)

    try:
        _ = push_mirrorer.mirror_repos(
            synced_repos=synced_repos,
            config=push_mirror_config,
        )
    except MirrorError as error:
        logger.fatal("Mirroring failed: %s", error)
        exit(3)
