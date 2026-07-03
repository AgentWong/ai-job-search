"""Regex pre-filter for Firecrawl ATS platform search results.

Deterministically removes obvious non-starters before the LLM sees results.
Applied to raw firecrawl_search output (title + description snippet fields).

Design: prefer false negatives (borderline passes through to LLM) over
false positives (good position wrongly discarded). The LLM handles edge cases.
"""

import re
import yaml
from urllib.parse import urlparse, unquote

from scripts.ats_scraper.location import (
    match_non_us,
    has_us_signal,
    url_segment_is_us,
)


# ---------------------------------------------------------------------------
# Patterns applied to TITLE only — very high confidence
# ---------------------------------------------------------------------------

_TITLE_SENIORITY = re.compile(
    r"\bsenior\b|\bsr\.?\b|\blead\b|\bprincipal\b|\bstaff\b|\bmanager\b|"
    r"\bdirector\b|\barchitect\b|\bhead\s+of\b|\bvp\b|\bvice\s+president\b|"
    r"\bcto\b|\bciso\b|\bfellow\b|\bdistinguished\b|"
    r"\bIII\b|\bIV\b|\bVP\b",
    re.IGNORECASE,
)

_TITLE_WRONG_ROLE = re.compile(
    r"\bbackend\b|\bfull[\s-]?stack\b|\bsoftware\s+engineer\b|"
    r"\bdata\s+(?:engineer|scientist|analyst)\b|"
    r"\bmachine\s+learning\s+engineer\b|"
    r"\bsecurity\s+analyst\b|\bnetwork\s+engineer\b|"
    r"\bqa\s+engineer\b|\bquality\s+assurance\b|"
    r"\bproduct\s+manager\b|\bproject\s+manager\b|"
    r"\bbusiness\s+analyst\b|\bsales\s+engineer\b|"
    r"\baccount\s+executive\b|\bsolutions\s+consultant\b|"
    r"\bdata\s+platform\s+engineer\b",
    re.IGNORECASE,
)

# Blockchain/crypto in title = strong company-type signal
_TITLE_CRYPTO = re.compile(
    r"\bcrypto\b|\bcryptocurrenc\b|\bblockchain\b|\bweb3\b|\bnft\b|\bdefi\b",
    re.IGNORECASE,
)

# Non-US location explicitly appended to title after a dash/pipe separator.
# Pattern: "Job Title - Berlin, Germany" or "Job Title | UK"
_TITLE_NON_US_LOCATION = re.compile(
    r"[-–|,]\s*(?:"
    r"uk|united kingdom|england|scotland|wales|"
    r"germany|france|spain|italy|netherlands|poland|sweden|"
    r"norway|denmark|finland|ireland|switzerland|austria|belgium|"
    r"portugal|czechia|czech republic|romania|hungary|ukraine|turkey|"
    r"india|pakistan|china|japan|korea|singapore|"
    r"australia|new zealand|"
    r"canada|mexico|"
    r"brazil|argentina|colombia|chile|peru|ecuador|latam|"
    r"berlin|london|paris|amsterdam|warsaw|prague|"
    r"bangalore|mumbai|hyderabad|pune|chennai|delhi|"
    r"toronto|montreal|sydney|melbourne"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Patterns applied to DESCRIPTION/SNIPPET — moderate confidence
# ---------------------------------------------------------------------------

# Blockchain/crypto in description = company is likely crypto-focused
_DESC_CRYPTO = re.compile(
    r"\bcryptocurrenc\b|\bblockchain\b|\bweb3\b|\bnft\b|\bdefi\b|\bdao\b",
    re.IGNORECASE,
)

# Unambiguous active-clearance phrases that leave no room for interpretation.
# Does NOT match "ability to obtain" (that's a penalty, not a disqualifier).
_DESC_ACTIVE_CLEARANCE = re.compile(
    r"\bactive\s+(?:secret|top\s+secret|ts/?sci)\s+clearance\b|"
    r"\bcurrently\s+hold(?:s|ing)?\s+(?:a\s+)?(?:secret|top\s+secret)\b|"
    r"\bmust\s+(?:hold|have|possess)\s+(?:an?\s+)?(?:active\s+)?(?:secret|top\s+secret)\b|"
    r"\bcac\s+required\b|"
    r"\bcommon\s+access\s+card\s+required\b|"
    r"\bexisting\s+(?:secret|ts)\s+clearance\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_excluded_companies(exclusions_path: str = "config/exclusions.yml") -> set:
    """Load excluded company names (lowercase) from exclusions.yml."""
    try:
        with open(exclusions_path) as f:
            data = yaml.safe_load(f)
        companies = (data or {}).get("excluded_companies", []) or []
        return {c.lower().strip() for c in companies if c}
    except (FileNotFoundError, yaml.YAMLError):
        return set()


def _url_company_slug(url: str) -> str:
    """Extract a company-like slug from the URL path for exclusion matching."""
    try:
        parts = [p for p in urlparse(url).path.split("/") if p]
        skip = {"jobs", "job", "careers", "career", "apply", "posting", "listings", "Details"}
        for part in parts:
            if part.lower() not in skip and len(part) > 2:
                return part.replace("-", " ").replace("_", " ").lower()
    except Exception:
        pass
    return ""


def _matches_excluded(title: str, url: str, description: str, excluded: set) -> bool:
    """True if any excluded company name appears in the combined searchable text."""
    haystack = f"{title} {description} {_url_company_slug(url)}".lower()
    return any(company in haystack for company in excluded)


def _is_listing_page(url: str) -> bool:
    """True if the URL is an ATS board listing/landing page, not a specific posting.

    Workday's SPA serves the same board URL for the whole career site (e.g.
    `bcbst.wd1.myworkdayjobs.com/External`, title "Search for Jobs"); a real
    posting always has a `/job/<location>/<title>_<reqid>` segment. A
    myworkdayjobs.com URL with no `/job/` path is therefore the board root —
    Firecrawl scrapes the listing markdown for it, which has no JD to score.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host.endswith("myworkdayjobs.com") and "/job/" not in parsed.path:
        return True
    return False


def _workday_location_segment(url: str) -> str:
    """Return the decoded location slug from a Workday /job/<location>/ URL, else ''.

    Workday encodes the posting's location as the path segment immediately after
    `/job/` (e.g. `/job/Singapore-CapitaSky/...`, `/job/Arlington-VA/...`). That
    segment is authoritative for the posting's geography, so matching it against
    the non-US regex catches foreign Workday postings whose title/snippet never
    name the country. Workday-only: other ATS hosts use opaque id/title slugs.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if not (parsed.hostname or "").lower().endswith("myworkdayjobs.com"):
        return ""
    parts = [p for p in parsed.path.split("/") if p]
    if "job" in parts:
        i = parts.index("job")
        if i + 1 < len(parts):
            return unquote(parts[i + 1]).replace("-", " ")
    return ""


# ---------------------------------------------------------------------------
# Listing health — drop dead/expired/un-rendered pages that carry no scoreable
# job description. Firecrawl returns HTTP 200 for soft-404s (Paylocity's "that
# job does not exist", Workday's JS-shell with only nav chrome), so a status
# check alone misses them. The real signal is the scraped CONTENT: a live JD has
# hundreds of words; a dead/un-rendered page has a few dozen of chrome. Without
# this gate the review agent scored these "Base only — no description" = 5 and
# queued them (the 2026-06-02 run queued an expired Paylocity listing + a 404
# Meridian Federal Systems page). Calibrated against that run: real JDs >= 81 words; every dead /
# career-root / un-rendered shell was <= 63. Threshold sits in the gap.
# ---------------------------------------------------------------------------

MIN_JD_WORDS = 70

_SOFT_404 = re.compile(
    r"does not exist|not currently active|no longer (?:available|accepting|active|open)|"
    r"position (?:has been |is )?filled|posting (?:has )?expired|this (?:job|posting|position) (?:is )?closed|"
    r"page (?:not found|cannot be found|doesn'?t exist)|we'?re sorry|"
    r"job (?:opening )?(?:is )?(?:no longer|closed|removed)",
    re.IGNORECASE,
)


def _real_word_count(markdown: str) -> int:
    """Count alphabetic words in markdown after stripping links/images/syntax.

    Workday JS-shells are mostly `[Skip to main content](url)` + image tags +
    bare URLs — high char count, almost no prose. Stripping markup before
    counting is what separates 'rendered chrome' from a real job description.
    """
    md = markdown or ""
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)      # images
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)   # links -> keep anchor text only
    md = re.sub(r"https?://\S+", " ", md)              # bare URLs
    md = re.sub(r"[#*`>\-_|]", " ", md)                # markdown punctuation
    return len(re.findall(r"[A-Za-z]{2,}", md))


