# Job Position Scoring Framework

This document defines the standardized scoring system (0-10 scale) used to evaluate job positions discovered through search workflows. All subagents should reference this framework when analyzing job postings.

---

## Overview

The scoring framework evaluates positions across multiple dimensions to produce a final quality score. Positions are categorized into tiers based on their total score.

**Important:** Disqualification criteria are **hard filters** that cannot be overcome by positive attributes. A position matching any disqualification trigger should be assigned a score of 0-3 and documented with a specific rejection reason.

---

## Score Tiers

### Application Ready (Score 6-10)
Positions that warrant immediate application effort.

| Score | Classification | Action |
|-------|---------------|--------|
| 8-10 | Exceptional | Apply immediately, prioritize |
| 6-7 | Strong | Apply, good opportunity |

### Review Required (Score 4-5)
Positions with potential but notable concerns.

| Score | Classification | Action |
|-------|---------------|--------|
| 4-5 | Moderate | Review manually before applying |

### Rejected (Score 0-3)
Positions that do not meet minimum criteria.

| Score | Classification | Action |
|-------|---------------|--------|
| 0-3 | Disqualified | Document rejection reason, do not apply |

---

## Scoring Calculation

### Base Score: 5 Points
A position meeting all basic requirements starts with 5 points:
- Cloud infrastructure focus confirmed
- Remote work confirmed
- US-based position
- Appropriate experience level (no senior indicators)
- No automatic disqualification triggers

### Score Boosters (Additive)

| Criterion | Points | Description |
|-----------|--------|-------------|
| Terraform mentioned | +2 | Explicit mention in requirements or description |
| Ansible mentioned | +2 | Explicit mention in requirements or description |
| AWS-focused | +2 | 80%+ of cloud technology mentions are AWS |
| Excellent culture | +1 | Clear work-life balance indicators, no red flags |
| Education flexibility | +1 | "Degree preferred" or "equivalent experience" language |
| Infrastructure automation emphasis | +1 | Primary responsibility is automation, not operations |

### Score Penalties (Subtractive)

| Criterion | Points | Description |
|-----------|--------|-------------|
| Azure-primary | -1 | Azure is primary cloud with AWS as secondary |
| Minor programming concerns | -1 | Some development language but not primary focus |
| Travel requirements | -2 | Any travel percentage mentioned |
| Unclear remote status | -1 | Remote not explicitly confirmed |
| Large company (5,000-10,000) | -1 | May have bureaucratic processes |
| Rotating on-call | -1 | Sustainable on-call schedule with rotation mentioned |
| HIPAA compliance environment | -1 | Healthcare industry compliance overhead |
| FedRAMP compliance environment | -1 | Government sector compliance overhead |
| Basic clearance obtainable | -1 | "Ability to obtain" Secret clearance (not TS/SCI) |

### Maximum Score: 10 Points
Even with all boosters, cap the score at 10.

---

## Automatic Disqualification (Score 0-3)

The following triggers result in immediate low scores regardless of other factors.

### Category 1: Seniority Level Disqualifications (Score 0-2)

**⚠️ CRITICAL: Check job titles FIRST before any other analysis. These are automatic disqualifiers.**

**Title-based disqualification if title contains:**
- Senior / Sr / Sr.
- Lead / Team Lead
- Principal
- Staff
- Manager
- Director
- Architect (as title, not just "working with architects")
- III / IV / V (Roman numerals indicating senior level)
- Head of

**⚠️ IMPORTANT:** Job titles like "Sr./Staff - Infrastructure Engineer" or "Senior Cloud Engineer" are IMMEDIATE disqualifiers. Do not proceed with scoring—assign score 0-2 and document rejection.

**Responsibility-based disqualification if description includes:**
- "Mentor junior engineers"
- "Lead a team of..."
- "Manage direct reports"
- "Primary architectural decision-making"
- "Define technical direction for the team"
- "Hire and grow the team"
- "Performance reviews for team members"

