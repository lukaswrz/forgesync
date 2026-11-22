from logging import Logger
from re import fullmatch
from typing import Self, override

from .forgejo import ForgejoSyncer
from .github import GithubSyncer
from .mirror import PushMirrorConfig, PushMirrorer
from .platform import CODEBERG_INSTANCE, GITHUB_INSTANCE, Platform
from .sync import RepositoryFeature, Syncer


class Destination:
    platform: Platform
    instance: str

    def __init__(self, platform: Platform, instance: str | None) -> None:
        self.platform = platform

        if instance is not None:
            self.instance = instance
        else:
            match platform:
                case Platform.GITHUB:
                    self.instance = GITHUB_INSTANCE
                case Platform.CODEBERG:
                    self.instance = CODEBERG_INSTANCE
                case Platform.FORGEJO:
                    raise DestinationError("Forgejo does not have a default instance")

    @classmethod
    def parse(cls, string: str) -> Self:
        match = fullmatch(r"(?P<platform>[^=]+)(=(?P<instance>.+))?", string)
        if match is None:
            raise ValueError(f"Invalid destination syntax: {string}")
        platform = match.group("platform")
        instance = match.group("instance")

        try:
            platform = Platform(platform.lower())
        except ValueError:
            raise DestinationError(f"Unknown destination platform: {platform}")

        return cls(platform=platform, instance=instance)

    def make_syncer(
        self,
        token: str,
        features: list[RepositoryFeature],
        logger: Logger,
        push_mirrorer: PushMirrorer,
        push_mirror_config: PushMirrorConfig,
    ) -> Syncer:
        match self.platform:
            case Platform.GITHUB:
                return GithubSyncer(
                    instance=self.instance,
                    token=token,
                    features=features,
                    logger=logger,
                    push_mirrorer=push_mirrorer,
                    push_mirror_config=push_mirror_config,
                )
            case Platform.FORGEJO | Platform.CODEBERG:
                return ForgejoSyncer(
                    instance=self.instance,
                    token=token,
                    features=features,
                    logger=logger,
                )

    @override
    def __str__(self) -> str:
        return f"{self.platform}={self.instance}"


class DestinationError(RuntimeError):
    pass
