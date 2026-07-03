"""
Slug suggesters: given a company name and an existing (broken) slug, generate
ranked candidate slugs likely to be the correct one for each platform.

Each suggester returns an ordered list of candidates (most-likely first). The
caller probes each candidate and stops at the first hit.

Suggestions stay deterministic — no network calls inside the suggester. The
combinatorial cost of probing is bounded by the small list each returns.
"""

from __future__ import annotations

import re
from typing import Iterable


def _company_slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _company_words(name: str) -> list[str]:
    s = re.sub(r"[^A-Za-z0-9]+", " ", name).strip()
    return [w for w in s.split(" ") if w]


def _dedup(seq: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for s in seq:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def suggest_greenhouse(name: str, current: str) -> list[str]:
    base = _company_slug(name)
    words = _company_words(name)
    candidates = [
        current,
        base,
        base + "inc",
        base + "careers",
        base + "jobs",
        "-".join(w.lower() for w in words),
        "".join(w.lower() for w in words) + "1",
        "".join(w.lower() for w in words) + "2",
        base + "1",
        base + "2",
        name.lower(),
    ]
    # Drop the original first-position duplicate; downstream caller already
    # tried the current slug, but we keep it so the suggester is usable
    # standalone.
    return _dedup(candidates)


def suggest_ashby(name: str, current: str) -> list[str]:
    """Ashby slugs are case-sensitive and commonly hyphenated TitleCase."""
    words = _company_words(name)
    lower_words = [w.lower() for w in words]
    cap_words = [w[:1].upper() + w[1:].lower() for w in words]
    candidates = [
        current,
        "-".join(cap_words),       # "Second-Front-Systems"
        "-".join(lower_words),     # "second-front-systems"
        "".join(lower_words),      # "secondfrontsystems"
        "".join(cap_words),        # "SecondFrontSystems"
        name.replace(" ", "-"),
        name.lower().replace(" ", ""),
    ]
    return _dedup(candidates)


def suggest_lever(name: str, current: str) -> list[str]:
    base = _company_slug(name)
    words_lower = [w.lower() for w in _company_words(name)]
    return _dedup([
        current,
        base,
        "-".join(words_lower),
        "".join(words_lower),
    ])


def suggest_smartrecruiters(name: str, current: str) -> list[str]:
    words = _company_words(name)
    cap = "".join(w[:1].upper() + w[1:].lower() for w in words)
    lower = "".join(w.lower() for w in words)
    return _dedup([
        current,
        cap,                # "Procoretechnologies"
        lower,              # "procoretechnologies"
        cap + "1",
        lower + "1",
        cap + "Inc",
        lower + "inc",
        "-".join(w.lower() for w in words),
    ])


def suggest_rippling(name: str, current: str) -> list[str]:
    base = _company_slug(name)
    return _dedup([
        current,
        base,
        "-".join(w.lower() for w in _company_words(name)),
    ])


def suggest_workday(name: str, current: str, career_url: str) -> list[str]:
    """
    Workday slug is '{tenant}.{dc}'. If the current is broken we only suggest
    different datacenter codes — the tenant string is rarely guessable.
    """
    out = [current]
    token = current.split(":", 1)[0]
    if "." in token:
        tenant, dc = token.split(".", 1)
        for alt_dc in ("wd1", "wd2", "wd3", "wd5", "wd103"):
            if alt_dc != dc:
                out.append(f"{tenant}.{alt_dc}")
    return _dedup(out)


def suggest_eightfold(name: str, current: str) -> list[str]:
    sub_current = current.split("|", 1)[0]
    base = _company_slug(name)
    return _dedup([
        current,
        sub_current,
        base,
        f"{base}|{base}.com",
        f"{base}|{base}.ai",
    ])


def suggest_dayforce(name: str, current: str) -> list[str]:
    """
    Dayforce slug is '{clientNamespace}:{jobBoardCode}'. Without the right
    jobBoardCode we cannot guess effectively; try common board codes against
    the current namespace.
    """
    if ":" in current:
        ns, _ = current.split(":", 1)
    else:
        ns = current
    return _dedup([
        current,
        f"{ns}:CANDIDATEPORTAL",
        f"{ns}:CAREERS",
        f"{ns}:JOBS",
        f"{ns}:CAREERPORTAL",
    ])


SUGGESTERS = {
    "greenhouse": suggest_greenhouse,
    "ashby": suggest_ashby,
    "lever": suggest_lever,
    "smartrecruiters": suggest_smartrecruiters,
    "rippling": suggest_rippling,
    "workday": suggest_workday,
    "eightfold": suggest_eightfold,
    "dayforce": suggest_dayforce,
}


def suggest(platform: str, name: str, current: str, career_url: str = "") -> list[str]:
    key = (platform or "").strip().lower()
    fn = SUGGESTERS.get(key)
    if fn is None:
        return [current]
    if key == "workday":
        return fn(name, current, career_url)
    return fn(name, current)
