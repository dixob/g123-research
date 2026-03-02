"""
Report generation — human-readable summaries and file output.
"""
from __future__ import annotations

import json
from pathlib import Path


def print_summary(results: dict) -> None:
    """Print a formatted comparison table to stdout."""
    models = results["models"]
    meta = results["meta"]

    print(f"\n{'='*70}")
    print(f"  BENCHMARK RESULTS — {meta['total_samples']} samples")
    print(f"  {meta['timestamp']}")
    print(f"{'='*70}\n")

    # ── Leaderboard ───────────────────────────────────────────
    print("  MODEL LEADERBOARD")
    print(f"  {'Model':<22} {'Score':>8} {'Avg Latency':>12} {'Parse Fail':>11} {'Errors':>8}")
    print(f"  {'-'*63}")

    ranked = sorted(
        models.items(),
        key=lambda x: x[1]["summary"]["overall_score"],
        reverse=True,
    )

    for model_name, data in ranked:
        s = data["summary"]
        print(
            f"  {model_name:<22} {s['overall_score']:>7.1f}% "
            f"{s['avg_latency_s']:>10.1f}s "
            f"{s['parse_failures']:>10} "
            f"{s['api_errors']:>7}"
        )

    # ── Per-field breakdown ───────────────────────────────────
    # Collect all field names
    all_fields = set()
    for data in models.values():
        all_fields.update(data["summary"].get("per_field", {}).keys())
    all_fields = sorted(all_fields)

    if all_fields:
        print(f"\n  PER-FIELD ACCURACY (mean score)")
        header = f"  {'Field':<20}"
        for model_name, _ in ranked:
            header += f" {model_name:>18}"
        print(header)
        print(f"  {'-'*(20 + 19 * len(ranked))}")

        for field in all_fields:
            row = f"  {field:<20}"
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

    with open(filepath, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Results saved to: {filepath}")
    return str(filepath)
