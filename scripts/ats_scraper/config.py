import csv
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CompanyTarget:
    name: str
    ats_platform: str
    board_token: str
    career_url: str

    # Workday-specific parsed fields
    workday_tenant: str = ""
    workday_datacenter: str = ""
    workday_board_name: str = ""

    def __post_init__(self):
        if self.ats_platform.lower() == "workday":
            self._parse_workday()

    def _parse_workday(self):
        # board_token formats:
        #   "wellsky.wd1"          -> tenant="wellsky", dc="wd1"
        #   "pax8inc:Pax8Careers"  -> tenant="pax8inc", dc from career_url (colon separates board name hint, ignored)
        #   "healthcatalyst"       -> tenant="healthcatalyst", dc from career_url
        import re
        token = self.board_token
        # Strip any ":BoardName" suffix — only the subdomain portion is the tenant.
        if ":" in token:
            token = token.split(":", 1)[0]
        if "." in token:
            parts = token.split(".", 1)
            self.workday_tenant = parts[0]
            self.workday_datacenter = parts[1]
        else:
            self.workday_tenant = token
            # Try to extract datacenter from career_url hostname
            # e.g. "https://healthcatalyst.wd5.myworkdayjobs.com/..."
            m = re.search(r"\.?(wd\d+)\.myworkdayjobs\.com", self.career_url)
            self.workday_datacenter = m.group(1) if m else "wd1"

        # career_url e.g. "https://wellsky.wd1.myworkdayjobs.com/en-US/WellSkyCareers"
        # Extract board_name = last path component
        path = self.career_url.rstrip("/")
        self.workday_board_name = path.split("/")[-1] if "/" in path else ""


@dataclass
class JobPosting:
    company: str
    title: str
    url: str
    location: str
    department: str
    description_text: str
    ats_platform: str
    compensation: str = ""
    posted_date: str = ""
    workplace_type: str = ""
    description_available: bool = True


def load_targets(csv_path: Path) -> list[CompanyTarget]:
    targets = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Strip spaces from header keys
        reader.fieldnames = [h.strip() for h in reader.fieldnames] if reader.fieldnames else []
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items() if k is not None}
            targets.append(CompanyTarget(
                name=row.get("Company_Name", ""),
                ats_platform=row.get("ATS_Platform", ""),
                board_token=row.get("ATS_Slug", ""),
                career_url=row.get("Career_Page_URL", ""),
            ))
    return targets


def load_config(yml_path: Path) -> dict:
    with open(yml_path, encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    merged = {}
    for doc in docs:
        if isinstance(doc, dict):
            merged.update(doc)
    return merged


def load_exclusions(yml_path: Path) -> list[str]:
    with open(yml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [c.lower() for c in data.get("excluded_companies", [])]