def listing_health(result: dict) -> str:
    """Return '' if the result has a scoreable JD, else a rejection reason.

    Reasons: 'dead_listing' (4xx/410 or a soft-404 message on a short page) or
    'no_description' (live-looking but too little prose to score — un-rendered
    SPA shell, career-page root, etc.). Only meaningful when markdown was
    scraped; callers in --no-scrape mode must skip this check.
    """
    md = result.get("markdown", "") or ""
    status = (result.get("metadata") or {}).get("statusCode")
    wc = _real_word_count(md)
    if isinstance(status, int) and status >= 400:
        return "dead_listing"
    if wc < 150 and _SOFT_404.search(md):
        return "dead_listing"
    if wc < MIN_JD_WORDS:
        return "no_description"
    return ""


# ---------------------------------------------------------------------------
# Main filter function
# ---------------------------------------------------------------------------

def filter_result(result: dict, excluded_companies: set, remote_mode: bool) -> tuple:
    """Evaluate one Firecrawl search result.

    Returns (keep: bool, reason: str) where reason is '' when keeping.
    Checks run from highest to lowest confidence so the first match wins.
    """
    title = result.get("title", "") or ""
    description = result.get("description", "") or ""
    url = result.get("url", "") or ""

    if _is_listing_page(url):
        return False, "listing_page"

    if _TITLE_SENIORITY.search(title):
        return False, "senior_title"

    if _TITLE_WRONG_ROLE.search(title):
        return False, "wrong_role_title"

    if _TITLE_CRYPTO.search(title):
        return False, "crypto_title"

    if _TITLE_NON_US_LOCATION.search(title):
        return False, "non_us_title"

    # Non-US embedded in a Workday /job/<location>/ URL segment (authoritative).
    # Guarded so US locales that collide with the regex (Moscow ID, Dublin OH,
    # Paris TX) are deferred to the LLM rather than dropped.
    wd_loc = _workday_location_segment(url)
    if wd_loc and match_non_us(wd_loc) and not url_segment_is_us(wd_loc):
        return False, "non_us_url"

    if _matches_excluded(title, url, description, excluded_companies):
        return False, "excluded_company"

    if _DESC_CRYPTO.search(description):
        return False, "crypto_description"

    if _DESC_ACTIVE_CLEARANCE.search(description):
        return False, "active_clearance"

    # Non-US in the snippet, UNLESS it also names a US locale (multi-locale
    # posting like "US-CO-Remote ... option to work in Spain" — keep for LLM).
    if match_non_us(description) and not has_us_signal(description):
        return False, "non_us_snippet"

    return True, ""
