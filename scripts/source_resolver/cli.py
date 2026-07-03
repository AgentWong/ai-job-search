"""
Resolve the `original_source` (LLM workflow that surfaced a posting) for a
clipped job by matching its `source` URL + company/role against the rows in
`results/application_queue.csv`.

Implements the matching ladder described in
`.claude/commands/process-clippings.md` step 4:

  1. Exact URL match between the clipping's `source` and a queue row's `url`.
  2. Substring match in either direction (tolerates trailing slashes, tracking
     params, minor canonicalization).
  3. Case-insensitive Company + Role match, normalized via the same rules the
     ATS cooldown filter uses (corporate suffixes stripped, seniority tokens
     dropped, SRE <-> Site Reliability Engineer collapsed).

If none of those hit, fall back to inference from the clipping URL host and
append `?` to flag the value as inferred.

Usage:
    .venv/bin/python -m scripts.source_resolver.cli --posting "<path/to/posting.md>"
    .venv/bin/python -m scripts.source_resolver.cli --url "<src>" --company "Acme" --role "DevOps Engineer"

Output: one JSON object on stdout. Exit 0 on success (including fallback);
exit 2 on missing input file. Never raises on a missing queue CSV — that just
forces the inference fallback.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Optional

from scripts.ats_scraper.cooldown import normalize_company, normalize_role


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE = REPO_ROOT / "results" / "application_queue.csv"


# Inference fallback table from process-clippings.md step 4.3
_HOST_INFERENCE = [
    ("linkedin.com", "linkedin-api?"),
    ("builtin.com", "builtin-api?"),
]

# Hosts that map to "unknown" because multiple workflows can surface them.
_AMBIGUOUS_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "workday.com",
    "paylocity.com",
    "paycomonline.net",
    "dayforcehcm.com",
    "applytojob.com",
    "icims.com",
    "jobs.gem.com",
    "oraclecloud.com",
    "adp.com",
    "workable.com",
    "rippling.com",
    "smartrecruiters.com",
    "jobvite.com",
    "recruitee.com",
    "bamboohr.com",
    "hiring.cafe",
)


def parse_frontmatter(posting_path: Path) -> dict:
    """Extract YAML-ish frontmatter from a clipping posting.md.

    Hand-rolled to avoid a yaml dependency. Pulls scalar string fields the
    resolver cares about: `source`, `title`, and `author` (used to disambiguate
    Built In / LinkedIn when the URL is ambiguous).
    """
    text = posting_path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}

    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end]

    out: dict = {}
    current_list_key: Optional[str] = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            current_list_key = None
            continue
        # List item under previous key
        m_item = re.match(r"^\s+-\s+(.*)$", line)
        if m_item and current_list_key:
            val = m_item.group(1).strip().strip('"').strip("'")
            out.setdefault(current_list_key, []).append(val)
            continue
        # `key: value` or `key:` (list header)
        m_kv = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', line)
        if not m_kv:
            current_list_key = None
            continue
        key, val = m_kv.group(1), m_kv.group(2).strip()
        if not val:
            current_list_key = key
            out.setdefault(key, [])
            continue
        out[key] = val.strip('"').strip("'")
        current_list_key = None
    return out


def parse_dir_name(posting_path: Path) -> tuple[str, str]:
    """Extract (company, role) from a `Company - Role/posting.md` parent dir."""
    parent = posting_path.parent.name
    if " - " not in parent:
        return ("", parent)
    company, _, role = parent.partition(" - ")
    return (company.strip(), role.strip())


def _url_substring_match(a: str, b: str) -> bool:
    """True if either URL contains the other (case-insensitive, scheme-agnostic)."""
    if not a or not b:
        return False
    aa = re.sub(r"^https?://", "", a.strip().lower()).rstrip("/")
    bb = re.sub(r"^https?://", "", b.strip().lower()).rstrip("/")
    if not aa or not bb:
        return False
    return aa in bb or bb in aa


def load_queue_rows(queue_csv: Path) -> list[dict]:
    if not queue_csv.exists():
        return []
    with open(queue_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resolve(
    source_url: str,
    company: str,
    role: str,
    author_tags: list[str],
    queue_csv: Path,
) -> dict:
    """Apply the matching ladder. Always returns a dict; never raises."""
    rows = load_queue_rows(queue_csv)

    # 1. Exact URL match
    src = (source_url or "").strip()
    if src:
        for row in rows:
            if (row.get("url") or "").strip() == src:
                return {
                    "original_source": (row.get("source_track") or "").strip() or "unknown",
                    "matched": True,
                    "match_strategy": "exact_url",
                    "queue_url": row.get("url", ""),
                }

    # 2. Substring URL match
    if src:
        for row in rows:
            if _url_substring_match(src, row.get("url", "")):
                return {
                    "original_source": (row.get("source_track") or "").strip() or "unknown",
                    "matched": True,
                    "match_strategy": "substring_url",
                    "queue_url": row.get("url", ""),
                }

    # 3. Company + Role normalized fallback
    if company and role:
        c_norm = normalize_company(company)
        r_norm = normalize_role(role)
        if c_norm and r_norm:
            for row in rows:
                if (normalize_company(row.get("company", "")) == c_norm
                        and normalize_role(row.get("title", "")) == r_norm):
                    return {
                        "original_source": (row.get("source_track") or "").strip() or "unknown",
                        "matched": True,
                        "match_strategy": "company_role",
                        "queue_url": row.get("url", ""),
                    }

    # 4. Inference fallback from URL host (and author tag for ambiguous hosts)
    return {
        "original_source": _infer_from_url(src, author_tags),
        "matched": False,
        "match_strategy": "inferred",
        "queue_url": "",
    }


def _infer_from_url(url: str, author_tags: list[str]) -> str:
    if not url:
        # No URL at all — author tag is the only signal
        for tag in author_tags or []:
            t = tag.lower()
            if "linkedin" in t:
                return "linkedin-api?"
            if "built in" in t or "builtin" in t:
                return "builtin-api?"
        return "unknown"

    host = url.lower()
    for needle, label in _HOST_INFERENCE:
        if needle in host:
            return label
    for needle in _AMBIGUOUS_HOSTS:
        if needle in host:
            return "unknown"
    # Last-resort: try author tag if host doesn't match known patterns
    for tag in author_tags or []:
        t = tag.lower()
        if "linkedin" in t:
            return "linkedin-api?"
        if "built in" in t or "builtin" in t:
            return "builtin-api?"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(
        description="Resolve original_source for a clipped job via the application_queue.csv."
    )
    parser.add_argument("--posting", type=Path, default=None,
                        help="Path to posting.md (frontmatter parsed for source URL; parent dir parsed for company/role)")
    parser.add_argument("--url", default="", help="Source URL (overrides --posting frontmatter)")
    parser.add_argument("--company", default="", help="Company name (overrides parent dir)")
    parser.add_argument("--role", default="", help="Role title (overrides parent dir)")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE,
                        help=f"Path to application queue CSV (default: {DEFAULT_QUEUE})")
    args = parser.parse_args()

    source_url = args.url
    company = args.company
    role = args.role
    author_tags: list[str] = []

    if args.posting is not None:
        if not args.posting.exists():
            print(f"ERROR: posting file not found: {args.posting}", file=sys.stderr)
            sys.exit(2)
        fm = parse_frontmatter(args.posting)
        if not source_url:
            source_url = fm.get("source", "") or ""
        author_val = fm.get("author")
        if isinstance(author_val, list):
            author_tags = author_val
        elif isinstance(author_val, str) and author_val:
            author_tags = [author_val]
        dir_company, dir_role = parse_dir_name(args.posting)
        if not company:
            company = dir_company
        if not role:
            role = dir_role

    result = resolve(source_url, company, role, author_tags, args.queue)
    result["input"] = {
        "url": source_url,
        "company": company,
        "role": role,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
