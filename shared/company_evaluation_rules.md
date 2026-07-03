# Company Evaluation Rules

This document defines the systematic criteria for evaluating and filtering companies during job search workflows. The focus is on **exclusion** - identifying companies that should be removed from consideration.

---

## Evaluation Philosophy

This is an **exclusion-focused** workflow. The goal is to systematically remove unsuitable companies, not to recommend companies for application. Companies that pass all exclusion filters proceed to individual position analysis.

---

## Mandatory Exclusions

### Business Model Exclusions

Companies with the following business models should be **automatically excluded**:

| Business Model | Reason | Detection Signals |
|----------------|--------|-------------------|
| **Managed Service Providers (MSPs)** | Client-focused work, reactive support | "managed services", "client infrastructure", "MSP", multiple client references |
| **IT Consulting Firms** | Project-based, billable hours culture | "consulting", "client engagements", "professional services" |
| **Staffing/Recruiting Agencies** | Contractor placement, not direct hire | "staffing", "recruiting", "placement", "contract roles" |
| **Defense Contractors (requiring Active/TS/SCI clearance)** | Clearance requirements, specialized focus | "defense", "military", "DoD", Active clearance required |

### Company Size Exclusions

| Size Category | Employee Count | Exclusion Reason |
|---------------|----------------|------------------|
| **Too Small** | < 50 employees | May lack dedicated infrastructure teams, limited resources, "wear many hats" expectations |
| **Too Large** | > 25,000 employees | Bureaucratic processes, limited individual impact, slow decision-making |

**Preferred Range:** 100-2,000 employees (mid-size with specialized teams)

**Note on the 10,000-25,000 band:** Companies in this range are **not excluded** — apply a `-1` scoring penalty instead (see Scoring Framework). The size cap exists to filter bureaucratic mega-corps, but large mature companies are well-resourced, have dedicated infrastructure teams, and are the *opposite* of the overwork risk that small startups carry. Scale itself is not the concern; bureaucracy is. The hard cap moves to >25,000.

**Federal-contractor exemption to the size cap:** Established federal/government IT contractors (e.g., Meridian Federal Systems, SAIC, Booz Allen, CACI, Peraton, Guidehouse) are **not** automatically excluded by size, even above the >25,000 cap. The size cap exists to filter bureaucratic commercial mega-corps; in the federal-contractor niche, scale and FedRAMP-authorized infrastructure are the value proposition, and pay bands ($110–160K) actually fit the candidate's target. These companies still must pass the clearance filter (Active/TS/SCI required → disqualify; basic obtainable Secret → -1 penalty).

### Industry Exclusions

The following industries should be excluded due to compliance overhead, cultural misfit, or regulatory burden:

| Industry | Primary Concern | Secondary Concerns |
|----------|-----------------|-------------------|
| **Financial Services** | SOX compliance, regulatory burden | Conservative culture, legacy systems |
| **Defense/Military (requiring Active/TS/SCI clearance)** | Clearance requirements | Specialized focus, restricted work |
| **Pharmaceutical/Biotech** | FDA regulations | Heavy compliance, slow processes |
| **Cryptocurrency/Blockchain** | Fad industry, high volatility | Unstable employment, regulatory uncertainty |
| **Web3/DeFi/NFT** | Fad industry, market collapse | Unproven business models |

**Note on Healthcare:** Healthcare companies are no longer automatically excluded. HIPAA compliance adds overhead but the actual infrastructure work (AWS, Terraform, etc.) is substantially similar. Apply a -1 scoring penalty for HIPAA environments.

**Note on Government:** Government employers and contractors are acceptable if they do not require Active security clearance or Top Secret/SCI. Roles requiring basic obtainable clearance should be reviewed manually with a -1 scoring penalty.

**Note on Cloud Service Providers (CSPs) and FedRAMP:** CSPs (companies whose primary commercial product is a SaaS/PaaS/IaaS offering) are an acceptable secondary target — including ones that pursue FedRAMP authorization for their own product. The candidate's prior FedRAMP experience is a +1 booster in this case.

### Fad Industry Exclusions

