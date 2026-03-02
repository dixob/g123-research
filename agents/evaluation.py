"""
Agent Evaluation — compare QA agent output vs ground truth annotations.

Measures:
  - Accuracy improvement from retries (does retry logic help?)
  - Cost of retries (is the accuracy gain worth the extra cost?)
  - Agent vs single-shot comparison
  - QA issue detection rate

Usage:
  python -m agents.evaluation --annotations-dir data/annotations/full --images-dir images
  python -m agents.evaluation --annotations-dir data/annotations/full --images-dir images --model gpt-4o --max-samples 5
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from benchmark.config import MODELS, FIELD_SPEC, EXTRACT_PROMPT
from benchmark.providers import call_model
from benchmark.runner import load_annotations, find_image
from benchmark.scoring import score_prediction
from .game_qa_agent import run_qa_agent


def evaluate_agent(
    annotations_source: str,
    images_dir: str,
    model_name: str = "gemini-2.5-flash",
    max_samples: int | None = None,
    max_retries: int = 2,
) -> dict:
    """
    Compare QA agent vs single-shot extraction on the same samples.

    Returns:
        Evaluation dict with per-sample comparisons and aggregate metrics.
    """
    annotations = load_annotations(annotations_source)
    if max_samples:
        annotations = annotations[:max_samples]

    total = len(annotations)
    print(f"Evaluating QA agent ({model_name}) on {total} samples...")

    results = {
        "meta": {
            "model": model_name,
            "max_retries": max_retries,
            "total_samples": total,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "samples": [],
        "aggregate": {},
    }

    # Accumulators
    single_scores = []
    agent_scores = []
    single_costs = []
    agent_costs = []
    single_latencies = []
    agent_latencies = []
    retries_used = []
    qa_issues_count = []

    for i, annotation in enumerate(annotations):
        sid = annotation["screenshot_id"]
        image_path = find_image(sid, images_dir)

        if not image_path:
            print(f"  [{i+1}/{total}] SKIP {sid} — image not found")
            continue

        print(f"  [{i+1}/{total}] {sid}...", end=" ", flush=True)

        # ── Single-shot extraction ────────────────────────────
        single_response = call_model(model_name, image_path, EXTRACT_PROMPT, MODELS)
        single_cost = single_response.get("cost_usd") or 0
        single_latency = single_response.get("latency_s", 0)

        if single_response.get("parsed"):
            single_score_result = score_prediction(
                single_response["parsed"], annotation, FIELD_SPEC
            )
            single_pct = (
                single_score_result["weighted_score"] / single_score_result["max_possible"] * 100
            ) if single_score_result["max_possible"] > 0 else 0
        else:
            single_pct = 0.0
            single_score_result = None

        # ── Agent extraction ──────────────────────────────────
        agent_report, trace = run_qa_agent(image_path, model_name, max_retries)

        if agent_report.get("extraction"):
            agent_score_result = score_prediction(
                agent_report["extraction"], annotation, FIELD_SPEC
            )
            agent_pct = (
                agent_score_result["weighted_score"] / agent_score_result["max_possible"] * 100
            ) if agent_score_result["max_possible"] > 0 else 0
        else:
            agent_pct = 0.0
            agent_score_result = None

        improvement = agent_pct - single_pct
        cost_increase = agent_report.get("cost_usd", 0) - single_cost

        print(
            f"single={single_pct:.0f}% agent={agent_pct:.0f}% "
            f"(+{improvement:+.1f}%, retries={agent_report['retries_used']}, "
            f"qa_issues={len(agent_report.get('qa_issues', []))})"
        )

        # Record
        single_scores.append(single_pct)
        agent_scores.append(agent_pct)
        single_costs.append(single_cost)
        agent_costs.append(agent_report.get("cost_usd", 0))
        single_latencies.append(single_latency)
        agent_latencies.append(agent_report.get("latency_s", 0))
        retries_used.append(agent_report["retries_used"])
        qa_issues_count.append(len(agent_report.get("qa_issues", [])))

        results["samples"].append({
            "screenshot_id": sid,
            "screen_type": annotation.get("screen_type"),
            "single_shot": {
                "score_pct": round(single_pct, 2),
                "cost_usd": single_cost,
                "latency_s": single_latency,
            },
            "agent": {
                "score_pct": round(agent_pct, 2),
                "cost_usd": agent_report.get("cost_usd", 0),
                "latency_s": agent_report.get("latency_s", 0),
                "retries_used": agent_report["retries_used"],
                "qa_issues": len(agent_report.get("qa_issues", [])),
            },
            "improvement_pct": round(improvement, 2),
            "cost_increase_usd": round(cost_increase, 6),
        })

    # ── Aggregate ─────────────────────────────────────────────
    n = len(single_scores)
    if n > 0:
        results["aggregate"] = {
            "samples_evaluated": n,
            "single_shot": {
                "avg_score_pct": round(sum(single_scores) / n, 2),
                "total_cost_usd": round(sum(single_costs), 6),
                "avg_cost_usd": round(sum(single_costs) / n, 6),
                "avg_latency_s": round(sum(single_latencies) / n, 2),
            },
            "agent": {
                "avg_score_pct": round(sum(agent_scores) / n, 2),
                "total_cost_usd": round(sum(agent_costs), 6),
                "avg_cost_usd": round(sum(agent_costs) / n, 6),
                "avg_latency_s": round(sum(agent_latencies) / n, 2),
                "avg_retries": round(sum(retries_used) / n, 2),
                "avg_qa_issues": round(sum(qa_issues_count) / n, 2),
            },
            "comparison": {
                "avg_improvement_pct": round(
                    sum(a - s for a, s in zip(agent_scores, single_scores)) / n, 2
                ),
                "cost_multiplier": round(
                    sum(agent_costs) / max(sum(single_costs), 0.000001), 2
                ),
                "samples_improved": sum(
                    1 for a, s in zip(agent_scores, single_scores) if a > s
                ),
                "samples_same": sum(
                    1 for a, s in zip(agent_scores, single_scores) if a == s
                ),
                "samples_degraded": sum(
                    1 for a, s in zip(agent_scores, single_scores) if a < s
                ),
            },
        }

    return results


def print_evaluation(results: dict) -> None:
    """Print a formatted evaluation comparison."""
    agg = results.get("aggregate", {})
    if not agg:
        print("No evaluation data available.")
        return

    n = agg["samples_evaluated"]
    ss = agg["single_shot"]
    ag = agg["agent"]
    comp = agg["comparison"]

    print(f"\n{'='*60}")
    print(f"  AGENT vs SINGLE-SHOT EVALUATION")
    print(f"  {n} samples, model: {results['meta']['model']}")
    print(f"{'='*60}\n")

    print(f"  {'Metric':<25} {'Single-Shot':>12} {'Agent':>12} {'Delta':>10}")
    print(f"  {'-'*60}")
    print(f"  {'Avg Score':<25} {ss['avg_score_pct']:>11.1f}% {ag['avg_score_pct']:>11.1f}% {comp['avg_improvement_pct']:>+9.1f}%")
    print(f"  {'Avg Cost/img':<25} ${ss['avg_cost_usd']:>10.5f} ${ag['avg_cost_usd']:>10.5f} {comp['cost_multiplier']:>9.1f}x")
    print(f"  {'Avg Latency':<25} {ss['avg_latency_s']:>11.1f}s {ag['avg_latency_s']:>11.1f}s")
    print(f"  {'Total Cost':<25} ${ss['total_cost_usd']:>10.5f} ${ag['total_cost_usd']:>10.5f}")
    print(f"  {'Avg Retries':<25} {'—':>12} {ag['avg_retries']:>12.1f}")
    print(f"  {'Avg QA Issues':<25} {'—':>12} {ag['avg_qa_issues']:>12.1f}")
    print()
    print(f"  Samples improved:  {comp['samples_improved']}/{n}")
    print(f"  Samples same:      {comp['samples_same']}/{n}")
    print(f"  Samples degraded:  {comp['samples_degraded']}/{n}")
    print()

    verdict = (
        f"Agent costs {comp['cost_multiplier']:.1f}x more but "
        f"{'improves' if comp['avg_improvement_pct'] > 0 else 'does not improve'} "
        f"accuracy by {abs(comp['avg_improvement_pct']):.1f}% on average."
    )
    print(f"  VERDICT: {verdict}")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate QA agent vs single-shot extraction"
    )
    parser.add_argument(
        "--annotations-dir", default="data/annotations/full",
        help="Path to annotations directory (v3)",
    )
    parser.add_argument(
        "--images-dir", default="images",
        help="Directory containing screenshot images",
    )
    parser.add_argument(
        "--model", default="gemini-2.5-flash",
        choices=list(MODELS.keys()),
        help="VLM model to evaluate",
    )
    parser.add_argument(
        "--max-samples", type=int,
        help="Limit number of samples",
    )
    parser.add_argument(
        "--max-retries", type=int, default=2,
        help="Maximum retries for agent",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save evaluation JSON to this path",
    )
    args = parser.parse_args()

    results = evaluate_agent(
        args.annotations_dir,
        args.images_dir,
        args.model,
        args.max_samples,
        args.max_retries,
    )

    print_evaluation(results)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str, ensure_ascii=False)
        print(f"  Evaluation saved to: {output_path}")


if __name__ == "__main__":
    main()
