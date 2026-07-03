"""
Unit checks for the Python-driven ATS platform search (Option A) and the
deterministic guards added after the first live run. Network-free. Runnable:

    .venv/bin/python -m tests.test_ats_platform_search
    .venv/bin/python -m pytest tests/test_ats_platform_search.py   # if pytest present

The repo has no test runner configured, so the __main__ block self-executes.
"""

from scripts.ats_scraper.cooldown import normalize_company, normalize_role
from scripts.ats_platform_filter.filters import (
    filter_result,
    _is_listing_page,
    _workday_location_segment,
    listing_health,
)
from scripts.ats_platform_search import query_builder as qb
from scripts.ats_scraper.platforms.workday import cxs_detail_url
from scripts.ats_scraper.location import (
    LocationConfig,
    has_us_signal,
    url_segment_is_us,
)
from scripts.ats_scraper.roles import active_role_buckets

REMOTE = LocationConfig(remote=True, state="Oregon", state_abbr="ID")
LOCAL_AUSTIN = LocationConfig(remote=False, city="Austin", state="Texas", state_abbr="TX")


# --- Fix 1: company normalization collapses compound-word spacing ----------

def test_compound_company_spacing_collapses():
    # The live-run miss: applied as "BlueCross BlueShield", rediscovered as
    # "Blue Cross Blue Shield" — must normalize to the same cooldown key.
    a = normalize_company("BlueCross BlueShield of Tennessee")
    b = normalize_company("Blue Cross Blue Shield of Tennessee")
    assert a == b == "bluecrossblueshieldoftennessee", (a, b)
    # Other common compound-split variants
    assert normalize_company("NetApp") == normalize_company("Net App")
    assert normalize_company("SmartRecruiters") == normalize_company("Smart Recruiters")
    # Distinct companies stay distinct
    assert normalize_company("Stripe") != normalize_company("Datadog")
    # Role unaffected; "Associate" stripped as seniority
    assert normalize_role("Associate MLOps Engineer") == normalize_role("MLOps Engineer") == "mlops engineer"


# --- Fix 2: Workday board listing pages are dropped ------------------------

def test_workday_listing_page_dropped():
    # Board root (no /job/ segment) — the junk row from the live run.
    assert _is_listing_page("https://bcbst.wd1.myworkdayjobs.com/External")
    # Real postings (with /job/) are kept.
    assert not _is_listing_page(
        "https://gdit.wd5.myworkdayjobs.com/External_Career_Site/job/Dev-Ops-Engineer_RQ220651-1"
    )
    assert not _is_listing_page(
        "https://agilent.wd5.myworkdayjobs.com/en-US/Agilent_Careers/job/X_4036644-1"
    )
    # Non-Workday hosts are unaffected by this rule.
    assert not _is_listing_page("https://careers-acme.icims.com/jobs/123")


def test_filter_result_drops_listing_page():
    rec = {
        "title": "Search for Jobs - Myworkdayjobs.com",
        "url": "https://bcbst.wd1.myworkdayjobs.com/External",
        "description": "Search for Jobs",
    }
    assert filter_result(rec, set(), True) == (False, "listing_page")


# --- Fix 3: deterministic non-US (URL segment + guarded snippet) -----------
# Grounds: the 2026-06-02 run sent ~14 non-US postings to the LLM that the
# title-only filter missed. Geography is deterministic; move it to Python.

def test_workday_location_segment_extraction():
    # Location lives in the segment right after /job/.
    assert _workday_location_segment(
        "https://tencent.wd1.myworkdayjobs.com/en-US/Tencent_Careers/job/Singapore-CapitaSky/Junior-SRE_R1"
    ) == "Singapore CapitaSky"
    # Non-Workday hosts: no segment (other ATS use opaque id/title slugs).
    assert _workday_location_segment("https://jobs.lever.co/acme/uuid-1234") == ""
    # Workday board root with no /job/ -> empty.
    assert _workday_location_segment("https://x.wd1.myworkdayjobs.com/External") == ""


def test_non_us_url_dropped():
    # Real foreign Workday postings from the run — title never names the country.
    for url, where in [
        ("https://tencent.wd1.myworkdayjobs.com/en-US/Tencent_Careers/job/Singapore-CapitaSky/Junior-SRE_R1", "Singapore"),
        ("https://hitachi.wd1.myworkdayjobs.com/en-US/hitachi/job/Remote---Lesser-Poland-Poland/Platform-Engineer_R1", "Poland"),
        ("https://kyndryl.wd5.myworkdayjobs.com/KyndrylProfessionalCareers/job/INMANBP-Bangalore-INMANBP/Mod-Engineer_R1", "Bangalore"),
        # czechia/prague were MISSING from the superset before this fix:
        ("https://kyndryl.wd5.myworkdayjobs.com/KyndrylProfessionalCareers/job/Brno-Jihomoravsk-kraj-Czechia/Infra-Engineer_R1", "Czechia"),
    ]:
        rec = {"title": "Infrastructure Engineer", "url": url, "description": ""}
        assert filter_result(rec, set(), True) == (False, "non_us_url"), where


