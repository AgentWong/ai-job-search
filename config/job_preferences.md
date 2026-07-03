# Job Search Preferences

This document defines the criteria and preferences for filtering job opportunities. All workflow prompts and subagents should reference this file when evaluating positions.

---

## Work Arrangement Requirements

**Work arrangement and location are driven by `config.yml` → `location`. Read it first.**
Use `location.remote` (true/false), `location.city`, `location.state`, `location.state_abbr`,
and `location.accept_remote_in_local_mode`. The rules below adapt to the configured mode.

### When `location.remote: true` (remote-only — current default)
- **Required:** Fully remote positions only. `location.state` (e.g. Oregon/ID) is the candidate's residence.
- **Unacceptable:** Hybrid, on-site, or any in-office requirements
- **Unacceptable:** "Remote" positions restricted to a state list that excludes `location.state` / `location.state_abbr`
- **Red Flags:**
  - "Occasional office visits"
  - "Quarterly team meetings in person"
  - "15% travel" or any travel percentage
  - "Must be within commuting distance"

### When `location.remote: false` (local — target = `location.city, location.state`)
- **Required:** Roles in or near `location.city, location.state`. Hybrid and on-site are acceptable here.
- **Also acceptable:** Fully-remote US roles — unless `location.accept_remote_in_local_mode: false`.
- **Unacceptable:** Roles in a different metro that require relocation away from the target.
- The remote-mode travel/office-visit red flags above do **not** apply (on-site is expected locally).

### Geographic Requirements (both modes)
- **Required:** US-based companies only
- **Required:** US-based positions (no international roles)
- **Unacceptable:** International remote positions

---

## Company Profile Requirements

### Company Size
- **Preferred Range:** 100-2,000 employees
- **Minimum:** 50 employees (smaller companies may lack dedicated infrastructure teams)
- **Maximum:** 25,000 employees (larger companies often have bureaucratic processes; 10,000-25,000 incurs a -1 penalty rather than exclusion — scale is not the concern, bureaucracy is)
- **Exemption:** Established federal/government IT contractors (Meridian Federal Systems, SAIC, Booz Allen, CACI, Peraton, Guidehouse, etc.) are exempt from the >25,000 cap. Scale and FedRAMP-authorized infrastructure are the value proposition in this niche; pay bands fit target range. Active/TS/SCI clearance requirements still disqualify on a per-role basis.

### Business Model Requirements
- **Required:** Internal IT/Infrastructure positions
- **Acceptable secondary target:** Cloud Service Providers (CSPs) — companies whose primary commercial product is a SaaS/PaaS/IaaS offering, where FedRAMP (if applicable) is something they pursue *for their own product*, not something they sell to others.
- **Avoid:**
  - Managed Service Providers (MSPs)
  - IT Consulting firms
  - Staffing/Recruiting agencies
  - Professional services firms
  - Defense contractors requiring Active/TS/SCI clearance

### Industry Restrictions
**Avoid these industries due to compliance overhead or cultural misalignment:**
- Financial Services (SOX, regulatory burden)
- Defense/Military requiring Active/TS/SCI clearance (clearance requirements)
- Pharmaceutical/Biotech (heavy regulatory focus)
- Crypto / Cryptocurrency / Blockchain / Web3 (fad industry, high volatility)
- DeFi (Decentralized Finance) (regulatory uncertainty)
- NFT-focused companies (fad industry, market collapse)
- AI startups (<10,000 employees) (fad-chasing, high failure rate)

**Accepted with scoring penalty (-1):**
- Healthcare (HIPAA compliance overhead, but infrastructure work is substantially similar)

**Accepted with scoring boost (+1):**
- FedRAMP environments where the employer is a **CSP buy-side** (pursuing authorization for their own cloud product). Candidate's prior FedRAMP IaC experience is directly relevant.
- Government/Federal without Active or TS/SCI clearance — provided the role is *not* sell-side FedRAMP (3PAO/advisory)

**Note on AI Companies:** Enterprise-scale AI companies (>10,000 employees) like major cloud providers are acceptable. Small AI startups (Series A-C) are chasing a trend without sustainable business models and carry high employment risk.

### Company Culture Red Flags
- "Fast-paced environment"
- "Work hard, play hard"
- "Wear many hats"
- "Startup mentality"
- "Move fast and break things"
- "Always available"
- "Whatever it takes"
- "Firefighting" culture
- "Rockstar/Ninja/Guru" language
- On-call without clear compensation or rotation schedules

---

## Role Requirements

### Target Role Titles
**Primary Targets:**
- Cloud Infrastructure Engineer
- Infrastructure Engineer
- DevOps Engineer (non-management, non-development focused)
- Cloud Engineer
- Platform Engineer
- Site Reliability Engineer (evaluate on-call requirements)
- Infrastructure Automation Engineer
- Cloud Automation Engineer

