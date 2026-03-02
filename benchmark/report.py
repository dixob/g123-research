"""
Report generation — human-readable summaries and file output.

Includes: model leaderboard, cost/token analysis, latency percentiles,
per-field accuracy breakdown, and cost-accuracy Pareto analysis.
"""
from __future__ import annotations

import json
from pathlib import Path


def _fmt_cost(val: float | None) -> str:
    """Format a USD cost value for display."""
    if val is None:
        return "n/a"
    if val < 0.01:
        return f"${val:.5f}"
    return f"${val:.4f}"


def _fmt_tokens(val: int | float) -> str:
    """Format token count with K/M suffix."""
    if val >= 1_000_000:
        return f"{val/1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val/1_000:.1f}K"
    return str(int(val))


def print_summary(results: dict) -> None:
    """Print a formatted multi-section report to stdout."""
    models = results["models"]
    meta = results["meta"]

    print(f"\n{'='*80}")
    print(f"  G123 VLM BENCHMARK RESULTS — {meta['total_samples']} samples")
    print(f"  {meta['timestamp']}")
    print(f"{'='*80}\n")

    ranked = sorted(
        models.items(),
        key=lambda x: x[1]["summary"]["overall_score"],
        reverse=True,
    )

    # ── Section 1: Leaderboard with cost ──────────────────────
    print("  MODEL LEADERBOARD")
    print(f"  {'Model':<20} {'Score':>7} {'$/img':>9} {'Latency':>8} "
          f"{'p50':>6} {'p90':>6} {'Parse':>6} {'Err':>5}")
    print(f"  {'-'*69}")

    for model_name, data in ranked:
        s = data["summary"]
        avg_cost = s.get("avg_cost_per_screenshot_usd")
        print(
            f"  {model_name:<20} {s['overall_score']:>6.1f}% "
            f"{_fmt_cost(avg_cost):>9} "
            f"{s['avg_latency_s']:>7.1f}s "
            f"{s['latency_p50_s']:>5.1f}s "
            f"{s['latency_p90_s']:>5.1f}s "
            f"{s['parse_failures']:>5} "
            f"{s['api_errors']:>4}"
        )

    # ── Section 2: Token & Cost Analysis ──────────────────────
    print(f"\n  TOKEN & COST ANALYSIS")
    print(f"  {'Model':<20} {'In Tok':>9} {'Out Tok':>9} {'Total $':>10} "
          f"{'$/1K img':>10} {'$/day@100':>10}")
    print(f"  {'-'*70}")

    for model_name, data in ranked:
        s = data["summary"]
        avg_in = s.get("avg_input_tokens", 0)
        avg_out = s.get("avg_output_tokens", 0)
        total_cost = s.get("total_cost_usd")
        avg_cost = s.get("avg_cost_per_screenshot_usd")

        # Projected costs
        cost_per_1k = (avg_cost * 1000) if avg_cost else None
        cost_per_day_100 = (avg_cost * 100) if avg_cost else None

        print(
            f"  {model_name:<20} "
            f"{_fmt_tokens(avg_in):>9} "
            f"{_fmt_tokens(avg_out):>9} "
            f"{_fmt_cost(total_cost):>10} "
            f"{_fmt_cost(cost_per_1k):>10} "
            f"{_fmt_cost(cost_per_day_100):>10}"
        )

    # ── Section 3: Cost-Accuracy Trade-off ────────────────────
    print(f"\n  COST-ACCURACY TRADE-OFF")
    print(f"  {'Model':<20} {'Score':>7} {'$/img':>9} {'Score/$':>10} {'Verdict':>12}")
    print(f"  {'-'*60}")

    for model_name, data in ranked:
        s = data["summary"]
        score = s["overall_score"]
        avg_cost = s.get("avg_cost_per_screenshot_usd")

        if avg_cost and avg_cost > 0:
            score_per_dollar = score / (avg_cost * 1000)  # score points per $1
            # Simple Pareto verdict
            verdict = "---"
        else:
            score_per_dollar = None
            verdict = "no cost data"

        spd_str = f"{score_per_dollar:.1f} pts/$1" if score_per_dollar else "n/a"
        print(
            f"  {model_name:<20} {score:>6.1f}% "
            f"{_fmt_cost(avg_cost):>9} "
            f"{spd_str:>10} "
            f"{verdict:>12}"
        )

    # Mark Pareto-optimal models
    # A model is Pareto-optimal if no other model has both higher score AND lower cost
    pareto = []
    for model_name, data in ranked:
        s = data["summary"]
        score = s["overall_score"]
        cost = s.get("avg_cost_per_screenshot_usd") or float("inf")
        dominated = False
        for other_name, other_data in ranked:
            if other_name == model_name:
                continue
            os = other_data["summary"]
            other_score = os["overall_score"]
            other_cost = os.get("avg_cost_per_screenshot_usd") or float("inf")
            if other_score >= score and other_cost <= cost and (other_score > score or other_cost < cost):
                dominated = True
                break
        if not dominated:
            pareto.append(model_name)

    if pareto:
        print(f"\n  Pareto-optimal: {', '.join(pareto)}")

    # ── Section 4: Per-field breakdown ────────────────────────
    all_fields = set()
    for data in models.values():
        all_fields.update(data["summary"].get("per_field", {}).keys())
    all_fields = sorted(all_fields)

    if all_fields:
        print(f"\n  PER-FIELD ACCURACY (mean score)")
        header = f"  {'Field':<22}"
        for model_name, _ in ranked:
            header += f" {model_name:>18}"
        print(header)
        print(f"  {'-'*(22 + 19 * len(ranked))}")

        for field in all_fields:
            row = f"  {field:<22}"
            for model_name, data in ranked:
                pf = data["summary"].get("per_field", {})
                val = pf.get(field, {}).get("mean", 0)
                row += f" {val*100:>17.1f}%"
            print(row)

    print()


def save_results(results: dict, output_dir: str) -> str:
    """Save full results JSON to the output directory. Returns the file path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    timestamp = results["meta"]["timestamp"].replace(":", "-")
    filepath = out / f"benchmark_{timestamp}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Results saved to: {filepath}")
    return str(filepath)
