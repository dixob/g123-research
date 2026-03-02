"""
Gacha Economy Tracker — extract and analyze gacha pull data from screenshots.

End-to-end demo: screenshots → VLM extraction → economy analysis report.

Demonstrates a concrete business application for CTW/G123:
  - Track pity progression across multiple pulls
  - Measure currency spend efficiency
  - Analyze rarity distribution vs expected rates
  - Estimate spend-to-SSR rate (key monetization metric)
  - Regulatory compliance: verify published gacha rates (JP gacha laws)

Usage:
  python -m demos.gacha_tracker --images images/highschooldxd_gacha_*.png
  python -m demos.gacha_tracker --images images/ --pattern "*gacha*"
  python -m demos.gacha_tracker --images images/ --model gpt-4o --output gacha_report.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict

from benchmark.config import MODELS, compute_cost
from benchmark.providers import call_model


# ── Gacha-specific extraction prompt ─────────────────────────

GACHA_EXTRACT_PROMPT = """\
This is a GACHA / SUMMONING screen from a G123 anime game.
Extract the gacha state as precisely as possible.
Respond with ONLY a raw JSON object, no markdown, no code fences.

{
  "screen_type": "gacha",
  "gacha_phase": "lobby|animation|reveal_single|reveal_multi",
  "banner_name": null,
  "banner_type": "standard|limited|collab|step_up",
  "pity_current": null,
  "pity_max": null,
  "pull_cost_type": null,
  "pull_cost_amount": null,
  "currency_premium_balance": null,
  "currency_tickets_balance": null,
  "free_pull_available": false,
  "cards": [
    {"name": "card name", "rarity": "SSR|SR|R|N", "is_new": true}
  ],
  "language": "EN|JP|MIXED"
}

