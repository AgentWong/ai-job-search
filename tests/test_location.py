"""
Unit checks for scripts/ats_scraper/location.py (the shared, mode-aware location
filter). Network-free. Runnable two ways:

    .venv/bin/python -m tests.test_location      # plain runner, prints PASS/FAIL
    .venv/bin/python -m pytest tests/test_location.py   # if pytest is available

The repo has no test runner configured, so the __main__ block self-executes.
"""

from scripts.ats_scraper.location import (
    LocationConfig,
    location_verdict,
    location_matches_metro,
    local_card_kept_by_metro,
    build_state_restrict_pattern,
    description_has_remote_signal,
    posting_has_remote_signal,
)

REMOTE_IDAHO = LocationConfig(remote=True, state="Idaho", state_abbr="ID")
LOCAL_AUSTIN = LocationConfig(
    remote=False, city="Austin", state="Texas", state_abbr="TX",
    accept_remote_in_local_mode=True,
)
LOCAL_AUSTIN_STRICT = LocationConfig(
    remote=False, city="Austin", state="Texas", state_abbr="TX",
    accept_remote_in_local_mode=False,
)
# Fairview, ID with a 25-mi radius vs. an exact-city (no-radius) search. The
# Fairview-Rivergate metro spans the ID/WA line, so a radius search legitimately
# returns WA towns the strict name match would drop. (Fictional example towns.)
LOCAL_FAIRVIEW_RADIUS = LocationConfig(
    remote=False, city="Fairview", state="Idaho", state_abbr="ID",
    accept_remote_in_local_mode=True, distance_miles=25,
)
LOCAL_FAIRVIEW_EXACT = LocationConfig(
    remote=False, city="Fairview", state="Idaho", state_abbr="ID",
    accept_remote_in_local_mode=True, distance_miles=0,
)


def _verdict(location, loc_cfg, workplace_type="", description=""):
    return location_verdict(location, workplace_type, description, loc_cfg)


def test_remote_mode_matches_legacy_behavior():
    assert _verdict("Remote, US", REMOTE_IDAHO) == (True, "")
    assert _verdict("Remote", REMOTE_IDAHO, workplace_type="remote") == (True, "")
    assert _verdict("", REMOTE_IDAHO, workplace_type="remote") == (True, "")
    # hybrid/onsite rejected
    assert _verdict("Hybrid - Chicago", REMOTE_IDAHO)[1] == "hybrid_or_onsite"
    assert _verdict("Onsite", REMOTE_IDAHO)[1] == "hybrid_or_onsite"
    # non-US rejected
    assert _verdict("London, UK", REMOTE_IDAHO)[1] == "non_us_geography"
    assert _verdict("Remote - Toronto", REMOTE_IDAHO)[1] == "non_us_geography"
    # no remote signal (a plain US city with no "remote")
    assert _verdict("Austin, TX", REMOTE_IDAHO)[1] == "no_remote_signal"
    # state restriction in description
    assert _verdict("Remote", REMOTE_IDAHO, description="Not available in Idaho")[1] == "state_restriction"
    assert _verdict("Remote", REMOTE_IDAHO, description="open to all, except Idaho")[1] == "state_restriction"
    # a remote role with a clean description survives
    assert _verdict("Remote", REMOTE_IDAHO, description="Work from anywhere in the US") == (True, "")


def test_state_restrict_pattern_is_idaho_identical():
    pat = build_state_restrict_pattern("Idaho")
    assert pat.search("this role is not available in Idaho")
    assert pat.search("except Idaho")
    assert pat.search("excluding idaho")
    assert not pat.search("available nationwide")
    # config-driven for another state
    tx = build_state_restrict_pattern("Texas")
    assert tx.search("except Texas") and not tx.search("except Idaho")


def test_local_mode_keeps_metro_and_remote():
    for loc in ["Austin, TX", "Austin, Texas", "Greater Austin Area",
                "Austin, TX, USA", "Boston, MA|Austin, TX"]:
        assert _verdict(loc, LOCAL_AUSTIN) == (True, ""), loc
    # hybrid/onsite in-metro is DESIRABLE in local mode
    assert _verdict("Hybrid - Austin, TX", LOCAL_AUSTIN) == (True, "")
    # remote kept when accept_remote_in_local_mode
    assert _verdict("Remote - US", LOCAL_AUSTIN) == (True, "")
    # missing location -> defer (keep)
    assert _verdict("", LOCAL_AUSTIN) == (True, "")


def test_local_mode_rejections():
    assert _verdict("Denver, CO", LOCAL_AUSTIN)[1] == "wrong_metro"
    assert _verdict("New York, NY", LOCAL_AUSTIN)[1] == "wrong_metro"
    assert _verdict("London, UK", LOCAL_AUSTIN)[1] == "non_us_geography"
    # strict local: remote no longer accepted
    assert _verdict("Remote - US", LOCAL_AUSTIN_STRICT)[1] == "remote_not_local"
    assert _verdict("Austin, TX", LOCAL_AUSTIN_STRICT) == (True, "")


