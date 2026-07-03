"""
Shared location / work-arrangement filtering for every scraper (ATS, Built In,
LinkedIn).

This module is the single source of truth for the location regexes that used to
be copy-pasted into each scraper's filters.py, plus the mode-aware decision
logic driven by config.yml `location`:

    location:
      remote: true   -> fully-remote US jobs (current behavior). `state` is the
                        candidate's residence and drives the state-restriction
                        eligibility check (replaces the old hard-coded Oregon).
      remote: false  -> local jobs in `city, state` (target metro). Hybrid/on-site
                        are acceptable; fully-remote US jobs are kept too unless
                        `accept_remote_in_local_mode: false`.

The deterministic checks here are the AUTHORITATIVE gate. The *-llm-review agents
are the fuzzy catch for anything the regexes miss (unmapped metro spellings,
eligible-state lists in prose, etc.).
"""

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Work-arrangement signals
# ---------------------------------------------------------------------------

_REMOTE_ACCEPT = re.compile(r"\bremote\b", re.IGNORECASE)

# workplace_type values that count as remote (from ATS structured fields)
_REMOTE_WORKPLACE_TYPES = frozenset({"remote", "fully_remote", "fully remote"})

# Hybrid / on-site signals. Superset of the three former copies (ats_scraper used
# the shorter `hybrid|on.site|onsite`; builtin/linkedin added in.office/in.person).
_NON_REMOTE = re.compile(
    r"\bhybrid\b|\bon.site\b|\bonsite\b|\bin.office\b|\bin.person\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Non-US geography tokens (canonical superset — formerly duplicated verbatim in
# builtin_scraper/filters.py and linkedin_scraper/filters.py; broader than the
# old ats_scraper list). Word-boundary matching so "us" in "us-east" doesn't
# false-match. Note a few tokens collide with rare US place names (Ontario CA,
# Manchester NH, Lima OH, Peru IN) — an accepted recall/precision tradeoff the
# LLM-review pass cleans up.
# ---------------------------------------------------------------------------
_NON_US_REJECT = re.compile(
    r"\b("
    # Countries / regions
    r"canada|toronto|vancouver|montreal|calgary|ottawa|edmonton|"
    r"alberta|ontario|quebec|british\s+columbia|"
    r"mexico|mexico\s+city|guadalajara|monterrey|"
    r"brazil|brasil|sao\s+paulo|rio\s+de\s+janeiro|"
    r"argentina|buenos\s+aires|chile|santiago|colombia|bogota|peru|lima|"
    r"uruguay|el\s+salvador|costa\s+rica|guatemala|honduras|nicaragua|"
    r"latam|latin\s+america|south\s+america|central\s+america|"
    r"united\s+kingdom|england|scotland|wales|"
    r"london|manchester|edinburgh|dublin|ireland|"
    r"germany|berlin|munich|hamburg|frankfurt|cologne|"
    r"france|paris|lyon|"
    r"netherlands|amsterdam|spain|madrid|barcelona|"
    r"italy|rome|milan|portugal|lisbon|"
    r"poland|warsaw|krakow|romania|bucharest|ukraine|kyiv|"
    # Central / Eastern Europe + Nordics (were missing — caused czechia/prague
    # Workday + snippet misses in the 2026-06-02 run). Bare city tokens that
    # collide with US place names (vienna VA, geneva IL/NY, athens GA/OH) are
    # deliberately OMITTED — country name only — so the US-presence guard isn't
    # needed to rescue them.
    r"czechia|czech\s+republic|prague|brno|slovakia|bratislava|"
    r"sweden|stockholm|norway|oslo|denmark|copenhagen|finland|helsinki|"
    r"switzerland|zurich|austria|belgium|brussels|hungary|budapest|"
    r"luxembourg|"
    r"turkey|istanbul|israel|tel\s+aviv|"
    r"emea|europe|european\s+union|eu\s+region|"
    r"india|bangalore|hyderabad|mumbai|delhi|chennai|pune|"
    r"japan|tokyo|osaka|china|beijing|shanghai|shenzhen|"
    r"hong\s+kong|taiwan|taipei|"
    r"philippines|manila|vietnam|ho\s+chi\s+minh|hanoi|"
    r"indonesia|jakarta|thailand|bangkok|malaysia|kuala\s+lumpur|"
    r"singapore|south\s+korea|seoul|"
    r"apac|asia\s+pacific|asia.pacific|"
    r"australia|sydney|melbourne|new\s+zealand|auckland|wellington|"
    r"uae|dubai|abu\s+dhabi|saudi\s+arabia|riyadh|"
    r"south\s+africa|johannesburg|cape\s+town|"
    r"egypt|cairo|nigeria|lagos|kenya|nairobi"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# US-presence signals — RESCUE a posting from a non-US match when the text also
# clearly names a US locale. `_NON_US_REJECT` deliberately collides with a few
# US place names (Ontario CA, Manchester NH, Paris TX, Moscow ID, Dublin OH,
# Prague OK, Lima OH, Peru IN...). These guards keep such postings out of the
# deterministic drop bucket and defer them to the LLM-review pass — honoring the
# "prefer false negatives over false positives" rule for the URL/snippet scans.
# ---------------------------------------------------------------------------

# 2-letter USPS state abbreviations as whole-word tokens. Reliable inside a
# structured URL location segment ("Arlington VA"); too noisy for free prose
# ("OR"/"IN"/"ME" as ordinary words) — hence not used by has_us_signal().
_US_STATE_ABBR = re.compile(
    r"\b(?:A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|"
    r"N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])\b"
)

# Full US state names — safe in prose; rescues "offices in London and New York".
_US_STATE_NAME = re.compile(
    r"\b(?:alabama|alaska|arizona|arkansas|california|colorado|connecticut|"
    r"delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|"
    r"kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|"
    r"mississippi|missouri|montana|nebraska|nevada|new\s+hampshire|"
    r"new\s+jersey|new\s+mexico|new\s+york|north\s+carolina|north\s+dakota|"
    r"ohio|oklahoma|oregon|pennsylvania|rhode\s+island|south\s+carolina|"
    r"south\s+dakota|tennessee|texas|utah|vermont|virginia|washington|"
    r"west\s+virginia|wisconsin|wyoming)\b",
    re.IGNORECASE,
)

# Explicit US-country / US-remote phrasings. Safe in free prose.
_US_PRESENCE = re.compile(
    r"\bunited\s+states\b|\bu\.?s\.?a\.?\b|\bus[-\s](?:remote|based|only|wide)\b|"
    r"\bremote\s*[-,]\s*us\b|\bus-[a-z]{2}\b",
    re.IGNORECASE,
)

# "City, ST" — the canonical US address shape. Anchors a bare state abbr to a
# preceding city so "Dublin, OH" reads as US but a stray "OR"/"IN" does not.
_US_CITY_STATE = re.compile(
    r"[A-Za-z][A-Za-z.\s]{2,},\s*"
    r"(?:A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|"
    r"N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])\b"
)


def has_us_signal(text: str) -> bool:
    """True if `text` clearly names a US locale (country phrasing, state name,
    or City, ST).

    The snippet-scan guard: a result whose snippet matches a non-US token but
    ALSO carries a US signal (e.g. 'US-CO-Remote ... option to work in Spain')
    is a multi-locale posting — keep it for the LLM rather than dropping blindly.
    Deliberately does NOT trust a bare 2-letter abbr in prose (too noisy).
    """
    t = text or ""
    return bool(
        _US_PRESENCE.search(t) or _US_STATE_NAME.search(t) or _US_CITY_STATE.search(t)
    )


def url_segment_is_us(segment: str) -> bool:
    """True if a (hyphen-decoded) URL location segment names a US locale.

    The Workday `/job/<location>/` guard. Segments are location-only and
    structured, so a whole-word state abbr ('Arlington VA', 'Moscow ID') is a
    reliable US signal here even though it would be too noisy in free prose.
    """
    s = segment or ""
    return bool(_US_PRESENCE.search(s) or _US_STATE_NAME.search(s) or _US_STATE_ABBR.search(s))


# ---------------------------------------------------------------------------
# Config object
# ---------------------------------------------------------------------------
@dataclass
class LocationConfig:
    """Resolved view of the config.yml `location` block.

    Defaults reproduce the historical hard-coded behavior (remote-US search from
    Oregon) so a config without a `location:` block is fully backward compatible.
    """
    remote: bool = True
    city: str = ""
    state: str = "Oregon"
    state_abbr: str = "ID"
    accept_remote_in_local_mode: bool = True
    # Search radius (miles) around city/state in local mode. Translated per-platform
    # by each search-URL builder: LinkedIn `distance`, Hiring Cafe
    # `options.radius`. Built In (metro-hub) ignores it.
    distance_miles: int = 25
    geo_codes: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, cfg: dict) -> "LocationConfig":
        loc = (cfg or {}).get("location") or {}
        return cls(
            remote=bool(loc.get("remote", True)),
            city=(loc.get("city") or "").strip(),
            state=(loc.get("state") or "Oregon").strip(),
            state_abbr=(loc.get("state_abbr") or "ID").strip(),
            accept_remote_in_local_mode=bool(loc.get("accept_remote_in_local_mode", True)),
            distance_miles=int(loc.get("distance_miles", 25) or 25),
            geo_codes={k: (v or "") for k, v in (loc.get("geo_codes") or {}).items()},
        )

    def describe(self) -> str:
        """Short one-line mode summary for CLI startup logs."""
        if self.remote:
            return f"remote (US, residence {self.state})"
        loc = ", ".join(p for p in (self.city, self.state) if p) or "(unset!)"
        extra = " +remote" if self.accept_remote_in_local_mode else ""
        return f"local {loc}{extra}"

    def require_geo_code(self, key: str, platform: str) -> str:
        """Return a required geo code, or raise a clear error if it's missing.

        Used by the search-URL builders in local mode so we fail loudly instead
        of silently searching the wrong (US-wide) geography.
        """
        val = (self.geo_codes.get(key) or "").strip()
        if not val:
            target = ", ".join(p for p in (self.city, self.state) if p) or "your target metro"
            raise ValueError(
                f"location.geo_codes.{key} is required for {platform} local-mode "
                f"search (location.remote: false). Look up the {platform} code for "
                f"'{target}' and set it in config/config.yml."
            )
        return val


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def build_state_restrict_pattern(state: str) -> re.Pattern:
    """Compile the description-scan pattern for state-restricted-remote postings.

    For state="Oregon" this reproduces the former hard-coded _IDAHO_RESTRICT
    exactly: `not available in idaho | except idaho | excluding idaho`.
    Only the full state name is matched (not the 2-letter abbr) to avoid the
    false positives a bare "ID"/"WA" token would cause — eligible-state lists
    that omit the state are left to the fuzzy LLM-review pass.
    """
    s = re.escape(state.strip())
    return re.compile(
        rf"not\s+available\s+in\s+{s}|except\s+{s}|excluding\s+{s}",
        re.IGNORECASE,
    )


def is_remote(location: str, workplace_type: str = "") -> bool:
    """True if the location string or workplace_type signals a remote role."""
    if _REMOTE_ACCEPT.search(location or ""):
        return True
    return (workplace_type or "").lower() in _REMOTE_WORKPLACE_TYPES


# Explicit remote-work phrasings in the body of a job description. Tighter than a
# bare "remote" substring (which matches "remote ground stations", "remote
# environments" — physical-distance uses, not work-arrangement). Used as the
# description half of the post-fetch remote gate.
_DESC_REMOTE = re.compile(
    r"\bfully[-\s]remote\b|\b100%\s*remote\b|\bremote[-\s]first\b|"
    r"\bwork\s+from\s+home\b|\bwork\s+remotely\b|\bremote\s+position\b|"
    r"\bremote\s+role\b|\bremote\s+work\b|\bremote\s+opportunity\b|"
    r"\bthis\s+is\s+a\s+remote\b|\bus[-\s]remote\b|\bremote[-\s]us\b|"
    r"\btelecommut\w*\b|\bremote\s+\(us\b|\bremote\s*-\s*united\s+states\b",
    re.IGNORECASE,
)


def description_has_remote_signal(description: str) -> bool:
    """True if the description body explicitly describes a remote arrangement.

    Deliberately stricter than `is_remote()`'s bare-word match so physical-
    distance uses of "remote" (ground stations, austere remote environments)
    don't read as a remote work arrangement.
    """
    return bool(_DESC_REMOTE.search(description or ""))


def posting_has_remote_signal(
    location: str, workplace_type: str, description: str
) -> bool:
    """True if a fetched posting carries a remote signal anywhere.

    Combines the location/workplace_type structured check with the stricter
    description-body scan. This is the post-fetch remote gate used by card-based
    scrapers (LinkedIn) whose search-URL `remote` param is leaky: the API returns
    fixed-metro on-site cards even with f_WT=2, so we must verify against the most
    authoritative text we have rather than trusting the search param.
    """
    if is_remote(location, workplace_type):
        return True
    return description_has_remote_signal(description)


def match_non_us(location: str) -> str:
    """Return the matched non-US token (for human-readable reason strings), else ''."""
    m = _NON_US_REJECT.search(location or "")
    return m.group(0) if m else ""


def match_non_remote(location: str) -> str:
    """Return the matched hybrid/on-site token, else ''."""
    m = _NON_REMOTE.search(location or "")
    return m.group(0) if m else ""


def location_matches_metro(location: str, loc_cfg: LocationConfig) -> bool:
    """True if `location` looks like it's in the configured city/state.

    Deliberately generous (favor recall — the search URL already constrains the
    metro, and the LLM-review pass prunes false positives): matches if any
    pipe-separated segment contains the city name, the full state name, or the
    state abbreviation as a whole word (so "TX" doesn't match inside a word).
    """
    if not location:
        return False
    segments = [s.strip() for s in location.split("|")]
    city = loc_cfg.city.lower().strip()
    state = loc_cfg.state.lower().strip()
    abbr_re = (
        re.compile(rf"\b{re.escape(loc_cfg.state_abbr.strip())}\b", re.IGNORECASE)
        if loc_cfg.state_abbr.strip()
        else None
    )
    for seg in segments:
        seg_l = seg.lower()
        if city and city in seg_l:
            return True
        if state and state in seg_l:
            return True
        if abbr_re and abbr_re.search(seg):
            return True
    return False


def local_card_kept_by_metro(location: str, loc_cfg: LocationConfig) -> bool:
    """Whether to KEEP a non-remote card in local mode, given how the search ran.

    For scrapers whose SEARCH URL is already geo-constrained (LinkedIn `distance`,
    Built In metro hub), a strict city/state-name match is the
    WRONG post-filter once a radius is in play: a `distance_miles` search around
    Portland, OR legitimately returns Clarkston/Asotin WA (same metro, across the
    river) and Moscow/Pullman — none of which contain "Portland/Oregon/ID". Strict
    matching would discard exactly what the radius was set to include.

    So: when `loc_cfg.distance_miles` is set, TRUST the radius-constrained search
    and keep any non-empty, in-US, non-remote card (the non-US and non-remote
    gates run upstream of this call); the LLM-review pass prunes true outliers.
    With distance unset/0 (exact-city search), fall back to the strict metro-name
    match.

    NOTE: this is for radius/metro-URL scrapers ONLY. The ATS scraper pulls every
    job from a board with NO geo URL to trust, so `location_verdict` keeps using
    the strict `location_matches_metro` directly.
    """
    if loc_cfg.distance_miles:
        return True
    return location_matches_metro(location, loc_cfg)


def location_verdict(
    location: str,
    workplace_type: str,
    description: str,
    loc_cfg: LocationConfig,
) -> tuple[bool, str]:
    """Authoritative location verdict for a posting.

    Returns (keep, reason). `reason` is "" when keep=True, otherwise a snake_case
    rejection bucket consumed by the ATS filter funnel / data_analysis:
      remote mode:  hybrid_or_onsite | non_us_geography | no_remote_signal | state_restriction
      local mode:   non_us_geography | remote_not_local | wrong_metro

    NOTE: this requires a positive remote signal in remote mode and is the verdict
    used by the ATS scraper, which pulls *every* job from a board. The Built In /
    LinkedIn card filters trust their remote/metro search URL and instead compose
    the shared regexes + helpers above directly (see their filters.py).
    """
    loc = location or ""
    wtype = (workplace_type or "").lower()
    desc = description or ""

    if loc_cfg.remote:
        # ----- REMOTE-ONLY MODE (state-restriction is now config-driven) -----
        if _NON_REMOTE.search(loc):
            return False, "hybrid_or_onsite"
        if _NON_US_REJECT.search(loc) and not has_us_signal(loc):
            return False, "non_us_geography"
        if not is_remote(loc, wtype):
            return False, "no_remote_signal"
        if desc and loc_cfg.state and build_state_restrict_pattern(loc_cfg.state).search(desc):
            return False, "state_restriction"
        return True, ""

    # ----- LOCAL MODE (target = loc_cfg.city, loc_cfg.state) -----
    if not loc.strip():
        # Missing location — can't assess; defer to the LLM-review / detail pass.
        return True, ""
    if _NON_US_REJECT.search(loc) and not has_us_signal(loc):
        return False, "non_us_geography"
    if is_remote(loc, wtype):
        if loc_cfg.accept_remote_in_local_mode:
            return True, ""
        return False, "remote_not_local"
    if location_matches_metro(loc, loc_cfg):
        return True, ""
    return False, "wrong_metro"