**Avoid:**
- Backend Engineer/Developer
- Software Engineer
- Full Stack Engineer
- Any role requiring "software development experience" (not just scripting)

### Experience Level
- **Target:** 2-5 years infrastructure experience
- **Acceptable:** Mid-level or intermediate positions
- **Unacceptable Senior Indicators:**
  - Titles: Senior/Sr/Lead/Principal/Staff/Manager/Director
  - Roman numerals: III or higher (II may be acceptable)
  - Explicit mentorship requirements
  - Team leadership responsibilities
  - Primary architectural decision-making responsibility

### Education Requirements
- **Background:** Associate's degree in IT
- **Acceptable:**
  - "Degree preferred"
  - "Degree or equivalent experience"
  - "Relevant education or experience"
- **Concerning (-1 penalty, not disqualifying):** "Bachelor's degree required" without an "or equivalent experience" alternative — frequently unenforced; review manually
- **Disqualifying:** "Master's degree required", "PhD required"

---

## Technical Requirements

### Required Technical Focus
- Cloud infrastructure management (AWS primary)
- Infrastructure-as-Code (Terraform and/or Ansible)
- Cloud automation and CI/CD for infrastructure
- Configuration management

### Cloud Platform Preferences
1. **AWS-primary** (highest priority, +2 score boost)
2. **AWS + Azure multi-cloud** (acceptable, neutral)
3. **Azure-primary with AWS secondary** (lower priority, -1 penalty)
4. **GCP as primary/exclusive** (automatic disqualification)

### IaC Tool Preferences
- **Terraform:** Strongly preferred (+2 score boost)
- **Ansible:** Strongly preferred (+2 score boost)
- **CloudFormation:** Acceptable
- **Pulumi:** Acceptable

### Programming Boundaries
**Acceptable:**
- "Python scripting"
- "Shell scripting"
- "Basic Python"
- "Automation scripts"
- "Configuration scripts"
- "Infrastructure scripting"
- "Operational scripting"

**Disqualifying:**
- "Software development experience" (key phrase - immediate disqualifier)
- "Software development experience using Python, Go, bash, or other languages"
- "Development experience" for building applications
- "Python development"
- "Software development in Python"
- "Python expertise"
- "Advanced Python programming"
- "Python frameworks" (Django, Flask, FastAPI)
- "Object-oriented programming"
- "Software design patterns"
- Backend/fullstack development
- Microservices development
- API development (beyond infrastructure tooling)
- "Build and maintain internal tools" as primary duty
- "Develop automation frameworks" (vs using/configuring them)

**⚠️ KEY DISTINCTION:**
The difference is between *using* existing tools and writing scripts vs *developing* software/applications. If a job posting mentions "software development experience" as a requirement, it is a software developer role disguised as infrastructure—reject immediately.

### Technical Red Flags
- Bare-metal infrastructure focus (KVM, QEMU, hypervisor management)
- GPU passthrough, RDMA technologies
- Heavy Kubernetes development (vs. operations)
- Primary focus on application development

---

## Compliance Considerations

### Compliance Considerations
**Avoid (disqualifying):**
- SOX
- PCI-DSS (unless clearly infrastructure-focused)
- Active security clearance (Secret, Top Secret, TS/SCI)
- Ability to obtain Top Secret/SCI

**Accept with penalty (-1):**
- HIPAA (healthcare infrastructure work is similar to standard cloud work)
- Basic "ability to obtain" Secret clearance

**Accept with boost (+1):**
- FedRAMP — when the employer is a **CSP buy-side** (the CSP pursuing authorization for their own product, not a 3PAO selling assessment/advisory services). Prior FedRAMP IaC experience is a direct match.

---

## Salary Requirements

- **Minimum:** $80,000 USD
- **Target Range:** $100,000 - $130,000 USD
- **Upper Caution:** $150,000+ may carry senior-level expectations

---

## Summary Decision Matrix

| Criterion | Required | Preferred | Avoid |
|-----------|----------|-----------|-------|
| Work arrangement | ✅ Per `config.yml` `location.remote`: fully remote (true) OR in `city, state` incl. hybrid/on-site (false) | - | Remote mode: hybrid/on-site, state-restricted excluding `{state}`. Local mode: other metros |
| Location | ✅ US-based; remote→available in `{state}`, local→in `{city}, {state}` (remote-US also OK) | - | International; remote mode: state-restricted without `{state}` |
| Company Size | 50-25,000 | 100-2,000 | <50 or >25,000 |
| Business Model | ✅ Internal IT | - | MSP, consulting |
| Cloud Platform | - | AWS | GCP-exclusive |
| IaC Tools | - | Terraform, Ansible | None mentioned |
| Experience Level | Mid-level | 2-5 years | Senior titles |
| Programming | Scripting OK | - | Development focus |
