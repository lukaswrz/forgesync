from typing import override
from pyforgejo import Repository


class SourceRepository:
    real: Repository
    name: str
    owner: str

    def __init__(self, real: Repository) -> None:
        if real.owner is None or real.owner.login is None or real.name is None:
            raise RuntimeError("Could not get name of Forgejo repository")

        self.real = real
        self.name = real.name
        self.owner = real.owner.login

    @override
    def __str__(self) -> str:
        return f"{self.owner}/{self.name}"
