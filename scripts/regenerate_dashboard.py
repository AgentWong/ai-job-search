#!/usr/bin/env python3
"""Regenerate the job search dashboard HTML from structured CSVs.

Reads:
    job_search_log/applications.csv
    job_search_log/pipeline_events.csv
    job_search_log/narratives.md

Writes:
    job_search_log/dashboard.html

The dashboard is the human-facing replacement for the per-month markdown
logs. It renders:
  - per-month application tables with pipeline-event timelines
  - manual narrative notes from narratives.md
  - aggregate summary stats

Usage:
    .venv/bin/python scripts/regenerate_dashboard.py
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

WEEKDAY_WINDOW_DAYS = 90
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

INTERVIEW_RE = re.compile(r"^interview_(\d+)$")
MONTH_RE = re.compile(r"^(\d{4}-\d{2})-\d{2}$")


def stage_index(stage: str) -> int:
    if stage == "applied":
        return 0
    if stage == "email_response":
        return 1
    if stage == "phone_screen":
        return 2
    m = INTERVIEW_RE.match(stage)
    if m:
        return 2 + int(m.group(1))
    if stage == "offer":
        return 1_000_000
    return -1


def stage_pretty(stage: str) -> str:
    if stage == "applied":
        return "Applied"
    if stage == "email_response":
        return "Email Response"
    if stage == "phone_screen":
        return "Phone Screen"
    if stage == "offer":
        return "Offer"
    m = INTERVIEW_RE.match(stage)
    if m:
        n = int(m.group(1))
        return f"Interview {n}"
    return stage


OUTCOME_BADGE = {
    "":           ("Advanced",    "#16a085"),
    "pending":    ("Pending",     "#3498db"),
    "no_response":("No Response", "#7f8c8d"),
    "rejected":   ("Rejected",    "#e74c3c"),
    "ghosted":    ("Ghosted",     "#e67e22"),
    "withdrew":   ("Withdrew",    "#f39c12"),
    "aborted":    ("Aborted",     "#9b59b6"),
    "accepted":   ("Accepted",    "#27ae60"),
    "declined":   ("Declined",    "#bdc3c7"),
}


def read_csv_dicts(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(2)
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def days_between(d1: str, d2: str) -> int | None:
    try:
        a = datetime.strptime(d1, "%Y-%m-%d").date()
        b = datetime.strptime(d2, "%Y-%m-%d").date()
        return (b - a).days
    except (ValueError, TypeError):
        return None


def parse_narratives(path: Path) -> dict[str, list[str]]:
    """Parse narratives.md into {month: [narrative lines...]}.

    Format expected:
        ## YYYY-MM
        - narrative one
        - narrative two
    """
    if not path.exists():
        return {}
    out: dict[str, list[str]] = {}
    current_month: str | None = None
    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        m = re.match(r"##\s+(\d{4}-\d{2})\s*$", line)
        if m:
            current_month = m.group(1)
            out.setdefault(current_month, [])
            continue
        if current_month is None:
            continue
        if line.startswith("- "):
            out[current_month].append(line[2:].strip())
    return out


def classify(events: list[dict]) -> tuple[str, str]:
    if not events:
        return ("applied", "unclassified")
    sorted_evs = sorted(events, key=lambda e: stage_index(e["event_stage"]))
    highest = sorted_evs[-1]
    outcome = (highest.get("event_outcome") or "").strip()
    if not outcome:
        outcome = "pending"
    return (highest["event_stage"], outcome)


def app_month(date_applied: str) -> str | None:
    m = MONTH_RE.match(date_applied or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def render_pipeline_cell(events: list[dict]) -> str:
    """Render the pipeline events as an inline timeline string."""
    if not events:
        return ""
    sorted_evs = sorted(events, key=lambda e: stage_index(e["event_stage"]))
    parts = []
    for ev in sorted_evs:
        stage = stage_pretty(ev["event_stage"])
        date_ = ev.get("event_date", "")
        outcome = (ev.get("event_outcome") or "").strip()
        notes = (ev.get("event_notes") or "").strip()
        label, color = OUTCOME_BADGE.get(outcome, ("?", "#888"))
        if outcome == "":
            tail = ""
        else:
            tail = f' <span class="badge" style="background:{color}">{esc(label)}</span>'
        date_html = f' <span class="ev-date">{esc(date_)}</span>' if date_ else ""
        notes_html = f' <span class="ev-notes" title="{esc(notes)}">i</span>' if notes else ""
        parts.append(f'<span class="ev"><b>{esc(stage)}</b>{date_html}{tail}{notes_html}</span>')
    return '<div class="timeline">' + "".join(parts) + "</div>"


def days_to_response(events: list[dict]) -> str:
    """Days from applied → first non-applied event."""
    if len(events) < 2:
        return ""
    sorted_evs = sorted(events, key=lambda e: stage_index(e["event_stage"]))
    applied = sorted_evs[0]
    nxt = sorted_evs[1]
    d = days_between(applied.get("event_date", ""), nxt.get("event_date", ""))
    return str(d) if d is not None else ""


def render_month_section(month: str, apps: list[dict],
                          events_by_app: dict[str, list[dict]],
                          narratives: list[str]) -> str:
    apps = sorted(apps, key=lambda a: a.get("company", "").lower())
    n = len(apps)
    yr, mo = month.split("-")
    today = date.today()
    if (today.year, today.month) == (int(yr), int(mo)):
        days_elapsed = today.day
    else:
        # Days in that month
        if int(mo) == 12:
            next_first = date(int(yr) + 1, 1, 1)
        else:
            next_first = date(int(yr), int(mo) + 1, 1)
        last_day = (next_first - date.resolution).day
        days_elapsed = last_day
    avg = (n / days_elapsed) if days_elapsed > 0 else 0

    # Resume format / cover letter consistency check
    resume_formats = {a.get("resume_format", "") for a in apps if a.get("resume_format")}
    cover_letter_vals = {a.get("used_cover_letter", "") for a in apps if a.get("used_cover_letter")}
    rf_str = ", ".join(sorted(resume_formats)) if resume_formats else "—"
    cl_str = "Yes" if cover_letter_vals == {"true"} else (
        "No" if cover_letter_vals == {"false"} else "Mixed"
    )

    parts = [f'<section class="month-section" id="month-{month}">']
    parts.append(f'<h2>{month}</h2>')
    parts.append('<div class="month-meta">')
    parts.append(f'<span><b>Applications:</b> {n}</span>')
    parts.append(f'<span><b>Avg/day:</b> {avg:.2f}</span>')
    parts.append(f'<span><b>Resume:</b> {esc(rf_str)}</span>')
    parts.append(f'<span><b>Cover letter:</b> {cl_str}</span>')
    parts.append('</div>')

    if narratives:
        parts.append('<div class="narratives"><b>Notes:</b><ul>')
        for line in narratives:
            parts.append(f'<li>{esc(line)}</li>')
        parts.append('</ul></div>')

    parts.append('<table class="apps-table">')
    parts.append('<thead><tr>'
                 '<th>Company</th>'
                 '<th>Role</th>'
                 '<th>Date Applied</th>'
                 '<th>Source</th>'
                 '<th>Original Source</th>'
                 '<th>Match</th>'
                 '<th>Pipeline</th>'
                 '<th>Days to Resp.</th>'
                 '<th>Notes</th>'
                 '</tr></thead><tbody>')
    for a in apps:
        evs = events_by_app.get(a["app_id"], [])
        stage, outcome = classify(evs)
        row_class = "row-rejected" if outcome == "rejected" else (
            "row-pending" if outcome in ("pending", "no_response") else
            "row-active" if outcome == "" else "row-other"
        )
        match_pct = a.get("match_pct", "")
        match_str = f"{match_pct}%" if match_pct else "—"
        parts.append(f'<tr class="{row_class}">')
        parts.append(f'<td>{esc(a.get("company", ""))}</td>')
        parts.append(f'<td>{esc(a.get("role", ""))}</td>')
        parts.append(f'<td class="cell-date">{esc(a.get("date_applied", ""))}</td>')
        parts.append(f'<td>{esc(a.get("source", ""))}</td>')
        parts.append(f'<td><code>{esc(a.get("original_source", ""))}</code></td>')
        parts.append(f'<td class="cell-num">{esc(match_str)}</td>')
        parts.append(f'<td>{render_pipeline_cell(evs)}</td>')
        parts.append(f'<td class="cell-num">{days_to_response(evs)}</td>')
        parts.append(f'<td class="cell-notes">{esc(a.get("application_notes", ""))}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')
    parts.append('</section>')
    return "\n".join(parts)


ROLE_BUCKETS: list[tuple[str, str]] = [
    ("devops",         "DevOps Eng."),
    ("cloud",          "Cloud Eng."),
    ("sre",            "SRE"),
    ("platform",       "Platform Eng."),
    ("infrastructure", "Infra. Eng."),
    ("systems",        "Systems Eng."),
    ("software",       "Software Eng."),
    ("other",          "Other"),
]


def _classify_role(role: str) -> str:
    rl = role.lower()
    has_devops = "devops" in rl or "dev ops" in rl
    has_sre = "site reliability" in rl or rl in ("sre engineer", "sre - infra") or (
        rl.startswith("sre") and "/" not in rl
    )
    # Hybrid titles with devops bias towards devops
    if has_sre and not has_devops:
        return "sre"
    if has_devops:
        return "devops"
    if "platform engineer" in rl or "platforms engineer" in rl or "platform operations engineer" in rl:
        return "platform"
    if any(k in rl for k in ("cloud infrastructure", "cloud operations", "cloudops",
                              "cloud enablement", "cloud administrator", "cloud platform engineer",
                              "cloud engineer", "aws cloud", "azure cloud", "saas cloud",
                              "it cloud engineer")):
        return "cloud"
    if any(k in rl for k in ("infrastructure engineer", "infrastructure linux", "infrastructure devops")):
        return "infrastructure"
    if "systems engineer" in rl or "it systems engineer" in rl:
        return "systems"
    if "software engineer" in rl:
        return "software"
    return "other"


def render_role_chart(apps: list[dict]) -> str:
    counts: dict[str, int] = {k: 0 for k, _ in ROLE_BUCKETS}
    for a in apps:
        bucket = _classify_role(a.get("role", ""))
        counts[bucket] = counts.get(bucket, 0) + 1

    total = len(apps)
    rows = [(label, counts[key]) for key, label in ROLE_BUCKETS if counts[key] > 0]
    if not rows:
        return ""

    max_count = max(c for _, c in rows)
    bar_h = 18
    label_w = 100
    count_w = 28
    track_w = 240
    gap = 6
    width = label_w + track_w + count_w + 12
    height = len(rows) * (bar_h + gap) - gap

    parts = [f'<h3>Applications by Role <span class="chart-sub">(normalized, n={total})</span></h3>']
    parts.append(f'<svg class="weekday-chart" width="{width}" height="{height}" '
                 f'xmlns="http://www.w3.org/2000/svg" role="img" '
                 f'aria-label="Applications by normalized role category">')
    for i, (label, n) in enumerate(rows):
        y = i * (bar_h + gap)
        bw = int(round((n / max_count) * track_w)) if max_count else 0
        text_y = y + bar_h - 5
        parts.append(f'<text x="0" y="{text_y}" class="wd-label">{esc(label)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{track_w}" height="{bar_h}" class="wd-track"/>')
        if bw > 0:
            parts.append(f'<rect x="{label_w}" y="{y}" width="{bw}" height="{bar_h}" class="wd-bar"/>')
        parts.append(f'<text x="{label_w + track_w + 6}" y="{text_y}" class="wd-count">{n}</text>')
    parts.append('</svg>')
    return "\n".join(parts)


def render_weekday_chart(apps: list[dict], window_days: int = WEEKDAY_WINDOW_DAYS) -> str:
    """Render a horizontal bar chart of applications per weekday over a rolling window."""
    cutoff = date.today() - timedelta(days=window_days)
    counts = [0] * 7
    for a in apps:
        raw = a.get("date_applied", "")
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if d < cutoff:
            continue
        counts[d.weekday()] += 1

    total = sum(counts)
    if total == 0:
        return ""

    max_count = max(counts)
    bar_h = 18
    label_w = 38
    count_w = 28
    track_w = 280
    gap = 6
    width = label_w + track_w + count_w + 12
    height = 7 * (bar_h + gap) - gap

    parts = [f'<h3>Applications by Weekday <span class="chart-sub">(last {window_days} days, n={total})</span></h3>']
    parts.append(f'<svg class="weekday-chart" width="{width}" height="{height}" '
                 f'xmlns="http://www.w3.org/2000/svg" role="img" '
                 f'aria-label="Applications by weekday over the last {window_days} days">')
    for i, label in enumerate(WEEKDAY_LABELS):
        y = i * (bar_h + gap)
        n = counts[i]
        bw = int(round((n / max_count) * track_w)) if max_count else 0
        text_y = y + bar_h - 5
        parts.append(f'<text x="0" y="{text_y}" class="wd-label">{label}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{track_w}" height="{bar_h}" class="wd-track"/>')
        if bw > 0:
            parts.append(f'<rect x="{label_w}" y="{y}" width="{bw}" height="{bar_h}" class="wd-bar"/>')
        parts.append(f'<text x="{label_w + track_w + 6}" y="{text_y}" class="wd-count">{n}</text>')
    parts.append('</svg>')
    return "\n".join(parts)


SUMMARY_BUCKETS = [
    ("applied_no_response", "No Response"),
    ("applied_rejected",    "Rejected (Pre-contact)"),
    ("applied_withdrew",    "Withdrew (Pre-contact)"),
    ("email_response_pending",  "At Email Response"),
    ("email_response_ghosted",  "Ghosted (Email)"),
    ("email_response_rejected", "Rejected (Email)"),
    ("email_response_withdrew", "Withdrew (Email)"),
    ("phone_screen_pending",  "At Phone Screen"),
    ("phone_screen_ghosted",  "Ghosted (Phone)"),
    ("phone_screen_rejected", "Rejected (Phone)"),
    ("phone_screen_withdrew", "Withdrew (Phone)"),
]


def render_summary(apps: list[dict], events_by_app: dict[str, list[dict]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for a in apps:
        evs = events_by_app.get(a["app_id"], [])
        stage, outcome = classify(evs)
        counts[f"{stage}_{outcome}"] += 1

    total = len(apps)
    no_response = counts.get("applied_no_response", 0)
    response_rate = ((total - no_response) / total * 100) if total else 0

    # Anyone whose furthest stage is interview_N or offer
    interviews = sum(v for k, v in counts.items() if INTERVIEW_RE.match(k.rsplit("_", 1)[0]) or k.startswith("offer_"))
    interview_rate = (interviews / total * 100) if total else 0

    parts = ['<section class="summary-section">']
    parts.append('<h2>Summary</h2>')
    parts.append('<div class="kpis">')
    parts.append(f'<div class="kpi"><div class="kpi-num">{total}</div><div class="kpi-label">Applications</div></div>')
    parts.append(f'<div class="kpi"><div class="kpi-num">{response_rate:.1f}%</div><div class="kpi-label">Response rate</div></div>')
    parts.append(f'<div class="kpi"><div class="kpi-num">{interview_rate:.1f}%</div><div class="kpi-label">Interview rate</div></div>')
    parts.append(f'<div class="kpi"><div class="kpi-num">{no_response}</div><div class="kpi-label">No response</div></div>')
    parts.append('</div>')

    # Bucket breakdown table
    parts.append('<h3>Bucket Breakdown</h3>')
    parts.append('<table class="summary-table"><thead><tr><th>Bucket</th><th>Count</th></tr></thead><tbody>')
    # Build dynamic buckets including interview rounds present in data
    extra: list[tuple[str, str]] = []
    seen_int_rounds = set()
    for k in counts:
        m = INTERVIEW_RE.match(k.rsplit("_", 1)[0])
        if m:
            seen_int_rounds.add(int(m.group(1)))
    for n in sorted(seen_int_rounds):
        for outcome, label in (
            ("pending", f"At {n}{ord_suffix(n)} Interview"),
            ("ghosted", f"Ghosted ({n}{ord_suffix(n)})"),
            ("rejected", f"Rejected ({n}{ord_suffix(n)})"),
            ("withdrew", f"Withdrew ({n}{ord_suffix(n)})"),
        ):
            key = f"interview_{n}_{outcome}"
            extra.append((key, label))
    extra.append(("offer_pending", "At Offer"))
    extra.append(("offer_accepted", "Accepted"))
    extra.append(("offer_declined", "Declined"))

    for key, label in SUMMARY_BUCKETS + extra:
        v = counts.get(key, 0)
        if v == 0:
            continue
        parts.append(f'<tr><td>{esc(label)}</td><td class="cell-num">{v}</td></tr>')
    parts.append('</tbody></table>')

    role_chart = render_role_chart(apps)
    if role_chart:
        parts.append(role_chart)

    weekday_chart = render_weekday_chart(apps)
    if weekday_chart:
        parts.append(weekday_chart)

    parts.append('<p class="summary-link">See <a href="job_search_sankey_d3.html">Sankey diagrams</a> for a visual flow.</p>')
    parts.append('</section>')
    return "\n".join(parts)


def ord_suffix(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Job Search Dashboard</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 1300px;
    margin: 0 auto;
    padding: 20px;
    background: #fafafa;
    color: #2c3e50;
  }
  h1 { margin: 0 0 4px; font-size: 24px; }
  h2 { margin: 28px 0 8px; font-size: 19px; border-bottom: 1px solid #d4dadf; padding-bottom: 4px; }
  h3 { margin: 16px 0 6px; font-size: 15px; color: #34495e; }
  .month-section, .summary-section {
    background: white;
    padding: 16px 20px;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    margin-bottom: 24px;
  }
  .month-meta { font-size: 13px; color: #7f8c8d; margin-bottom: 10px; }
  .month-meta span { margin-right: 18px; }
  .narratives { background: #fef9e7; border-left: 3px solid #f39c12; padding: 8px 12px; margin: 8px 0 14px; font-size: 13px; }
  .narratives ul { margin: 4px 0 0 18px; padding: 0; }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  .apps-table th, .apps-table td { padding: 6px 8px; border-bottom: 1px solid #ecf0f1; vertical-align: top; }
  .apps-table th { text-align: left; background: #f4f6f7; font-weight: 600; }
  .apps-table tr.row-pending { background: #fafbfc; }
  .apps-table tr.row-rejected { background: #fdf2f1; }
  .apps-table tr.row-active { background: #f1f9f5; }
  .cell-num, .cell-date { white-space: nowrap; font-variant-numeric: tabular-nums; }
  .cell-notes { font-size: 11.5px; color: #555; }
  code { font-size: 11px; background: #f4f4f4; padding: 1px 4px; border-radius: 3px; }
  .timeline { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .ev { font-size: 11px; padding: 2px 6px; background: #ecf0f1; border-radius: 3px; }
  .ev-date { color: #7f8c8d; margin-left: 4px; }
  .badge { color: white; padding: 1px 5px; border-radius: 2px; font-size: 10px; margin-left: 4px; }
  .ev-notes { display: inline-block; width: 14px; height: 14px; line-height: 14px; text-align: center; background: #34495e; color: white; border-radius: 50%; font-size: 10px; margin-left: 4px; cursor: help; }
  .kpis { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 12px; }
  .kpi { background: #ecf0f1; padding: 10px 16px; border-radius: 8px; min-width: 110px; text-align: center; }
  .kpi-num { font-size: 22px; font-weight: 600; color: #2c3e50; }
  .kpi-label { font-size: 12px; color: #7f8c8d; }
  .summary-table { max-width: 480px; }
  .summary-table th, .summary-table td { padding: 4px 10px; border-bottom: 1px solid #ecf0f1; font-size: 13px; }
  .summary-link { font-size: 13px; color: #7f8c8d; }
  .toc { font-size: 13px; margin-bottom: 14px; }
  .toc a { margin-right: 14px; color: #2980b9; text-decoration: none; }
  .toc a:hover { text-decoration: underline; }
  .chart-sub { font-size: 12px; color: #95a5a6; font-weight: normal; margin-left: 6px; }
  .weekday-chart { display: block; margin: 6px 0 4px; }
  .weekday-chart .wd-label { font: 600 12px -apple-system, sans-serif; fill: #34495e; }
  .weekday-chart .wd-track { fill: #ecf0f1; }
  .weekday-chart .wd-bar { fill: #2980b9; }
  .weekday-chart .wd-count { font: 600 12px -apple-system, sans-serif; fill: #2c3e50; }
</style>
</head>
<body>
"""

