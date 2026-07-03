"""
Unit checks for scripts/builtin_scraper/search.py — the search-URL builder and
card parser. Network-free (parses static HTML fixtures). Runnable two ways:

    .venv/bin/python -m tests.test_builtin_search           # plain runner
    .venv/bin/python -m pytest tests/test_builtin_search.py  # if pytest present

Locks in the 2026-05 location fix: Built In constrains the metro via city/state
QUERY PARAMS, not a "<city>-<state>" path slug (the slug returned nationwide
results). See scripts/builtin_scraper/search.py module docstring.
"""

from urllib.parse import parse_qs, urlsplit

from scripts.ats_scraper.location import LocationConfig
from scripts.builtin_scraper.search import build_search_url, parse_search_html

REMOTE = LocationConfig(remote=True, state="Oregon", state_abbr="ID")
LOCAL_AUSTIN = LocationConfig(
    remote=False, city="Austin", state="Texas", state_abbr="TX",
    accept_remote_in_local_mode=True,
)
LOCAL_AUSTIN_STRICT = LocationConfig(
    remote=False, city="Austin", state="Texas", state_abbr="TX",
    accept_remote_in_local_mode=False,
)


def _parts(url):
    s = urlsplit(url)
    return s.path, parse_qs(s.query)


# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------
def test_remote_mode_url():
    path, q = _parts(build_search_url("DevOps Engineer", time_filter="past_2_days", loc_cfg=REMOTE))
    assert path == "/jobs/remote/entry-level/junior/mid-level/51-200/201-500/501-1000/1000"
    assert q["search"] == ['"DevOps Engineer"']
    assert q["daysSinceUpdated"] == ["2"]
    assert q["country"] == ["USA"]
    assert q["allLocations"] == ["true"]
    assert q["handler"] == ["SearchResults"]
    # Remote mode must NOT emit city/state params.
    assert "city" not in q and "state" not in q


def test_local_mode_url_uses_query_params_not_path_slug():
    path, q = _parts(build_search_url("DevOps Engineer", time_filter="past_week", loc_cfg=LOCAL_AUSTIN))
    # Work-arrangement segments only; NO "austin-tx" slug in the path.
    assert path == "/jobs/remote/hybrid/office/entry-level/junior/mid-level/51-200/201-500/501-1000/1000"
    assert "austin" not in path.lower()
    # The metro is carried by query params.
    assert q["city"] == ["Austin"]
    assert q["state"] == ["Texas"]
    assert q["allLocations"] == ["true"]
    assert q["daysSinceUpdated"] == ["7"]


def test_local_strict_mode_drops_remote():
    path, q = _parts(build_search_url("Cloud Engineer", time_filter="past_day", loc_cfg=LOCAL_AUSTIN_STRICT))
    # No "remote" work-arrangement segment, and no allLocations param.
    assert path == "/jobs/hybrid/office/entry-level/junior/mid-level/51-200/201-500/501-1000/1000"
    assert q["city"] == ["Austin"]
    assert "allLocations" not in q


def test_unknown_time_filter_raises():
    try:
        build_search_url("DevOps Engineer", time_filter="last_year", loc_cfg=REMOTE)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown time_filter")


# ---------------------------------------------------------------------------
# Card parsing — work-arrangement + location extraction
# ---------------------------------------------------------------------------
# Minimal card matching Built In's live structure (icons label each attribute).
def _card(job_id, slug, company, title, arrangement, loc):
    loc_row = (
        f'<div class="d-flex align-items-start gap-sm">'
        f'<div class="iconwrap"><i class="fa-regular fa-location-dot fs-xs"></i></div>'
        f'<div><span class="font-barlow">{loc}</span></div></div>'
    ) if loc else ""
    return (
        f'<div data-id="job-card" id="job-card-{job_id}">'
        f'<a data-id="company-title" href="/company/x"><span>{company}</span></a>'
        f'<a data-id="job-card-title" href="/job/{slug}/{job_id}">{title}</a>'
        f'<div class="d-flex align-items-start gap-sm">'
        f'<div class="iconwrap"><i class="fa-regular fa-house-building fs-xs"></i></div>'
        f'<span class="font-barlow">{arrangement}</span></div>'
        f'{loc_row}'
        f'</div>'
    )


def test_card_extracts_arrangement_and_location():
    html = _card("111", "devops-engineer-austin", "CrowdStrike",
                 "DevOps Engineer (Hybrid, Austin)", "Hybrid", "Austin, TX, USA")
    cards = parse_search_html(html)
    assert len(cards) == 1
    c = cards[0]
    assert c.job_id == "111"
    assert c.company == "CrowdStrike"
    assert c.location == "Hybrid | Austin, TX, USA"


def test_card_remote_location():
    html = _card("222", "cloud-engineer-devops", "Innovative Solutions",
                 "Cloud Engineer - DevOps", "Remote", "USA")
    cards = parse_search_html(html)
    assert cards[0].location == "Remote | USA"


def test_card_missing_location_icons_degrades_to_empty():
    # A card with the title/company anchors but no attribute icons must still
    # parse (location="" -> filter_card defers to Phase 2), not crash.
    html = (
        '<div data-id="job-card" id="job-card-333">'
        '<a data-id="company-title" href="/company/y"><span>Acme</span></a>'
        '<a data-id="job-card-title" href="/job/devops/333">DevOps Engineer</a>'
        '</div>'
    )
    cards = parse_search_html(html)
    assert len(cards) == 1
    assert cards[0].location == ""


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
