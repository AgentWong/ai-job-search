"""Direct Firecrawl /v2/search + feedback client.

The credit cost of a search is a property of the REQUEST PARAMETERS, not of who
issues it — a Python call with `scrapeOptions` preserved costs the identical
~2cr/10 the MCP server's call did (verified 2026-06-02). Moving the call here
only removes the raw payload from any LLM context; it does not change billing.

API surface (all verified live 2026-06-02):

  POST {API_BASE}/v2/search
    body: {query, limit, tbs, location, scrapeOptions: {formats, onlyMainContent}}
    resp: {success, data: {web: [{url, title, description, position, markdown}]},
           creditsUsed, id}

  POST {API_BASE}/v2/search/{searchId}/feedback        # 1-credit refund
    body: {rating: "good"|"bad"|"partial", origin,
           valuableSources: [{url, reason?}], missingContent: [{topic, description?}]}
    resp: {success, feedbackId, creditsRefunded, creditsRefundedToday, dailyRefundCap}
    - rating "good"    requires >=1 valuableSources entry
    - rating "bad"     requires >=1 missingContent entry (or querySuggestions)
    - rating "partial" requires valuableSources OR missingContent
    - idempotent per searchId (repeat calls do not double-refund)
    - stops refunding once creditsRefundedToday >= dailyRefundCap (~100/UTC-day)

NOTE: the feedback endpoint is NOT in Firecrawl's public api-reference docs; it
exists only in the firecrawl-mcp-server source. A path/body change upstream would
surface here as a non-200 from submit_feedback() — which is logged, not silently
swallowed (the assessment's one objection to owning this endpoint). If refunds
start failing en masse, switch the orchestrator to the MCP feedback tool
(Option A').
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import requests

API_BASE = "https://api.firecrawl.dev"
FEEDBACK_ORIGIN = "api"
REPO_ROOT = Path(__file__).resolve().parents[2]

# Retry only on transient statuses; 4xx (bad query/body) is a real error.
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class FirecrawlError(RuntimeError):
    """Raised when a Firecrawl request fails after retries or returns non-200."""


def load_api_key() -> str:
    """Resolve FIRECRAWL_API_KEY from the environment, falling back to the key
    stored in the user's ~/.claude.json MCP config for this project.

    The key is never written to disk by this package; it is read at runtime.
    """
    env = os.environ.get("FIRECRAWL_API_KEY")
    if env:
        return env.strip()

    claude_json = Path("~/.claude.json").expanduser()
    try:
        data = json.loads(claude_json.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise FirecrawlError(
            "FIRECRAWL_API_KEY not in environment and ~/.claude.json unreadable: "
            f"{exc}"
        ) from exc

    # Look up the firecrawl MCP server env for this project; fall back to any
    # project that defines it (the key is account-wide, not project-scoped).
    projects = data.get("projects", {})
    candidates = [str(REPO_ROOT)] + [p for p in projects if p != str(REPO_ROOT)]
    for proj in candidates:
        try:
            key = projects[proj]["mcpServers"]["firecrawl"]["env"]["FIRECRAWL_API_KEY"]
        except (KeyError, TypeError):
            continue
        if key:
            return key.strip()

    raise FirecrawlError(
        "FIRECRAWL_API_KEY not found in environment or ~/.claude.json "
        "(projects.*.mcpServers.firecrawl.env.FIRECRAWL_API_KEY)."
    )


class FirecrawlClient:
    def __init__(self, api_key: str | None = None, timeout: int = 180):
        self.api_key = api_key or load_api_key()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def _post(self, path: str, body: dict, *, retries: int = 3) -> dict:
        url = f"{API_BASE}{path}"
        backoff = 2.0
        last_exc: Exception | None = None
        for _ in range(retries):
            try:
                resp = self.session.post(url, json=body, timeout=self.timeout)
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(backoff + random.uniform(0, backoff * 0.25))
                backoff *= 2
                continue
            if resp.status_code in _RETRY_STATUSES:
                last_exc = FirecrawlError(f"{resp.status_code} from {path}: {resp.text[:300]}")
                time.sleep(backoff + random.uniform(0, backoff * 0.25))
                backoff *= 2
                continue
            if resp.status_code != 200:
                # Non-retryable error (e.g. 400 bad query) — surface it.
                raise FirecrawlError(f"{resp.status_code} from {path}: {resp.text[:500]}")
            return resp.json()
        raise FirecrawlError(f"{path} failed after {retries} retries: {last_exc}")

    def search(
        self,
        query: str,
        *,
        limit: int,
        tbs: str | None = None,
        location: str | None = None,
        scrape_markdown: bool = True,
    ) -> dict:
        """Call /v2/search and return the parsed response dict.

        scrapeOptions is preserved by default (the credit-economics constraint):
        it bundles the per-result markdown scrape into the single search call.
        """
        body: dict = {"query": query, "limit": limit}
        if tbs:
            body["tbs"] = tbs
        if location:
            body["location"] = location
        if scrape_markdown:
            body["scrapeOptions"] = {"formats": ["markdown"], "onlyMainContent": True}
        return self._post("/v2/search", body)

    def submit_feedback(
        self,
        search_id: str,
        *,
        valuable_urls: list[str] | None = None,
        missing_topic: str | None = None,
    ) -> dict:
        """Submit the 1-credit refund feedback for a completed search.

        Pass `valuable_urls` (results were useful → rating "good") OR
        `missing_topic` (empty/irrelevant results → rating "bad"). Exactly one
        path is taken; "good" wins if both are supplied and urls are non-empty.

        Returns the parsed response on 200; raises FirecrawlError otherwise so
        a refund failure is visible to the caller (never silently swallowed).
        """
        if valuable_urls:
            body = {
                "rating": "good",
                "origin": FEEDBACK_ORIGIN,
                "valuableSources": [{"url": u} for u in valuable_urls[:10] if u],
            }
        else:
            topic = (missing_topic or "no qualifying US-remote infrastructure roles").strip()
            body = {
                "rating": "bad",
                "origin": FEEDBACK_ORIGIN,
                "missingContent": [{"topic": topic[:200]}],
            }
        # Feedback is cheap + idempotent; one retry is plenty.
        return self._post(f"/v2/search/{search_id}/feedback", body, retries=2)