def test_us_workday_url_kept_collision_guard():
    # US locales that COLLIDE with the non-US regex must NOT be dropped —
    # deferred to the LLM via the state-abbr / USA guard.
    for url, where in [
        ("https://bah.wd1.myworkdayjobs.com/en-US/BAH_Jobs/job/Arlington-VA/Cloud-Engineer_R0241232", "Arlington VA"),
        ("https://appliedis.wd5.myworkdayjobs.com/FeaturedJobs/job/USA-Remote/K8s-Platform-Engineer_JR1", "USA-Remote"),
        ("https://acme.wd1.myworkdayjobs.com/Careers/job/Dublin-OH/Platform-Engineer_R1", "Dublin OH (not Ireland)"),
        ("https://acme.wd1.myworkdayjobs.com/Careers/job/Ontario-CA/DevOps-Engineer_R1", "Ontario CA (not Canada)"),
    ]:
        rec = {"title": "Platform Engineer", "url": url, "description": "Remote role"}
        keep, reason = filter_result(rec, set(), True)
        assert keep, f"{where} wrongly dropped as {reason}"


def test_non_us_snippet_dropped():
    # Country only visible in the Google snippet, not the title or URL.
    cases = [
        ("Cloud Engineer 2, Site Reliability Engineering", "https://careers-kinaxis.icims.com/jobs/34845/x/job",
         "Canada is now hiring a Cloud Engineer 2, SRE in Remote."),
        ("AirOps - Platform Engineer", "https://jobs.ashbyhq.com/silver/uuid",
         "AirOps - Platform Engineer. Location. Remote; Argentina; Uruguay."),
        ("Bluelight Consulting", "https://jobs.lever.co/bluelightconsulting?location=x",
         "DevOps Engineer - Remote, Latin America. Santa Ana, El Salvador."),
    ]
    for title, url, desc in cases:
        rec = {"title": title, "url": url, "description": desc}
        assert filter_result(rec, set(), True) == (False, "non_us_snippet"), title


def test_us_signal_rescues_multilocale_snippet():
    # The Agilent job we QUALIFIED: US-CO-Remote primary, Spain as an option.
    # Must survive the snippet scan (kept for the LLM), not be dropped.
    rec = {
        "title": "DevOps & Platform Engineer (AWS / CI/CD)",
        "url": "https://agilent.wd5.myworkdayjobs.com/en-US/Agilent_Careers/job/DevOps-Platform-Engineer_4036644-1",
        "description": "locations: US-CO-Remote Location: Option to work in Spain. Apply now.",
    }
    keep, reason = filter_result(rec, set(), True)
    assert keep, f"Agilent (US-CO-Remote) wrongly dropped as {reason}"


def test_us_signal_guard_unit():
    # Rescued (US locale present alongside foreign mention)
    assert has_us_signal("US-CO-Remote ... option to work in Spain")
    assert has_us_signal("Austin, TX")                       # City, ST
    assert has_us_signal("offices in New York and London")   # full state name
    assert has_us_signal("USA Remote")
    # Genuinely non-US (no US signal) -> not rescued
    assert not has_us_signal("Remote; Argentina; Uruguay")
    assert not has_us_signal("Bangalore, India")
    assert not has_us_signal("Campinas, SP")                 # SP is not a US abbr


def test_url_segment_is_us_unit():
    assert url_segment_is_us("Arlington VA")
    assert url_segment_is_us("USA Remote")
    assert url_segment_is_us("Dublin OH")                    # collision-safe
    assert not url_segment_is_us("Singapore CapitaSky")
    assert not url_segment_is_us("Lesser Poland Poland")


# --- Fix 4: dead/expired/un-rendered listings carry no scoreable JD --------
# Grounds: the 2026-06-02 run queued an expired Paylocity listing (HTTP 200,
# "that job does not exist") and a 404 GDIT Workday shell (HTTP 200, nav chrome
# only). 5 of 7 "qualified" had no real description and got base-5 by default.

def test_listing_health_soft_404_is_dead():
    # Real Paylocity expired page: HTTP 200 + soft-404 message, ~13 words.
    rec = {
        "url": "https://recruiting.paylocity.com/Recruiting/Jobs/Details/4214242",
        "markdown": "### We're sorry, that job does not exist or is not currently active.",
        "metadata": {"statusCode": 200},
    }
    assert listing_health(rec) == "dead_listing"


