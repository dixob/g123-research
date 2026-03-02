"""
Migrate v1 annotations to v3 hydrated format.

Converts 111 v1 annotations from the legacy monolithic JSON into
individual v3 hydrated JSON files compatible with the benchmark runner.

V1 → V3 Mapping:
  Screen types: character/dialogue/event/idle_overworld/menu/shop → idle
                battle → battle
                pre_battle → pre_battle
                post_battle → post_battle
                gacha → gacha

  game_state: player_hp → player_hp_current (split from "current/max" if needed)
              total_damage → (dropped, v3 doesn't track aggregate damage)
              current_stage → stage_id
              currency_jewel → currency_premium
              currency_gold → (stored in ext)

  gacha: Restructured from flat fields to nested card objects

  ui_elements: Preserved as-is (v3 format is compatible)

  text_content: Preserved as-is with small text extraction

Usage:
  python scripts/migrate_v1_to_v3.py
  python scripts/migrate_v1_to_v3.py --input data/annotations/legacy/hsdxd_annotations_v1.json
  python scripts/migrate_v1_to_v3.py --output-dir data/annotations/migrated --dry-run
"""
from __future__ import annotations

import json
import sys
import re
from pathlib import Path
from datetime import date


# ── Screen type mapping ───────────────────────────────────────
V1_TO_V3_SCREEN = {
    "battle": "battle",
    "pre_battle": "pre_battle",
    "post_battle": "post_battle",
    "gacha": "gacha",
    # Everything else → idle
    "idle_overworld": "idle",
    "menu": "idle",
    "shop": "idle",
    "character": "idle",
    "dialogue": "idle",
    "event": "idle",
}


def _parse_hp(val) -> tuple[int | None, int | None]:
    """Parse HP from various v1 formats: int, 'current/max', or null."""
    if val is None:
        return None, None
    if isinstance(val, (int, float)):
        return int(val), None
    if isinstance(val, str) and "/" in val:
        parts = val.split("/")
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, IndexError):
            return None, None
    try:
        return int(val), None
    except (ValueError, TypeError):
        return None, None


def _extract_speed(ui_elements: list[dict]) -> str | None:
    """Extract speed multiplier from UI elements (e.g., 'x3' from Speed toggle)."""
    for elem in (ui_elements or []):
        name = (elem.get("name") or "").lower()
        label = elem.get("label_text") or ""
        if "speed" in name:
            match = re.search(r'x(\d+)', label or name)
            if match:
                return f"x{match.group(1)}"
    return None


def _migrate_gacha(v1_gacha: dict | None) -> dict | None:
    """Convert v1 flat gacha fields to v3 nested structure."""
    if not v1_gacha:
        return None

    phase = v1_gacha.get("phase")
    if not phase:
        return None

    # Build cards list from v1 flat fields
    cards = []
    # v1 has cards_revealed as a list of dicts sometimes
    cards_revealed = v1_gacha.get("cards_revealed") or []
    if isinstance(cards_revealed, list):
        for card in cards_revealed:
            if isinstance(card, dict):
                cards.append({
                    "card_name": card.get("card_name") or card.get("name") or "Unknown",
                    "rarity": card.get("card_rarity") or card.get("rarity"),
                    "stars": card.get("card_stars") or card.get("stars"),
                    "is_new": card.get("is_new", False),
                })

    # v1 also has single card fields
    if not cards and v1_gacha.get("card_name"):
        cards.append({
            "card_name": v1_gacha["card_name"],
            "rarity": v1_gacha.get("card_rarity"),
            "stars": v1_gacha.get("card_stars"),
            "is_new": v1_gacha.get("is_new", False),
        })

    result = {
        "phase": phase,
        "banner_type": v1_gacha.get("banner_type"),
        "banner_name": None,  # v1 doesn't have banner_name
        "pull_cost_type": None,
        "pity_current": v1_gacha.get("pity_current"),
        "pity_max": v1_gacha.get("pity_max"),
        "free_pull_available": v1_gacha.get("free_pull_available", False),
        "free_pull_timer": None,
        "revealed_cards": cards if cards else None,
    }

    return result