HTML_FOOT = """\
</body></html>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps", default="job_search_log/applications.csv")
    parser.add_argument("--events", default="job_search_log/pipeline_events.csv")
    parser.add_argument("--narratives", default="job_search_log/narratives.md")
    parser.add_argument("--out", default="job_search_log/dashboard.html")
    args = parser.parse_args(argv)

    apps = read_csv_dicts(Path(args.apps))
    events = read_csv_dicts(Path(args.events))
    narratives = parse_narratives(Path(args.narratives))

    events_by_app: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        events_by_app[ev["app_id"]].append(ev)

    apps_by_month: dict[str, list[dict]] = defaultdict(list)
    for a in apps:
        m = app_month(a.get("date_applied", ""))
        if m:
            apps_by_month[m].append(a)

    months = sorted(apps_by_month.keys(), reverse=True)

    parts = [HTML_HEAD]
    parts.append('<h1>Job Search Dashboard</h1>')
    parts.append(f'<div class="month-meta">Generated {date.today().isoformat()} — '
                 f'source: <code>applications.csv</code>, <code>pipeline_events.csv</code>, '
                 f'<code>narratives.md</code></div>')
    parts.append('<div class="toc">Jump to: ')
    for m in months:
        parts.append(f'<a href="#month-{m}">{m}</a>')
    parts.append('<a href="#summary">Summary</a>')
    parts.append('</div>')

    parts.append('<div id="summary">')
    parts.append(render_summary(apps, events_by_app))
    parts.append('</div>')

    for m in months:
        parts.append(render_month_section(
            m, apps_by_month[m], events_by_app, narratives.get(m, []),
        ))

    parts.append(HTML_FOOT)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts))
    print(f"Wrote {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
