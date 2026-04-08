DEFAULT_BLOCKLIST = [
    "happy birthday",
    "work anniversary",
    "excited to announce my new role",
    "open to work",
    "pleased to share",
    "thrilled to announce",
    "congratulations on your",
    "looking for new opportunities",
]


def keyword_prefilter(
    content: str,
    signal_keywords: list[str],
    anti_keywords: list[str],
) -> bool:
    """
    Returns True if the post should proceed to semantic matching.
    Returns False if the post should be discarded.

    Stage 1 of the matching pipeline — fast, cheap, synchronous.
    """
    content_lower = content.lower()

    # Hard blocklist — combined default + workspace anti_keywords
    full_blocklist = DEFAULT_BLOCKLIST + [kw.lower() for kw in anti_keywords]
    if any(term in content_lower for term in full_blocklist):
        return False

    # Must contain at least one signal keyword
    if not any(kw.lower() in content_lower for kw in signal_keywords):
        return False

    return True
