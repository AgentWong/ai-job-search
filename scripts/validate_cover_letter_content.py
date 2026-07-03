#!/usr/bin/env python3
"""
Validate a tailored cover letter JSON against writing-style rules.

Mirrors `validate_resume_content.py` for the cover-letter agents. The agent
prompts spell out the constraints in prose; the agents have been observed to
self-report "word_count_verified: true" while still violating them. This is the
hard gate.

Auto-detects variant from JSON shape:
  - has `paragraphs` key  -> pitch       (150-250 words)
  - has `requirements` key -> point-by-point (350-425 words)

Hard fails (exit 1):
  - Word count outside target range for the detected variant
  - Em dashes (U+2014) anywhere in content
  - "Happy to ..." phrasing (recognized LLM tell; see memory feedback_no_happy_to)
  - Banned AI words / phrases (leveraged, spearheaded, thrilled, etc.)
  - Variant could not be detected (missing both paragraphs and requirements)

Pass (exit 0):
  - All checks pass; prints PASS line and word count to stdout

Usage:
    .venv/bin/python scripts/validate_cover_letter_content.py <cover_letter.json>
    .venv/bin/python scripts/validate_cover_letter_content.py <cover_letter.json> --variant pitch
"""

import argparse
import json
import re
import sys
from pathlib import Path


WORD_COUNT_RANGES = {
    "point_by_point": (350, 425),
    "pitch": (125, 250),
}

# Banned words/phrases. Single tokens get \b-bounded; multi-word phrases match
# as literal substrings (case-insensitive). Sourced from:
#   - cover-letter.agent.md (Step 0 writing style)
#   - cover-letter-pitch.agent.md (Step 0 writing style)
#   - resume validator BANNED_AI_WORDS (shared writing-style guide)
BANNED_AI_WORDS = [
    "leveraged", "leveraging",
    "spearheaded",
    "streamlined", "streamlining",
    "facilitated", "facilitating",
    "championed",
    "cultivated",
    "synergized",
    "cutting-edge",
    "cross-functional collaboration",
    "proven track record",
    "passionate about",
    "results-driven",
    "transformative impact",
    "stakeholder engagement",
    "dynamic environment",
    "dynamic team",
    "thrilled",
    "eager to contribute",
    "esteemed organization",
    "comprehensive suite",
    "drive operational excellence",
    "operational excellence",
]

# "Happy to ..." opener is the LLM tell. Match it at sentence start or
# anywhere preceded by whitespace/punctuation.
_HAPPY_TO = re.compile(r"(?:^|[\s\.\!\?\,\;\:\"\'])(happy to\b)", re.IGNORECASE)


def detect_variant(data: dict, override: str | None) -> str:
    if override:
        if override not in WORD_COUNT_RANGES:
            raise SystemExit(f"ERROR: unknown variant '{override}'. "
                             f"Choices: {list(WORD_COUNT_RANGES)}")
        return override
    if "paragraphs" in data and isinstance(data["paragraphs"], list):
        return "pitch"
    if "requirements" in data and isinstance(data["requirements"], list):
        return "point_by_point"
    raise SystemExit(
        "ERROR: cannot detect cover-letter variant. JSON must have either "
        "`paragraphs` (pitch) or `requirements` (point-by-point) array."
    )


def collect_content_text(data: dict, variant: str) -> str:
    """Concatenate all rendered text fields. Excludes signature contact info."""
    pieces: list[str] = []
    pieces.append(data.get("recipient", ""))

    if variant == "pitch":
        for p in data.get("paragraphs", []) or []:
            if isinstance(p, str):
                pieces.append(p)
    else:
        pieces.append(data.get("opening", ""))
        for req in data.get("requirements", []) or []:
            if not isinstance(req, dict):
                continue
            pieces.append(req.get("requirement", ""))
            for b in req.get("bullets", []) or []:
                if isinstance(b, str):
                    pieces.append(b)
        pieces.append(data.get("closing", ""))

    sig = data.get("signature") or {}
    if isinstance(sig, dict):
        # Include the name only (contact info doesn't count toward style/word checks)
        pieces.append(sig.get("name", ""))

    return " ".join(p for p in pieces if p)


def count_words(text: str) -> int:
    clean = re.sub(r"\*\*", "", text)
    return len(clean.split())


def validate(json_path: Path, variant_override: str | None) -> list[str]:
    errors: list[str] = []
    with open(json_path) as f:
        data = json.load(f)

    variant = detect_variant(data, variant_override)
    text = collect_content_text(data, variant)

    wc = count_words(text)
    lo, hi = WORD_COUNT_RANGES[variant]
    if wc < lo or wc > hi:
        errors.append(
            f"Word count {wc} outside {variant} target range [{lo}, {hi}]"
        )

    if "—" in text:
        contexts = [m.group() for m in re.finditer(r".{0,20}—.{0,20}", text)]
        errors.append(f"Em dash (—) found in content. Context(s): {contexts[:3]}")

    happy_matches = _HAPPY_TO.findall(text)
    if happy_matches:
        # Surface a short context so the user can see where the phrase landed
        ctxs = [m.group() for m in re.finditer(r".{0,30}happy to\b.{0,30}", text, re.IGNORECASE)]
        errors.append(
            f"'Happy to' phrasing found ({len(happy_matches)}x) — banned LLM tell. "
            f"Context(s): {ctxs[:3]}"
        )

    for phrase in BANNED_AI_WORDS:
        if " " in phrase or "-" in phrase:
            pattern = re.escape(phrase)
        else:
            pattern = rf"\b{re.escape(phrase)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            errors.append(f"Banned AI word/phrase '{phrase}' present in content")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate a tailored cover letter JSON against writing-style rules."
    )
    parser.add_argument("json_path", type=Path, help="Path to cover letter content JSON")
    parser.add_argument(
        "--variant",
        choices=list(WORD_COUNT_RANGES.keys()),
        default=None,
        help="Force a specific variant. Auto-detected from JSON shape if omitted.",
    )
    args = parser.parse_args()

    if not args.json_path.exists():
        print(f"ERROR: JSON file not found: {args.json_path}", file=sys.stderr)
        sys.exit(2)

    errors = validate(args.json_path, args.variant)
    if errors:
        print(f"FAIL — {len(errors)} validation error(s) in {args.json_path.name}:",
              file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.json_path) as f:
        data = json.load(f)
    variant = detect_variant(data, args.variant)
    text = collect_content_text(data, variant)
    print(f"PASS — {args.json_path.name} ({count_words(text)} words, variant={variant})")


if __name__ == "__main__":
    main()
