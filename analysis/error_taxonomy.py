"""
Error Taxonomy — classify every VLM prediction error into a failure category.

Loads benchmark results JSON and produces a structured error analysis:
  - Per-model error distribution
  - Per-field error type breakdown
  - Worst-offender fields per error class
  - Actionable improvement recommendations

Error Categories:
  numeric_ocr       — Wrong number (digit transposition, misread, off-by-one)
  text_hallucination — Model produces text not present in ground truth
  jp_text_error     — Japanese-specific failures (kanji misread, encoding issues)
  screen_type_confusion — Wrong screen type classification
  spatial_error     — UI element listed but wrong zone / location
  false_null        — Model returns null for a field that has ground truth data
  false_positive    — Model returns non-null for a field with null ground truth
  partial_match     — Fuzzy/set scored >0 but <1 (partially correct)
  parse_failure     — Model output wasn't valid JSON (tracked at sample level)
  correct           — Field was scored 1.0 (not an error)

Usage:
  python -m analysis.error_taxonomy benchmark_results/benchmark_2026-03-01T12-00-00.json
  python -m analysis.error_taxonomy benchmark_results/benchmark_2026-03-01T12-00-00.json --output analysis/errors.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ── Error category definitions ────────────────────────────────

ERROR_CATEGORIES = {
    "correct":               "Field scored perfectly (1.0)",
    "false_null":            "Model returned null but ground truth has data",
    "false_positive":        "Model returned data but ground truth is null",
    "numeric_ocr":           "Wrong number (digit transposition, misread)",
    "screen_type_confusion": "Wrong screen type classification",
    "text_hallucination":    "Model produced text absent from ground truth",
    "jp_text_error":         "Japanese text failure (kanji/encoding)",
    "spatial_error":         "UI element in wrong zone or location",
    "partial_match":         "Partially correct (0 < score < 1)",
    "total_miss":            "Completely wrong value (score = 0)",
    "parse_failure":         "Sample-level JSON parse failure",
}


def _contains_japanese(text: str) -> bool:
    """Check if a string contains Japanese characters (hiragana, katakana, CJK)."""
    if not text:
        return False
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', str(text)))


def _is_numeric_like(val: Any) -> bool:
    """Check if a value is or can be interpreted as numeric."""
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return True
    try:
        float(str(val))
        return True
    except (ValueError, TypeError):
        return False


def _digits_of(val: Any) -> str | None:
    """Extract just the digits from a numeric-like value."""
    if val is None:
        return None
    s = str(val).replace(".", "").replace("-", "").replace(",", "")
    digits = re.sub(r'[^\d]', '', s)
    return digits if digits else None


def classify_field_error(
    field_name: str,
    predicted: Any,
    ground_truth: Any,
    score: float,
    scoring_type: str,
) -> str:
    """
    Classify a single field error into a taxonomy category.

    Args:
        field_name: The field name (e.g., 'player_hp_current')
        predicted: What the model returned
        ground_truth: The correct annotation value
        score: The computed score (0.0 to 1.0)
        scoring_type: The scoring method ('exact', 'numeric', 'boolean', 'fuzzy', 'set')

    Returns:
        Error category string
    """
    # Perfect score → not an error
    if score >= 1.0:
        return "correct"

    # Null handling
    pred_is_null = predicted is None or (isinstance(predicted, str) and predicted.strip().lower() in ("null", "none", ""))
    gt_is_null = ground_truth is None

    if pred_is_null and not gt_is_null:
        return "false_null"
    if not pred_is_null and gt_is_null:
        return "false_positive"

    # Screen type confusion
    if field_name == "screen_type":
        return "screen_type_confusion"

    # Numeric fields — check for OCR-like errors
    if scoring_type == "numeric" and score == 0.0:
        # Both are numeric but different
        if _is_numeric_like(predicted) and _is_numeric_like(ground_truth):
            pred_digits = _digits_of(predicted)
            gt_digits = _digits_of(ground_truth)
            if pred_digits and gt_digits:
                # Digit transposition: same digits, different order
                if sorted(pred_digits) == sorted(gt_digits) and pred_digits != gt_digits:
                    return "numeric_ocr"
                # Off-by-small-amount (likely OCR misread of a single digit)
                try:
                    diff = abs(float(predicted) - float(ground_truth))
                    gt_val = abs(float(ground_truth))
                    if gt_val > 0 and diff / gt_val < 0.2:
                        return "numeric_ocr"
                except (ValueError, TypeError):
                    pass
            return "numeric_ocr"
        return "total_miss"

    # Japanese text errors — detect via field name (text_jp) or content analysis
    if scoring_type in ("fuzzy", "exact"):
        is_jp_field = field_name in ("text_jp",)
        gt_has_jp = _contains_japanese(str(ground_truth))
        pred_has_jp = _contains_japanese(str(predicted))
        if is_jp_field or gt_has_jp or pred_has_jp:
            if score < 1.0:
                return "jp_text_error"

    # UI set scoring — check for spatial/location-based errors
    if scoring_type in ("set", "ui_set") and field_name == "ui_elements":
        if 0 < score < 1.0:
            return "spatial_error"
        return "spatial_error" if score == 0.0 else "partial_match"

    # Fuzzy/set partial matches
    if scoring_type in ("fuzzy", "set") and 0 < score < 1.0:
        return "partial_match"

    # Text hallucination: model produced text content that doesn't match
    if scoring_type == "fuzzy" and score == 0.0:
        if predicted and ground_truth:
            return "text_hallucination"

    # Catch-all for complete misses
    if score == 0.0:
        return "total_miss"

    return "partial_match"


def analyze_results(results: dict) -> dict:
    """
    Analyze benchmark results and classify all errors.

    Args:
        results: Full benchmark results dict (from runner.py)

    Returns:
        Analysis dict with per-model error distributions and per-field breakdowns.
    """
    analysis = {
        "meta": {
            "total_samples": results["meta"]["total_samples"],
            "models": results["meta"]["models"],
        },
        "models": {},
        "cross_model": {},
    }

    for model_name, model_data in results["models"].items():
        model_errors = {
            "error_distribution": Counter(),
            "per_field": defaultdict(lambda: Counter()),
            "error_examples": defaultdict(list),  # category → list of example errors
            "parse_failures": model_data["summary"]["parse_failures"],
            "api_errors": model_data["summary"]["api_errors"],
            "total_fields_evaluated": 0,
            "total_errors": 0,
        }

        # Count parse failures as their own category
        model_errors["error_distribution"]["parse_failure"] = model_data["summary"]["parse_failures"]

        for sample in model_data["samples"]:
            # Skip samples without scores (errors, parse failures)
            if "scores" not in sample:
                continue

            sid = sample["screenshot_id"]

            for field_name, field_data in sample["scores"]["fields"].items():
                score = field_data["score"]
                predicted = field_data.get("predicted")
                ground_truth = field_data.get("ground_truth")
                scoring_type = field_data.get("scoring", "exact")

                # Skip fields where both are null (nothing to evaluate)
                if predicted is None and ground_truth is None:
                    continue

                model_errors["total_fields_evaluated"] += 1

                category = classify_field_error(
                    field_name, predicted, ground_truth, score, scoring_type
                )

                model_errors["error_distribution"][category] += 1
                model_errors["per_field"][field_name][category] += 1

                if category != "correct":
                    model_errors["total_errors"] += 1

                    # Store examples (limit to 3 per category)
                    if len(model_errors["error_examples"][category]) < 3:
                        model_errors["error_examples"][category].append({
                            "screenshot_id": sid,
                            "field": field_name,
                            "predicted": predicted,
                            "ground_truth": ground_truth,
                            "score": score,
                        })

        # Convert defaultdicts to regular dicts for JSON serialization
        model_errors["per_field"] = {
            field: dict(counts) for field, counts in model_errors["per_field"].items()
        }
        model_errors["error_examples"] = dict(model_errors["error_examples"])
        model_errors["error_distribution"] = dict(model_errors["error_distribution"])

        # Compute error rate
        total_eval = model_errors["total_fields_evaluated"]
        model_errors["error_rate"] = (
            model_errors["total_errors"] / total_eval * 100
        ) if total_eval > 0 else 0

        analysis["models"][model_name] = model_errors

    # ── Cross-model analysis ──────────────────────────────────
    # Find fields that ALL models struggle with
    problem_fields = Counter()
    for model_name, model_errors in analysis["models"].items():
        for field, counts in model_errors["per_field"].items():
            error_count = sum(v for k, v in counts.items() if k != "correct")
            if error_count > 0:
                problem_fields[field] += error_count

    analysis["cross_model"]["hardest_fields"] = dict(
        problem_fields.most_common(10)
    )

    # Find error categories that dominate across models
    all_error_cats = Counter()
    for model_name, model_errors in analysis["models"].items():
        for cat, count in model_errors["error_distribution"].items():
            if cat != "correct":
                all_error_cats[cat] += count

    analysis["cross_model"]["most_common_errors"] = dict(
        all_error_cats.most_common()
    )

    return analysis


def generate_recommendations(analysis: dict) -> list[str]:
    """Generate actionable recommendations based on error analysis."""
    recs = []

    for model_name, model_errors in analysis["models"].items():
        dist = model_errors["error_distribution"]
        total = model_errors["total_fields_evaluated"]
        if total == 0:
            continue

        # Check dominant error types
        if dist.get("false_null", 0) / max(total, 1) > 0.15:
            recs.append(
                f"[{model_name}] High false-null rate ({dist['false_null']}/{total}). "
                f"Model often misses visible data. Consider: more explicit prompts, "
                f"higher resolution images, or per-field extraction."
            )
        if dist.get("numeric_ocr", 0) > 3:
            recs.append(
                f"[{model_name}] Numeric OCR errors ({dist['numeric_ocr']}). "
                f"Model misreads numbers. Consider: cropped number regions, "
                f"OCR-specialized preprocessing, or two-pass verification."
            )
        if dist.get("jp_text_error", 0) > 3:
            recs.append(
                f"[{model_name}] Japanese text errors ({dist['jp_text_error']}). "
                f"Model struggles with JP text. Consider: JP-specialized prompts, "
                f"kanji-aware tokenization, or JP-focused fine-tuning."
            )
        if dist.get("screen_type_confusion", 0) > 0:
            recs.append(
                f"[{model_name}] Screen type confusion ({dist['screen_type_confusion']}). "
                f"Consider: CLIP pre-classifier for screen type, then specialized "
                f"extraction prompts per screen type."
            )
        if dist.get("parse_failure", 0) > 2:
            recs.append(
                f"[{model_name}] Parse failures ({dist['parse_failure']}). "
                f"Model outputs invalid JSON. Consider: structured output mode, "
                f"retry with error feedback, or JSON schema constraints."
            )

    # Cross-model recommendations
    cross = analysis.get("cross_model", {})
    hardest = cross.get("hardest_fields", {})
    if hardest:
        top_field = list(hardest.keys())[0]
        recs.append(
            f"[ALL MODELS] Hardest field: '{top_field}' ({hardest[top_field]} total errors). "
            f"Consider: field-specific prompts, annotation review for ambiguity, "
            f"or relaxing scoring threshold."
        )

    return recs


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Classify VLM benchmark errors into taxonomy categories"
    )
    parser.add_argument(
        "results_file",
        help="Path to benchmark results JSON file",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save analysis JSON to this path (default: print summary only)",
    )
    parser.add_argument(
        "--examples", action="store_true",
        help="Show example errors for each category",
    )
    args = parser.parse_args()

    # Load results
    results_path = Path(args.results_file)
    if not results_path.exists():
        print(f"Error: {results_path} not found")
        sys.exit(1)

    with open(results_path, encoding="utf-8") as f:
        results = json.load(f)

    # Run analysis
    analysis = analyze_results(results)
    recs = generate_recommendations(analysis)

    # ── Print summary ─────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  ERROR TAXONOMY ANALYSIS")
    print(f"  {analysis['meta']['total_samples']} samples")
    print(f"{'='*70}\n")

    for model_name, model_errors in analysis["models"].items():
        dist = model_errors["error_distribution"]
        total_eval = model_errors["total_fields_evaluated"]
        total_err = model_errors["total_errors"]
        err_rate = model_errors["error_rate"]

        print(f"  {model_name}")
        print(f"  {'-'*50}")
        print(f"  Fields evaluated: {total_eval}  |  Errors: {total_err}  |  Error rate: {err_rate:.1f}%")
        print()

        # Sort by count descending, skip 'correct'
        sorted_cats = sorted(
            ((k, v) for k, v in dist.items() if k != "correct"),
            key=lambda x: x[1],
            reverse=True,
        )

        if sorted_cats:
            max_label = max(len(c) for c, _ in sorted_cats)
            for cat, count in sorted_cats:
                pct = count / max(total_eval, 1) * 100
                bar = "█" * int(pct / 2)
                desc = ERROR_CATEGORIES.get(cat, "")
                print(f"    {cat:<{max_label}}  {count:>4}  ({pct:>5.1f}%)  {bar}  {desc}")
        print()

        # Per-field breakdown (top 5 error fields)
        field_errors = {}
        for field, counts in model_errors["per_field"].items():
            err_count = sum(v for k, v in counts.items() if k != "correct")
            if err_count > 0:
                field_errors[field] = err_count

        if field_errors:
            print(f"    Top error fields:")
            for field, count in sorted(field_errors.items(), key=lambda x: x[1], reverse=True)[:5]:
                cats = model_errors["per_field"][field]
                cat_str = ", ".join(f"{k}={v}" for k, v in sorted(cats.items(), key=lambda x: x[1], reverse=True) if k != "correct")
                print(f"      {field:<22} {count} errors  ({cat_str})")
            print()

        # Show examples if requested
        if args.examples and model_errors["error_examples"]:
            print(f"    Example errors:")
            for cat, examples in model_errors["error_examples"].items():
                print(f"      [{cat}]")
                for ex in examples[:2]:
                    print(f"        {ex['screenshot_id']}.{ex['field']}: "
                          f"pred={ex['predicted']!r}  gt={ex['ground_truth']!r}  score={ex['score']}")
            print()

    # ── Cross-model insights ──────────────────────────────────
    cross = analysis["cross_model"]
    if cross.get("hardest_fields"):
        print(f"  CROSS-MODEL ANALYSIS")
        print(f"  {'-'*50}")
        print(f"  Hardest fields (total errors across all models):")
        for field, count in list(cross["hardest_fields"].items())[:5]:
            print(f"    {field:<22} {count} total errors")
        print()

    if cross.get("most_common_errors"):
        print(f"  Most common error types (all models combined):")
        for cat, count in cross["most_common_errors"].items():
            desc = ERROR_CATEGORIES.get(cat, "")
            print(f"    {cat:<25} {count:>4}  {desc}")
        print()

    # ── Recommendations ───────────────────────────────────────
    if recs:
        print(f"  RECOMMENDATIONS")
        print(f"  {'-'*50}")
        for i, rec in enumerate(recs, 1):
            print(f"  {i}. {rec}")
        print()

    # ── Save to file if requested ─────────────────────────────
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output = {
            **analysis,
            "recommendations": recs,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str, ensure_ascii=False)
        print(f"  Analysis saved to: {output_path}")


if __name__ == "__main__":
    main()