def test_metro_matcher_directly():
    assert location_matches_metro("Austin, TX", LOCAL_AUSTIN)
    assert location_matches_metro("Dallas, TX", LOCAL_AUSTIN)  # generous: same-state via abbr
    assert not location_matches_metro("Seattle, WA", LOCAL_AUSTIN)
    assert not location_matches_metro("", LOCAL_AUSTIN)


def test_radius_trust_keeps_in_radius_neighbors():
    # With a radius set, the geo-constrained search is trusted: in-US neighbors
    # that don't name Fairview/Idaho/ID (Rivergate WA, Millbrook WA across the line)
    # are KEPT for the radius-URL scrapers (LinkedIn/Built In).
    assert local_card_kept_by_metro("Fairview, ID", LOCAL_FAIRVIEW_RADIUS)
    assert local_card_kept_by_metro("Rivergate, WA", LOCAL_FAIRVIEW_RADIUS)
    assert local_card_kept_by_metro("Millbrook, WA", LOCAL_FAIRVIEW_RADIUS)
    # An empty location stays kept too (the upstream missing-location defer);
    # the non-US / non-remote gates run before this helper, not inside it.
    assert local_card_kept_by_metro("", LOCAL_FAIRVIEW_RADIUS)


def test_no_radius_falls_back_to_strict_metro():
    # distance_miles=0 -> exact-city search -> strict name match (legacy behavior).
    assert local_card_kept_by_metro("Fairview, ID", LOCAL_FAIRVIEW_EXACT)
    assert not local_card_kept_by_metro("Rivergate, WA", LOCAL_FAIRVIEW_EXACT)
    assert not local_card_kept_by_metro("Millbrook, WA", LOCAL_FAIRVIEW_EXACT)


def test_description_remote_signal_ignores_physical_distance():
    # Real false positive from the 2026-06-07 LinkedIn run: Northwood's JD used
    # "remote" to mean austere field environments, not a work arrangement.
    assert not description_has_remote_signal(
        "bringing up systems in remote or austere environments, ground stations"
    )
    assert not description_has_remote_signal("Manage remote servers in our data centers.")
    assert not description_has_remote_signal("")
    # Genuine work-arrangement phrasings
    assert description_has_remote_signal("This is a fully-remote position open to US candidates.")
    assert description_has_remote_signal("Work from home anywhere in the US.")
    assert description_has_remote_signal("You may work remotely.")
    assert description_has_remote_signal("We offer a remote-first culture.")
    assert description_has_remote_signal("Telecommuting is supported.")


def test_local_mode_multi_location_pipe_join():
    # Workday multi-location postings: the target metro can be buried anywhere
    # in a pipe-joined location/additionalLocations string, not just first.
    # Example scenario: a multi-state posting listing primary location
    # "Salt Lake City, UT" with "Fairview, ID" among nine additionalLocations
    # entries.
    joined = "Salt Lake City, UT|Renton, WA|Medford, OR|Portland, OR|Fairview, ID|Boise, ID|Spokane, WA|Burlington, WA|Fargo, ND|Vancouver, WA"
    assert _verdict(joined, LOCAL_FAIRVIEW_EXACT) == (True, "")


def test_us_signal_rescues_non_us_token_collisions():
    # "Vancouver" (Canada) and "Ontario" (Canada) are non-US reject tokens that
    # collide with real US places (Vancouver, WA / Ontario, CA). has_us_signal()
    # rescues these via the "City, ST" shape.
    assert _verdict("Vancouver, WA", LOCAL_AUSTIN)[1] != "non_us_geography"
    assert _verdict("Ontario, CA", REMOTE_IDAHO, workplace_type="remote")[1] != "non_us_geography"
    # genuine non-US still rejected
    assert _verdict("Vancouver, Canada", LOCAL_AUSTIN)[1] == "non_us_geography"
    assert _verdict("Toronto, Ontario", REMOTE_IDAHO, workplace_type="remote")[1] == "non_us_geography"


def test_posting_remote_gate():
    # The three on-site jobs that leaked to the queue: metro location, no
    # workplace_type, arrangement-silent description -> must be gated OUT.
    assert not posting_has_remote_signal("Torrance, CA", "", "We bring up systems in remote environments.")
    assert not posting_has_remote_signal("Huntington Beach, CA", "", "We build defense hardware.")
    assert not posting_has_remote_signal("New York City Metropolitan Area", "", "On-call rotation. SRE work.")
    # Genuine remote signals survive the gate
    assert posting_has_remote_signal("United States (Remote)", "", "")
    assert posting_has_remote_signal("Remote", "", "")
    assert posting_has_remote_signal("Austin, TX", "remote", "")          # via workplace_type
    assert posting_has_remote_signal("Dallas, TX", "", "This is a fully-remote position.")  # via description


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
