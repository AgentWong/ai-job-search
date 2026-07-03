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
- Work arrangement matches `config.yml` `location` (fully remote when `location.remote: true`, or in the target `city, state` when `location.remote: false`)
- US-based position
- Appropriate experience level (no senior indicators)
- No automatic disqualification triggers

### Score Boosters (Additive)

| Criterion | Points | Description |
|-----------|--------|-------------|
| Terraform mentioned | +2 | Explicit mention in requirements or description |
| Ansible mentioned | +2 | Explicit mention in requirements or description |
| AWS-focused | +2 | 80%+ of cloud technology mentions are AWS |
| Automation-first philosophy | +3 | Posting treats automation as a core value or mission, not a checkbox — see criteria below |
| FedRAMP environment (CSP buy-side) | +1 | Candidate has prior FedRAMP IaC experience; relevant when employer is the CSP pursuing authorization for *their own* product (not selling FedRAMP services to others — see 3PAO disqualifier) |
| Excellent culture | +1 | Clear work-life balance indicators, no red flags |
| Education flexibility | +1 | "Degree preferred" or "equivalent experience" language |
| Infrastructure automation emphasis | +1 | Primary responsibility is automation, not operations |

#### Automation-First Philosophy (+3) — Qualifying Criteria

Award +3 if the posting demonstrates automation as a **philosophy or cultural value**, not just a task list item. This requires **at least two** of the following signals:

**Philosophy / Mission Language:**
- "everything as code" or "100% [X] as code"
- "automation first" / "automation-first mindset"
- "bias for automation"
- "passionate about automation" (as a stated requirement)
- "culture of automation" / "evangelize automation"
- Automation mentioned in the opening summary/mission — not buried in a requirements list

**Toil Reduction as Explicit Goal:**
- "reduce toil" / "eliminating toil"
- "identify repetitive operational work and replace it with software"
- "eliminate manual tasks" / "eliminating manual work"
- "operational burden" reduction language

**Reusability / Platform Thinking:**
- "reusability at heart" / "write once, reuse everywhere"
- "100% self-service automation"
- Reusability applied across multiple artifact types (IaC, pipelines, templates, images)
- "self-service" automation platform language

**Scale / Scope of Automation Mandate:**
- Automation explicitly listed as a primary responsibility (not one of ten equal items)
- Multiple sections of the posting reference automation independently
- "automate everything" / "automate [X] across the organization" framing

**Note:** Generic IaC mentions ("experience with Terraform"), single automation bullet points, or automation listed alongside unrelated duties do NOT qualify. The signal must show the company *values* automation as a principle, not just *uses* it as a tool.

### Score Penalties (Subtractive)

| Criterion | Points | Description |
|-----------|--------|-------------|
| Azure-primary | -1 | Azure is primary cloud with AWS as secondary |
| Minor programming concerns | -1 | Some development language but not primary focus |
| Travel requirements | -2 | Any travel percentage mentioned |
| Unclear remote status | -1 | Remote not explicitly confirmed (applies when `config.yml` `location.remote: true`; in local mode, judge unclear work-location instead) |
| Large company (5,000-10,000) | -1 | May have bureaucratic processes |
| Very large company (10,000-25,000) | -1 | Bureaucratic processes; scale itself is not disqualifying (see size note) |
| Rotating on-call | -1 | Sustainable on-call schedule with rotation mentioned |
| Small company (< 50 employees) | Disqualify | Underfunded, "wear many hats", risk of vaporware |
| HIPAA compliance environment | -1 | Healthcare industry compliance overhead |
| Basic clearance obtainable | -1 | "Ability to obtain" Secret clearance (not TS/SCI) |
| "Family" culture language | -1 | "We're a family", "family environment" — signals boundary issues, overwork expectations |
| Bachelor's degree required (no "or equivalent") | -1 | Degree-required is frequently unenforced; penalty not disqualifier — review manually |

### Maximum Score: 10 Points
Even with all boosters, cap the score at 10. Note: Terraform (+2) + Ansible (+2) + AWS (+2) + Automation-first (+3) already totals 9 boosters before culture/education, so +3 automation postings that also hit Terraform/Ansible/AWS will cap at 10.

---

## Automatic Disqualification (Score 0-3)

The following triggers result in immediate low scores regardless of other factors.

