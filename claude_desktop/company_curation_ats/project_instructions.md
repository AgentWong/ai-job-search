# Company Curation for ATS API Targets via Claude Desktop Research Mode

Discover and evaluate companies whose career pages are hosted on ATS platforms with public APIs. Output a CSV artifact of qualified companies for automated job extraction.

**This is a pilot project to build a sample set of companies whose jobs can be queried via public ATS APIs.**

---

## Goal

Find 20-30 companies that:
1. Have career pages hosted on a **compatible ATS platform** with a public API (see Target ATS Platforms below)
2. Hire for remote US cloud infrastructure roles (DevOps, Platform, SRE, Cloud Engineer)
3. Pass all exclusion criteria (size, industry, business model, offshoring)

**Secondary target — Cloud Service Providers (CSPs):** Companies whose primary commercial product is a SaaS/PaaS/IaaS offering are an acceptable secondary target, *including* CSPs that pursue FedRAMP authorization for their own product (the candidate has relevant FedRAMP IaC experience). The hard line is **sell-side FedRAMP** — see the 3PAO / FedRAMP-as-a-Service exclusion below.

---

## Target ATS Platforms

Only include companies whose career pages are hosted on one of these platforms. These have confirmed open/public API access for job listings with no employer credentials required:

| Platform | How to Identify | API Endpoint Pattern |
|----------|----------------|---------------------|
| **Greenhouse** | Career page URL contains `boards.greenhouse.io` or redirects there; iframes from `boards-api.greenhouse.io` | `boards-api.greenhouse.io/v1/boards/{token}/jobs` |
| **Lever** | Career page URL contains `jobs.lever.co` or redirects there | `api.lever.co/v0/postings/{company}` |
| **Ashby** | Career page URL contains `jobs.ashbyhq.com` or embeds from `api.ashbyhq.com` | `api.ashbyhq.com/posting-api/job-board/{name}` |
| **SmartRecruiters** | Career page URL contains `jobs.smartrecruiters.com` or uses SmartRecruiters widget | `api.smartrecruiters.com/v1/companies/{id}/postings` |
| **Recruitee** | Career page URL contains `*.recruitee.com` | `{slug}.recruitee.com/api/offers` |
| **Pinpoint** | Career page URL contains `*.pinpointhq.com` | `{slug}.pinpointhq.com/postings.json` |
| **Rippling** | Career page URL contains `ats.rippling.com` | `api.rippling.com/platform/api/ats/v1/board/{slug}/jobs` |
| **Comeet** | Career page URL contains `comeet.co` or embeds the Comeet widget | `comeet.co/careers-api/2.0/company/{uid}/positions?token={token}` (UID *and* public widget token are both required — both are embedded in the career-page HTML, neither is a credential) |
| **Workday** | Career page URL contains `*.myworkdayjobs.com` | `{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` (POST, undocumented) |
| **BambooHR** | Career page URL contains `*.bamboohr.com/careers` | `{slug}.bamboohr.com/careers/list` (list, JSON with `Accept: application/json`) + per-job HTML detail page with embedded JSON for description |
| **Breezy HR** | Career page URL contains `*.breezy.hr` | `{slug}.breezy.hr/json` (list) + per-position HTML page with `JobPosting` JSON-LD for description |
| **Oracle Recruiting Cloud** | Career page URL matches `{POD}.fa.{DC}.oraclecloud.com/hcmUI/CandidateExperience/...` or `{POD}.fa.oraclecloud.com/...` or `{POD}.fa.ocs.oraclecloud.com/...` (replaces legacy Taleo; DO NOT confuse with Taleo `*.taleo.net`) | `{base}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?finder=findReqs;siteNumber={site},...` — the `siteNumber` is the path segment after `/sites/` in the career URL (e.g. `jobsearch`, `CX_1`, `CX_1001`) |
| **Trakstar Hire** | Career page URL contains `*.recruiterbox.com` or `*.hire.trakstar.com` (Trakstar is migrating subdomains; the API path is unchanged) | `jsapi.recruiterbox.com/v1/openings?client_name={slug}` (returns structured `allows_remote` boolean) |
| **Polymer** | Career page URL contains `*.polymer.co` or embeds the Polymer widget from `app.polymerhq.io` | `api.polymer.co/v1/hire/organizations/{slug}/jobs` (returns structured `remote_restriction_country_list`) |
| **Gem ATS** | Career page URL contains `jobs.gem.com/{slug}` (only Gem **ATS** customers — Gem's *sourcing* CRM does not host public boards) | `api.gem.com/job_board/v0/{slug}/job_posts/` (Greenhouse-style flat list response) |
| **Careerpuck** | Career page URL contains `app.careerpuck.com` or embeds the Careerpuck widget | `api.careerpuck.com/v1/public/job-boards/{slug}` — **DEDUP CAVEAT**: Careerpuck is often a front-end overlay on Greenhouse/Lever; if the same company is reachable via the underlying ATS, prefer that platform (the `atsSourcePlatform` field in each job confirms the underlying source) |
| **Eightfold** | Career page URL contains `{subdomain}.eightfold.ai` or its careers subdomain CNAMEs to it | `{subdomain}.eightfold.ai/api/apply/v2/jobs?domain={domain}` — most enterprise tenants are anonymous, but some (Qualcomm, Citi, Starbucks, Amex) have moved to the gated PCSX search and return `403 "Not authorized for PCSX"`; verify with a test request before adding |
| **Dayforce HCM** | Career page URL contains `jobs.dayforcehcm.com/{locale}/{namespace}/{boardCode}` (typical board codes: `CANDIDATEPORTAL`, `CAREER`, `JOBS`) | `jobs.dayforcehcm.com/api/geo/{namespace}/jobposting/search` (POST). Two-step CSRF flow: first `GET /api/auth/csrf` to obtain `csrfToken`, then POST with `X-CSRF-Token` header. Full job description returned inline — no detail fetch needed. Cloudflare-fronted but passes through with a browser-like User-Agent. Skews enterprise (1,000+ employees); treat as a Workday/ORC/Eightfold-class secondary target. |
| **Workable** | Career page URL contains `apply.workable.com/{slug}` or `{slug}.workable.com`, or company career page embeds the Workable widget pointing at `apply.workable.com` | The scraper tries three unauthenticated career-widget endpoints in fallback order: `www.workable.com/api/accounts/{slug}?details=true` → `apply.workable.com/api/v1/widget/accounts/{slug}` → `apply.workable.com/api/v3/accounts/{slug}/jobs` (POST). The `{slug}` is the company's Workable subdomain. **Not** the documented `workable.com/spi/v3/...` API, which requires an account-owner Bearer token; these endpoints power the public widget and need no credentials. |
| **iSolvedHire** (ApplicantPro) | Career page URL contains `{subdomain}.isolvedhire.com` (the ApplicantPro careers product) | `{subdomain}.isolvedhire.com/core/jobs/{domain_id}?getParams={}` (list, JSON — returns every posting in one call, no pagination) + `{subdomain}.isolvedhire.com/core/jobs/{domain_id}/{job_id}/job-details` (per-job description). `{domain_id}` is the numeric internal site id (distinct from the subdomain); the scraper auto-resolves it from the `domainId : NNNN` bootstrap value embedded in the `/jobs/` page, so only the subdomain is required. The `getParams={}` query arg is mandatory (the controller JSON-decodes it). |

**Excluded ATS platforms** (require employer credentials, no public API):
- Jobvite, iCIMS, Taleo (legacy — replaced by Oracle Recruiting Cloud, which IS supported), JazzHR, Teamtailor

**Gray zone** (limited/undocumented public access — do NOT include):
- SAP SuccessFactors (XML feed at `career{N}.successfactors.com/career?company={ID}&resultType=XML` works but the scraper does not yet parse XML — defer until a fetcher is added)
- Phenom / Cornerstone (CSOD) / Paycom (require token-extraction bootstrap from the career-page HTML — defer until token-tier fetchers are added)
- Zoho Recruit / HireHive / Recooty / GoHire / CareerPlug (HTML / JSON-LD scraping; the scraper is currently JSON-API-only). **Note:** iSolvedHire / ApplicantPro (`*.isolvedhire.com`) IS now supported — see the Target ATS Platforms table above; it exposes a public JSON API.
- ADP MyJobs / ADP Workforce Now / HiringThing (pure JS-SPA — require Playwright)
- Freshteam (sunset by Freshworks: renewals halted Mar 2026, full shutdown Apr 2027 — actively shrinking customer base)
- Oleeo / TalNet (Cloudflare interstitial blocks plain `requests`; UK-skewed customer base)
- Personio / Homerun / Join.com (EU/DACH-skewed; minimal US-remote DevOps yield)

---

## Input Context

The user will paste the contents of these files into the conversation. You need all of them before starting:

1. **Exclusions list** (`exclusions.yml`) — companies to skip entirely
2. **Inclusions config** (`config.yml`) — target roles and ATS platforms already covered
3. **Company evaluation rules** (`company_evaluation_rules.md`) — exclusion criteria
4. **Job preferences** (`job_preferences.md`) — role requirements, technical stack, salary
5. **Existing ATS targets** (`company_targets_ats.json`) — lean list of companies already in the ATS pipeline. Use this for duplicate detection.

The JSON file contains only `name`, `company_url`, `career_page_url`, and `ats_platform` per entry. It is the canonical dedup source for this workflow — do not request the full CSV. The CSV carries paragraphs of research notes per row that consume context without helping with deduplication.

If any of these five inputs are missing, ask the user to provide them before proceeding.

### How to check if a candidate company is already covered

For every company you consider returning, perform this check using the JSON input:

1. Normalize the candidate's name to lowercase and compare against every `name` in `company_targets_ats.json` (case-insensitive match). If found → already covered, skip.
2. Compare the candidate's career page URL against every `career_page_url` (case-insensitive, ignore trailing slashes). If found → already covered, skip.
3. Compare the candidate's primary domain against every `company_url`. If found → already covered, skip.

Any single hit across these three checks means the company is already on the monitored list. Do not re-add.

---

## Research Strategy

This is a **breadth-first query**. Deploy 3-5 research subagents in parallel, each covering a different search angle. Each subagent should apply the full exclusion criteria before returning results, so only qualified companies reach you.

### Subagent Allocation

**Subagent 1: DevOps/Infrastructure role search on ATS platforms**
Search for companies actively hiring DevOps Engineers, Infrastructure Engineers, and Cloud Engineers for remote US positions. Focus on mid-size tech companies (100-2,000 employees) whose career pages are hosted on Greenhouse, Lever, or Ashby. Search job boards and aggregators for listings that originate from these ATS platforms.

**Subagent 2: Platform/SRE role search on ATS platforms**
Search for companies hiring Platform Engineers and Site Reliability Engineers for remote US positions. Focus on SaaS, developer tools, and observability companies. Look specifically for career pages hosted on SmartRecruiters, Recruitee, Pinpoint, Rippling, Trakstar Hire, Polymer, or Gem ATS.

**Subagent 3: Industry vertical search with ATS identification**
Search for companies in specific verticals known to have good infrastructure teams: developer tools, data infrastructure, cybersecurity, e-commerce platforms, EdTech, MarTech. For each company found, verify that their career page is hosted on one of the target ATS platforms. Companies with self-hosted career pages should be skipped.

**Subagent 4: ATS platform directory mining**
Search for published lists of companies known to use specific ATS platforms: "companies using Greenhouse", "Lever customers", "Ashby customers", "Trakstar Hire customers" (formerly Recruiterbox), "Polymer hire customers", curated ATS customer directories, and tech company career page roundups. Cross-reference against infrastructure hiring and remote US positions.

**Subagent 5 (optional): Workday tenant discovery**
Search for mid-size tech companies (100-2,000 employees) whose career pages use Workday (`*.myworkdayjobs.com`). Workday is the highest-value mid-market target but requires extra discovery effort (tenant name, data center number). Document the full Workday career page URL for each company found.

**Subagent 6 (optional): Oracle Recruiting Cloud, Eightfold, and Dayforce enterprise discovery**
Search for **larger enterprises** (1,000–10,000 employees) whose career pages are hosted on Oracle Recruiting Cloud (`*.fa.*.oraclecloud.com`, `*.fa.oraclecloud.com`, or `*.fa.ocs.oraclecloud.com`), Eightfold (`*.eightfold.ai`), or Dayforce HCM (`jobs.dayforcehcm.com/{locale}/{namespace}/{boardCode}`). These are former Taleo / iCIMS / SuccessFactors estates that are now newly accessible. ORC requires both the POD identifier (parsed from hostname) and the `siteNumber` (parsed from `/sites/{name}/`); Eightfold requires both the subdomain and the company's web domain; Dayforce requires both the `clientNamespace` and the `jobBoardCode` (both parsed from the career URL). **Verify the API responds anonymously before recording** — some Eightfold tenants (Qualcomm, Citi, Starbucks, Amex) are gated behind PCSX and return 403. Test by hitting the appropriate endpoint with a browser User-Agent. Document the full career-page URL so the scraper can parse the host components.

---

## Mandatory Instructions for ALL Subagents

Include the following rules verbatim in every subagent prompt:

### ATS Platform Verification — CRITICAL

**The entire point of this workflow is to find companies on compatible ATS platforms.** Every company you return MUST have a career page hosted on one of these platforms:

- `boards.greenhouse.io` / Greenhouse
- `jobs.lever.co` / Lever
- `jobs.ashbyhq.com` / Ashby
- `jobs.smartrecruiters.com` / SmartRecruiters
- `*.recruitee.com` / Recruitee
- `*.pinpointhq.com` / Pinpoint
- `ats.rippling.com` / Rippling
- `comeet.co` / Comeet
- `*.myworkdayjobs.com` / Workday
- `*.bamboohr.com/careers` / BambooHR
- `*.breezy.hr` / Breezy HR
- `*.fa.*.oraclecloud.com`, `*.fa.oraclecloud.com`, `*.fa.ocs.oraclecloud.com` / Oracle Recruiting Cloud
- `*.recruiterbox.com` or `*.hire.trakstar.com` / Trakstar Hire
- `*.polymer.co` / Polymer
- `jobs.gem.com/*` / Gem ATS (only paths under jobs.gem.com — Gem's sourcing CRM does **not** host public boards)
- `app.careerpuck.com` / Careerpuck (note: often a front-end over Greenhouse/Lever — prefer the underlying ATS if reachable)
- `*.eightfold.ai` / Eightfold
- `jobs.dayforcehcm.com/*` / Dayforce HCM
- `apply.workable.com/*` or `*.workable.com` / Workable
- `*.isolvedhire.com` / iSolvedHire (ApplicantPro)

**How to verify:** When you visit a company's careers page, check where it redirects to or what domain serves the job listings. The career page URL itself or its underlying iframe/redirect must point to one of the above domains.

**Eightfold extra step:** Eightfold tenants split into two groups — anonymous v2 (works) and gated PCSX (returns `403 "Not authorized for PCSX"`). Before recording an Eightfold company, fetch `https://{subdomain}.eightfold.ai/api/apply/v2/jobs?domain={domain}&hl=en&start=0&num=5` with a browser User-Agent. If you get a 200 with a `positions` array → include. If 403 → skip and note the gating in research notes.

**Oracle Recruiting Cloud extra step:** ORC's `siteNumber` is a required API parameter — extract it from the path segment after `/sites/` in the career-page URL (typical values: `jobsearch`, `CX_1`, `CX_1001`, `nfcu`). Without the site number the scraper cannot query the tenant.

**Dayforce extra step:** Dayforce's API requires both the `clientNamespace` AND `jobBoardCode` — both are path segments of the career URL `https://jobs.dayforcehcm.com/{locale}/{namespace}/{boardCode}` (e.g. `paradigm` and `CANDIDATEPORTAL` from `https://jobs.dayforcehcm.com/en-US/paradigm/CANDIDATEPORTAL`). To verify a tenant is live, fetch `https://jobs.dayforcehcm.com/api/auth/csrf` (GET) for a token, then POST `{"clientNamespace": "...", "jobBoardCode": "...", "cultureCode": "en-US", "distanceUnit": 0, "paginationStart": 0}` to `https://jobs.dayforcehcm.com/api/geo/{namespace}/jobposting/search` with the `X-CSRF-Token` header set to the token from step 1. A response with `maxCount > 0` confirms the tenant is active.

**If a company has a self-hosted career page or uses a non-target ATS platform (Jobvite, iCIMS, legacy Taleo, JazzHR, Teamtailor, Phenom, Cornerstone, Paycom, Zoho Recruit, ADP, SuccessFactors, etc.), skip it.**

### Exclusion Pre-Check — Do This FIRST Before Any Research

**Before visiting any company's career page or investing research time**, apply these checks in order. If a company fails any check, skip it immediately and move on to the next candidate. Do NOT scrape, fetch, or investigate further.

1. **Already monitored?** Cross-reference the candidate against `company_targets_ats.json` using all three of: name (case-insensitive), `career_page_url` (case-insensitive, ignore trailing slash), and `company_url` (primary domain). If any of the three match → skip immediately.
2. **Already excluded?** Cross-reference against the `exclusions.yml` excluded companies list (case-insensitive substring match). If found → skip immediately.
3. **Excluded industry/model?** Based on the company's known description from search results, does it obviously match a disqualifying category (crypto, MSP, staffing, AI startup <10K employees, etc.)? If yes → skip immediately without visiting the career page.

Only proceed to career page research for companies that pass all three checks above.

---

### Company Exclusion Criteria — Apply Before Returning

Each subagent MUST apply these filters. Do NOT return companies that fail any check.

**Business Model Exclusions (automatic disqualification):**
- Managed Service Providers (MSPs) — "managed services", "client infrastructure"
- IT Consulting firms — "consulting", "client engagements", "professional services"
- Staffing/Recruiting agencies — "staffing", "recruiting", "placement"
- Defense contractors **requiring Active/TS/SCI clearance** — the clearance requirement is the disqualifier, not the contractor status itself
- **3PAOs and FedRAMP-as-a-Service shops** — non-compete risk from candidate's prior employment at Coalfire. Named 3PAOs include Coalfire, Schellman, A-LIGN, Kratos, Moss Adams. FedRAMP advisory / FaaS shops include stackArmor, Fortreum, Anitian, Steampunk, ScaleSec. Sell-side FedRAMP language: "help *our clients* achieve ATO", "FedRAMP-as-a-Service", "deliver FedRAMP-ready landing zones to customers", "reusable accelerators for client engagements". The label (CSP/MSP/MSSP/"platform provider") is not the signal — read the actual service description.

**Government / Federal Contractors — Acceptable with Caveats:**
Government employers and federal contractors are **not** automatically excluded. Apply these rules:
- If the role **requires Active/Secret/TS/SCI clearance** → disqualify that role
- If the role requires a **basic obtainable clearance** (e.g., "ability to obtain Public Trust") → include, flag with `-1` scoring penalty in `Extraction_Notes`
- If the role has **no clearance requirement** → include normally
- Established federal-IT contractors (GDIT, SAIC, Booz Allen, CACI, Peraton, Guidehouse, etc.) are **also exempt from the 10,000-employee size cap** — scale and FedRAMP-authorized infrastructure are the value proposition in this niche and pay bands fit the candidate's target range

**Acceptable secondary target — Cloud Service Providers (CSPs):**
A CSP whose primary commercial product is a SaaS/PaaS/IaaS offering is acceptable, including ones pursuing FedRAMP authorization for their own product (buy-side FedRAMP). Safe-side signals: "Helping us prepare *our* product for FedRAMP", "Building *our* FedRAMP boundary", "Maintaining *our* ConMon posture". The candidate has prior FedRAMP IaC experience and these roles are a strong fit.

**Industry Exclusions (automatic disqualification):**
- Cryptocurrency / Blockchain / Web3 / DeFi / NFT
- AI startups with <10,000 employees ("AI-first", "AI-native", "ML startup")
- GPU Cloud companies (primary product is GPU compute or AI model hosting)
- Financial Services / Banking / Insurance
- Pharmaceutical / Biotech

**Company Size:**
- Minimum: 50 employees
- Maximum: 10,000 employees for commercial companies (25,000 with -1 penalty)
- **No size cap for established federal/government IT contractors** — see above
- Preferred: 100-2,000 employees

**Position Viability — Check These Before Including:**
- Record the seniority mix of currently visible infrastructure roles in `Extraction_Notes` (e.g., "all senior-titled", "mix of mid + senior", "one Cloud Engineer II open"). Senior titles to flag: Senior/Sr/Lead/Principal/Staff/Manager/Director/Architect/III+. **Do not exclude a company on seniority alone.** The 2026 market is in a "high fire, low hire" holding pattern; companies whose current snapshot is senior-only often open mid-level posts later in the cycle, and capturing them now means they're already monitored when that happens.
- Company should show evidence of remote US hiring (not just remote-EMEA or remote-APAC)
- If >80% of visible roles are on-site/hybrid, exclude as non-remote culture
- If >40% of positions are in offshore locations (India, Philippines, APAC-only), exclude as heavy offshoring

### Excluded Companies — Do NOT Return These

The user has provided an exclusions list. Cross-reference every company you find against this list using case-insensitive matching. Skip any match.

Also skip any company already present in the existing `company_targets_ats.json` — check by name, `career_page_url`, and `company_url` as described in the Exclusion Pre-Check above.

---

## What Each Subagent Should Return (intermediate format — NOT the final output)

This key-value format is for **subagent-to-lead-agent reporting only**. The lead agent MUST transform it into the single CSV codeblock described in Step 4 below. Do **not** emit the final report as a list of per-company key-value blocks — the downstream parser will read zero rows and the run will be wasted.

For each qualifying company, the subagent returns:

```
Company Name: [name]
Company URL: [https://company.com]
Career Page URL: [full URL of the ATS-hosted career page, e.g., https://boards.greenhouse.io/companyname]
ATS Platform: [Greenhouse | Lever | Ashby | SmartRecruiters | Recruitee | Pinpoint | Rippling | Comeet | Workday | BambooHR | Breezy | Oracle | Trakstar | Polymer | Gem | Careerpuck | Eightfold | Dayforce | Workable | iSolvedHire]
ATS Slug/Token: [the company identifier used in the API endpoint — see "ATS_Slug formatting" in Step 4 below for per-platform format]
Employee Count Estimate: [e.g., ~500, 100-500]
Company Focus: [one-line description of what the company does]
Remote Culture: [evidence of remote hiring — e.g., "careers page shows 60% remote roles"]
Infrastructure Roles Seen: [list any infra/DevOps/Cloud/Platform/SRE roles visible]
Seniority Assessment: [entry/mid-level roles available? or all senior?]
Clearance Note: [none required | basic obtainable (-1 penalty) | Active/TS/SCI required (disqualify)]
Exclusion Check: PASS [or reason for concern]
Source: [URL where you found this company]
```

---

## Lead Agent: Aggregation

After all subagents complete:

### Step 1: Deduplicate within subagent results
Remove companies that appear in multiple subagent results (case-insensitive name match, also compare career page URLs).

### Step 2: Final Exclusion Gate — MANDATORY re-check against JSON inputs

Subagents have been observed to return companies that are already in the monitored list even after being told not to. **The lead agent MUST re-verify every candidate against the JSON inputs before emitting the final report.** Do not trust the subagents' own dedup claims.

For each candidate in the merged pool, perform all three checks:

1. Name match (case-insensitive) against `name` fields in `company_targets_ats.json` → discard if match
2. Career page URL match (case-insensitive, ignore trailing slash) against `career_page_url` fields → discard if match
3. Primary domain match against `company_url` fields → discard if match

Also cross-reference against:
- `exclusions.yml` excluded companies list (case-insensitive substring match)
- Non-target ATS platforms (discard any that slipped through on a non-compatible platform)

Log the counts for each discard reason in the final summary so you can see whether the JSON check actually fired — if it reports zero discards when the input was 30+ candidates, you probably skipped this step.

### Step 3: Assess Viability
For each remaining company, verify:
- Infrastructure hiring footprint exists (a current senior-only snapshot is acceptable — record the seniority mix in `Extraction_Notes` rather than excluding)
- Remote US positions are available
- Career page is confirmed on a target ATS platform
- ATS slug/token has been identified for API access

### Step 4: Generate CSV Artifact — STRICT FORMAT REQUIREMENTS

The final report MUST contain **exactly one fenced codeblock** holding all qualified companies as CSV. The downstream Python parser (`scripts/curation_appender/report_parser.py`) reads only the inside of fenced codeblocks whose first line starts with `Company_Name`. If you emit the data in any other shape — multiple per-company codeblocks, key-value blocks, a markdown table, or prose — the parser will read zero rows and the entire run is wasted.

**Format checklist (all of these must hold):**

1. The codeblock opens with a triple-backtick fence (` ``` `, with or without a `csv` language tag) and closes with a matching fence.
2. The **first line inside the fence** is the header line, exactly:
   ```
   Company_Name, Company_URL, Career_Page_URL, ATS_Platform, ATS_Slug, Employee_Count_Estimate, Company_Focus, Remote_Culture_Score, Current_Remote_Roles, Overall_Fit_Score, Research_Notes, Source_References, URL_Status, Total_Jobs_Visible, Engineering_Jobs_Visible, Extraction_Notes, Last_Validated
   ```
3. Every subsequent line is one company, with the same 17 fields in the same order, delimited by `, ` (comma + space).
4. If a field's value contains a literal comma, wrap that single field in double quotes (e.g., `"AWS, GCP, and Kubernetes"`). Do not quote fields that have no commas.
5. Do **not** put each company in its own codeblock. Do **not** repeat the header. Do **not** use a markdown table. One codeblock, one header, N data rows.

**Self-check before emitting:** count the data rows inside your codeblock. If you claim "20 companies added" in the summary, the codeblock must contain 20 data rows beneath the header. Mismatches mean the format is wrong.

**Field guidance:**
- `ATS_Platform`: One of: Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Pinpoint, Rippling, Comeet, Workday, BambooHR, Breezy, Oracle, Trakstar, Polymer, Gem, Careerpuck, Eightfold, Dayforce, Workable, iSolvedHire
- `ATS_Slug`: The company identifier needed to query the public API. Per-platform formats:
  - **Greenhouse / Lever / Ashby / SmartRecruiters / Recruitee / Pinpoint / Rippling / BambooHR / Breezy / Trakstar / Polymer / Gem / Careerpuck / Workable**: the slug visible in the career-page URL path (e.g. `companyname` from `boards.greenhouse.io/companyname`, or `huggingface` from `apply.workable.com/huggingface`).
  - **Workday**: `tenant.dc` (e.g. `wellsky.wd1`); the scraper extracts the board name from `Career_Page_URL`.
  - **Oracle**: the `siteNumber` from the path segment after `/sites/` (e.g. `jobsearch`, `CX_1`, `CX_1001`); the scraper extracts POD/datacenter from `Career_Page_URL`.
  - **Comeet**: `{uid}|{token}` — both the company UID and the public widget token (separated by a literal `|`). Both are embedded in the career-page widget HTML/JS; neither is a credential.
  - **Eightfold**: `{subdomain}` if the company's web domain is `{subdomain}.com`, otherwise `{subdomain}|{domain}` (e.g. `hsbc|hsbc.com`).
  - **Dayforce**: `{clientNamespace}:{jobBoardCode}` — both parsed from the career URL `https://jobs.dayforcehcm.com/{locale}/{namespace}/{boardCode}` (e.g. `paradigm:CANDIDATEPORTAL` from `https://jobs.dayforcehcm.com/en-US/paradigm/CANDIDATEPORTAL`). The board code defaults to `CANDIDATEPORTAL` if omitted, but always include it explicitly — some tenants use `CAREER` or `JOBS`.
  - **iSolvedHire**: the `{subdomain}` from the career URL `https://{subdomain}.isolvedhire.com/jobs/` (e.g. `summit7`). The scraper auto-resolves the numeric `domain_id` from the `/jobs/` page, so the bare subdomain is enough; optionally pin it as `{subdomain}:{domain_id}` (e.g. `summit7:5511`) to skip the resolution fetch if you captured the `domainId` value during research.
- `Remote_Culture_Score`: Leave blank (requires deeper analysis)
- `Current_Remote_Roles`: Count of remote US infra roles visible during research
- `Overall_Fit_Score`: Leave blank
- `Research_Notes`: Key findings about the company's suitability. Quote the field if it contains commas.
- `Source_References`: URLs where you found the company
- `URL_Status`: "active" (you verified the career page loads)
- `Total_Jobs_Visible`: Approximate count from career page (may be blank)
- `Engineering_Jobs_Visible`: Approximate count of engineering/infra roles (may be blank)
- `Extraction_Notes`: Summary of role availability and any concerns. Quote the field if it contains commas. If a clearance penalty applies, note it here (e.g., "basic obtainable clearance flagged; -1 penalty applied").
- `Last_Validated`: Today's date (YYYY-MM-DD)

**Worked example** (header + 2 sample rows; one row has a quoted field with embedded commas):

```
Company_Name, Company_URL, Career_Page_URL, ATS_Platform, ATS_Slug, Employee_Count_Estimate, Company_Focus, Remote_Culture_Score, Current_Remote_Roles, Overall_Fit_Score, Research_Notes, Source_References, URL_Status, Total_Jobs_Visible, Engineering_Jobs_Visible, Extraction_Notes, Last_Validated
ExampleCo, https://example.com, https://boards.greenhouse.io/exampleco, Greenhouse, exampleco, ~500, B2B observability SaaS, , 2, , Mid-level SRE confirmed; remote-US tagged, https://boards.greenhouse.io/exampleco/jobs/123, active, 40, 12, Two non-senior infra roles open, 2026-04-25
SampleCorp, https://samplecorp.io, https://jobs.lever.co/samplecorp, Lever, samplecorp, 200-500, Developer tooling platform, , 1, , "Senior Platform Engineer (AWS, Terraform, K8s); fully remote US", https://jobs.lever.co/samplecorp/abc-123, active, 25, 8, "Senior-leaning; verify mid-level surfaces in next cycle", 2026-04-25
```

### Step 5: Summary Report

After the CSV, provide a brief summary:

```
## Company Curation for ATS API Targets Complete

### Results
- Companies discovered across all subagents: X
- Companies deduplicated within subagent results: Y
- Companies discarded at Step 2 JSON re-check (name match): a
- Companies discarded at Step 2 JSON re-check (career_page_url match): b
- Companies discarded at Step 2 JSON re-check (company_url match): c
- Companies excluded (non-target ATS platform): Z
- Companies excluded (industry/size/model): W
- Companies excluded (already in exclusions.yml): V
- Companies excluded (Active/TS/SCI clearance required): Q
- Companies flagged with clearance penalty (-1) but included: P
- **Companies added to CSV: N**

### ATS Platform Breakdown
- Greenhouse: N companies
- Lever: N companies
- Ashby: N companies
- SmartRecruiters: N companies
- Workday: N companies
- Oracle: N companies
- Eightfold: N companies
- Dayforce: N companies
- Trakstar / Polymer / Gem / Careerpuck / Comeet: N companies
- Other (Recruitee / Pinpoint / Rippling / BambooHR / Breezy / Workable / iSolvedHire): N companies

### Search Coverage
- Subagents deployed: N
- Search angles covered: [list]

### Notable Findings
- [Any patterns observed, e.g., "Most developer tools companies use Lever"]
- [Companies worth watching that didn't qualify yet]

### Recommended Next Steps
- Review CSV and validate ATS slugs by testing API endpoints
- Build API integration scripts for each ATS platform represented
- Run initial job extraction against the curated company list
```

---

## Quality Guidelines

- **Prefer specificity over volume.** 20 well-researched companies with confirmed ATS slugs are better than 50 with unverified platforms.
- **Verify ATS platform identification.** Actually visit the career page and confirm which ATS serves the listings. Don't guess based on company size or industry.
- **Extract the ATS slug/token.** This is critical for API access. The slug is typically visible in the career page URL (e.g., `boards.greenhouse.io/companyslug`, `jobs.lever.co/companyslug`).
- **Look for evidence, not assumptions.** Don't assume a company is remote-friendly because they're a tech company. Check their actual job listings.
- **When in doubt, include with notes.** If a company is borderline (e.g., 180 employees, one senior infra role), include it with clear notes so the user can decide.
- **GovCon: filter on clearance level, not contractor status.** A federal IT contractor with no clearance requirement or only a basic obtainable Public Trust is a valid candidate. Only disqualify if the role explicitly requires Active Secret, Top Secret, or SCI access. Note any clearance penalty in `Extraction_Notes`.
- **For Workday companies, document the full URL.** Workday requires the tenant name AND data center number (wd1, wd3, wd5), both visible in the career page URL. Record the complete `*.wd{N}.myworkdayjobs.com` URL.
- **For Oracle companies, document the full URL.** ORC requires both the POD subdomain (and optional datacenter, e.g. `eeho.fa.us2.oraclecloud.com`) AND the `siteNumber` (the path segment after `/sites/`, e.g. `jobsearch`). Record the complete career-page URL so both can be parsed.
- **For Eightfold companies, test the endpoint before recording.** Some tenants (Qualcomm, Citi, Starbucks, Amex) have moved to gated PCSX search and return `403 "Not authorized for PCSX"` to anonymous v2 calls. Skip those.
- **For Comeet companies, capture the public widget token.** Both the UID and `token` query parameters are required and both are embedded as plaintext in the career-page widget. Without the token the API returns no results.
- **For Careerpuck companies, prefer the underlying ATS if available.** Careerpuck is frequently a front-end overlay on Greenhouse or Lever; the same jobs are usually reachable via the underlying ATS, which is more stable. The `atsSourcePlatform` field on each Careerpuck job confirms the underlying source — record the company on that ATS instead and skip the Careerpuck entry.
- **For Dayforce companies, document the full career-page URL.** Dayforce's API requires both the `clientNamespace` AND `jobBoardCode` — both are path segments of the career URL. Record the URL in the form `https://jobs.dayforcehcm.com/{locale}/{namespace}/{boardCode}` so the `ATS_Slug` (`{namespace}:{boardCode}`) can be derived unambiguously. Dayforce skews enterprise-sized (1,000+ employees), so prioritize it during enterprise discovery rather than mid-market sweeps.