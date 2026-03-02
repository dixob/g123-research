"""
Batch QA Runner — runs the Game QA Agent across a full screenshot directory.

Generates:
  - Per-screenshot QA report
  - Aggregate QA summary: screenshots analyzed, potential bugs found, validation errors
  - Cost report: total API spend, cost per screenshot, projected daily cost

Usage:
  python -m agents.batch_qa --dir images/ --max 5
  python -m agents.batch_qa --dir images/ --model gpt-4o --output qa_reports/
  python -m agents.batch_qa --dir images/ --pattern "highschooldxd_battle*"
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from benchmark.config import MODELS
from .game_qa_agent import run_qa_agent


def run_batch_qa(
    images_dir: str,
    model_name: str = "gemini-2.5-flash",
    max_images: int | None = None,
    pattern: str = "*.png",
    max_retries: int = 2,
) -> dict:
    """
    Run QA agent on all matching screenshots in a directory.

    Args:
        images_dir: Directory containing screenshot images
        model_name: VLM model to use
        max_images: Maximum number of images to process
        pattern: Glob pattern for image files
        max_retries: Maximum validation retry attempts

    Returns:
        Batch results dict with per-image reports and aggregate summary
    """
    images_path = Path(images_dir)
    image_files = sorted(images_path.glob(pattern))

    # Also check for jpg
    if not image_files:
        image_files = sorted(images_path.glob(pattern.replace(".png", ".*")))

    if max_images:
        image_files = image_files[:max_images]

    total = len(image_files)
    print(f"Running QA agent on {total} images with {model_name}...")

    batch_results = {
        "meta": {
            "model": model_name,
            "images_dir": str(images_dir),
            "pattern": pattern,
            "total_images": total,
            "max_retries": max_retries,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "reports": [],
        "aggregate": {},
    }

    # Accumulators
    total_cost = 0.0
    total_latency = 0.0
    total_retries = 0
    total_qa_issues = 0
    total_validation_errors = 0
    screen_type_counts: dict[str, int] = {}
    qa_severity_counts: dict[str, int] = {}
    qa_rule_counts: dict[str, int] = {}
    errors = 0

    for i, image_file in enumerate(image_files):
        print(f"\n  [{i+1}/{total}] {image_file.name}...", end=" ", flush=True)

        try:
            report, trace = run_qa_agent(str(image_file), model_name, max_retries)
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
            batch_results["reports"].append({
                "image": image_file.name,
                "error": str(e),
            })
            continue

        total_cost += report.get("cost_usd", 0)
        total_latency += report.get("latency_s", 0)
        total_retries += report.get("retries_used", 0)

        # Track screen types
        st = report.get("screen_type", "unknown")
        screen_type_counts[st] = screen_type_counts.get(st, 0) + 1

        # Track QA issues
        qa_issues = report.get("qa_issues", [])
        total_qa_issues += len(qa_issues)
        for issue in qa_issues:
            sev = issue.get("severity", "unknown")
            qa_severity_counts[sev] = qa_severity_counts.get(sev, 0) + 1
            rule = issue.get("rule", "unknown")
            qa_rule_counts[rule] = qa_rule_counts.get(rule, 0) + 1

        # Track validation errors
        val_errors = report.get("validation_errors", [])
        total_validation_errors += len(val_errors)

        status_parts = [f"type={st}"]
        if report.get("cost_usd"):
            status_parts.append(f"${report['cost_usd']:.4f}")
        if qa_issues:
            status_parts.append(f"{len(qa_issues)} issues")
        print(", ".join(status_parts))

        batch_results["reports"].append({
            "image": image_file.name,
            "screen_type": st,
            "extraction": report.get("extraction"),
            "qa_issues": qa_issues,
            "validation_errors": val_errors,
            "retries_used": report.get("retries_used", 0),
            "cost_usd": report.get("cost_usd", 0),
            "latency_s": report.get("latency_s", 0),
        })

    # ── Aggregate ─────────────────────────────────────────────
    processed = total - errors
    batch_results["aggregate"] = {
        "images_processed": processed,
        "images_errored": errors,
        "screen_type_distribution": screen_type_counts,
        # QA findings
        "total_qa_issues": total_qa_issues,
        "qa_severity_distribution": qa_severity_counts,
        "qa_rule_distribution": qa_rule_counts,
        "total_validation_errors": total_validation_errors,
        "total_retries": total_retries,
        # Cost
        "total_cost_usd": round(total_cost, 6),
        "avg_cost_per_image_usd": round(total_cost / max(processed, 1), 6),
        "total_latency_s": round(total_latency, 2),
        "avg_latency_per_image_s": round(total_latency / max(processed, 1), 2),
        # Projections
        "projected_cost_100_images_usd": round(total_cost / max(processed, 1) * 100, 4),
        "projected_cost_1000_images_usd": round(total_cost / max(processed, 1) * 1000, 4),
    }

    return batch_results


def print_batch_summary(results: dict) -> None:
    """Print a formatted batch QA summary."""
    agg = results.get("aggregate", {})
    meta = results.get("meta", {})

    print(f"\n{'='*60}")
    print(f"  BATCH QA SUMMARY")
    print(f"{'='*60}\n")

    print(f"  Model:       {meta.get('model')}")
    print(f"  Processed:   {agg.get('images_processed', 0)} / {meta.get('total_images', 0)}")
    print(f"  Errors:      {agg.get('images_errored', 0)}")
    print()

    # Screen type distribution
    st_dist = agg.get("screen_type_distribution", {})
    if st_dist:
        print(f"  Screen Types:")
        for st, count in sorted(st_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"    {st:<15} {count}")
        print()

    # QA Issues
    print(f"  QA Issues Found: {agg.get('total_qa_issues', 0)}")
    sev_dist = agg.get("qa_severity_distribution", {})
    if sev_dist:
        for sev, count in sorted(sev_dist.items()):
            print(f"    {sev:<12} {count}")

    rule_dist = agg.get("qa_rule_distribution", {})
    if rule_dist:
        print(f"\n  QA Rules Triggered:")
        for rule, count in sorted(rule_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"    {rule:<30} {count}")

    # Cost
    print(f"\n  Cost Analysis:")
    print(f"    Total cost:        ${agg.get('total_cost_usd', 0):.5f}")
    print(f"    Avg per image:     ${agg.get('avg_cost_per_image_usd', 0):.5f}")
    print(f"    Projected @ 100:   ${agg.get('projected_cost_100_images_usd', 0):.4f}")
    print(f"    Projected @ 1000:  ${agg.get('projected_cost_1000_images_usd', 0):.4f}")

    print(f"\n  Latency:")
    print(f"    Total:             {agg.get('total_latency_s', 0):.1f}s")
    print(f"    Avg per image:     {agg.get('avg_latency_per_image_s', 0):.1f}s")
    print(f"    Total retries:     {agg.get('total_retries', 0)}")
    print(f"    Validation errors: {agg.get('total_validation_errors', 0)}")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run QA agent on a batch of screenshots"
    )
    parser.add_argument(
        "--dir", required=True,
        help="Directory containing screenshot images",
    )
    parser.add_argument(
        "--model", default="gemini-2.5-flash",
        choices=list(MODELS.keys()),
        help="VLM model to use",
    )
    parser.add_argument(
        "--max", type=int,
        help="Maximum number of images to process",
    )
    parser.add_argument(
        "--pattern", default="*.png",
        help="Glob pattern for image files (default: *.png)",
    )
    parser.add_argument(
        "--max-retries", type=int, default=2,
        help="Maximum retries per image",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save batch results JSON to this path",
    )
    args = parser.parse_args()

    if not Path(args.dir).exists():
        print(f"Error: {args.dir} not found", file=sys.stderr)
        sys.exit(1)

    results = run_batch_qa(
        args.dir,
        args.model,
        args.max,
        args.pattern,
        args.max_retries,
    )

    print_batch_summary(results)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str, ensure_ascii=False)
        print(f"  Batch results saved to: {output_path}")


if __name__ == "__main__":
    main()
