#!/usr/bin/env python3
"""
Count words in a resume JSON file (1-page or 2-page format).

Usage:
    .venv/bin/python scripts/count_resume_words.py <path-to-json>

Exits with code 0 and prints the word count.
Handles both formats:
  - 2-page: projects entries use "bullets" (list)
  - 1-page: projects entries use "bullet" (single string)
"""

import json
import re
import sys


def count_words(json_path: str) -> int:
    with open(json_path) as f:
        data = json.load(f)

    text = []

    text.append(data["name"])
    for c in data["contact"]:
        text.append(c)

    for section in data["sections"]:
        text.append(section["title"])
        t = section["type"]

        if t == "summary":
            text.append(section["content"])

        elif t == "experience":
            for entry in section["entries"]:
                text.append(entry["company"])
                text.append(entry["location"])
                text.append(entry["role"])
                text.append(entry["dates"])
                for b in entry["bullets"]:
                    text.append(b)

        elif t == "projects":
            for entry in section["entries"]:
                text.append(entry["name"])
                text.append(entry["date"])
                # 2-page format uses "bullets" (list); 1-page uses "bullet" (string)
                if "bullets" in entry:
                    for b in entry["bullets"]:
                        text.append(b)
                elif "bullet" in entry:
                    text.append(entry["bullet"])

        elif t == "table":
            for row in section["rows"]:
                text.append(" ".join(row))

        elif t == "education":
            for entry in section["entries"]:
                text.append(entry["institution"])
                text.append(entry["location"])
                text.append(entry["degree"])
                text.append(entry["field"])
                text.append(entry["date"])

    full_text = " ".join(text)
    clean = re.sub(r"\*\*", "", full_text)
    return len(clean.split())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-json>", file=sys.stderr)
        sys.exit(1)

    count = count_words(sys.argv[1])
    print(f"Word count: {count}")