### Category 2: Technical Disqualifications (Score 0-1)

**Cloud Platform Disqualifications:**
| Trigger | Reason |
|---------|--------|
| GCP as primary cloud | No GCP experience |
| GCP as only cloud | Cannot meet requirements |
| "Google Cloud expertise required" | Direct requirement mismatch |
| No AWS mentioned at all | AWS is primary strength |

**Infrastructure Focus Disqualifications:**
| Trigger | Reason |
|---------|--------|
| KVM/QEMU primary focus | Bare-metal, not cloud |
| Hypervisor management | VMware/bare-metal, not cloud IaC |
| GPU passthrough | Specialized hardware |
| RDMA technologies | Specialized networking |
| "Data center operations" | Physical infrastructure |
| "Hardware provisioning" | Physical infrastructure |

**Programming Disqualifications:**
| Trigger | Reason |
|---------|--------|
| "Python development required" | Software development focus |
| "Python expertise" or "Advanced Python" | Beyond scripting |
| "Software development experience" | Software developer role, not infrastructure |
| "Software development experience using Python, Go, bash" | Developer role disguised as infrastructure |
| "Development experience" for building applications | Application development, not automation |
| Django, Flask, FastAPI mentioned | Web framework development |
| "Object-oriented programming" | Software development |
| "Software design patterns" | Software development |
| "Backend developer" | Wrong role type |
| "Full-stack developer" | Wrong role type |
| "Microservices development" | Application development |
| "API development" as primary duty | Application development |
| Java / Node.js / Go as primary language | Wrong technical focus |
| "Build and maintain internal tools" as primary duty | Software development focus |
| "Develop automation frameworks" (not use/configure) | Software development focus |

**⚠️ KEY DISTINCTION:**
- ✅ ACCEPTABLE: "Python scripting", "automation scripts", "shell scripting", "operational scripting"
- ❌ DISQUALIFYING: "Software development experience", "development experience using [languages]", "build internal tools"

The key difference is between *using* existing tools/writing scripts vs *developing* software/applications.

### Category 3: Work Arrangement Disqualifications (Score 1-2)

**Location Disqualifications:**
| Trigger | Reason |
|---------|--------|
| "Hybrid" work arrangement | Not fully remote |
| "On-site" or "In-office" | Not remote |
| Specific office location required | Not remote |
| "Must be within X miles of office" | Not remote |
| International position | Must be US-based |
| "Relocation required" | Not remote |
| "Visa sponsorship available" | International focus |

**Travel Disqualifications:**
| Trigger | Reason |
|---------|--------|
| Travel percentage >5% | Excessive travel |
| "Quarterly on-site meetings" | Regular travel required |
| "Occasional office visits required" | Not fully remote |

**Note:** "Annual team summits" may be acceptable—review manually.

### Category 4: Company/Business Model Disqualifications (Score 2-3)

**Business Model Disqualifications:**
| Trigger | Reason |
|---------|--------|
| Managed Service Provider (MSP) | Client-focused work |
| IT Consulting firm | Billable hours culture |
| Staffing/Recruiting agency | Not direct employment |

**Industry/Sector Disqualifications:**
| Trigger | Reason |
|---------|--------|
| Crypto / Cryptocurrency company | Fad industry, high volatility, unstable employment |
| Blockchain company | Fad industry, high volatility, unstable employment |
| Web3 company | Fad industry, high volatility, unstable employment |
| DeFi (Decentralized Finance) | Fad industry, regulatory uncertainty |
| NFT-focused company | Fad industry, market collapse |
| AI startup (<10,000 employees) | Fad-chasing, high failure rate, unproven business model |
| "AI-first" or "AI-native" company (small) | Fad-chasing unless Enterprise-scale |
| ML/AI infrastructure startup | Fad-chasing unless established (Anthropic/OpenAI-scale) |

**Note on AI Companies:** Enterprise-scale AI companies (>10,000 employees) like major cloud providers adding AI services are acceptable. The concern is small AI startups (Series A-C) chasing the AI trend without sustainable business models.