def _migrate_rewards(v1_rewards: list | None) -> list[str] | None:
    """Convert v1 post_battle_rewards to v3 format."""
    if not v1_rewards:
        return None

    results = []
    for reward in v1_rewards:
        if isinstance(reward, dict):
            name = reward.get("item_name") or reward.get("name") or "Unknown"
            qty = reward.get("quantity") or reward.get("amount") or 1
            results.append(f"{name}|{qty}")
        elif isinstance(reward, str):
            results.append(reward)

    return results if results else None


def _migrate_mvp(v1_mvp: dict | None) -> dict | None:
    """Convert v1 MVP data to v3 format."""
    if not v1_mvp:
        return None
    return {
        "name": v1_mvp.get("unit_name") or v1_mvp.get("name"),
        "damage": v1_mvp.get("damage"),
        "pct": v1_mvp.get("damage_pct") or v1_mvp.get("pct"),
    }


def migrate_annotation(v1: dict, seq: int) -> dict:
    """Convert a single v1 annotation to v3 hydrated format."""
    # Screen type mapping
    v1_screen = v1.get("screen_type", "idle")
    v3_screen = V1_TO_V3_SCREEN.get(v1_screen, "idle")

    # Language
    lang = v1.get("language", "EN").upper()

    # Game state
    v1_gs = v1.get("game_state") or {}
    hp_current, hp_max = _parse_hp(v1_gs.get("player_hp"))
    enemy_hp_val, _ = _parse_hp(v1_gs.get("enemy_hp"))

    # Currency
    currency_premium = v1_gs.get("currency_jewel")
    if currency_premium is None:
        # Try other field names
        currency_premium = v1_gs.get("currency_premium")

    # Speed from UI elements
    speed = _extract_speed(v1.get("ui_elements", []))

    # Stage
    stage = v1_gs.get("current_stage") or v1_gs.get("stage_id")

    # Text content
    v1_text = v1.get("text_content") or {}
    text_en = v1_text.get("EN") if isinstance(v1_text, dict) else None
    text_jp = v1_text.get("JP") if isinstance(v1_text, dict) else None

    # Detect small text (labels with small font indicators or short numeric strings)
    small_texts = []
    if isinstance(v1_text, dict):
        for lang_texts in v1_text.values():
            if isinstance(lang_texts, list):
                for t in lang_texts:
                    if isinstance(t, str) and re.match(r'^[\d/:x×]+$', t.strip()):
                        small_texts.append(t)

    # UI elements (already in compatible format)
    ui_elements = v1.get("ui_elements") or []

    # Available actions
    actions = v1.get("available_actions") or []

    # Text content combined (for matching what the model will produce)
    text_combined_en = text_en
    text_combined_jp = text_jp

    # Build v3 hydrated format
    v3 = {
        "screenshot_id": v1["screenshot_id"].lower(),
        "game_name": v1.get("game_name", "High School DxD: Operation Paradise Infinity"),
        "game_slug": v1.get("game_slug", "highschooldxd"),
        "language": lang,
        "screen_type": v3_screen,
        "sub_type": None,
        "game_state": {
            "player_hp_current": hp_current,
            "player_hp_max": hp_max,
            "enemy_hp": enemy_hp_val,
            "turn_current": v1_gs.get("turn_current"),
            "turn_max": v1_gs.get("turn_max"),
            "stage_id": stage,
            "team_power_player": v1_gs.get("team_power_player"),
            "team_power_enemy": v1_gs.get("team_power_enemy"),
            "currency_premium": currency_premium,
            "currency_tickets": None,
            "auto_battle_active": v1_gs.get("auto_battle_active"),
            "auto_battle_timer": v1_gs.get("auto_battle_timer"),
            "speed_multiplier": speed,
        },
        "gacha": _migrate_gacha(v1.get("gacha")),
        "post_battle_rewards": _migrate_rewards(v1.get("post_battle_rewards")),
        "mvp": _migrate_mvp(v1.get("mvp")),
        "ui_elements": ui_elements,
        "text_content": {
            "EN": text_combined_en,
            "JP": text_combined_jp,
            "small": small_texts if small_texts else None,
        },
        "available_actions": actions,
        "game_extension": None,
        "screen_notes": v1.get("screen_notes", ""),
        "annotation_metadata": {
            "annotator": "migration_v1_to_v3",
            "annotation_date": str(date.today()),
            "confidence": "medium",
            "expected_difficulty": "medium",
            "source": "v1_migration",
            "v1_original_id": v1.get("_original_id"),
            "v1_screen_type": v1_screen,
        },
    }

    # Store v1-only fields in game_extension
    ext = {}
    if v1_gs.get("total_damage"):
        ext["total_damage"] = v1_gs["total_damage"]
    if v1_gs.get("currency_gold"):
        ext["currency_gold"] = v1_gs["currency_gold"]
    if v1.get("combat_indicators"):
        ci = v1["combat_indicators"]
        if any(v for v in ci.values() if v is not None):
            ext["combat_indicators"] = ci
    if v1.get("unit_roster"):
        ext["unit_roster"] = v1["unit_roster"]
    if v1.get("sidebar_notifications"):
        ext["sidebar_notifications"] = v1["sidebar_notifications"]
    if v1.get("bottom_nav"):
        ext["bottom_nav"] = v1["bottom_nav"]
    if v1.get("overlay"):
        ext["overlay"] = v1["overlay"]

    if ext:
        v3["game_extension"] = ext

    return v3


