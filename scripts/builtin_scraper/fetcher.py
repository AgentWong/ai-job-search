"""Re-export LinkedIn's generic rate-limited HTTP session for Builtin use.

The class is platform-agnostic. Keeping a local module name lets the rest of
the builtin_scraper package use relative imports (`.fetcher`) without
referencing linkedin_scraper directly.
"""
from scripts.linkedin_scraper.fetcher import RateLimitedSession, RateLimitError, USER_AGENTS

__all__ = ["RateLimitedSession", "RateLimitError", "USER_AGENTS"]