**CITATION REQUIREMENT FOR AGENTS:** When disqualifying a position, the reason field MUST cite a specific category and trigger from this document (e.g., "Category 1 — Title contains 'Senior'", "Category 2 — GCP as primary cloud", "Category 4 — Crypto company"). If you cannot cite a specific trigger in this document, the position is **NOT disqualified**. Do not invent disqualifier categories that don't exist here.

**Common false-positive disqualifiers (these are NOT disqualifiers):**
- **AWS GovCloud** — GovCloud is AWS. Not a disqualifier on its own. Disqualify only if the role also requires active TS/SCI clearance.
- **"Ability to obtain Secret" clearance** — `-1` scoring penalty, NOT a disqualifier. Only **Active** Secret/TS/SCI or "ability to obtain TS/SCI" are disqualifiers.
- **Public Trust clearance** — NOT a disqualifier (lower-tier background check, routine for many roles).
- **Title with "II"** — NOT a disqualifier. Only `III` / `IV` / `V` are.
- **HIPAA / Healthcare** — `-1` scoring penalty, NOT a disqualifier.
- **FedRAMP buy-side** (CSP pursuing authorization for their own product) — `+1` scoring booster, NOT a disqualifier. Only **3PAO** firms and **FedRAMP-as-a-Service** shops (sell-side) are disqualifiers under Category 4.
- **Bachelor's degree preferred** — NOT a disqualifier. **Bachelor's degree *required*** (without an or-equivalent alternative) is also NOT a disqualifier — it is a `-1` penalty (Category 8). Only **Master's / PhD required** are hard disqualifiers.

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