def test_listing_health_http_error_is_dead():
    rec = {"url": "https://x.applytojob.com/apply/expired", "markdown": "Gone",
           "metadata": {"statusCode": 410}}
    assert listing_health(rec) == "dead_listing"


def test_listing_health_unrendered_shell_is_no_description():
    # Real GDIT Workday shell: 200, chars but only nav chrome (~29 real words).
    chrome = (
        "[Skip to main content](https://gdit.wd5.myworkdayjobs.com/x) "
        "![](https://gdit.wd5.myworkdayjobs.com/img.png) Dev Ops Engineer "
        "Apply Save Sign In Search for Jobs View All Jobs Privacy Cookies"
    )
    rec = {"url": "https://gdit.wd5.myworkdayjobs.com/External_Career_Site/job/Dev-Ops-Engineer_RQ220651-1",
           "markdown": chrome, "metadata": {"statusCode": 200}}
    assert listing_health(rec) == "no_description"
    # Empty markdown is also unscoreable.
    assert listing_health({"url": "https://x", "markdown": "", "metadata": {}}) == "no_description"


def test_listing_health_real_jd_is_healthy():
    # ~120 words of real JD prose -> scoreable, kept.
    jd = ("We are hiring a DevOps Engineer to join our platform team. " * 4 +
          "You will build and maintain AWS infrastructure using Terraform and Ansible, "
          "manage CI/CD pipelines with GitHub Actions, operate Kubernetes clusters, "
          "and improve observability with Prometheus and Grafana. Strong Linux and "
          "scripting skills required. Remote within the United States. ") * 2
    rec = {"url": "https://jobs.lever.co/acme/uuid", "markdown": jd, "metadata": {"statusCode": 200}}
    assert listing_health(rec) == ""


def test_listing_health_soft404_phrase_in_long_jd_not_dead():
    # A long, real JD that merely contains a soft-404-like phrase must NOT be
    # killed — the dead_listing rule is gated to short pages (< 150 words).
    jd = ("Senior platform team backfill. " * 60 +
          "Note: we're sorry our last posting closed early. Apply now for the live role. " * 2)
    rec = {"url": "https://jobs.lever.co/acme/uuid2", "markdown": jd, "metadata": {"statusCode": 200}}
    assert listing_health(rec) == ""


# --- Query builder: shape + attribution ------------------------------------

SAMPLE_CFG = {
    "target_roles": {
        "primary": [{"name": "DevOps Engineer"}, {"name": "Platform Engineer"}],
        "secondary": [{"name": "MLOps Engineer"}],
    },
    "job_boards": {
        "primary": [{"domain": "icims.com"}, {"domain": "*.applytojob.com"}],
        "watch": [{"domain": "myworkdayjobs.com"}],
        "secondary": [{"domain": "jobs.jobvite.com"}, {"domain": "wellfound.com"}],
    },
}


def test_queue_numbering_and_shape():
    queue = qb.build_queue(SAMPLE_CFG)
    primary = [q for q in queue if q.tier == "primary"]
    secondary = [q for q in queue if q.tier == "secondary"]
    # 3 individual boards (2 primary + 1 watch) + 1 bundled = 4 per tier
    assert len(primary) == 4 and len(secondary) == 4
    # Global numbering: primary 1..4, secondary 5..8 (stable filenames)
    assert [q.query_number for q in primary] == [1, 2, 3, 4]
    assert [q.query_number for q in secondary] == [5, 6, 7, 8]
    # Bundled-secondary query carries every secondary domain
    bundled = primary[-1]
    assert bundled.bundled_domains == ["jobs.jobvite.com", "wellfound.com"]
    assert bundled.board_label.startswith("bundled-secondary(")


def test_query_string_remote_vs_local():
    q = qb.build_queue(SAMPLE_CFG)[0]  # icims, primary roles
    s = qb.build_query_string(q, REMOTE)
    assert s.startswith("site:icims.com ")
    assert '("DevOps Engineer" OR "Platform Engineer")' in s
    assert '"remote"' in s and "-blockchain" in s
    assert qb.search_location(REMOTE) == "United States"
    # Local mode swaps the work clause + geo target
    s_local = qb.build_query_string(q, LOCAL_AUSTIN)
    assert '"Austin"' in s_local and '"remote"' not in s_local
    assert qb.search_location(LOCAL_AUSTIN) == "Austin, Texas"


def test_bundled_site_clause_uses_or_group():
    bundled = qb.build_queue(SAMPLE_CFG)[3]  # the bundled-secondary primary query
    s = qb.build_query_string(bundled, REMOTE)
    assert s.startswith("(site:jobs.jobvite.com OR site:wellfound.com) ")