def migrate_all(
    input_path: str = "data/annotations/legacy/hsdxd_annotations_v1.json",
    output_dir: str = "data/annotations/migrated",
    dry_run: bool = False,
) -> dict:
    """
    Migrate all v1 annotations to v3 format.

    Returns summary dict with migration stats.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)

    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    annotations = data.get("annotations", [])
    total = len(annotations)
    print(f"Migrating {total} v1 annotations to v3 format...")

    output_path = Path(output_dir)
    if not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)

    migrated = 0
    skipped = 0
    screen_type_map = {}
    errors = []

    for i, v1 in enumerate(annotations):
        try:
            v3 = migrate_annotation(v1, i + 1)
            sid = v3["screenshot_id"]

            v1_st = v1.get("screen_type", "?")
            v3_st = v3["screen_type"]
            screen_type_map[f"{v1_st} -> {v3_st}"] = screen_type_map.get(f"{v1_st} -> {v3_st}", 0) + 1

            if not dry_run:
                out_file = output_path / f"{sid}.json"
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(v3, f, indent=2, ensure_ascii=False)

            migrated += 1

        except Exception as e:
            sid = v1.get("screenshot_id", f"index_{i}")
            errors.append(f"{sid}: {e}")
            skipped += 1

    # Summary
    summary = {
        "total_v1": total,
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "screen_type_mapping": screen_type_map,
        "output_dir": str(output_dir),
    }

    print(f"\nMigration complete:")
    print(f"  Migrated: {migrated}/{total}")
    print(f"  Skipped:  {skipped}")
    print(f"\n  Screen type mapping:")
    for mapping, count in sorted(screen_type_map.items()):
        print(f"    {mapping}: {count}")

    if errors:
        print(f"\n  Errors:")
        for err in errors[:10]:
            print(f"    {err}")
        if len(errors) > 10:
            print(f"    ... and {len(errors) - 10} more")

    if not dry_run:
        print(f"\n  Output: {output_path}/")
        print(f"  Files: {migrated} JSON files")

    return summary


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate v1 annotations to v3 format"
    )
    parser.add_argument(
        "--input", default="data/annotations/legacy/hsdxd_annotations_v1.json",
        help="Path to v1 annotations JSON",
    )
    parser.add_argument(
        "--output-dir", default="data/annotations/migrated",
        help="Output directory for v3 JSON files",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be migrated without writing files",
    )
    args = parser.parse_args()

    summary = migrate_all(args.input, args.output_dir, args.dry_run)

    if args.dry_run:
        print("\n  (DRY RUN — no files written)")


if __name__ == "__main__":
    main()
