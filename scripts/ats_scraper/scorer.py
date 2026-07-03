"""
Position scoring framework for ATS API scraper.

Mirrors the rules in shared/scoring_framework.md but operates purely on
JobPosting fields (title, description_text, workplace_type, compensation).
No LLM involvement — regex only.

Scoring:
  Base: 5 (passes all hard filters)
  Boosters: Terraform +2, Ansible +2, AWS-focused +2, Automation-first +3,
            Education flexibility +1, Excellent culture +1, IaC-primary +1
  Penalties: Azure-primary -1, On-call rotation -1, HIPAA -1, FedRAMP -1,
             Travel -2, Family-culture -1, Unclear remote -1
  Cap: 10

  Score >= 4 → kept in qualified output
  Score < 4  → should have been caught by an earlier disqualifier; score anyway
"""

import re
from dataclasses import dataclass

from .config import JobPosting

# ---------------------------------------------------------------------------
# Booster patterns
# ---------------------------------------------------------------------------

_TERRAFORM = re.compile(r"\bterraform\b", re.IGNORECASE)
_ANSIBLE = re.compile(r"\bansible\b", re.IGNORECASE)

# Cloud mention counters (AWS vs Azure vs GCP)
_AWS_MENTIONS = re.compile(
    r"\baws\b|\bamazon web services\b"
    r"|ec2\b|s3\b|\beks\b|\becs\b|\blambda\b|\bcloudwatch\b"
    r"|\brds\b|\bsqs\b|\bsns\b|\biam\b|\bvpc\b|\broute\s*53\b"
    r"|\bcloudformation\b|\bcodepipeline\b|\bcodebuild\b",
    re.IGNORECASE,
)
_AZURE_MENTIONS = re.compile(
    r"\bazure\b|\bmicrosoft azure\b|\baks\b|\bazure devops\b",
    re.IGNORECASE,
)
_GCP_MENTIONS = re.compile(
    r"\bgcp\b|\bgoogle cloud\b|\bgke\b|\bbigquery\b|\bcloud run\b",
    re.IGNORECASE,
)

# Automation-first philosophy signals (need 2+ to award +3)
_AUTO_PHILOSOPHY_PATTERNS = [
    re.compile(r"everything as code|100%\s+\w+\s+as code", re.IGNORECASE),
    re.compile(r"automation.first\s+mindset|automation[ -]first", re.IGNORECASE),
    re.compile(r"\bbias for automation\b", re.IGNORECASE),
    re.compile(r"passionate about automation", re.IGNORECASE),
    re.compile(r"culture of automation|evangelize automation", re.IGNORECASE),
    re.compile(r"\breduce toil\b|eliminating toil|eliminate toil", re.IGNORECASE),
    re.compile(r"eliminating manual tasks|eliminate manual work|operational burden", re.IGNORECASE),
    re.compile(r"reusability at heart|write once.{0,25}reuse everywhere|100%\s+self.service automation", re.IGNORECASE),
    re.compile(r"automate everything|automate\s+\w+\s+across the organization", re.IGNORECASE),
    re.compile(r"replace\w*\s+\w*\s*with\s+software|identify repetitive.*replace", re.IGNORECASE),
]

_EDU_FLEXIBILITY = re.compile(
    r"degree preferred|equivalent experience|bachelor.{0,20}preferred"
    r"|or equivalent|experience in lieu",
    re.IGNORECASE,
)

