"""Compute the Firecrawl/Google `tbs` time-filter string for a named window.

Firecrawl's `tbs` parameter accepts Google's two time-filter encodings:

  * Predefined ranges:     qdr:d (24h) | qdr:w (week) | qdr:m (month) | qdr:y (year)
  * Custom date ranges:    cdr:1,cd_min:M/D/YYYY,cd_max:M/D/YYYY

Google does NOT expose a 2-day predefined range, so `past_2_days` has to be
emitted as a custom range (today-2 .. today). Other windows pass through to
the cheaper `qdr:` form.

Usage:
    .venv/bin/python -m scripts.firecrawl_tbs past_2_days
        → cdr:1,cd_min:5/5/2026,cd_max:5/7/2026

    .venv/bin/python -m scripts.firecrawl_tbs past_day
        → qdr:d

Importable:
    from scripts.firecrawl_tbs import tbs_for_window
    tbs_for_window("past_2_days")  # → "cdr:1,cd_min:..."
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

PREDEFINED = {
    "past_day": "qdr:d",
    "past_week": "qdr:w",
    "past_month": "qdr:m",
    "past_year": "qdr:y",
}

# Custom-range windows expressed in days. Add new entries here when Google
# still doesn't have the predefined bucket you need.
CUSTOM_DAYS = {
    "past_2_days": 2,
}

WINDOWS = list(PREDEFINED) + list(CUSTOM_DAYS)


def _format_mdy(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year}"


def tbs_for_window(window: str, today: date | None = None) -> str:
    if window in PREDEFINED:
        return PREDEFINED[window]
    if window in CUSTOM_DAYS:
        if today is None:
            today = date.today()
        days = CUSTOM_DAYS[window]
        cd_min = today - timedelta(days=days)
        return f"cdr:1,cd_min:{_format_mdy(cd_min)},cd_max:{_format_mdy(today)}"
    raise ValueError(f"unknown time window: {window!r}. Known: {WINDOWS}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("window", choices=WINDOWS,
                        help="Named time window (e.g. past_day, past_2_days, past_week)")
    parser.add_argument("--today", default=None,
                        help="Override today's date as YYYY-MM-DD (testing only)")
    args = parser.parse_args(argv)

    today = date.fromisoformat(args.today) if args.today else None
    sys.stdout.write(tbs_for_window(args.window, today=today))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
