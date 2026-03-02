"""
Benchmark runner — orchestrates model calls, scoring, and result collection.
Supports v3 per-file annotations and legacy monolithic JSON.

Tracks per-call: latency, input/output tokens, USD cost.
Aggregates: latency percentiles (p50/p90/p99), total cost, cost per screenshot.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from .config import MODELS, FIELD_SPEC, EXTRACT_PROMPT
from .providers import call_model
from .scoring import score_prediction


def _percentile(values: list[float], p: float) -> float:
    """Compute the p-th percentile (0-100) of a sorted list."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (p / 100) * (len(sorted_vals) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def load_annotations(annotations_source: str) -> list[dict]:
    """
    Load ground-truth annotations.

    Accepts either:
      - A directory of per-file JSONs (v3 hydrated annotations)
      - A single JSON file (legacy monolithic format)
    """
    source = Path(annotations_source)

    if source.is_dir():
        # v3: one JSON per annotation in a directory
        annotations = []
        for f in sorted(source.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            # Skip template/instruction files
            if "_TEMPLATE_VERSION" in data or "_BLANK_TEMPLATE" in data:
                continue
            annotations.append(data)
        return annotations

    # Legacy: monolithic JSON with "annotations" key
    with open(source, encoding="utf-8") as f:
        data = json.load(f)
    if "annotations" in data:
        return data["annotations"]
    # Single annotation file
    return [data]


def find_image(screenshot_id: str, images_dir: str) -> str | None:
    """
    Resolve a screenshot_id to a file path.

    v3 IDs are lowercase (e.g. 'highschooldxd_battle_001_en').
    v1 IDs may be mixed case (e.g. 'highschooldxd_battle_001_EN').
    Tries multiple case variations to find the image.
    """
    images = Path(images_dir)
    sid = screenshot_id

    for ext in (".png", ".jpg", ".jpeg"):
        # Exact case
        candidate = images / f"{sid}{ext}"
        if candidate.exists():
            return str(candidate)

        # Uppercase language suffix (v3 lowercase id → v1 uppercase file)
        upper = sid.replace("_en", "_EN").replace("_jp", "_JP").replace("_mixed", "_MIXED")
        candidate = images / f"{upper}{ext}"
        if candidate.exists():
            return str(candidate)

        # Lowercase everything
        candidate = images / f"{sid.lower()}{ext}"
        if candidate.exists():
            return str(candidate)

        # Uppercase everything
        candidate = images / f"{sid.upper()}{ext}"
        if candidate.exists():
            return str(candidate)

    return None


def run_benchmark(
    annotations_source: str,
    images_dir: str,
    models: list[str] | None = None,
    max_samples: int | None = None,
    screen_types: list[str] | None = None,
    languages: list[str] | None = None,
    prompt: str | None = None,
) -> dict:
    """
    Run the full benchmark.

    Args:
        annotations_source: Path to annotations directory (v3) or JSON file (legacy).
        images_dir: Directory containing screenshot images.
        models: List of model names to benchmark (defaults to all in config).
        max_samples: Limit the number of samples (for quick testing).
        screen_types: Filter to specific screen types (e.g. ["battle", "gacha"]).
        languages: Filter to specific languages (e.g. ["EN"]).
        prompt: Override the default extraction prompt.

    Returns:
        Full results dict with per-model, per-sample breakdowns.
    """
    model_names = models or list(MODELS.keys())
    extract_prompt = prompt or EXTRACT_PROMPT
    annotations = load_annotations(annotations_source)

    # Apply filters
    if screen_types:
        st_lower = [s.lower() for s in screen_types]
        annotations = [a for a in annotations if a.get("screen_type", "").lower() in st_lower]
    if languages:
        lang_upper = [lang.upper() for lang in languages]
        annotations = [a for a in annotations if a.get("language", "").upper() in lang_upper]
    if max_samples:
        annotations = annotations[:max_samples]

    total = len(annotations)
    print(f"Benchmarking {len(model_names)} models on {total} samples")

    results = {
        "meta": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_samples": total,
            "models": model_names,
            "filters": {
                "screen_types": screen_types,
                "languages": languages,
                "max_samples": max_samples,
            },
        },
        "models": {},
    }

    for model_name in model_names:
        print(f"\n{'='*60}")
        print(f"  Model: {model_name}")
        print(f"{'='*60}")

        model_results = {
            "samples": [],
            "summary": {},
        }

        total_weighted = 0.0
        total_max = 0.0
        parse_failures = 0
        api_errors = 0
        skipped = 0

        # Track per-call metrics for aggregation
        latencies: list[float] = []
        costs: list[float] = []
        total_input_tokens = 0
        total_output_tokens = 0

        # Track extraction recall (excludes null-null agreements)
        extraction_recalls: list[float] = []
        null_rates: list[float] = []

        for i, annotation in enumerate(annotations):
            sid = annotation["screenshot_id"]
            image_path = find_image(sid, images_dir)

            if not image_path:
                print(f"  [{i+1}/{total}] SKIP {sid} — image not found")
                skipped += 1
                continue

            print(f"  [{i+1}/{total}] {sid}...", end=" ", flush=True)

            response = call_model(model_name, image_path, extract_prompt, MODELS)

            # Extract token usage
            in_tok = response.get("input_tokens")
            out_tok = response.get("output_tokens")
            cost = response.get("cost_usd")

            if response["error"]:
                print(f"ERROR: {response['error'][:80]}")
                api_errors += 1
                model_results["samples"].append({
                    "screenshot_id": sid,
                    "error": response["error"],
                    "latency_s": response["latency_s"],
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "cost_usd": cost,
                })
                continue

            if response["parsed"] is None:
                print(f"PARSE FAIL ({response['latency_s']:.1f}s)")
                parse_failures += 1
                model_results["samples"].append({
                    "screenshot_id": sid,
                    "error": "json_parse_failure",
                    "raw": response["raw"][:500] if response["raw"] else None,
                    "latency_s": response["latency_s"],
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "cost_usd": cost,
                })
                # Still track tokens/cost even on parse failures
                if in_tok is not None:
                    total_input_tokens += in_tok
                if out_tok is not None:
                    total_output_tokens += out_tok
                if cost is not None:
                    costs.append(cost)
                latencies.append(response["latency_s"])
                continue

            scores = score_prediction(response["parsed"], annotation, FIELD_SPEC)
            pct = (scores["weighted_score"] / scores["max_possible"] * 100) if scores["max_possible"] > 0 else 0

            cost_str = f"${cost:.4f}" if cost is not None else "n/a"
            tok_str = f"{in_tok or '?'}+{out_tok or '?'} tok"
            er_str = f" ER:{scores['extraction_recall']:.0f}%" if scores["extraction_recall"] is not None else ""
            print(f"{pct:.0f}%{er_str} ({response['latency_s']:.1f}s, {cost_str}, {tok_str})")

            total_weighted += scores["weighted_score"]
            total_max += scores["max_possible"]
            latencies.append(response["latency_s"])

            # Track extraction recall
            if scores["extraction_recall"] is not None:
                extraction_recalls.append(scores["extraction_recall"])
            null_rates.append(scores["null_agreement_rate"])

            if in_tok is not None:
                total_input_tokens += in_tok
            if out_tok is not None:
                total_output_tokens += out_tok
            if cost is not None:
                costs.append(cost)

            model_results["samples"].append({
                "screenshot_id": sid,
                "screen_type": annotation.get("screen_type"),
                "language": annotation.get("language"),
                "scores": scores,
                "latency_s": response["latency_s"],
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_usd": cost,
            })

        # Compute summary
        scored_count = total - parse_failures - api_errors - skipped
        total_cost = sum(costs) if costs else None
        total_calls = len(latencies)

        model_results["summary"] = {
            "overall_score": (total_weighted / total_max * 100) if total_max > 0 else 0,
            "extraction_recall": (
                sum(extraction_recalls) / len(extraction_recalls)
                if extraction_recalls else None
            ),
            "null_agreement_rate": (
                sum(null_rates) / len(null_rates)
                if null_rates else 0.0
            ),
            "samples_scored": scored_count,
            "samples_skipped": skipped,
            "parse_failures": parse_failures,
            "api_errors": api_errors,
            # Latency stats
            "avg_latency_s": (sum(latencies) / total_calls) if total_calls > 0 else 0,
            "total_latency_s": sum(latencies),
            "latency_p50_s": _percentile(latencies, 50),
            "latency_p90_s": _percentile(latencies, 90),
            "latency_p99_s": _percentile(latencies, 99),
            # Token usage
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "avg_input_tokens": (total_input_tokens / total_calls) if total_calls > 0 else 0,
            "avg_output_tokens": (total_output_tokens / total_calls) if total_calls > 0 else 0,
            # Cost
            "total_cost_usd": total_cost,
            "avg_cost_per_screenshot_usd": (total_cost / total_calls) if total_cost and total_calls else None,
        }

        # Per-field averages
        field_scores: dict[str, list[float]] = {}
        for sample in model_results["samples"]:
            if "scores" not in sample:
                continue
            for field, detail in sample["scores"]["fields"].items():
                field_scores.setdefault(field, []).append(detail["score"])

        model_results["summary"]["per_field"] = {
            field: {
                "mean": sum(vals) / len(vals) if vals else 0,
                "count": len(vals),
            }
            for field, vals in field_scores.items()
        }

        results["models"][model_name] = model_results

    return results