**Clearance Disqualifications:**
| Trigger | Reason |
|---------|--------|
| "Active Secret/Top Secret" required | No clearance held |
| "Active TS/SCI" or "Top Secret/SCI" required | No clearance held; highest-level clearance |
| "Ability to obtain Top Secret/SCI" | Invasive vetting process, extremely high bar |
| Defense contractor requiring clearance | Clearance incompatible with remote work |

**Note on Government Roles:** Government employers and contractors are acceptable. Roles requiring **Active** clearance or **Top Secret/SCI** (including ability to obtain) remain disqualifying. Roles mentioning basic "security clearance required" or "ability to obtain Secret clearance" should be reviewed manually — these may be obtainable and are not automatic disqualifiers. Apply a -1 penalty for roles requiring obtainable clearance.

**Industry Disqualifications (Score 2-3):**
| Trigger | Reason |
|---------|--------|
| Financial services / Banking | SOX compliance overhead |
| Pharmaceutical / Biotech | FDA regulatory burden |

**Note on Healthcare:** Healthcare companies are no longer automatically excluded. HIPAA compliance adds overhead but the actual infrastructure work (AWS, Terraform, Ansible, etc.) is substantially similar. Apply a -1 scoring penalty for HIPAA environments instead.

**Compliance Disqualifications:**
| Trigger | Reason |
|---------|--------|
| "SOX compliance experience" | Financial compliance |
| "GDPR experience required" | European compliance |
| "GDPR familiarity" as requirement | European compliance |

**Note:** HIPAA and FedRAMP compliance environments are no longer automatic disqualifiers. Apply a -1 penalty instead (see Score Penalties).

### Category 5: Cultural Disqualifications (Score 2-3)

**Work Culture Red Flags:**
| Trigger | Reason |
|---------|--------|
| "Startup environment" | High stress, unclear scope |
| "Move fast and break things" | Unhealthy culture |
| "Wear many hats" | Unclear role boundaries |
| "Work hard, play hard" | Work-life imbalance |
| "Always available" | On-call abuse |
| "Whatever it takes" | Overwork expectation |
| "Rockstar/Ninja/Guru" | Unrealistic expectations |
| "Firefighting" emphasis | Crisis culture |
| "We're a family" / "family environment" | Boundary issues, overwork guilt |
| "Passionate" as compensation substitute | Passion exploited in lieu of pay/benefits |
| "No ego" / "leave your ego at the door" | Discourages self-advocacy |

**On-Call Disqualifications:**
| Trigger | Reason |
|---------|--------|
| "24/7 on-call" | No work-life balance |
| "Primary on-call responsibility" | Excessive burden |

**Note on SRE Roles:** Site Reliability Engineer (SRE) positions are NOT automatically disqualifying. Evaluate on-call requirements:
- **Egregious on-call is disqualifying:** 24/7/365 coverage, explicitly no rotation, or <15 minute response time requirements
- **Standard rotating on-call:** Apply -1 penalty for sustainable on-call with rotation
- Evaluate each SRE role on its actual on-call requirements, not assumptions

### Category 6: Experience Level Disqualifications (Score 1-3)

**Experience Requirements:**
| Trigger | Reason |
|---------|--------|
| "8+ years required" | Senior-level expectations |
| "10+ years experience" | Senior-level expectations |
| "Extensive enterprise experience" | May imply senior level |
| "Expert-level skills required" | Senior-level expectations |

**Education Requirements:**
| Trigger | Reason |
|---------|--------|
| "Master's degree required" | Exceeds background |
| "PhD required" | Exceeds background |
| "Computer Science degree required" | Associates in IT held |

---

## Scoring Examples

### Example 1: Exceptional Opportunity (Score 10)
```
Position: Cloud Infrastructure Engineer
Company: Mid-size SaaS company (500 employees)
- Base score: 5
- Terraform required: +2
- Ansible preferred: +2
- AWS-primary (90% AWS): +2
- Education: "degree or equivalent": +1
- Remote, no travel, great culture: Already in base
- Capped at: 10
Final Score: 10 (Exceptional)
```

