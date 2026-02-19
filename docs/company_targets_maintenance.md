# Company Targets Maintenance Guide

This guide documents how to maintain the [config/company_targets.csv](../config/company_targets.csv) file, which defines the list of companies checked during the company-direct-search workflow.

---

## File Structure

**Location:** `config/company_targets.csv`

**Columns:**
- `company` - Company name (must match exclusions.yml if applicable)
- `career_url` - Direct URL to the company's careers/jobs page
- `status` - Either `active` or `excluded`
- `last_checked` - ISO 8601 date (YYYY-MM-DD) when last validated
- `exclusion_reason` - Reason for exclusion (blank if status=active)
- `last_position_count` - Number of engineering positions found in last check

**Example:**
```csv
company,career_url,status,last_checked,exclusion_reason,last_position_count
Datadog,https://careers.datadoghq.com/all-jobs,active,2025-12-22,,43
Splunk,https://www.splunk.com/careers,excluded,2025-12-15,redirects_to_job_board,0
```

---

## Adding New Companies

### 1. Research Company Career Page

Before adding a company, verify:
- ✅ Direct career page URL (not a job board)
- ✅ Page loads without authentication
- ✅ Page is not a redirect to LinkedIn/Indeed/etc.
- ✅ Company has infrastructure/DevOps engineering roles
- ✅ Company is not already in `config/exclusions.yml` applied/rejected lists

### 2. Add CSV Row

Add a new row to `company_targets.csv` with:

```csv
Company Name,https://company.com/careers/,active,,,
```

**Fields:**
- `company` - Official company name
- `career_url` - Full HTTPS URL to careers page
- `status` - Set to `active`
- `last_checked` - Leave blank (will be updated after first run)
- `exclusion_reason` - Leave blank
- `last_position_count` - Leave blank (will be populated after first run)

### 3. Verify Format

Ensure:
- No spaces around commas
- URL includes `https://`
- Company name has no commas (or escape with quotes: `"Company, Inc"`)
- Row ends with two trailing commas for blank fields

---

## Excluding Companies

### When to Exclude

Exclude companies from `status=active` if they have:
- **URL issues:** Redirects to job boards, authentication walls, 404 errors
- **No relevant positions:** Zero infrastructure roles for 3+ consecutive months
- **Structural issues:** Career page changed to incompatible format
- **Applied/Rejected:** Company moved to `exclusions.yml` lists

### How to Exclude

1. **Change status to `excluded`:**
   ```csv
   Company Name,https://company.com/careers/,excluded,2025-12-22,redirects_to_job_board,0
   ```

2. **Add exclusion_reason:**
   - `redirects_to_job_board` - Career URL redirects to LinkedIn/Indeed/etc.
   - `authentication_required` - Page requires login or account
   - `page_not_found` - 404 or URL no longer exists
   - `access_blocked` - Cloudflare, rate limiting, or geo-blocking
   - `no_positions_found` - Zero relevant positions for 3+ months
   - `applied_to_company` - Moved to exclusions.yml applied list
   - `rejected_by_company` - Moved to exclusions.yml rejected list
   - `incompatible_format` - Career page structure incompatible with fetch_webpage

3. **Update last_checked:**
   - Set to the date the exclusion was identified (ISO 8601 format)

---

## Interpreting Validation Reports

After running the company-direct-search workflow, you'll receive a **Stage 4.5 Validation Report** with two sections:

### URL Validation Issues

**Table format:**
| Company | Career URL | Issue Type | Details | Last Checked |
|---------|------------|------------|---------|--------------|
| Example Co | https://... | redirect | Redirects to linkedin.com | 2025-12-22 |

**Common issue types:**
- `redirect` - URL redirects to job board or external site
- `404` - Page not found
- `timeout` - Request timed out or failed
- `auth_required` - Authentication wall encountered
- `access_blocked` - Cloudflare challenge or IP block

**Action:** Review each issue and update `company_targets.csv`:
1. If issue is temporary (timeout, access block) - retry next month
2. If issue is permanent (redirect, 404) - set `status=excluded`

### Diagnostic Warnings

**Format:**
```
⚠️ Batch 3: Zero positions found for Company A, Company B, Company C (no URL issues detected)
```

**Possible causes:**
- **No mid-level positions:** Company only hiring senior-level (common in Dec 2025)
- **Search term mismatch:** Company uses different role titles
- **Temporary hiring freeze:** No active requisitions
- **Page structure change:** Fetch method can't parse new format

**Action:**
- If 3+ consecutive zero-result checks → set `status=excluded` with `exclusion_reason=no_positions_found`
- If first occurrence → monitor next month
- Check company career page manually to verify

---

## Monthly Audit Process

### Recommended Schedule: 1st of each month

**Steps:**

1. **Review excluded companies:**
   - Check if any `excluded` companies should be re-activated
   - Companies with `no_positions_found` may resume hiring
   - Companies with `page_not_found` may have new career pages

2. **Update last_checked dates:**
   - After workflow runs, update `last_checked` for all `active` companies
   - Use ISO 8601 format: `2025-12-22`

