from datetime import datetime
from re import compile, VERBOSE

PATTERN_REGEX = compile(
    r"""^
    (?P<year>\*|\d{4})-(?P<month>\*|\d{2})-(?P<day>\*|\d{2}) # YYYY-MM-DD
    [ ]
    (?P<hour>\*|\d{2}):(?P<minute>\*|\d{2}):(?P<second>\*|\d{2}) # HH:MM:SS
    $
    """,
    VERBOSE,
)


class RemirrorSyntaxError(RuntimeError):
    pass


def should_remirror(rule: str, now: datetime | None = None) -> bool:
    now = now or datetime.now()

    if rule == "always":
        return True
    if rule == "never":
        return False

    match = PATTERN_REGEX.search(rule)
    if match is None:
        raise RemirrorSyntaxError(f"Remirror syntax of rule '{rule}' does not match")

    compare_parts = {
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": now.minute,
        "second": now.second,
    }

    for k, actual in compare_parts.items():
        expected = match.group(k)
        if expected != "*" and int(expected) != actual:
            return False

    return True
