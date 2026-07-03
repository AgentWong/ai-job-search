#!/usr/bin/env python3
"""Generate high-fidelity Sankey diagrams from sankey_data.json.

Reads `<stage>_<outcome>` bucket counts and produces a cascading flow:

    Applications → No Response, Pre-contact Rejected, Pre-contact Withdrew,
                   Email Response (intermediate)
    Email Response → Ghosted (Email), Rejected (Email), Withdrew (Email),
                     Phone Screen (intermediate)
    Phone Screen → Ghosted (Phone), Rejected (Phone), Withdrew (Phone),
                   1st Interview (intermediate)
    1st Interview → Ghosted (1st), Rejected (1st), Withdrew (1st),
                    2nd Interview (intermediate)
    2nd Interview → Ghosted (2nd), Rejected (2nd), Withdrew (2nd),
                    3rd Interview (intermediate)
    ... (extends to whatever interview_N stages exist)
    Final Interview → Job Offer

Output: `job_search_log/job_search_sankey_d3.html` — standalone HTML with
embedded D3.js + d3-sankey.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

DEFAULT_DATA_PATH = Path("job_search_log/sankey_data.json")
DEFAULT_OUTPUT_PATH = Path("job_search_log/job_search_sankey_d3.html")

INTERVIEW_RE = re.compile(r"^interview_(\d+)$")

# Stages in display order
BASE_STAGES = ["applied", "email_response", "phone_screen"]

# Outcome rendering metadata
OUTCOME_INFO = {
    "no_response":  {"label": "No Response", "color": "#999999", "link_rgba": "rgba(160,160,160,0.35)"},
    "rejected":     {"label": "Rejected",    "color": "#e74c3c", "link_rgba": "rgba(231,76,60,0.4)"},
    "ghosted":      {"label": "Ghosted",     "color": "#e67e22", "link_rgba": "rgba(230,126,34,0.45)"},
    "withdrew":     {"label": "Withdrew",    "color": "#f39c12", "link_rgba": "rgba(243,156,18,0.45)"},
    "aborted":      {"label": "Aborted",     "color": "#9b59b6", "link_rgba": "rgba(155,89,182,0.45)"},
    "pending":      {"label": "Pending",     "color": "#3498db", "link_rgba": "rgba(52,152,219,0.4)"},
    "accepted":     {"label": "Accepted",    "color": "#f1c40f", "link_rgba": "rgba(241,196,15,0.5)"},
    "declined":     {"label": "Declined",    "color": "#bdc3c7", "link_rgba": "rgba(189,195,199,0.5)"},
}

STAGE_INFO = {
    "applied":        {"label": "Applications",   "color": "#4a90d9", "link_rgba": "rgba(74,144,217,0.45)"},
    "email_response": {"label": "Email Response", "color": "#16a085", "link_rgba": "rgba(22,160,133,0.45)"},
    "phone_screen":   {"label": "Phone Screen",   "color": "#2ecc71", "link_rgba": "rgba(46,204,113,0.45)"},
    "offer":          {"label": "Job Offer",      "color": "#f1c40f", "link_rgba": "rgba(241,196,15,0.5)"},
}

INTERVIEW_COLORS = ["#27ae60", "#1abc9c", "#16a085", "#0e6655", "#0b5345", "#073d33"]


def ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def stage_label_short(stage: str) -> str:
    """Short label used inside terminal-node names like 'Ghosted (Email)'."""
    if stage == "applied":
        return "Pre-contact"
    if stage == "email_response":
        return "Email"
    if stage == "phone_screen":
        return "Phone"
    if stage == "offer":
        return "Offer"
    m = INTERVIEW_RE.match(stage)
    if m:
        return ordinal(int(m.group(1)))
    return stage


def stage_node_label(stage: str) -> str:
    """Label for the intermediate stage node itself."""
    if stage in STAGE_INFO:
        return STAGE_INFO[stage]["label"]
    m = INTERVIEW_RE.match(stage)
    if m:
        return f"{ordinal(int(m.group(1)))} Interview"
    return stage


def stage_color(stage: str) -> str:
    if stage in STAGE_INFO:
        return STAGE_INFO[stage]["color"]
    m = INTERVIEW_RE.match(stage)
    if m:
        n = int(m.group(1))
        return INTERVIEW_COLORS[min(n - 1, len(INTERVIEW_COLORS) - 1)]
    return "#888888"


def stage_link_rgba(stage: str) -> str:
    if stage in STAGE_INFO:
        return STAGE_INFO[stage]["link_rgba"]
    m = INTERVIEW_RE.match(stage)
    if m:
        return "rgba(39,174,96,0.45)"
    return "rgba(136,136,136,0.4)"


def discover_pipeline_stages(buckets: dict) -> list[str]:
    """Return ordered stage list present in the buckets, including 'applied'
    and 'offer' if any bucket references them. Always includes the chain up
    to the highest interview_N seen.
    """
    seen: set[str] = set()
    max_int = 0
    for key in buckets:
        # key format: <stage>_<outcome> where stage may itself contain underscores
        # We need to identify the stage prefix. Try suffix matching against
        # known outcomes.
        for outcome in OUTCOME_INFO:
            if key.endswith(f"_{outcome}"):
                stage = key[: -(len(outcome) + 1)]
                seen.add(stage)
                m = INTERVIEW_RE.match(stage)
                if m:
                    max_int = max(max_int, int(m.group(1)))
                break

    # Build ordered chain
    ordered = ["applied"]
    if "email_response" in seen or any(s.startswith("phone_screen") or INTERVIEW_RE.match(s) or s == "offer" for s in seen):
        ordered.append("email_response")
    if "phone_screen" in seen or any(INTERVIEW_RE.match(s) or s == "offer" for s in seen):
        ordered.append("phone_screen")
    for n in range(1, max_int + 1):
        ordered.append(f"interview_{n}")
    if "offer" in seen:
        ordered.append("offer")

    return ordered


def split_bucket_key(key: str) -> tuple[str, str] | None:
    for outcome in OUTCOME_INFO:
        if key.endswith(f"_{outcome}"):
            return (key[: -(len(outcome) + 1)], outcome)
    return None


def build_diagram(cohort: dict) -> dict:
    """Build node/link data for one cohort."""
    title = cohort["title"]
    total = cohort["total"]
    buckets: dict[str, int] = cohort["buckets"]

    # Group counts by (stage, outcome)
    by_stage_outcome: dict[tuple[str, str], int] = {}
    for key, count in buckets.items():
        parsed = split_bucket_key(key)
        if not parsed:
            continue
        by_stage_outcome[parsed] = by_stage_outcome.get(parsed, 0) + count

    # Compute total reaching each stage = sum of (this stage's terminations) +
    # (everyone who advanced past this stage). Walk pipeline order.
    pipeline = discover_pipeline_stages(buckets)

    # advanced[i] = number who reached stage[i] AND moved on to stage[i+1]
    # reached[i] = total who reached stage[i] = terminations_at_stage[i] + advanced[i]
    reached: dict[str, int] = {}
    terminations: dict[str, dict[str, int]] = {}
    for stage in pipeline:
        terminations[stage] = {}
        for (s, outcome), count in by_stage_outcome.items():
            if s == stage:
                terminations[stage][outcome] = count

    # Walk from last stage backwards to compute reached
    advanced: dict[str, int] = {}
    cum = 0
    for stage in reversed(pipeline):
        # advanced from previous stage = sum at this stage and beyond
        term_sum = sum(terminations.get(stage, {}).values())
        cum_at_this_stage = term_sum + cum
        reached[stage] = cum_at_this_stage
        # advanced INTO this stage from previous = cum_at_this_stage
        # advanced FROM this stage to next = cum (the prior accumulation)
        advanced[stage] = cum
        cum = cum_at_this_stage

    # ----- Build nodes/links -----
    nodes: list[dict] = []
    node_idx: dict[str, int] = {}

    def add_node(name: str, color: str) -> int:
        if name not in node_idx:
            node_idx[name] = len(nodes)
            nodes.append({"name": name, "color": color})
        return node_idx[name]

    links: list[dict] = []

    def add_link(src: str, dst: str, value: int, color: str):
        if value > 0:
            links.append({
                "source": node_idx[src],
                "target": node_idx[dst],
                "value": value,
                "color": color,
            })

    # Add pipeline stage nodes (only those reached)
    for stage in pipeline:
        if reached.get(stage, 0) > 0:
            add_node(stage_node_label(stage), stage_color(stage))

    # For each stage, add terminal-outcome nodes and links
    for i, stage in enumerate(pipeline):
        stage_node = stage_node_label(stage)
        terms = terminations.get(stage, {})

        # First add the "advance to next stage" link (positive outcome rendered first)
        adv = advanced.get(stage, 0)
        if adv > 0 and i + 1 < len(pipeline):
            next_stage = pipeline[i + 1]
            next_node = stage_node_label(next_stage)
            add_link(stage_node, next_node, adv, stage_link_rgba(next_stage))

        # Terminal outcomes at this stage
        for outcome, count in terms.items():
            if count <= 0:
                continue
            info = OUTCOME_INFO.get(outcome)
            if info is None:
                continue
            # Special-case stage 0 outcomes — they don't need the "(Pre-contact)"
            # qualifier on no_response, but rejected/withdrew/aborted at stage 0
            # do benefit from it for clarity.
            if stage == "applied":
                if outcome == "no_response":
                    label = "No Response"
                elif outcome in ("rejected", "withdrew", "aborted"):
                    label = f"{info['label']} (Pre-contact)"
                else:
                    label = info["label"]
            elif stage == "offer":
                label = info["label"]
            else:
                label = f"{info['label']} ({stage_label_short(stage)})"

            add_node(label, info["color"])
            add_link(stage_node, label, count, info["link_rgba"])

    # ----- Stats line -----
    no_response = terminations.get("applied", {}).get("no_response", 0)
    responded = total - no_response
    response_rate = (responded / total * 100) if total else 0
    interview_reached = sum(
        reached.get(s, 0) for s in pipeline if INTERVIEW_RE.match(s)
    )
    # Number of distinct apps that reached ANY interview round = reached[interview_1]
    interviews = reached.get("interview_1", 0)
    interview_rate = (interviews / total * 100) if total else 0

    stats = (
        f"Response Rate: {response_rate:.1f}% ({responded}/{total})"
        f"  |  Interview Rate: {interview_rate:.1f}% ({interviews}/{total})"
    )

    return {
        "title": title,
        "stats": stats,
        "nodes": nodes,
        "links": links,
    }


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Job Search Sankey Diagrams</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://unpkg.com/d3-sankey@0.12.3/dist/d3-sankey.min.js"></script>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 1100px;
    margin: 0 auto;
    padding: 20px;
    background: #fafafa;
  }
  .diagram-card {
    background: white;
    padding: 20px 24px 16px;
    margin-bottom: 28px;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  }
  .diagram-title {
    font-size: 17px;
    font-weight: 600;
    color: #2c3e50;
    margin: 0 0 2px;
  }
  .diagram-stats {
    font-size: 13px;
    color: #7f8c8d;
    margin: 0 0 12px;
  }
  .node rect {
    shape-rendering: crispEdges;
  }
  .node text {
    font-size: 12.5px;
    fill: #333;
    font-weight: 500;
  }
  .link {
    fill: none;
    stroke-opacity: 0.4;
  }
  .link:hover {
    stroke-opacity: 0.65;
  }
</style>
</head>
<body>

<script>
const diagrams = %%DIAGRAMS_JSON%%;

const WIDTH = 1040;
const HEIGHT = 460;
const MARGIN = {top: 8, right: 200, bottom: 8, left: 8};
const NODE_WIDTH = 22;
const NODE_PAD = 22;

diagrams.forEach((data, idx) => {
  const card = d3.select("body").append("div").attr("class", "diagram-card");
  card.append("p").attr("class", "diagram-title").text(data.title);
  card.append("p").attr("class", "diagram-stats").text(data.stats);

  const svg = card.append("svg")
    .attr("width", WIDTH)
    .attr("height", HEIGHT)
    .attr("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);

  const innerWidth = WIDTH - MARGIN.left - MARGIN.right;
  const innerHeight = HEIGHT - MARGIN.top - MARGIN.bottom;

  const g = svg.append("g")
    .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

  const sankey = d3.sankey()
    .nodeId(d => d.index)
    .nodeWidth(NODE_WIDTH)
    .nodePadding(NODE_PAD)
    .nodeAlign(d3.sankeyJustify)
    .extent([[0, 0], [innerWidth, innerHeight]]);

  const graph = sankey({
    nodes: data.nodes.map((d, i) => ({...d, index: i})),
    links: data.links.map(d => ({...d})),
  });

  const link = g.append("g")
    .selectAll(".link")
    .data(graph.links)
    .join("path")
      .attr("class", "link")
      .attr("d", d3.sankeyLinkHorizontal())
      .attr("stroke", d => d.color || "#aaa")
      .attr("stroke-width", d => Math.max(1, d.width))
    .append("title")
      .text(d => `${d.source.name} → ${d.target.name}: ${d.value}`);

  const node = g.append("g")
    .selectAll(".node")
    .data(graph.nodes)
    .join("g")
      .attr("class", "node")
      .attr("transform", d => `translate(${d.x0},${d.y0})`);

  node.append("rect")
    .attr("height", d => Math.max(1, d.y1 - d.y0))
    .attr("width", d => d.x1 - d.x0)
    .attr("fill", d => d.color || "#69b3a2")
    .attr("stroke", d => d3.color(d.color || "#69b3a2").darker(0.6))
    .attr("stroke-width", 0.5)
    .attr("rx", 2)
    .append("title")
      .text(d => `${d.name}: ${d.value}`);

  node.append("text")
    .attr("x", d => (d.x1 - d.x0) + 8)
    .attr("y", d => (d.y1 - d.y0) / 2)
    .attr("dy", "0.35em")
    .attr("text-anchor", "start")
    .text(d => `${d.name} (${d.value})`);
});
</script>
</body>
</html>
"""


def generate_html(diagrams: list[dict], output_path: Path) -> None:
    diagrams_json = json.dumps(diagrams, indent=2)
    content = HTML_TEMPLATE.replace("%%DIAGRAMS_JSON%%", diagrams_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    print(f"Saved {output_path} with {len(diagrams)} diagrams")


def main(argv=None) -> int:
    if not DEFAULT_DATA_PATH.exists():
        raise SystemExit(
            f"{DEFAULT_DATA_PATH} not found. Run scripts/extract_sankey_data.py first."
        )
    with DEFAULT_DATA_PATH.open() as f:
        data = json.load(f)

    diagrams = []
    for key in ("all_apps", "one_page", "two_page"):
        if key not in data:
            continue
        diagrams.append(build_diagram(data[key]))

    generate_html(diagrams, DEFAULT_OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
