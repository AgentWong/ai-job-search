"""Normalize ATS_Platform values from curation reports to scraper registry keys.

The Claude Desktop curation prompt describes platforms by their full marketing
name ("Oracle Recruiting Cloud", "Breezy HR", "Dayforce HCM") in some places
and by their canonical short form ("Oracle", "Breezy", "Dayforce") in others.
The curation LLM occasionally emits the verbose form into the CSV's ATS_Platform
column, which the scraper's PLATFORM_REGISTRY lookup (lowercased) does not match.

Map common verbose aliases back to the canonical short form before append.
"""

from __future__ import annotations


PLATFORM_ALIASES: dict[str, str] = {
    "oracle recruiting cloud": "Oracle",
    "orc": "Oracle",
    "breezy hr": "Breezy",
    "breezyhr": "Breezy",
    "dayforce hcm": "Dayforce",
    "ceridian dayforce": "Dayforce",
    "trakstar hire": "Trakstar",
    "recruiterbox": "Trakstar",
    "gem ats": "Gem",
    "smart recruiters": "SmartRecruiters",
    "bamboo hr": "BambooHR",
    "bamboohr ats": "BambooHR",
}


def normalize_platform(value: str) -> str:
    """Map a verbose ATS platform name to its canonical short form.

    Returns the input unchanged when no alias matches, so canonical values
    (e.g. "Oracle", "Greenhouse") and intentional sentinels (e.g. "disabled",
    "Unknown") pass through untouched.
    """
    if not value:
        return value
    key = value.strip().lower()
    return PLATFORM_ALIASES.get(key, value.strip())


def normalize_rows(rows: list[dict[str, str]]) -> list[str]:
    """Rewrite each row's ATS_Platform in place; return list of (name, before, after)
    tuples for changed rows so the caller can log them.
    """
    changes: list[str] = []
    for row in rows:
        before = row.get("ATS_Platform", "")
        after = normalize_platform(before)
        if after != before:
            row["ATS_Platform"] = after
            name = row.get("Company_Name", "").strip() or "(unnamed)"
            changes.append(f"{name}: '{before}' -> '{after}'")
    return changes
