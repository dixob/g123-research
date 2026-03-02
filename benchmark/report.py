"""
Report generation — human-readable summaries and file output.

Includes: model leaderboard with extraction recall, cost/token analysis,
latency percentiles, per-field accuracy, cost-accuracy Pareto analysis,
bootstrap confidence intervals, and stratified reporting by screen type
and language.
"""
from __future__ import annotations

import json
import random
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


def _bootstrap_ci(
    values: list[float],
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """
    Compute bootstrap 95% confidence interval for the mean.

    Uses a fixed seed for reproducible reports.
    """
    if len(values) < 2:
        mean = values[0] if values else 0.0
        return (mean, mean)
    rng = random.Random(seed)
    means = []
    for _ in range(n_resamples):
        sample = rng.choices(values, k=len(values))
        means.append(sum(sample) / len(sample))
    means.sort()
    lo = means[int(alpha / 2 * n_resamples)]
    hi = means[int((1 - alpha / 2) * n_resamples)]
    return (lo, hi)


def _get_per_sample_scores(data: dict) -> list[float]:
    """Extract per-sample overall percentage scores for CI computation."""
    scores = []
    for sample in data.get("samples", []):
        if "scores" not in sample:
            continue
        s = sample["scores"]
        if s["max_possible"] > 0:
            scores.append(s["weighted_score"] / s["max_possible"] * 100)
    return scores


def _get_per_sample_extraction_recalls(data: dict) -> list[float]:
    """Extract per-sample extraction recall scores for CI computation."""
    recalls = []
    for sample in data.get("samples", []):
        if "scores" not in sample:
            continue
        er = sample["scores"].get("extraction_recall")
        if er is not None:
            recalls.append(er)
    return recalls


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

    # ── Section 1: Leaderboard with extraction recall ─────
    print("  MODEL LEADERBOARD")
    print(f"  {'Model':<20} {'Score':>14} {'ExtRecall':>14} "
          f"{'Null%':>6} {'$/img':>9} {'p50':>6} {'p90':>6}")
    print(f"  {'-'*77}")

    for model_name, data in ranked:
        s = data["summary"]
        avg_cost = s.get("avg_cost_per_screenshot_usd")

        # Bootstrap CIs for overall score
        sample_scores = _get_per_sample_scores(data)
        if len(sample_scores) >= 2:
            ci_lo, ci_hi = _bootstrap_ci(sample_scores)
            score_str = f"{s['overall_score']:>5.1f}% [{ci_lo:.1f}-{ci_hi:.1f}]"
        else:
            score_str = f"{s['overall_score']:>5.1f}%"

        # Extraction recall with CI
        er = s.get("extraction_recall")
        er_samples = _get_per_sample_extraction_recalls(data)
        if er is not None and len(er_samples) >= 2:
            er_lo, er_hi = _bootstrap_ci(er_samples)
            er_str = f"{er:>5.1f}% [{er_lo:.1f}-{er_hi:.1f}]"
        elif er is not None:
            er_str = f"{er:>5.1f}%"
        else:
            er_str = "n/a"

        null_rate = s.get("null_agreement_rate", 0)

        print(
            f"  {model_name:<20} {score_str:>14} {er_str:>14} "
            f"{null_rate*100:>5.1f}% "
            f"{_fmt_cost(avg_cost):>9} "
            f"{s['latency_p50_s']:>5.1f}s "
            f"{s['latency_p90_s']:>5.1f}s"
        )

    # ── Section 2: Token & Cost Analysis ──────────────────
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

    # ── Section 3: Cost-Accuracy Trade-off ────────────────
    print(f"\n  COST-ACCURACY TRADE-OFF")
    print(f"  {'Model':<20} {'Score':>7} {'$/img':>9} {'Score/$':>10} {'Verdict':>12}")
    print(f"  {'-'*60}")

    for model_name, data in ranked:
        s = data["summary"]
        score = s["overall_score"]
        avg_cost = s.get("avg_cost_per_screenshot_usd")

        if avg_cost and avg_cost > 0:
            score_per_dollar = score / (avg_cost * 1000)
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

    # Pareto-optimal models
    pareto = []
    for model_name, data in ranked:
        s = data["summary"]
        score = s["overall_score"]
        cost = s.get("avg_cost_per_screenshot_usd") or float("inf")
        dominated = False
        for other_name, other_data in ranked:
            if other_name == model_name:
                continue
            os_ = other_data["summary"]
            other_score = os_["overall_score"]
            other_cost = os_.get("avg_cost_per_screenshot_usd") or float("inf")
            if other_score >= score and other_cost <= cost and (other_score > score or other_cost < cost):
                dominated = True
                break
        if not dominated:
            pareto.append(model_name)

    if pareto:
        print(f"\n  Pareto-optimal: {', '.join(pareto)}")

    # ── Section 4: Per-field breakdown ────────────────────
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

    # ── Section 5: Accuracy by Screen Type ────────────────
    _print_stratified(ranked, "screen_type", "ACCURACY BY SCREEN TYPE")

    # ── Section 6: Accuracy by Language ───────────────────
    _print_stratified(ranked, "language", "ACCURACY BY LANGUAGE")

    print()


def _print_stratified(ranked: list, group_key: str, title: str) -> None:
    """Print a stratified accuracy breakdown grouped by a sample attribute."""
    # Collect all group values across all models
    all_groups: set[str] = set()
    for _, data in ranked:
        for sample in data.get("samples", []):
            if "scores" in sample and sample.get(group_key):
                all_groups.add(sample[group_key])

    if not all_groups:
        return

    sorted_groups = sorted(all_groups)

    print(f"\n  {title}")
    header = f"  {group_key:<15} {'N':>4}"
    for model_name, _ in ranked:
        header += f" {model_name:>16}"
    print(header)
    print(f"  {'-'*(20 + 17 * len(ranked))}")

    for group in sorted_groups:
        row = f"  {group:<15}"
        n_shown = False
        for model_name, data in ranked:
            group_samples = [
                s for s in data.get("samples", [])
                if "scores" in s and s.get(group_key) == group
            ]
            if not n_shown:
                row += f" {len(group_samples):>3}"
                n_shown = True

            if group_samples:
                total_w = sum(s["scores"]["weighted_score"] for s in group_samples)
                total_m = sum(s["scores"]["max_possible"] for s in group_samples)
                pct = (total_w / total_m * 100) if total_m > 0 else 0
                row += f" {pct:>15.1f}%"
            else:
                row += f" {'n/a':>16}"
        print(row)


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
