"""Build the Firecrawl query queue from config/config.yml.

Ports the query-construction logic that previously lived in the
ats-platform-search orchestrator prompt and the firecrawl-job-search agent
prompt into deterministic code, so the search subagent (and its raw-payload
context cost) can be removed entirely.

Board tiers drive query SHAPE:
  - primary + watch boards  -> one individual query each (own result pool)
  - secondary boards        -> one bundled `(site:a OR site:b ...)` query

Role tiers drive query PHASE (the orchestrator runs primary-role queries first,
then secondary-role queries only if the target count is not yet met):
  - "primary"   queries search the primary role OR-group across every board
  - "secondary" queries search the secondary role OR-group across every board
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from scripts.ats_scraper.location import LocationConfig

# Negative-term tail, verbatim from the firecrawl-job-search agent's query
# template. Trims senior/wrong-role/crypto noise at the Google layer so they
# never consume a result slot.
NEGATIVE_TERMS = (
    "-intitle:senior -intitle:lead -intitle:principal -intitle:manager "
    "-intitle:director -intitle:architect -intitle:backend -intitle:fullstack "
    "-intitle:software -intitle:staff -intitle:Jobgether -inurl:senior "
    "-inurl:manager -blockchain -crypto -web3"
)


@dataclass
class Query:
    query_number: int          # global, stable across tiers (primary first)
    tier: str                  # role tier: "primary" | "secondary"
    roles: list[str]           # role names for attribution
    board_label: str           # display label (domain or "bundled-secondary(...)")
    bundled_domains: list[str]  # one domain (individual) or many (bundled)

    @property
    def role_terms(self) -> str:
        """Parenthesized OR-group of individually-quoted role names."""
        return "(" + " OR ".join(f'"{r}"' for r in self.roles) + ")"


def _site_clause(domains: list[str]) -> str:
    if len(domains) == 1:
        return f"site:{domains[0]}"
    return "(" + " OR ".join(f"site:{d}" for d in domains) + ")"


def build_query_string(query: Query, loc_cfg: LocationConfig) -> str:
    """Assemble the full Firecrawl `query` string for a Query."""
    if loc_cfg.remote:
        work_clause = '"remote"'
    else:
        work_clause = f'"{loc_cfg.city}"'
    parts = [_site_clause(query.bundled_domains), query.role_terms, work_clause, NEGATIVE_TERMS]
    return " ".join(p for p in parts if p)


def search_location(loc_cfg: LocationConfig) -> str:
    """The Firecrawl `location` soft-geo-targeting parameter."""
    if loc_cfg.remote:
        return "United States"
    return ", ".join(p for p in (loc_cfg.city, loc_cfg.state) if p)


def _role_names(cfg: dict, bucket: str) -> list[str]:
    roles_cfg = (cfg or {}).get("target_roles") or {}
    names: list[str] = []
    for entry in roles_cfg.get(bucket) or []:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if name:
            names.append(name.strip())
    return names


def _board_domains(cfg: dict, tier: str) -> list[str]:
    boards_cfg = (cfg or {}).get("job_boards") or {}
    out: list[str] = []
    for entry in boards_cfg.get(tier) or []:
        domain = entry.get("domain") if isinstance(entry, dict) else entry
        if domain:
            out.append(domain.strip())
    return out


def build_queue(cfg: dict, loc_cfg: LocationConfig | None = None) -> list[Query]:
    """Build the full, globally-numbered query queue (both role tiers).

    Numbering is stable: primary-role queries get 1..K, secondary-role queries
    get K+1..N — so q{NN}_*.json filenames never collide regardless of which
    tier is executed in a given invocation.

    In local mode (loc_cfg.remote is False) the high-noise `local_only` roles
    are folded into the secondary OR-group, so they ride the existing secondary
    queries (no extra Firecrawl credits / no new query slots); in remote mode
    they're skipped entirely. A None loc_cfg defaults to remote-US for backward
    compatibility.
    """
    if loc_cfg is None:
        loc_cfg = LocationConfig()
    primary_roles = _role_names(cfg, "primary")
    secondary_roles = _role_names(cfg, "secondary")
    if not loc_cfg.remote:
        secondary_roles = secondary_roles + _role_names(cfg, "local_only")

    individual_boards = _board_domains(cfg, "primary") + _board_domains(cfg, "watch")
    bundled_boards = _board_domains(cfg, "secondary")
    bundled_label = (
        "bundled-secondary(" + ",".join(bundled_boards) + ")" if bundled_boards else ""
    )

    def _tier_queue(roles: list[str], tier: str, start: int) -> list[Query]:
        queue: list[Query] = []
        n = start
        for domain in individual_boards:
            queue.append(Query(n, tier, roles, domain, [domain]))
            n += 1
        if bundled_boards:
            queue.append(Query(n, tier, roles, bundled_label, list(bundled_boards)))
            n += 1
        return queue

    queue: list[Query] = []
    if primary_roles:
        queue.extend(_tier_queue(primary_roles, "primary", 1))
    if secondary_roles:
        queue.extend(_tier_queue(secondary_roles, "secondary", len(queue) + 1))
    return queue


# ---------------------------------------------------------------------------
# Deterministic attribution (formerly LLM-side board_stats / role_stats)
# ---------------------------------------------------------------------------

def _normalize_base(domain: str) -> str:
    """Strip a leading wildcard so '*.applytojob.com' -> 'applytojob.com'."""
    return domain[2:] if domain.startswith("*.") else domain


def attribute_board(url: str, bundled_domains: list[str]) -> str:
    """Map a result URL back to its source domain within the query's bundle.

    Suffix-match (host == base or host endswith '.'+base) so wildcard entries
    like '*.applytojob.com' catch 'bluevoyant.applytojob.com', and bare entries
    like 'icims.com' catch 'careers-foo.icims.com'. Returns 'unmatched' if no
    bundled domain claims the host (rare adjacent Google hits).
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        host = ""
    if not host:
        return "unmatched"
    for domain in bundled_domains:
        base = _normalize_base(domain).lower()
        if host == base or host.endswith("." + base):
            return domain
    return "unmatched"


def attribute_role(title: str, roles: list[str]) -> str:
    """Assign a result title to the most specific matching role term.

    Longest matching role name wins (so 'Cloud Infrastructure Engineer' maps to
    'Infrastructure Engineer' over a looser match). Falls back to the first role
    in the OR-group when nothing matches.
    """
    title_l = (title or "").lower()
    best = ""
    for role in roles:
        if role.lower() in title_l and len(role) > len(best):
            best = role
    if best:
        return best
    return roles[0] if roles else ""
