"""
Error Report Generator — produces a markdown report from error taxonomy analysis.

Takes either:
  - A pre-computed analysis JSON (from error_taxonomy.py --output)
  - A raw benchmark results JSON (will run analysis first)

Outputs a publication-ready markdown report with tables, charts (text-based),
and actionable insights.

Usage:
  python -m analysis.error_report benchmark_results/benchmark_2026-03-01T12-00-00.json
  python -m analysis.error_report analysis/errors.json --output analysis/error_report.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime


def _make_bar(value: float, max_width: int = 20) -> str:
    """Create a text-based bar chart segment."""
    filled = int(value / 100 * max_width)
    return "█" * filled + "░" * (max_width - filled)


def generate_report(analysis: dict, include_examples: bool = True) -> str:
    """
    Generate a markdown error analysis report.

    Args:
        analysis: Analysis dict from error_taxonomy.analyze_results()
        include_examples: Whether to include example errors

    Returns:
        Markdown string
    """
    lines = []
    meta = analysis["meta"]

    lines.append("# G123 VLM Benchmark — Error Taxonomy Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Samples:** {meta['total_samples']}")
    lines.append(f"**Models:** {', '.join(meta['models'])}")
    lines.append("")

    # ── Executive Summary ─────────────────────────────────────
    lines.append("## Executive Summary")
    lines.append("")

    for model_name, model_errors in analysis["models"].items():
        err_rate = model_errors["error_rate"]
        total_eval = model_errors["total_fields_evaluated"]
        total_err = model_errors["total_errors"]

        # Find dominant error
        dist = model_errors["error_distribution"]
        non_correct = {k: v for k, v in dist.items() if k not in ("correct",)}
        if non_correct:
            top_error = max(non_correct, key=non_correct.get)
            top_count = non_correct[top_error]
        else:
            top_error = "none"
            top_count = 0

        lines.append(
            f"- **{model_name}**: {err_rate:.1f}% error rate "
            f"({total_err}/{total_eval} fields). "
            f"Dominant failure: `{top_error}` ({top_count} instances)."
        )

    lines.append("")

    # ── Per-Model Error Distribution ──────────────────────────
    lines.append("## Error Distribution by Model")
    lines.append("")

    for model_name, model_errors in analysis["models"].items():
        lines.append(f"### {model_name}")
        lines.append("")

        dist = model_errors["error_distribution"]
        total_eval = model_errors["total_fields_evaluated"]
        total_err = model_errors["total_errors"]
        correct = dist.get("correct", 0)

        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Fields evaluated | {total_eval} |")
        lines.append(f"| Correct | {correct} ({correct/max(total_eval,1)*100:.1f}%) |")
        lines.append(f"| Errors | {total_err} ({model_errors['error_rate']:.1f}%) |")
        lines.append(f"| Parse failures | {model_errors['parse_failures']} |")
        lines.append(f"| API errors | {model_errors['api_errors']} |")
        lines.append("")

        # Error breakdown table
        non_correct = sorted(
            ((k, v) for k, v in dist.items() if k != "correct"),
            key=lambda x: x[1],
            reverse=True,
        )

        if non_correct:
            lines.append("| Error Category | Count | % of Evaluated | Distribution |")
            lines.append("|----------------|------:|---------------:|:-------------|")

            for cat, count in non_correct:
                pct = count / max(total_eval, 1) * 100
                bar = _make_bar(pct)
                lines.append(f"| `{cat}` | {count} | {pct:.1f}% | `{bar}` |")

            lines.append("")

        # Per-field error breakdown
        field_errors = {}
        for field, counts in model_errors["per_field"].items():
            err_count = sum(v for k, v in counts.items() if k != "correct")
            if err_count > 0:
                field_errors[field] = (err_count, counts)

        if field_errors:
            lines.append("**Top Error Fields:**")
            lines.append("")
            lines.append("| Field | Errors | Dominant Error Type |")
            lines.append("|-------|-------:|---------------------|")

            for field, (count, cats) in sorted(
                field_errors.items(), key=lambda x: x[1][0], reverse=True
            )[:8]:
                # Find dominant non-correct category
                dom_cat = max(
                    ((k, v) for k, v in cats.items() if k != "correct"),
                    key=lambda x: x[1],
                    default=("—", 0),
                )
                lines.append(f"| `{field}` | {count} | `{dom_cat[0]}` ({dom_cat[1]}) |")

            lines.append("")

        # Examples
        if include_examples and model_errors.get("error_examples"):
            lines.append("<details>")
            lines.append(f"<summary>Example errors for {model_name}</summary>")
            lines.append("")

            for cat, examples in model_errors["error_examples"].items():
                lines.append(f"**`{cat}`**")
                lines.append("")
                for ex in examples[:2]:
                    pred_str = repr(ex["predicted"])[:60]
                    gt_str = repr(ex["ground_truth"])[:60]
                    lines.append(
                        f"- `{ex['screenshot_id']}` → `{ex['field']}`: "
                        f"predicted `{pred_str}`, expected `{gt_str}` (score: {ex['score']:.2f})"
                    )
                lines.append("")

            lines.append("</details>")
            lines.append("")

    # ── Cross-Model Analysis ──────────────────────────────────
    cross = analysis.get("cross_model", {})

    lines.append("## Cross-Model Analysis")
    lines.append("")

    if cross.get("hardest_fields"):
        lines.append("### Hardest Fields (total errors across all models)")
        lines.append("")
        lines.append("| Field | Total Errors |")
        lines.append("|-------|------------:|")
        for field, count in list(cross["hardest_fields"].items())[:8]:
            lines.append(f"| `{field}` | {count} |")
        lines.append("")

    if cross.get("most_common_errors"):
        lines.append("### Most Common Error Types (all models)")
        lines.append("")
        lines.append("| Error Type | Total Count |")
        lines.append("|------------|------------:|")
        for cat, count in cross["most_common_errors"].items():
            lines.append(f"| `{cat}` | {count} |")
        lines.append("")

    # ── Recommendations ───────────────────────────────────────
    recs = analysis.get("recommendations", [])
    if recs:
        lines.append("## Recommendations")
        lines.append("")
        for i, rec in enumerate(recs, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

    # ── Production Implications ───────────────────────────────
    lines.append("## Production Implications for CTW / G123")
    lines.append("")
    lines.append(
        "The error taxonomy reveals key patterns that inform production deployment strategy:"
    )
    lines.append("")
    lines.append(
        "- **Numeric OCR errors** → Consider two-pass extraction: initial VLM call + "
        "targeted re-extraction of numeric fields with cropped regions."
    )
    lines.append(
        "- **Japanese text failures** → Evaluate JP-specialized models or "
        "add Japanese OCR preprocessing (e.g., manga OCR). Critical for G123's "
        "primarily Japanese game catalog."
    )
    lines.append(
        "- **Screen type confusion** → Implement CLIP pre-classifier as a "
        "lightweight routing layer. Eliminates irrelevant field extraction "
        "and reduces cost per screenshot."
    )
    lines.append(
        "- **False nulls** → Indicates the model fails to 'see' visible data. "
        "Higher resolution images, better prompts, or multi-crop strategies "
        "may help. Critical for game QA: missing data = missed bugs."
    )
    lines.append(
        "- **Parse failures** → Production systems need structured output mode "
        "(OpenAI JSON mode, Gemini JSON schema) and retry logic. "
        "The LangGraph agent pipeline addresses this with validate→retry nodes."
    )
    lines.append("")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate markdown error analysis report"
    )
    parser.add_argument(
        "input_file",
        help="Path to benchmark results JSON or analysis JSON",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save markdown report to this path (default: stdout)",
    )
    parser.add_argument(
        "--no-examples", action="store_true",
        help="Omit example errors from report",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    # Detect if this is raw benchmark results or pre-computed analysis
    if "models" in data and "meta" in data:
        # Could be either — check for error_distribution
        first_model = next(iter(data["models"].values()), {})
        if "error_distribution" in first_model:
            # Pre-computed analysis
            analysis = data
        else:
            # Raw benchmark results — run analysis
            from .error_taxonomy import analyze_results, generate_recommendations
            analysis = analyze_results(data)
            analysis["recommendations"] = generate_recommendations(analysis)
    else:
        print("Error: Unrecognized file format", file=sys.stderr)
        sys.exit(1)

    # Generate report
    report = generate_report(analysis, include_examples=not args.no_examples)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report saved to: {output_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
