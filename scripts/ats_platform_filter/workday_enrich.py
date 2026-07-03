"""Backfill job descriptions for Workday results Firecrawl could not render.

Workday is a JS SPA: a public `/{locale}/{board}/job/...` URL scrapes to nav
chrome only, so every Workday result reaches the filter as `no_description` and
is dropped — even though the posting's full description is served verbatim by
Workday's public CXS JSON API. This module derives the CXS endpoint from the
public URL (no new search, no Firecrawl credits) and injects the fetched
description into the result's `markdown` field, so the rest of the
ats-platform-search pipeline (listing_health → stage → review) treats the
Workday item exactly like a server-rendered board.

Conservative by design: if the CXS fetch fails or returns too little prose, the
result is left unchanged and falls through to the existing `no_description`
gate — no un-scoreable Workday item reaches the LLM.
"""

from __future__ import annotations

import requests

from scripts.ats_scraper.platforms.workday import (
    fetch_description_from_url,
    make_session,
    WORKDAY_HEADERS,
)
from scripts.ats_platform_filter.filters import _real_word_count, MIN_JD_WORDS


def _is_workday(url: str) -> bool:
    return "myworkdayjobs.com" in (url or "").lower()


def make_workday_session() -> requests.Session:
    """One session reused across a query's Workday fetches (keep-alive)."""
    return make_session(extra_headers=WORKDAY_HEADERS)


def enrich_workday_result(item: dict, session: requests.Session | None = None) -> bool:
    """Backfill `item['markdown']` from the Workday CXS API when it's missing.

    Only acts on myworkdayjobs.com results whose scraped markdown is too thin to
    score (the un-rendered SPA shell). On a successful fetch that yields real
    prose, replaces `markdown` with the description and refreshes the snippet
    location. Returns True if the item was enriched, False otherwise (caller's
    downstream gates are unchanged either way).
    """
    url = item.get("url", "") or ""
    if not _is_workday(url):
        return False
    # Already has a scoreable JD (rare for Workday, but don't clobber it).
    if _real_word_count(item.get("markdown", "") or "") >= MIN_JD_WORDS:
        return False

    fetched = fetch_description_from_url(url, session=session)
    desc = fetched.get("description", "")
    if _real_word_count(desc) < MIN_JD_WORDS:
        return False  # fetch failed or still too thin → leave for no_description gate

    item["markdown"] = desc
    loc = fetched.get("location", "")
    if loc:
        # Surface the authoritative CXS location in the snippet for the
        # title/snippet-based non-US and US-signal filters that run next.
        item["description"] = f"{loc}. {item.get('description', '') or ''}".strip()
    return True