_IaC_PRIMARY = re.compile(
    r"infrastructure as code.{0,40}primary|primary.{0,40}infrastructure as code"
    r"|automation is (?:a\s+)?(?:core|primary|central)\s+(?:value|responsibility)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Penalty patterns
# ---------------------------------------------------------------------------

_ROTATING_ONCALL = re.compile(
    r"on.call rotation|rotating on.call|rotation schedule|shared on.call",
    re.IGNORECASE,
)
_HIPAA = re.compile(r"\bhipaa\b", re.IGNORECASE)
_FEDRAMP = re.compile(r"\bfedramp\b", re.IGNORECASE)
_TRAVEL = re.compile(
    r"\d+\s*%\s*travel|travel\s+\d+\s*%|travel required|quarterly on.?site visit"
    r"|occasional office visit",
    re.IGNORECASE,
)
_FAMILY_CULTURE = re.compile(
    r"we.?re a family|family environment|family.oriented (workplace|culture|atmosphere)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Description-level disqualifiers (hard filters that the title stage can't catch)
# ---------------------------------------------------------------------------

_ONCALL_24_7 = re.compile(
    r"24/7\s+on.?call|24x7\s+on.?call|24.7.365\s+on.?call"
    r"|primary on.call responsibility",
    re.IGNORECASE,
)
_CONTINGENT = re.compile(
    r"contingent upon\s+(?:contract award|task order|funding|award|bid|winning)",
    re.IGNORECASE,
)
_PIPELINE_POSTING = re.compile(
    r"building a talent pipeline|talent pipeline|talent community|talent pool"
    r"|we.?re always looking for talented|pipeline opportunity",
    re.IGNORECASE,
)
_SOFTWARE_DEV_DESC = re.compile(
    r"software development experience|development experience using\s+\w+"
    r"|build and maintain internal tools as primary",
    re.IGNORECASE,
)
_CRYPTO_DESC = re.compile(
    r"\bcryptocurrency\b|\bblockchain\b|\bweb3\b|\bdefi\b|\bnft.?focused\b",
    re.IGNORECASE,
)

# Compensation: $0 floor or below-market floor
_COMP_ZERO_FLOOR = re.compile(r"\$\s*0\b", re.IGNORECASE)


@dataclass
class ScoringResult:
    score: int
    iac_tools: str          # comma-separated, e.g. "Terraform, Ansible"
    cloud_platform: str     # e.g. "AWS", "Azure", "AWS+Azure", "Multi-cloud"
    match_reasons: str      # e.g. "Terraform +2, AWS +2"
    disqualifiers: str      # e.g. "FedRAMP -1" or "None"
    description_disqualified: bool = False
    disqualify_reason: str = ""


def score_posting(posting: JobPosting) -> ScoringResult:
    """Score a single posting. Returns ScoringResult with all fields populated."""
    desc = posting.description_text or ""
    comp = posting.compensation or ""

    # --- Hard description-level disqualifiers ---
    if _ONCALL_24_7.search(desc):
        return ScoringResult(
            score=1, iac_tools="", cloud_platform="", match_reasons="",
            disqualifiers="24/7 on-call",
            description_disqualified=True, disqualify_reason="24/7 on-call",
        )
    if _CONTINGENT.search(desc):
        return ScoringResult(
            score=1, iac_tools="", cloud_platform="", match_reasons="",
            disqualifiers="contingent posting",
            description_disqualified=True, disqualify_reason="contingent upon contract/award",
        )
    if _PIPELINE_POSTING.search(desc):
        return ScoringResult(
            score=1, iac_tools="", cloud_platform="", match_reasons="",
            disqualifiers="pipeline/evergreen posting",
            description_disqualified=True, disqualify_reason="talent pipeline posting",
        )
    if _CRYPTO_DESC.search(desc):
        return ScoringResult(
            score=2, iac_tools="", cloud_platform="", match_reasons="",
            disqualifiers="crypto/blockchain/web3 company",
            description_disqualified=True, disqualify_reason="crypto/blockchain/web3",
        )
    if _COMP_ZERO_FLOOR.search(comp):
        return ScoringResult(
            score=1, iac_tools="", cloud_platform="", match_reasons="",
            disqualifiers="$0 salary floor",
            description_disqualified=True, disqualify_reason="$0 salary floor — scam indicator",
        )

    # --- Base score ---
    score = 5
    boost_reasons: list[str] = []
    penalty_reasons: list[str] = []

    # --- IaC tool detection ---
    iac_tools: list[str] = []
    if _TERRAFORM.search(desc):
        score += 2
        iac_tools.append("Terraform")
        boost_reasons.append("Terraform +2")
    if _ANSIBLE.search(desc):
        score += 2
        iac_tools.append("Ansible")
        boost_reasons.append("Ansible +2")

    # --- Cloud platform analysis ---
    aws_count = len(_AWS_MENTIONS.findall(desc))
    azure_count = len(_AZURE_MENTIONS.findall(desc))
    gcp_count = len(_GCP_MENTIONS.findall(desc))
    total_cloud = aws_count + azure_count + gcp_count

    if total_cloud == 0:
        cloud_platform = "unspecified"
    elif total_cloud > 0:
        if aws_count / total_cloud >= 0.8:
            cloud_platform = "AWS"
            score += 2
            boost_reasons.append("AWS-focused +2")
        elif azure_count > aws_count and aws_count > 0:
            cloud_platform = "AWS+Azure"
            score -= 1
            penalty_reasons.append("Azure-primary -1")
        elif azure_count > aws_count and aws_count == 0:
            cloud_platform = "Azure"
            score -= 1
            penalty_reasons.append("Azure-primary -1")
        elif gcp_count >= aws_count and gcp_count > 0:
            cloud_platform = "GCP"
            # GCP-only should have been caught by filters, but penalize anyway
            score -= 1
            penalty_reasons.append("GCP-primary -1")
        else:
            # Multi-cloud with AWS present
            if aws_count > 0:
                cloud_platform = "Multi-cloud (AWS)"
            else:
                cloud_platform = "Multi-cloud"

    # --- Automation-first philosophy ---
    automation_signals = sum(1 for p in _AUTO_PHILOSOPHY_PATTERNS if p.search(desc))
    if automation_signals >= 2:
        score += 3
        boost_reasons.append(f"Automation-first +3 ({automation_signals} signals)")

    # --- Education flexibility booster ---
    if _EDU_FLEXIBILITY.search(desc):
        score += 1
        boost_reasons.append("Education flexibility +1")

    # --- IaC primary responsibility booster ---
    if _IaC_PRIMARY.search(desc):
        score += 1
        boost_reasons.append("IaC-primary +1")

    # --- Penalties ---
    if _ROTATING_ONCALL.search(desc):
        score -= 1
        penalty_reasons.append("On-call rotation -1")
    if _HIPAA.search(desc):
        score -= 1
        penalty_reasons.append("HIPAA -1")
    if _FEDRAMP.search(desc):
        score -= 1
        penalty_reasons.append("FedRAMP -1")
    if _TRAVEL.search(desc):
        score -= 2
        penalty_reasons.append("Travel -2")
    if _FAMILY_CULTURE.search(desc):
        score -= 1
        penalty_reasons.append("Family-culture -1")

    # --- Cap at 10, floor at 0 ---
    score = max(0, min(10, score))

    match_reasons = ", ".join(boost_reasons) or "Base only"
    disqualifiers_str = ", ".join(penalty_reasons) or "None"

    return ScoringResult(
        score=score,
        iac_tools=", ".join(iac_tools),
        cloud_platform=cloud_platform if total_cloud > 0 else "unspecified",
        match_reasons=match_reasons,
        disqualifiers=disqualifiers_str,
    )


def score_posting_no_description(posting: JobPosting) -> ScoringResult:
    """Score a posting without a description (e.g. Rippling). Base score only."""
    return ScoringResult(
        score=5,
        iac_tools="unknown (no description)",
        cloud_platform="unknown (no description)",
        match_reasons="Base only — no description available",
        disqualifiers="needs_verification",
    )
