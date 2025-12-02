from typing import override
from pyforgejo import PyforgejoApi

from .dest import Destination
from .mirror import PushMirrorConfig, PushMirrorer
from .source import SourceRepository
from .sync import Syncer


class Task:
    syncer: Syncer
    source_client: PyforgejoApi
    description_template: str
    source_repo: SourceRepository
    topics: list[str]
    push_mirrorer: PushMirrorer
    push_mirror_config: PushMirrorConfig
    destination: Destination

    def __init__(
        self,
        syncer: Syncer,
        source_client: PyforgejoApi,
        description_template: str,
        source_repo: SourceRepository,
        push_mirrorer: PushMirrorer,
        push_mirror_config: PushMirrorConfig,
        destination: Destination,
    ) -> None:
        self.syncer = syncer
        self.source_client = source_client
        self.description_template = description_template
        self.source_repo = source_repo
        self.push_mirrorer = push_mirrorer
        self.push_mirror_config = push_mirror_config
        self.destination = destination

        topics_list = source_client.repository.repo_list_topics(
            owner=source_repo.owner,
            repo=source_repo.name,
        )
        self.topics = topics_list.topics if topics_list.topics is not None else []

    def run(self) -> None:
        description = self.description_template.format(
            description=self.source_repo.real.description,
            url=self.source_repo.real.html_url,
            website=self.source_repo.real.website,
            full_name=self.source_repo.real.full_name,
            clone_url=self.source_repo.real.clone_url,
        )

        synced_repo = self.syncer.sync(
            source_repo=self.source_repo,
            description=description,
            topics=self.topics,
        )

        if not synced_repo.mirrored:
            _ = self.push_mirrorer.mirror_repo(
                synced_repo=synced_repo,
                config=self.push_mirror_config,
            )

    @override
    def __str__(self) -> str:
        return f"Synchronize {self.source_repo.owner}/{self.source_repo.name} to {self.destination}"
