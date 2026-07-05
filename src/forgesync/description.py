from pyforgejo import Repository


def make_placeholders(repo: Repository) -> dict[str, str]:
    fallback = ""

    return {
        "description": repo.description or fallback,
        "url": repo.html_url or fallback,
        "website": repo.website or fallback,
        "full_name": repo.full_name or fallback,
        "clone_url": repo.clone_url or fallback,
    }