Companies in trendy/speculative sectors should be **automatically excluded**:

| Category | Detection Signals | Reason |
|----------|-------------------|--------|
| **Cryptocurrency** | "crypto", "cryptocurrency", "Bitcoin", "Ethereum", mining | Volatile industry, unstable employment |
| **Blockchain** | "blockchain", "distributed ledger", "smart contracts" (as primary focus) | Fad technology, limited practical adoption |
| **Web3** | "Web3", "decentralized web", "dApps" | Speculative sector, unproven models |
| **DeFi** | "DeFi", "decentralized finance", "yield farming", "liquidity pools" | Regulatory uncertainty, high risk |
| **NFT** | "NFT", "non-fungible token", "digital collectibles" | Market collapse, fad product |
| **AI Startups** | "AI-first", "AI-native", "ML startup" with <10,000 employees | Fad-chasing, high failure rate, unproven business model |

**Note on AI Companies:** Enterprise-scale AI companies (>10,000 employees) or established AI research labs (Anthropic, OpenAI, etc.) are acceptable. The exclusion targets small AI startups (Series A-C) chasing the AI trend without sustainable business models.

---

## Research Protocol

For each unique company discovered in search results:

### Step 1: Basic Information Gathering
- Company website review
- Employee count (LinkedIn, company page)
- Business model identification
- Industry classification

### Step 2: Exclusion Criteria Application
Apply each exclusion category systematically:

```
FOR each company:
    IF business_model IN excluded_business_models:
        EXCLUDE with reason "Business Model: {model}"
    ELSE IF employee_count < 50:
        EXCLUDE with reason "Company Size: Too small ({count} employees)"
    ELSE IF employee_count > 25000:
        EXCLUDE with reason "Company Size: Too large ({count} employees)"
    ELSE IF industry IN excluded_industries:
        EXCLUDE with reason "Industry: {industry}"
    ELSE:
        PASS to position analysis
```

### Step 3: Documentation
For each excluded company, document:
- Company name
- Number of positions excluded
- Primary exclusion reason
- Business model (if identified)
- Additional notes

---

## Borderline Cases

### Companies That May Pass (Use Judgment)

| Scenario | Decision Guidance |
|----------|-------------------|
| **Fintech (not pure finance)** | May pass if tech-focused, not banking |
| **Company size 50-100** | May pass if growing rapidly, modern tech stack |
| **Company size 5,000-25,000** | May pass; apply -1 penalty (10K-25K). Scale is not disqualifying — bureaucracy is the concern |
| **Government without clearance** | Acceptable; apply -1 penalty if basic clearance obtainable |

### Companies That Always Fail

| Scenario | Reason |
|----------|--------|
| **Defense contractor requiring Active/TS/SCI clearance** | Clearance requirements |
| **Pure MSP** | Client-focused work model |
| **Bank/insurance IT** | Regulatory compliance focus |
| **Staffing agency** | Not direct employment |

---

## Output Format

### Qualified Companies Dataset
```csv
Company_Name,Job_Title,URL,Company_Size,Business_Model,Industry_Sector,Exclusion_Applied
TechCorp,DevOps Engineer,https://...,500,Product Company,SaaS,None
```

### Excluded Companies Dataset
```csv
Company_Name,Excluded_Positions_Count,Exclusion_Reason,Business_Model,Additional_Notes
MSPCo,3,Business Model: MSP,Managed Services Provider,Primary business is client IT management
BigBank,2,Industry: Financial Services,Internal IT,Large bank with SOX compliance requirements
```

---

## Success Metrics

A well-executed company evaluation should:

- **Exclude 30-50%** of companies based on systematic criteria
- **Provide clear rationale** for each exclusion
- **Avoid false exclusions** of legitimate product companies
- **Complete quickly** using simple string matching and basic research

---

## Related Documents

- [Exclusions Configuration](../config/exclusions.yml) - Pre-defined exclusion lists
- [Job Preferences](../config/job_preferences.md) - Full preference criteria
- [Scoring Framework](./scoring_framework.md) - Position scoring after company passes
