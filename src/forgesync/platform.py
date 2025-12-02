from github.GithubObject import Consts
from enum import StrEnum

GITHUB_INSTANCE = Consts.DEFAULT_BASE_URL
CODEBERG_INSTANCE = "https://codeberg.org/api/v1"


class Platform(StrEnum):
    FORGEJO = "forgejo"
    CODEBERG = "codeberg"
    GITHUB = "github"
