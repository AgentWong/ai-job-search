"""
Cross-role deduplication and spam removal for LinkedIn search results.

LinkedIn allows companies to post the same role to multiple cities, generating
distinct job_ids per city. Search-page de-dup (in search.py) only catches
within-role repeats; identical (company, title) pairs across roles and across
cities survive into Phase 2 and waste detail fetches on duplicates and spam.

Two passes against the cross-role survivor pool:

1. **Spam pass** — count (normalized_company, normalized_title) occurrences
   across ALL roles. If a pair appears `spam_threshold`+ times, drop every
   instance. Premise: a company saturating the board with the same title in
   3+ cities is gaming visibility (e.g. Bright Vision Technologies posting
   "AWS Cloud Engineer" 10x). The signal is the duplication itself, so dropping
   one and keeping another doesn't help — discard the whole pair.

2. **Dedupe pass** — for surviving (company, title) pairs that still appear
   more than once (2 instances under the threshold), keep only the first
   occurrence. Role iteration order is priority-sorted, so "first" is the
   highest-priority role match.
"""

from dataclasses import dataclass, field

from scripts.ats_scraper.cooldown import normalize_company, normalize_role

from .search import SearchCard


@dataclass
class DedupStats:
    """Counts and identifiers emitted by detect_spam_and_dedupe."""

    spam_dropped: int = 0
    duplicate_dropped: int = 0
    # List of (company_display, title_display, count) for the spam summary.
    spam_pairs: list[tuple[str, str, int]] = field(default_factory=list)


def detect_spam_and_dedupe(
    survivors_by_role: dict[str, list[SearchCard]],
    *,
    spam_threshold: int = 3,
) -> tuple[dict[str, list[SearchCard]], DedupStats]:
    """
    Drop spam (>=spam_threshold identical postings) and cross-role duplicates.

    Returns the rebuilt survivors_by_role plus a DedupStats record. Role keys
    and iteration order are preserved so downstream per-role reporting still
    aligns.
    """
    if spam_threshold < 2:
        raise ValueError(f"spam_threshold must be >= 2, got {spam_threshold}")

    # Pass 1: count occurrences across all roles
    counts: dict[tuple[str, str], int] = {}
    display: dict[tuple[str, str], tuple[str, str]] = {}
    for cards in survivors_by_role.values():
        for c in cards:
            key = (normalize_company(c.company), normalize_role(c.title))
            counts[key] = counts.get(key, 0) + 1
            display.setdefault(key, (c.company, c.title))

    spam_keys = {k for k, n in counts.items() if n >= spam_threshold}

    # Pass 2: rebuild survivors, dropping spam and second+ occurrences
    seen_non_spam: set[tuple[str, str]] = set()
    rebuilt: dict[str, list[SearchCard]] = {}
    stats = DedupStats(
        spam_pairs=sorted(
            ((display[k][0], display[k][1], counts[k]) for k in spam_keys),
            key=lambda t: (-t[2], t[0].lower(), t[1].lower()),
        )
    )

    for role, cards in survivors_by_role.items():
        kept: list[SearchCard] = []
        for c in cards:
            key = (normalize_company(c.company), normalize_role(c.title))
            if key in spam_keys:
                stats.spam_dropped += 1
                continue
            if key in seen_non_spam:
                stats.duplicate_dropped += 1
                continue
            seen_non_spam.add(key)
            kept.append(c)
        rebuilt[role] = kept

    return rebuilt, stats
