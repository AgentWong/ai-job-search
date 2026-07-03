"""Applications-and-outcomes view: groups apps by source and joins pipeline events."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from .loaders import parse_iso_date, read_csv


def analyze(
    *,
    today: date,
    window_days: int,
    applications_csv: Path,
    pipeline_events_csv: Path,
) -> dict:
    cutoff = today.fromordinal(today.toordinal() - window_days)

    apps = read_csv(applications_csv)
    apps_in_window = []
    for a in apps:
        d = parse_iso_date(a.get("date_applied", ""))
        if d is not None and d >= cutoff:
            apps_in_window.append(a)

    events = read_csv(pipeline_events_csv)
    events_by_app: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        app_id = (e.get("app_id") or "").strip()
        if app_id:
            events_by_app[app_id].append(e)

    by_source: dict[str, dict] = defaultdict(lambda: {
        "applications": 0,
        "any_response": 0,
        "phone_screen_or_better": 0,
        "rejected": 0,
        "no_response": 0,
    })

    for a in apps_in_window:
        src = (a.get("source") or "unknown").strip() or "unknown"
        m = by_source[src]
        m["applications"] += 1
        app_id = (a.get("app_id") or "").strip()
        stages = {e.get("event_stage", "").strip() for e in events_by_app.get(app_id, [])}
        outcomes = {e.get("event_outcome", "").strip() for e in events_by_app.get(app_id, [])}

        if any(s in stages for s in ("email_response", "phone_screen", "interview_1", "interview_2", "offer")):
            m["any_response"] += 1
        if any(s in stages for s in ("phone_screen", "interview_1", "interview_2", "offer")):
            m["phone_screen_or_better"] += 1
        if "rejected" in outcomes:
            m["rejected"] += 1
        if "no_response" in outcomes:
            m["no_response"] += 1

    sources = []
    for src, m in by_source.items():
        sources.append({
            "source": src,
            **m,
            "response_rate_pct": round(m["any_response"] / m["applications"] * 100.0, 2) if m["applications"] else 0.0,
        })
    sources.sort(key=lambda r: -r["applications"])

    return {
        "window_days": window_days,
        "cutoff_date": cutoff.isoformat(),
        "total_applications_in_window": len(apps_in_window),
        "by_source": sources,
    }
