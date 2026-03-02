#!/usr/bin/env python3
"""
Run the VLM benchmark.

Usage:
    # Full benchmark — all models, all samples
    python run_benchmark.py

    # Quick smoke test — 3 samples, one model
    python run_benchmark.py --models gpt-4o --max-samples 3

    # Filter by screen type and language
    python run_benchmark.py --screen-types battle gacha --languages EN

    # Specific models only
    python run_benchmark.py --models gpt-4o gemini-2.5-flash

    # Custom output directory
    python run_benchmark.py --output-dir ./my_results
"""
import argparse
import sys

from benchmark.config import MODELS
from benchmark.runner import run_benchmark
from benchmark.report import print_summary, save_results


def main():
    parser = argparse.ArgumentParser(description="G123 Game State Extraction Benchmark")

    parser.add_argument(
        "--annotations",
        default="images/hsdxd_annotations_final.json",
        help="Path to annotations JSON (default: images/hsdxd_annotations_final.json)",
    )
    parser.add_argument(
        "--images-dir",
        default="images",
        help="Directory containing screenshot images (default: images)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(MODELS.keys()),
        default=None,
        help=f"Models to benchmark (default: all). Choices: {list(MODELS.keys())}",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Limit number of samples (useful for quick tests)",
    )
    parser.add_argument(
        "--screen-types",
        nargs="+",
        default=None,
        help="Filter by screen types (e.g. battle menu gacha)",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=None,
        help="Filter by language (EN, JP)",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmark_results",
        help="Directory for result files (default: benchmark_results)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to file (print only)",
    )

    args = parser.parse_args()

    # Validate models
    if args.models:
        for m in args.models:
            if m not in MODELS:
                print(f"Error: unknown model '{m}'. Choose from: {list(MODELS.keys())}")
                sys.exit(1)

    results = run_benchmark(
        annotations_path=args.annotations,
        images_dir=args.images_dir,
        models=args.models,
        max_samples=args.max_samples,
        screen_types=args.screen_types,
        languages=args.languages,
    )

    print_summary(results)

    if not args.no_save:
        save_results(results, args.output_dir)


if __name__ == "__main__":
    main()