If this is a lobby/pre-pull screen, cards should be empty [].
If this is a reveal screen, list ALL visible cards.
Use null for anything not visible."""


@dataclass
class GachaPull:
    """A single gacha pull event (one screenshot)."""
    image: str
    phase: str | None = None
    banner_name: str | None = None
    banner_type: str | None = None
    pity_current: int | None = None
    pity_max: int | None = None
    pull_cost_type: str | None = None
    pull_cost_amount: float | None = None
    currency_balance: float | None = None
    free_pull: bool = False
    cards: list[dict] = field(default_factory=list)
    language: str | None = None
    raw_extraction: dict | None = None
    cost_usd: float = 0.0
    latency_s: float = 0.0


@dataclass
class GachaSession:
    """Aggregated gacha session data across multiple pulls."""
    pulls: list[GachaPull] = field(default_factory=list)
    total_cards: int = 0
    rarity_counts: dict[str, int] = field(default_factory=dict)
    new_card_count: int = 0
    duplicate_count: int = 0
    pity_progression: list[dict] = field(default_factory=list)
    currency_spent: float = 0.0
    total_cost_usd: float = 0.0
    total_latency_s: float = 0.0


def extract_gacha_data(
    image_path: str,
    model_name: str = "gemini-2.5-flash",
) -> GachaPull:
    """Extract gacha data from a single screenshot."""
    response = call_model(model_name, image_path, GACHA_EXTRACT_PROMPT, MODELS)

    pull = GachaPull(
        image=Path(image_path).name,
        cost_usd=response.get("cost_usd") or 0,
        latency_s=response.get("latency_s", 0),
    )

    parsed = response.get("parsed")
    if not parsed or not isinstance(parsed, dict):
        pull.raw_extraction = {"error": response.get("error") or "parse_failure"}
        return pull

    pull.raw_extraction = parsed
    pull.phase = parsed.get("gacha_phase")
    pull.banner_name = parsed.get("banner_name")
    pull.banner_type = parsed.get("banner_type")
    pull.language = parsed.get("language")
    pull.free_pull = parsed.get("free_pull_available", False)

    # Parse pity
    try:
        pull.pity_current = int(parsed["pity_current"]) if parsed.get("pity_current") is not None else None
    except (ValueError, TypeError):
        pass
    try:
        pull.pity_max = int(parsed["pity_max"]) if parsed.get("pity_max") is not None else None
    except (ValueError, TypeError):
        pass

    # Parse cost
    pull.pull_cost_type = parsed.get("pull_cost_type")
    try:
        pull.pull_cost_amount = float(parsed["pull_cost_amount"]) if parsed.get("pull_cost_amount") is not None else None
    except (ValueError, TypeError):
        pass

    # Parse currency balance
    try:
        pull.currency_balance = float(parsed["currency_premium_balance"]) if parsed.get("currency_premium_balance") is not None else None
    except (ValueError, TypeError):
        pass

    # Parse cards
    raw_cards = parsed.get("cards", [])
    if isinstance(raw_cards, list):
        for card in raw_cards:
            if isinstance(card, dict):
                pull.cards.append({
                    "name": card.get("name", "Unknown"),
                    "rarity": card.get("rarity", "?"),
                    "is_new": card.get("is_new", False),
                })

    return pull


def analyze_session(pulls: list[GachaPull]) -> GachaSession:
    """Aggregate pulls into a gacha session analysis."""
    session = GachaSession(pulls=pulls)

    for pull in pulls:
        session.total_cost_usd += pull.cost_usd
        session.total_latency_s += pull.latency_s

        # Track cards
        for card in pull.cards:
            session.total_cards += 1
            rarity = card.get("rarity", "?")
            session.rarity_counts[rarity] = session.rarity_counts.get(rarity, 0) + 1

            if card.get("is_new"):
                session.new_card_count += 1
            else:
                session.duplicate_count += 1

        # Track pity
        if pull.pity_current is not None:
            session.pity_progression.append({
                "image": pull.image,
                "pity": pull.pity_current,
                "pity_max": pull.pity_max,
            })

        # Track spending
        if pull.pull_cost_amount and not pull.free_pull:
            session.currency_spent += pull.pull_cost_amount

    return session


def run_gacha_tracker(
    images: list[str],
    model_name: str = "gemini-2.5-flash",
) -> dict:
    """
    Run the gacha tracker on a list of screenshots.

    Args:
        images: List of image file paths
        model_name: VLM model to use

    Returns:
        Full gacha analysis report dict
    """
    total = len(images)
    print(f"Extracting gacha data from {total} screenshots with {model_name}...")

    pulls = []
    for i, image_path in enumerate(images):
        print(f"  [{i+1}/{total}] {Path(image_path).name}...", end=" ", flush=True)
        pull = extract_gacha_data(image_path, model_name)

        status = f"phase={pull.phase}"
        if pull.cards:
            status += f", {len(pull.cards)} cards"
        if pull.pity_current is not None:
            status += f", pity={pull.pity_current}"
        print(f"${pull.cost_usd:.4f} | {status}")

        pulls.append(pull)

    session = analyze_session(pulls)

    # ── Build report ──────────────────────────────────────────
    report = {
        "meta": {
            "model": model_name,
            "total_screenshots": total,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "session": {
            "total_cards": session.total_cards,
            "rarity_distribution": session.rarity_counts,
            "new_cards": session.new_card_count,
            "duplicates": session.duplicate_count,
            "new_rate": round(session.new_card_count / max(session.total_cards, 1) * 100, 1),
            "pity_progression": session.pity_progression,
            "currency_spent": session.currency_spent,
        },
        "cost": {
            "total_api_cost_usd": round(session.total_cost_usd, 6),
            "avg_cost_per_screenshot_usd": round(session.total_cost_usd / max(total, 1), 6),
            "total_latency_s": round(session.total_latency_s, 2),
        },
        "rarity_analysis": {},
        "pulls": [asdict(p) for p in pulls],
    }

    # Rarity analysis
    total_cards = session.total_cards
    if total_cards > 0:
        for rarity, count in sorted(session.rarity_counts.items()):
            rate = count / total_cards * 100
            report["rarity_analysis"][rarity] = {
                "count": count,
                "rate_pct": round(rate, 2),
            }

        # SSR rate and spend analysis
        ssr_count = session.rarity_counts.get("SSR", 0) + session.rarity_counts.get("SSR+", 0)
        if ssr_count > 0 and session.currency_spent > 0:
            report["rarity_analysis"]["spend_per_ssr"] = round(
                session.currency_spent / ssr_count, 1
            )
            report["rarity_analysis"]["pulls_per_ssr"] = round(
                total_cards / ssr_count, 1
            )

    return report


def print_gacha_report(report: dict) -> None:
    """Print a formatted gacha economy report."""
    session = report["session"]
    cost = report["cost"]
    rarity = report["rarity_analysis"]

    print(f"\n{'='*60}")
    print(f"  GACHA ECONOMY REPORT")
    print(f"{'='*60}\n")

    print(f"  Screenshots analyzed: {report['meta']['total_screenshots']}")
    print(f"  Model:               {report['meta']['model']}")
    print(f"  API cost:            ${cost['total_api_cost_usd']:.5f}")
    print()

    print(f"  CARD SUMMARY")
    print(f"  {'-'*40}")
    print(f"  Total cards:   {session['total_cards']}")
    print(f"  New cards:     {session['new_cards']} ({session['new_rate']}%)")
    print(f"  Duplicates:    {session['duplicates']}")
    print()

    if rarity:
        print(f"  RARITY DISTRIBUTION")
        print(f"  {'-'*40}")
        print(f"  {'Rarity':<10} {'Count':>6} {'Rate':>8}")

        # Sort by typical rarity order
        rarity_order = ["SSR+", "SSR", "SR", "R", "N"]
        for r in rarity_order:
            if r in rarity:
                data = rarity[r]
                bar = "+" * max(1, int(data["rate_pct"] / 2))
                print(f"  {r:<10} {data['count']:>6} {data['rate_pct']:>7.1f}% {bar}")

        # Other rarities not in standard order
        for r, data in rarity.items():
            if r not in rarity_order and r not in ("spend_per_ssr", "pulls_per_ssr"):
                bar = "+" * max(1, int(data["rate_pct"] / 2))
                print(f"  {r:<10} {data['count']:>6} {data['rate_pct']:>7.1f}% {bar}")

        if "spend_per_ssr" in rarity:
            print(f"\n  Currency per SSR: {rarity['spend_per_ssr']:.0f}")
        if "pulls_per_ssr" in rarity:
            print(f"  Pulls per SSR:    {rarity['pulls_per_ssr']:.0f}")

    print()

    # Pity progression
    pity = session.get("pity_progression", [])
    if pity:
        print(f"  PITY PROGRESSION")
        print(f"  {'-'*40}")
        for p in pity:
            pity_max_str = f"/{p['pity_max']}" if p.get('pity_max') else ""
            pct = (p["pity"] / p["pity_max"] * 100) if p.get("pity_max") else 0
            bar = "=" * int(pct / 5) + ">" if pct > 0 else ""
            print(f"  {p['image']:<35} {p['pity']}{pity_max_str}  {bar}")
        print()


def main():
    import argparse
    import glob

    parser = argparse.ArgumentParser(
        description="Track gacha economy from game screenshots"
    )
    parser.add_argument(
        "--images", required=True, nargs="+",
        help="Image files or directories (supports glob patterns)",
    )
    parser.add_argument(
        "--pattern", default="*gacha*",
        help="Glob pattern when --images is a directory (default: *gacha*)",
    )
    parser.add_argument(
        "--model", default="gemini-2.5-flash",
        choices=list(MODELS.keys()),
        help="VLM model to use",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save report JSON to this path",
    )
    args = parser.parse_args()

    # Resolve image paths
    image_files = []
    for path_arg in args.images:
        p = Path(path_arg)
        if p.is_dir():
            for ext in ("*.png", "*.jpg", "*.jpeg"):
                # Filter by pattern
                pattern = args.pattern + ext if not args.pattern.endswith(ext) else args.pattern
                image_files.extend(sorted(p.glob(pattern)))
            # If pattern didn't match, try with extension only
            if not image_files:
                for ext in ("*.png", "*.jpg"):
                    image_files.extend(sorted(p.glob(ext)))
        elif p.exists():
            image_files.append(p)
        else:
            # Try as glob pattern
            matched = sorted(Path().glob(path_arg))
            image_files.extend(matched)

    # Deduplicate and sort
    image_files = sorted(set(str(f) for f in image_files))

    if not image_files:
        print("Error: No image files found", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(image_files)} images")

    report = run_gacha_tracker(image_files, args.model)
    print_gacha_report(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str, ensure_ascii=False)
        print(f"  Report saved to: {output_path}")


if __name__ == "__main__":
    main()