3. **Update last_position_count:**
   - Record engineering position counts from workflow results
   - Helps track hiring trends over time

4. **Prune persistent zero-result companies:**
   - If company shows `0` positions for 3+ months → exclude
   - Exception: Known high-quality companies (may be temporary freeze)

5. **Sync with exclusions.yml:**
   - If you applied to a company → set `status=excluded`, `exclusion_reason=applied_to_company`
   - If rejected → set `status=excluded`, `exclusion_reason=rejected_by_company`

6. **Add new companies:**
   - Research 2-3 new infrastructure-focused companies per month
   - Add to bottom of CSV with `status=active`

---

## Restoring Excluded Companies

### When to Restore

Re-activate excluded companies if:
- **URL issue fixed:** Company fixed redirect or updated career page
- **Hiring resumed:** Company with `no_positions_found` is hiring again
- **False positive:** Exclusion was temporary issue (timeout, access block)

### How to Restore

1. **Verify career URL is working:**
   - Manually visit the URL
   - Confirm it loads and shows job listings
   - Check for infrastructure/DevOps roles

2. **Update CSV row:**
   ```csv
   Company Name,https://company.com/careers/,active,,,
   ```
   - Change `status` to `active`
   - Clear `exclusion_reason` (leave blank)
   - Clear `last_checked` and `last_position_count` (will update on next run)

3. **Monitor first run:**
   - After next workflow execution, verify positions are found
   - If issues persist, re-exclude with updated reason

---

## Best Practices

### ✅ Do

- **Keep URLs direct:** Use company career pages, not job boards
- **Use HTTPS:** Always include `https://` in career_url
- **Document exclusions:** Always fill in `exclusion_reason` when excluding
- **Update regularly:** Keep `last_checked` current (monthly minimum)
- **Verify before adding:** Test career URL manually before adding to CSV
- **Sync with exclusions.yml:** Don't search companies you've applied/rejected

### ❌ Don't

- **Don't add job boards:** No LinkedIn, Indeed, Glassdoor URLs
- **Don't add ATS platforms:** No boards.greenhouse.io, jobs.lever.co direct links
- **Don't leave dangling exclusions:** If excluded, always document why
- **Don't ignore validation reports:** Review and act on Stage 4.5 issues
- **Don't over-exclude:** Temporary issues (timeouts) may resolve next run
- **Don't duplicate:** Check for company before adding (case-sensitive)

---

## Troubleshooting

### Problem: Career URL changed

**Symptom:** 404 errors in validation report

**Solution:**
1. Search for company's new career page URL
2. Update `career_url` in CSV with new URL
3. Test manually before next run

### Problem: Company redirects to job board

**Symptom:** Validation report shows `redirect` to linkedin.com/indeed.com

**Solution:**
1. Set `status=excluded`
2. Set `exclusion_reason=redirects_to_job_board`
3. Update `last_checked` to current date

### Problem: Zero positions for high-quality company

**Symptom:** Diagnostic warning for company that should have roles

**Solution:**
1. Manually check company career page
2. If hiring freeze → leave active, check next month
3. If roles exist but not found → report workflow issue (search term mismatch)
4. If truly no roles → exclude after 3 months

### Problem: Duplicate company in CSV

**Symptom:** Same company appears twice with different URLs or spelling

**Solution:**
1. Determine which URL is correct (test both)
2. Remove duplicate row
3. Keep the URL that returns best results

### Problem: CSV parse errors

**Symptom:** Workflow fails to load company_targets.csv

**Solution:**
1. Check for missing commas at end of rows
2. Check for commas in company names (must quote: `"Company, Inc"`)
3. Verify no blank lines in middle of CSV
4. Ensure no special characters or extra spaces

---

## Example Maintenance Workflow

**Monthly routine (10-15 minutes):**

```bash
1. Run company-direct-search workflow
2. Review Stage 4.5 Validation Report
3. Open config/company_targets.csv
4. For each validation issue:
   - Update status to excluded if permanent issue
   - Add exclusion_reason
5. For diagnostic warnings:
   - Note companies with 3+ months of zero results
   - Exclude if persistent
6. Update all active companies:
   - Set last_checked to current date
   - Update last_position_count from workflow results
7. Add 2-3 new companies researched this month
8. Save and commit changes
9. Sync with exclusions.yml (check applied/rejected lists)
```

---

## Related Files

- **[config/company_targets.csv](../config/company_targets.csv)** - The company list (you are here)
- **[config/exclusions.yml](../config/exclusions.yml)** - Companies already applied/rejected
- **[.github/prompts/company-direct-search.prompt.md](../.github/prompts/company-direct-search.prompt.md)** - Workflow that uses this file
- **[results/application_queue.csv](../results/application_queue.csv)** - Positions discovered from workflow

---

## Questions?

If you encounter issues not covered in this guide:
1. Check validation report details carefully
2. Manually test career URL in browser
3. Review recent workflow results for patterns
4. Consider if issue is temporary (retry next month) or permanent (exclude now)
