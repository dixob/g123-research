"""
Gacha Report Generator — produces a markdown analytics report from gacha tracker data.

Takes the JSON output from gacha_tracker.py and generates a publication-ready
markdown report with economy analysis and business insights.

Usage:
  python -m demos.gacha_report gacha_results.json
  python -m demos.gacha_report gacha_results.json --output gacha_analysis.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime


def generate_gacha_report(data: dict) -> str:
    """Generate a markdown gacha economy analysis report."""
    lines = []
    meta = data["meta"]
    session = data["session"]
    cost = data["cost"]
    rarity = data.get("rarity_analysis", {})

    lines.append("# Gacha Economy Analysis Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Model:** {meta['model']}")
    lines.append(f"**Screenshots:** {meta['total_screenshots']}")
    lines.append(f"**API Cost:** ${cost['total_api_cost_usd']:.5f}")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")

    total_cards = session["total_cards"]
    new_rate = session["new_rate"]
    ssr_count = rarity.get("SSR", {}).get("count", 0) + rarity.get("SSR+", {}).get("count", 0)
    ssr_rate = ((rarity.get("SSR", {}).get("rate_pct", 0) or 0) +
                (rarity.get("SSR+", {}).get("rate_pct", 0) or 0))

    lines.append(f"Across {meta['total_screenshots']} screenshots, "
                 f"**{total_cards} cards** were extracted with a "
                 f"**{new_rate}% new card rate**.")
    if ssr_count > 0:
        lines.append(f"The observed SSR+ rate is **{ssr_rate:.1f}%** "
                     f"({ssr_count} out of {total_cards} cards).")
    lines.append("")

    # Rarity Distribution
    if rarity:
        lines.append("## Rarity Distribution")
        lines.append("")
        lines.append("| Rarity | Count | Rate | Visual |")
        lines.append("|--------|------:|-----:|:-------|")

        rarity_order = ["SSR+", "SSR", "SR", "R", "N"]
        for r in rarity_order:
            if r in rarity and isinstance(rarity[r], dict):
                d = rarity[r]
                bar = "█" * max(1, int(d["rate_pct"] / 2))
                lines.append(f"| **{r}** | {d['count']} | {d['rate_pct']:.1f}% | `{bar}` |")

        for r, d in rarity.items():
            if r not in rarity_order and isinstance(d, dict) and "count" in d:
                bar = "█" * max(1, int(d["rate_pct"] / 2))
                lines.append(f"| {r} | {d['count']} | {d['rate_pct']:.1f}% | `{bar}` |")

        lines.append("")

        # Efficiency metrics
        if "spend_per_ssr" in rarity or "pulls_per_ssr" in rarity:
            lines.append("### Efficiency Metrics")
            lines.append("")
            if "spend_per_ssr" in rarity:
                lines.append(f"- **Currency per SSR:** {rarity['spend_per_ssr']:.0f}")
            if "pulls_per_ssr" in rarity:
                lines.append(f"- **Pulls per SSR:** {rarity['pulls_per_ssr']:.0f}")
            lines.append("")

    # Pity Progression
    pity = session.get("pity_progression", [])
    if pity:
        lines.append("## Pity Progression")
        lines.append("")
        lines.append("| Screenshot | Pity | Max | Progress |")
        lines.append("|------------|-----:|----:|:---------|")

        for p in pity:
            pity_max = p.get("pity_max") or "?"
            if isinstance(pity_max, (int, float)) and pity_max > 0:
                pct = p["pity"] / pity_max * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"| `{p['image']}` | {p['pity']} | {pity_max} | `{bar}` {pct:.0f}% |")
            else:
                lines.append(f"| `{p['image']}` | {p['pity']} | {pity_max} | — |")

        lines.append("")

    # Currency Analysis
    if session.get("currency_spent", 0) > 0:
        lines.append("## Currency Analysis")
        lines.append("")
        lines.append(f"- **Total currency spent:** {session['currency_spent']:.0f}")
        if total_cards > 0:
            lines.append(f"- **Currency per card:** {session['currency_spent'] / total_cards:.1f}")
        lines.append("")

    # Business Implications
    lines.append("## Business Implications for CTW / G123")
    lines.append("")
    lines.append(
        "This automated gacha analysis demonstrates several production applications:"
    )
    lines.append("")
    lines.append("1. **Rate Compliance Monitoring**: Automatically verify that observed "
                 "gacha rates match published rates. Critical for compliance with "
                 "Japanese gacha regulations (JOGA guidelines).")
    lines.append("2. **Economy Balance Tracking**: Monitor pity progression and "
                 "currency efficiency across game updates to detect economy disruptions.")
    lines.append("3. **A/B Test Analysis**: Compare gacha metrics across banner variants "
                 "to optimize monetization without degrading player experience.")
    lines.append("4. **Player Behavior Analytics**: Aggregate gacha data across player "
                 "segments to understand spending patterns and churn risk.")
    lines.append("5. **QA Automation**: Detect gacha bugs (negative pity, missing cards, "
                 "wrong rarity borders) from screenshot-level analysis.")
    lines.append("")

    # Cost Analysis
    lines.append("## VLM Cost Analysis")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|------:|")
    lines.append(f"| Total API cost | ${cost['total_api_cost_usd']:.5f} |")
    lines.append(f"| Cost per screenshot | ${cost['avg_cost_per_screenshot_usd']:.5f} |")
    lines.append(f"| Total latency | {cost['total_latency_s']:.1f}s |")

    # Projections
    avg_cost = cost['avg_cost_per_screenshot_usd']
    lines.append(f"| Cost @ 100 screenshots/day | ${avg_cost * 100:.4f}/day |")
    lines.append(f"| Cost @ 1000 screenshots/day | ${avg_cost * 1000:.4f}/day |")
    lines.append(f"| Cost @ 10K screenshots/day | ${avg_cost * 10000:.2f}/day |")
    lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate markdown gacha economy report"
    )
    parser.add_argument(
        "input_file",
        help="Path to gacha tracker JSON output",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save markdown report to this path (default: stdout)",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    report = generate_gacha_report(data)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report saved to: {output_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