### Example 2: Strong Opportunity (Score 7)
```
Position: DevOps Engineer
Company: Tech company (800 employees)
- Base score: 5
- Terraform mentioned: +2
- Ansible not mentioned: +0
- AWS + Azure multi-cloud: +0
- Education: Bachelor's required: +0
Final Score: 7 (Strong)
```

### Example 3: Moderate Opportunity (Score 4)
```
Position: Infrastructure Engineer
Company: Enterprise company (3000 employees)
- Base score: 5
- No IaC tools mentioned: +0
- Azure-primary with some AWS: -1
- Large company: -1
- Some Python development language: -1
Final Score: 4 (Moderate - review required)
```

### Example 4: Disqualified (Score 2)
```
Position: Senior DevOps Engineer
Company: Tech company (800 employees)
- Senior title: Disqualified
Final Score: 2 (Rejected - Senior title)
```

---

## Implementation Guide

### Processing Order

When evaluating a position:

1. **Check seniority indicators first** - fastest to identify
2. **Check technical disqualifiers** - requires reading requirements
3. **Check work arrangement** - look for remote/hybrid/on-site
4. **Check company/industry** - may require brief research
5. **Check cultural indicators** - look for red flag phrases
6. **Check experience requirements** - verify year requirements

### Scoring Assignment by Disqualification Category

| Disqualification Category | Score Range |
|---------------------------|-------------|
| Technical Misalignment | 0-1 |
| Seniority Level | 0-2 |
| Work Arrangement | 1-2 |
| Company/Industry | 2-3 |
| Cultural Issues | 2-3 |
| Experience Level | 1-3 |

### Subagent Implementation Notes

When implementing scoring in subagent prompts:

1. **First check for automatic disqualifications** - if any trigger is found, assign score 0-3 and document the reason
2. **Calculate base score** - verify all basic requirements are met for 5 points
3. **Apply boosters** - check for each booster criterion
4. **Apply penalties** - check for each penalty criterion
5. **Cap at 10** - do not exceed maximum score
6. **Document reasoning** - include brief justification in output

### Output Format for Subagents

```csv
Quality_Score,Score_Breakdown,Boost_Factors,Penalty_Factors,Disqualification_Reason
7,"Base:5 + Terraform:2","Terraform mentioned","None","N/A"
2,"Disqualified","N/A","N/A","Senior title in posting"
```

Rejection output format:
```csv
Company,Title,URL,Score,Rejection_Category,Rejection_Reason,Details
TechCorp,Senior DevOps Engineer,https://...,1,Seniority Level,Senior title,Title contains "Senior"
MedCo,Cloud Engineer,https://...,2,Industry,Healthcare IT,Hospital systems company
```

---

## Edge Cases

### May Not Be Disqualifying (Review Manually)

- "Senior" in company name but not job title
- "Lead" referring to technical leadership, not people management
- "Architect" as collaboration partner, not the role itself
- Travel for optional events clearly marked as optional
- Level II positions (may be acceptable)
- Government roles where clearance level is ambiguous (review manually)
- Defense companies without clearance requirements

### Always Disqualifying

- Active security clearance required (Secret, Top Secret, TS/SCI)
- Ability to obtain Top Secret/SCI
- Any explicit senior title (Senior, Sr, Staff, Lead, Principal, Director, III+)
- GCP as only cloud platform
- Explicit software development role or "software development experience" requirements
- Non-remote work arrangement
- 24/7 on-call requirements
- Crypto / Blockchain / Web3 / DeFi companies
- AI startups (<10,000 employees)

---

## Related Documents

- [Job Preferences](../config/job_preferences.md) - Full criteria and requirements
- [Technical Requirements](./technical_requirements.md) - Technical skill matching
- [Company Evaluation Rules](./company_evaluation_rules.md) - Company filtering logic
