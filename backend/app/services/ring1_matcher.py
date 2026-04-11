"""Ring 1 matcher — fast literal-phrase matching of a post against configured signals.

Design note: this is intentionally a pure function with no database access or
async dependencies. The caller is responsible for loading the signals. This
keeps the matcher trivially testable and fast enough to run in the hot path
of every ingested post.
"""
from typing import Iterable, Protocol


class SignalLike(Protocol):
    id: object
    phrase: str
    enabled: bool


def match_post_to_ring1_signals(
    post_content: str,
    signals: Iterable[SignalLike],
) -> list[str]:
    """Return the IDs of signals whose phrase appears literally in the post.

    Case-insensitive, substring match. Disabled signals are skipped.
    Returns signal IDs as strings (UUID or str, coerced via str()).
    """
    if not post_content:
        return []

    content_lower = post_content.lower()
    matches: list[str] = []

    for signal in signals:
        if not getattr(signal, "enabled", True):
            continue
        phrase = (signal.phrase or "").strip().lower()
        if not phrase:
            continue
        if phrase in content_lower:
            matches.append(str(signal.id))

    return matches
