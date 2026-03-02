"""
Benchmark runner — orchestrates model calls, scoring, and result collection.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import MODELS, FIELD_SPEC, EXTRACT_PROMPT
from .providers import call_model
from .scoring import score_prediction


def load_annotations(annotations_path: str) -> list[dict]:
    """Load the ground-truth annotations JSON."""
    with open(annotations_path) as f:
        data = json.load(f)
    return data["annotations"]


def find_image(screenshot_id: str, images_dir: str) -> str | None:
    """
    Resolve a screenshot_id like 'highschooldxd_battle_001_EN' to a file path.
    Tries common extensions and case variations.
    """
    images = Path(images_dir)
    for ext in (".png", ".jpg", ".jpeg"):
        # Try exact case
        candidate = images / f"{screenshot_id}{ext}"
        if candidate.exists():
            return str(candidate)
        # Try lowercase
        candidate = images / f"{screenshot_id.lower()}{ext}"
        if candidate.exists():
            return str(candidate)
        # Try the format with lowercase language suffix
        candidate = images / f"{screenshot_id.lower().replace('_en', '_EN').replace('_jp', '_JP')}{ext}"
        if candidate.exists():
            return str(candidate)
    return None


def run_benchmark(
    annotations_path: str,
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
        annotations_path: Path to the annotations JSON file.
        images_dir: Directory containing screenshot images.
        models: List of model names to benchmark (defaults to all in config).
        max_samples: Limit the number of samples (for quick testing).
        screen_types: Filter to specific screen types (e.g. ["battle", "menu"]).
        languages: Filter to specific languages (e.g. ["EN"]).
        prompt: Override the default extraction prompt.

    Returns:
        Full results dict with per-model, per-sample breakdowns.
    """
    model_names = models or list(MODELS.keys())
    extract_prompt = prompt or EXTRACT_PROMPT
    annotations = load_annotations(annotations_path)

    # Apply filters
    if screen_types:
        st_lower = [s.lower() for s in screen_types]
        annotations = [a for a in annotations if a.get("screen_type", "").lower() in st_lower]
    if languages:
        lang_upper = [l.upper() for l in languages]
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
        total_latency = 0.0
        parse_failures = 0
        api_errors = 0

        for i, annotation in enumerate(annotations):
            sid = annotation["screenshot_id"]
            image_path = find_image(sid, images_dir)

            if not image_path:
                print(f"  [{i+1}/{total}] SKIP {sid} — image not found")
                continue

            print(f"  [{i+1}/{total}] {sid}...", end=" ", flush=True)

            response = call_model(model_name, image_path, extract_prompt, MODELS)

            if response["error"]:
                print(f"ERROR: {response['error'][:80]}")
                api_errors += 1
                model_results["samples"].append({
                    "screenshot_id": sid,
                    "error": response["error"],
                    "latency_s": response["latency_s"],
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
                })
                continue

            scores = score_prediction(response["parsed"], annotation, FIELD_SPEC)
            pct = (scores["weighted_score"] / scores["max_possible"] * 100) if scores["max_possible"] > 0 else 0

            print(f"{pct:.0f}% ({response['latency_s']:.1f}s)")

            total_weighted += scores["weighted_score"]
            total_max += scores["max_possible"]
            total_latency += response["latency_s"]

            model_results["samples"].append({
                "screenshot_id": sid,
                "screen_type": annotation.get("screen_type"),
                "language": annotation.get("language"),
                "scores": scores,
                "latency_s": response["latency_s"],
            })

        # Compute summary
        scored_count = total - parse_failures - api_errors
        model_results["summary"] = {
            "overall_score": (total_weighted / total_max * 100) if total_max > 0 else 0,
            "samples_scored": scored_count,
            "parse_failures": parse_failures,
            "api_errors": api_errors,
            "avg_latency_s": (total_latency / scored_count) if scored_count > 0 else 0,
            "total_latency_s": total_latency,
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
