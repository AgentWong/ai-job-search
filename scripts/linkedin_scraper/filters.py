"""
Phase 1 filters — applied to search-result cards BEFORE fetching detail pages.

Goal: drop obviously-disqualifying postings (senior titles, wrong role family,
excluded companies, non-US locations) using just the card text, so we don't
burn HTTP requests on jobs we'd reject anyway.

The LLM agent does fuzzy review of survivors later — these filters only need
to catch the clear cases that string-match cheaply.
"""

import re
from dataclasses import dataclass
from typing import Optional

from .search import SearchCard
from scripts.ats_scraper.location import (
    LocationConfig,
    is_remote,
    local_card_kept_by_metro,
    match_non_remote,
    match_non_us,
)

# ---------------------------------------------------------------------------
# Title disqualifiers (mirror shared/scoring_framework.md and ats_scraper)
# ---------------------------------------------------------------------------

# Seniority signals. "I" alone is too aggressive (would match "Engineer I"
# but also any word with stray I). We anchor to whole tokens with surrounding
# context to avoid false positives.
_SENIOR_TITLE = re.compile(
    r"\b("
    r"senior|sr\.?|snr\.?|"
    r"lead(?:\s+\w+)?|tech\s+lead|team\s+lead|"
    r"principal|staff|"
    r"manager|director|head\s+of|vp\b|vice\s+president|chief|"
    r"architect|"
    r"ii+|iv|vi*"   # II, III, IV, V, VI, VII (level indicators)
    r")\b",
    re.IGNORECASE,
)

# Wrong role families — we want infra, not these
_WRONG_ROLE = re.compile(
    r"\b("
    r"software\s+engineer|software\s+developer|"
    r"backend|back.end|"
    r"frontend|front.end|front[- ]end\s+developer|"
    r"fullstack|full.stack|"
    r"data\s+engineer|data\s+scientist|"
    r"ml\s+engineer|machine\s+learning\s+engineer|"
    r"security\s+engineer|"
    r"qa\s+engineer|test\s+engineer|sdet|"
    r"business\s+analyst|product\s+manager|product\s+owner|"
    r"sales\s+engineer|solutions?\s+engineer|"
    r"customer\s+success|account\s+manager|"
    r"recruiter|talent\s+(?:partner|acquisition)"
    r")\b",
    re.IGNORECASE,
)

# Location disqualifiers (non-US + hybrid/on-site regexes, plus the mode-aware
# metro logic) now live in scripts/ats_scraper/location.py, shared with the ATS
# and Built In scrapers. See filter_card() below.


@dataclass
class FilterVerdict:
    """Result of running pre-fetch filters on one card."""
    keep: bool
    reason: str = ""   # reason for rejection if keep=False


def filter_card(
    card: SearchCard,
    excluded_companies: list[str],
    loc_cfg: LocationConfig,
) -> FilterVerdict:
    """
    Apply Phase 1 filters to a single search card.

    Returns FilterVerdict(keep=True) if the card survives, else
    FilterVerdict(keep=False, reason="...").

    The reason strings are user-readable and feed into the rejection
    breakdown the CLI prints.
    """
    title = card.title or ""
    company = card.company or ""
    location = card.location or ""

    # 1. Title-based seniority disqualifier
    if _SENIOR_TITLE.search(title):
        m = _SENIOR_TITLE.search(title)
        return FilterVerdict(False, f"Senior title: '{m.group(0)}'")

    # 2. Wrong role family
    if _WRONG_ROLE.search(title):
        m = _WRONG_ROLE.search(title)
        return FilterVerdict(False, f"Wrong role family: '{m.group(0)}'")

    # 3. Excluded company (case-insensitive substring match)
    company_lower = company.lower()
    for excluded in excluded_companies:
        if excluded and excluded in company_lower:
            return FilterVerdict(False, f"Excluded company: '{company}'")

    # 4. Location (mode-aware; shared logic in scripts/ats_scraper/location.py)
    if location:
        token = match_non_us(location)
        if token:
            return FilterVerdict(False, f"Non-US location: '{token}'")
        if loc_cfg.remote:
            # Remote-only: f_WT=2 already constrains the URL, so we only drop
            # loosely-tagged hybrid/on-site cards.
            token = match_non_remote(location)
            if token:
                return FilterVerdict(False, f"Non-remote: '{token}'")
        else:
            # Local: keep in-metro cards (hybrid/on-site welcome) and, unless
            # turned off, fully-remote cards too. When distance_miles is set the
            # search URL already constrained the radius, so we trust it and keep
            # in-US neighbors (Clarkston WA, Pullman) the strict name match would
            # drop; with no radius we fall back to the strict metro-name match.
            if is_remote(location):
                if not loc_cfg.accept_remote_in_local_mode:
                    return FilterVerdict(False, f"Remote (not local): '{location}'")
            elif not local_card_kept_by_metro(location, loc_cfg):
                target = ", ".join(p for p in (loc_cfg.city, loc_cfg.state) if p)
                return FilterVerdict(False, f"Not in {target}: '{location}'")

    return FilterVerdict(True)
