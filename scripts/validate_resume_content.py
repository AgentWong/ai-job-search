#!/usr/bin/env python3
"""
Validate a tailored resume JSON against tailoring rules.

Hard fails (exit 1):
- Word count outside target range
- 1-page resume with a summary section, or 2-page without one
- 2-page summary sentence count != 2
- Summary contains banned catch-all phrases ("Background spans", "Skilled in", etc.)
- Em dashes (U+2014) present in resume content
- AI-flagged words present in resume content (Leveraged, Spearheaded, ...)
- Conditional acronyms (NGFW, IRSA, MDT/WDS, etc.) appear in resume but NOT in job posting
- Equivalence annotations ("(comparable to X)", "(X-equivalent ...)") reference a
  tool name that does NOT appear in the job posting

Pass (exit 0):
- All checks pass; prints PASS line and word count to stdout

Usage:
    .venv/bin/python scripts/validate_resume_content.py <resume_json> --type 1page|2page [--posting <posting_path>]

Example:
    .venv/bin/python scripts/validate_resume_content.py \\
        resumes/generated/tailored/Alex_Johnson_Foo_Bar_content_2page.json \\
        --type 2page \\
        --posting "config/target_jobs/Foo - Bar.md"
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


WORD_COUNT_RANGES = {
    "1page": (400, 475),
    "2page": (800, 900),
}

CONDITIONAL_ACRONYMS = [
    "NGFW", "NDES", "SubCA", "IKE", "BGP", "DAG", "BITS", "ADAM", "NLA",
    "MDT", "WDS", "PXE", "IRSA", "VxRail", "DSC", "vROPs", "vLOG",
]

BANNED_SUMMARY_PHRASES = [
    "Background spans",
    "Background covers",
    "Background includes",
    "Skilled in",
    "Proficient in",
    "Specialties include",
    "Areas of expertise",
]

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
]


def _walk_text(data: dict, include_metadata: bool):
    pieces = []
    if include_metadata:
        pieces.append(data.get("name", ""))
        for c in data.get("contact", []):
            pieces.append(c)
    for section in data.get("sections", []):
        if include_metadata:
            pieces.append(section.get("title", ""))
        t = section.get("type", "")
        if t == "summary":
            pieces.append(section.get("content", ""))
        elif t == "experience":
            for entry in section.get("entries", []):
                if include_metadata:
                    pieces.append(entry.get("company", ""))
                    pieces.append(entry.get("location", ""))
                    pieces.append(entry.get("dates", ""))
                pieces.append(entry.get("role", ""))
                for b in entry.get("bullets", []):
                    pieces.append(b)
        elif t == "projects":
            for entry in section.get("entries", []):
                pieces.append(entry.get("name", ""))
                if include_metadata:
                    pieces.append(entry.get("date", ""))
                if "bullets" in entry:
                    for b in entry["bullets"]:
                        pieces.append(b)
                elif "bullet" in entry:
                    pieces.append(entry["bullet"])
        elif t == "table":
            for row in section.get("rows", []):
                pieces.append(" ".join(row))
        elif t == "education" and include_metadata:
            for entry in section.get("entries", []):
                pieces.append(entry.get("institution", ""))
                pieces.append(entry.get("location", ""))
                pieces.append(entry.get("degree", ""))
                pieces.append(entry.get("field", ""))
                pieces.append(entry.get("date", ""))
    return pieces


def count_words(data: dict) -> int:
    full_text = " ".join(_walk_text(data, include_metadata=True))
    clean = re.sub(r"\*\*", "", full_text)
    return len(clean.split())


def collect_content_text(data: dict) -> str:
    return " ".join(_walk_text(data, include_metadata=False))


def get_summary(data: dict) -> Optional[str]:
    for s in data.get("sections", []):
        if s.get("type") == "summary":
            return s.get("content", "")
    return None


def count_sentences(text: str) -> int:
    parts = re.split(r"[.!?]+(?:\s|$)", text.strip())
    return len([p for p in parts if p.strip()])


def validate(json_path: Path, resume_type: str, posting_path: Optional[Path]) -> list[str]:
    errors: list[str] = []
    with open(json_path) as f:
        data = json.load(f)

    wc = count_words(data)
    lo, hi = WORD_COUNT_RANGES[resume_type]
    if wc < lo or wc > hi:
        errors.append(f"Word count {wc} outside {resume_type} target range [{lo}, {hi}]")

    summary = get_summary(data)
    if resume_type == "1page" and summary is not None:
        errors.append("1-page resume must NOT have a summary section")
    if resume_type == "2page" and summary is None:
        errors.append("2-page resume MUST have a summary section")

    if resume_type == "2page" and summary:
        sc = count_sentences(summary)
        if sc != 2:
            preview = summary[:120].replace("\n", " ")
            errors.append(f"Summary must be exactly 2 sentences, found {sc}: '{preview}...'")
        for phrase in BANNED_SUMMARY_PHRASES:
            if re.search(re.escape(phrase), summary, re.IGNORECASE):
                errors.append(f"Summary contains banned catch-all phrase '{phrase}'")

    full_text = collect_content_text(data)

    if "—" in full_text:
        contexts = [m.group() for m in re.finditer(r".{0,20}—.{0,20}", full_text)]
        errors.append(f"Em dash (—) found in resume content. Context(s): {contexts[:3]}")

    for word in BANNED_AI_WORDS:
        pattern = rf"\b{re.escape(word)}\b" if " " not in word else re.escape(word)
        if re.search(pattern, full_text, re.IGNORECASE):
            errors.append(f"Banned AI word/phrase '{word}' present in resume content")

    if posting_path is not None:
        if not posting_path.exists():
            errors.append(f"Posting path provided but file not found: {posting_path}")
        else:
            posting_text = posting_path.read_text()
            for acro in CONDITIONAL_ACRONYMS:
                if re.search(rf"\b{re.escape(acro)}\b", full_text):
                    if not re.search(rf"\b{re.escape(acro)}\b", posting_text):
                        errors.append(
                            f"Acronym '{acro}' appears in resume but not in posting "
                            f"'{posting_path.name}'. Drop or compress to plain English."
                        )
            errors.extend(_check_equivalence_annotations(full_text, posting_text, posting_path.name))

    return errors


_EQUIV_COMPARABLE = re.compile(r"\(\s*(?:[^)]*?,\s*)?comparable to ([^)]+?)\s*\)", re.IGNORECASE)
_EQUIV_SUFFIX = re.compile(r"\(\s*([A-Za-z][A-Za-z0-9 /]*?)[- ]equivalent\b[^)]*\)", re.IGNORECASE)


def _check_equivalence_annotations(full_text: str, posting_text: str, posting_name: str) -> list[str]:
    errors: list[str] = []
    targets: list[str] = []
    for m in _EQUIV_COMPARABLE.finditer(full_text):
        targets.extend(t.strip() for t in m.group(1).split("/"))
    for m in _EQUIV_SUFFIX.finditer(full_text):
        targets.extend(t.strip() for t in m.group(1).split("/"))
    for tool in targets:
        if not tool:
            continue
        if not re.search(re.escape(tool), posting_text, re.IGNORECASE):
            errors.append(
                f"Equivalence annotation references '{tool}', but '{tool}' does "
                f"not appear in posting '{posting_name}'. Remove the annotation; "
                f"only annotate tools the job posting literally mentions."
            )
    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate a tailored resume JSON.")
    parser.add_argument("json_path", type=Path, help="Path to resume content JSON")
    parser.add_argument("--type", choices=["1page", "2page"], required=True,
                        help="Resume variant")
    parser.add_argument("--posting", type=Path, default=None,
                        help="Optional path to job posting markdown for conditional acronym check")
    args = parser.parse_args()

    if not args.json_path.exists():
        print(f"ERROR: JSON file not found: {args.json_path}", file=sys.stderr)
        sys.exit(2)

    errors = validate(args.json_path, args.type, args.posting)
    if errors:
        print(f"FAIL — {len(errors)} validation error(s) in {args.json_path.name}:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.json_path) as f:
        data = json.load(f)
    wc = count_words(data)
    print(f"PASS — {args.json_path.name} ({wc} words, type={args.type})")


if __name__ == "__main__":
    main()