def test_board_attribution_suffix_and_wildcard():
    # Wildcard entry catches any subdomain
    assert qb.attribute_board("https://x.applytojob.com/apply/1", ["*.applytojob.com"]) == "*.applytojob.com"
    # Bare domain catches subdomains
    assert qb.attribute_board("https://careers-acme.icims.com/jobs/9", ["icims.com"]) == "icims.com"
    # Bundled: routed to the matching domain by host
    assert qb.attribute_board("https://wellfound.com/jobs/1", ["jobs.jobvite.com", "wellfound.com"]) == "wellfound.com"
    # No match -> unmatched bucket
    assert qb.attribute_board("https://example.com/x", ["icims.com"]) == "unmatched"


def test_role_attribution_most_specific():
    roles = ["Cloud Engineer", "Infrastructure Engineer"]
    assert qb.attribute_role("Cloud Infrastructure Engineer", roles) == "Infrastructure Engineer"
    assert qb.attribute_role("Senior Cloud Engineer", roles) == "Cloud Engineer"
    # Fallback to first when nothing matches
    assert qb.attribute_role("Widget Wrangler", roles) == "Cloud Engineer"


# --- local_only role tier (high-noise generalists, local mode only) --------

SAMPLE_CFG_LOCAL_ONLY = {
    "target_roles": {
        "primary": [{"name": "DevOps Engineer"}],
        "secondary": [{"name": "MLOps Engineer"}],
        "local_only": [{"name": "Systems Administrator"}, {"name": "Systems Engineer"}],
    },
    "job_boards": {
        "primary": [{"domain": "icims.com"}],
        "secondary": [{"domain": "jobs.jobvite.com"}],
    },
}


def _secondary_role_set(queue):
    names = set()
    for q in queue:
        if q.tier == "secondary":
            names.update(q.roles)
    return names


def test_active_role_buckets_mode_gating():
    assert active_role_buckets(REMOTE) == ("primary", "secondary")
    assert active_role_buckets(LOCAL_AUSTIN) == ("primary", "secondary", "local_only")


def test_local_only_excluded_in_remote_mode():
    queue = qb.build_queue(SAMPLE_CFG_LOCAL_ONLY, REMOTE)
    assert _secondary_role_set(queue) == {"MLOps Engineer"}
    # No query of any tier carries a local_only role in remote mode
    assert all("Systems Administrator" not in q.roles for q in queue)


def test_local_only_folded_into_secondary_in_local_mode():
    remote_q = qb.build_queue(SAMPLE_CFG_LOCAL_ONLY, REMOTE)
    local_q = qb.build_queue(SAMPLE_CFG_LOCAL_ONLY, LOCAL_AUSTIN)
    assert _secondary_role_set(local_q) == {
        "MLOps Engineer", "Systems Administrator", "Systems Engineer",
    }
    # Folded into the EXISTING secondary OR-group: no extra query slots/credits
    assert len(local_q) == len(remote_q)
    # local_only never leaks into the primary tier
    assert all(
        "Systems Administrator" not in q.roles for q in local_q if q.tier == "primary"
    )


def test_build_queue_default_loc_is_remote():
    # Backward compat: omitting loc_cfg behaves like remote (local_only skipped)
    assert _secondary_role_set(qb.build_queue(SAMPLE_CFG_LOCAL_ONLY)) == {"MLOps Engineer"}


# --- Workday CXS detail-URL derivation (description backfill) --------------

def test_cxs_url_simple_slug():
    # /en-US/{board}/job/{slug} → /wday/cxs/{tenant}/{board}/job/{slug}
    assert cxs_detail_url(
        "https://bullhorn.wd1.myworkdayjobs.com/en-US/BullhornCareers/job/Infrastructure-Engineer-II_JR1304"
    ) == "https://bullhorn.wd1.myworkdayjobs.com/wday/cxs/bullhorn/BullhornCareers/job/Infrastructure-Engineer-II_JR1304"


def test_cxs_url_with_location_segment():
    # The /job/<location>/<slug> tail is mirrored unchanged.
    assert cxs_detail_url(
        "https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/Remote-USA/DevOps-Engineer_JR123"
    ) == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Careers/job/Remote-USA/DevOps-Engineer_JR123"


def test_cxs_url_no_locale_prefix():
    # Public URLs without a leading /en-US/ locale segment still map.
    assert cxs_detail_url(
        "https://acme.wd5.myworkdayjobs.com/Careers/job/DevOps-Engineer_JR123"
    ) == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Careers/job/DevOps-Engineer_JR123"


def test_cxs_url_listing_root_returns_empty():
    # A board root (no /job/ segment) is not a scoreable posting.
    assert cxs_detail_url("https://acme.wd5.myworkdayjobs.com/en-US/Careers") == ""


def test_cxs_url_non_workday_returns_empty():
    assert cxs_detail_url("https://boards.greenhouse.io/foo/jobs/123") == ""


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed


if __name__ == "__main__":
    import sys
    sys.exit(1 if _run() else 0)