**Title typos that bypass regex (LLM agents must catch):**
- `lll` (three lowercase L's) — typo for `III`
- `Ill` (capital I + lowercase LL) — typo for `III`
- `L3`, `L4`, `L5` — internal level designators equivalent to III/IV/V
- "Level III" or higher — explicit level designator
- "Tier 3" or higher — explicit tier designator

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
| OCI / Oracle Cloud as primary cloud | No Oracle Cloud experience |
| OCI / Oracle Cloud as only cloud | Cannot meet requirements |
| "Oracle Cloud expertise required" | Direct requirement mismatch |

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

**Location rules are driven by `config.yml` → `location`. Read it first.** `location.remote`
selects the mode; `location.city` / `location.state` / `location.state_abbr` are the
candidate's residence (remote mode) or the target metro (local mode). The deterministic
Python scrapers already enforce this in `scripts/ats_scraper/location.py` — apply the
same logic here as the fuzzy catch. Substitute the configured values wherever this
section writes `{state}`, `{state_abbr}`, `{city}`.

#### When `location.remote: true` (remote-only mode — current default)

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
| Remote but restricted to states that exclude `{state}` | State-restricted remote that excludes the candidate's state is not eligible |
| "Must live in [state list]" without `{state}`/`{state_abbr}` | State-restricted remote, candidate's state not included |
| "Open to residents of [state list]" without `{state}`/`{state_abbr}` | State-restricted remote, candidate's state not included |

**State-restricted remote (description language), using `{state}` from config:**
- "not available in {state}", "except {state}", "all states except {state}"
- Explicit eligible-states lists that omit {state}/{state_abbr} (e.g. "Eligible states: AZ, CA, CO, ...")

#### When `location.remote: false` (local mode — target = `{city}, {state}`)

Hybrid and on-site roles are **acceptable** in local mode — that's the point. Disqualify
instead when the role is neither in the target metro nor a fully-remote US role:
| Trigger | Reason |
|---------|--------|
| Location is not in/near `{city}, {state}` AND not fully-remote US | Outside the target metro |
| International position | Must be US-based |
| "Relocation required" to a metro other than `{city}, {state}` | Not the target location |
| Fully-remote role, only when `location.accept_remote_in_local_mode: false` | Local-only search excludes remote |

(When `accept_remote_in_local_mode: true` — the default — fully-remote US roles are kept alongside local ones.)

**Travel Disqualifications:**
| Trigger | Reason |
|---------|--------|
| Travel percentage >5% | Excessive travel (both modes) |
| "Quarterly on-site meetings" | Regular travel required — disqualifying in **remote** mode only |
| "Occasional office visits required" | Not fully remote — disqualifying in **remote** mode only; expected/fine in local mode |

**Note:** "Annual team summits" may be acceptable—review manually.

**Non-US Locations (full list — applies in BOTH modes; LLM agents must apply even if the location field also says "Remote"):**

Reject if the location field, description, or eligible-states list contains any of these countries/regions:

- **Americas (non-US):** Mexico, Brazil, Argentina, Chile, Colombia, Peru, Latin America, LATAM
- **Canada:** Toronto, Vancouver, Montreal, Calgary, Ottawa, Edmonton, Alberta, Ontario, Quebec, British Columbia, BC — plus any other Canadian city/province
- **Europe:** UK, United Kingdom, Ireland, Germany, France, Netherlands, Spain, Italy, Poland, Romania, Ukraine, Turkey, EMEA
- **Middle East / Africa:** Israel, UAE, South Africa, Egypt, Nigeria, Kenya
- **Asia / Pacific:** India, China, Hong Kong, Taiwan, Japan, South Korea, Singapore, Philippines, Vietnam, Indonesia, Thailand, Malaysia, APAC, Australia, New Zealand

**Country/region codes** (when used as country indicators in the location field):
`CA` (Canada), `MX`, `BR`, `AR`, `CL`, `CO`, `PE`, `UK`, `DE`, `FR`, `NL`, `ES`, `IT`, `PL`, `IN`, `JP`, `KR`, `SG`, `AU`, `NZ`, `IL`, `AE`, `ZA`

### Category 4: Company/Business Model Disqualifications (Score 2-3)

**Business Model Disqualifications:**
| Trigger | Reason |
|---------|--------|
| Managed Service Provider (MSP) | Client-focused work |
| IT Consulting firm | Billable hours culture |
| Staffing/Recruiting agency | Not direct employment |
| FedRAMP-as-a-Service / FedRAMP advisory shop | Sell-side FedRAMP — same Prohibited Activity as a 3PAO regardless of what they call themselves. Examples: stackArmor, Fortreum, Anitian, Steampunk, ScaleSec |

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

**Note:** HIPAA is no longer an automatic disqualifier — apply a -1 penalty instead (see Score Penalties). FedRAMP is **not** a penalty: candidate's prior experience makes FedRAMP environments a +1 booster when the employer is the **CSP buy-side** (pursuing authorization for their own cloud product).

### Category 5: Compensation Disqualifications (Score 0-2)

**⚠️ Clown car low salaries indicate scam postings, offshore arbitrage traps, or companies that have no idea what they're hiring for.**

| Trigger | Reason |
|---------|--------|
| Salary floor is $0 (e.g. "$0 – $200,000/yr") | Nonsense range; company has no idea what the role is worth, scam indicator, or placeholder posting — disqualify immediately regardless of ceiling |
| Salary floor below $70,000/year (e.g. "$50K–$63K", "$55K–$90K", "$45K–$75K") — applies to any US remote infrastructure/DevOps/cloud role regardless of ceiling | Far below market rate; indicative of scam, misclassified contract-to-hire trap, or non-US role mislabeled as remote. **Always evaluate the floor. A high ceiling does not save a low floor. "$50K–$63K" has a floor of $50K and is disqualified.** |
| Apply instructions direct to a personal email (e.g. `@outlook.com`, `@gmail.com`, `@yahoo.com`) | Scam indicator — legitimate companies use ATS systems, not personal inboxes |
| "Send resume to [personal email]" as the only application method | Scam indicator |

**Critical evaluation rule:** When a salary range is shown, the **floor** is the only number that matters for disqualification. Do not average the range. Do not use the ceiling. Do not use the midpoint. If the floor is below $70,000, disqualify immediately — regardless of what the ceiling is.

---

### Category 6: Ghost Job / Pipeline Posting Disqualifications (Score 0-2)

**⚠️ These indicate the position may not actually exist or be actively filled.**

| Trigger | Score | Reason |
|---------|-------|--------|
| LinkedIn "Reposted" badge visible | 0-1 | Strong ghost job signal — role has been cycled without filling, likely collecting resumes |
| "Contingent upon contract award" | 0-1 | Position does not currently exist; company is bench-building for a potential future contract |
| "Contingent upon task order" | 0-1 | Same as above — speculative role pending a government task order award |
| "Contingent upon funding" | 0-1 | Position does not exist yet; dependent on future funding approval |
| "Contingent upon award" | 0-1 | Position does not exist yet; dependent on winning a bid or contract |
| "Contingent pipeline" / "pipeline opportunity" | 0-1 | Explicitly signals a non-active opening; candidate collection for future roles |
| "Talent pool" / "talent community" language | 1-2 | Not an active opening; company is collecting resumes for future use |
| "Building a talent pipeline" / "building a pipeline of candidates" | 0-1 | Explicitly a pipeline posting, not a specific open role |
| "We're always looking for talented..." | 1-2 | Evergreen/pipeline posting, not a specific open role |

**⚠️ "Contingent" keyword handling — read carefully:**

If the word "contingent" appears anywhere in the posting, identify what it is contingent on before disqualifying:

- **Contingent on security background check / clearance investigation** → Routine pre-employment condition. Do NOT disqualify. This is standard practice.
- **Contingent on contract award, task order, funding, bid award, or similar** → Immediate disqualifier (Score 0-1). The role does not currently exist.

Do not skip this classification step. "Contingent" alone is not enough — the object matters.

**Note on LinkedIn "Reposted":** This applies specifically to LinkedIn's repost indicator. A job appearing on multiple boards simultaneously is not the same signal. The concern is a single listing being recycled on LinkedIn, which suggests the role has been open for an extended period without being filled — either because it's a ghost job or the company's hiring bar is unrealistic.

**Note on Government Contractors:** Contingency on contract award is common in government contracting and is sometimes disclosed transparently. These roles are speculative by definition — the company is collecting candidates in case they win a bid. Do not apply until the contract is confirmed.

### Category 7: Cultural Disqualifications (Score 2-3)

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

### Category 8: Experience Level Disqualifications (Score 1-3)

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

**Note on Bachelor's-required:** "Bachelor's / BS / BA degree required" (without an "or equivalent experience" alternative) is **NOT** a disqualifier — apply a `-1` penalty and review manually. With the candidate's experience, degree-required is frequently not enforced; hard-rejecting it costs real volume for a soft requirement. Only **Master's** or **PhD** required remain hard disqualifiers. (See Score Penalties.)

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

### Example 1b: Exceptional — Automation-First Philosophy (Score 10)
```
Position: DevOps Engineer (AAPC example)
Company: Mid-size company
- Base score: 5
- Terraform mentioned: +2
- Ansible not mentioned: +0
- AWS-focused: +2
- Automation-first philosophy (+3): "100% everything as code", "Reusability at heart",
  "automate deployment processes", "100% self-service automation" — 4 qualifying signals
- Capped at: 10
Final Score: 10 (Exceptional — automation philosophy is exact match for candidate profile)
```

### Example 2: Strong Opportunity (Score 7)
```
Position: DevOps Engineer
Company: Tech company (800 employees)
- Base score: 5
- Terraform mentioned: +2
- Ansible not mentioned: +0
- AWS + Azure multi-cloud: +0
- No education requirement specified: +0
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
5. **Check ghost job / pipeline posting signals** - check for repost indicators, contingency language
6. **Check cultural indicators** - look for red flag phrases
7. **Check experience requirements** - verify year requirements

### Scoring Assignment by Disqualification Category

| Disqualification Category | Score Range |
|---------------------------|-------------|
| Technical Misalignment | 0-1 |
| Seniority Level | 0-2 |
| Work Arrangement | 1-2 |
| Company/Industry | 2-3 |
| Ghost Job / Pipeline Posting | 0-2 |
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

- Company size 10,000-25,000 (-1 penalty, not a disqualifier — bureaucracy, not scale, is the concern)
- Bachelor's degree required without "or equivalent" (-1 penalty; only Master's/PhD required disqualify)
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
- GCP or OCI/Oracle Cloud as only cloud platform
- Explicit software development role or "software development experience" requirements
- Non-remote work arrangement — **only when `config.yml` `location.remote: true`** (in local mode, hybrid/on-site in `{city}, {state}` is acceptable)
- State-restricted remote that excludes `{state}` (the candidate's state from `config.yml` `location`) — remote mode only
- 24/7 on-call requirements
- Crypto / Blockchain / Web3 / DeFi companies
- AI startups (<10,000 employees)
- LinkedIn "Reposted" badge visible
- "Contingent upon contract award / task order / funding / award" (any form of contract-contingent language)

---

## Related Documents

- [Job Preferences](../config/job_preferences.md) - Full criteria and requirements
- [Technical Requirements](./technical_requirements.md) - Technical skill matching
- [Company Evaluation Rules](./company_evaluation_rules.md) - Company filtering logic

# End of File
