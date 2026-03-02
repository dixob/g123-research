"""
Benchmark configuration — models, fields, scoring weights, and pricing.
Aligned with g123_schema v3.0.
"""
from __future__ import annotations


# ── Model registry ────────────────────────────────────────────
MODELS = {
    "gpt-4o": {
        "provider": "openai",
        "model_id": "gpt-4o",
        "max_tokens": 500,
    },
    "gemini-2.5-flash": {
        "provider": "google",
        "model_id": "gemini-2.5-flash",
    },
    "qwen3-vl-32b": {
        "provider": "together",
        "model_id": "Qwen/Qwen3-VL-32B-Instruct",
        "max_tokens": 1000,
        "temperature": 0.1,
    },
}

# ── Pricing (USD per 1M tokens) ──────────────────────────────
# Updated 2026-03. Source: provider pricing pages.
# Format: { model_name: (input_per_1M, output_per_1M) }
PRICING = {
    "gpt-4o":           (2.50, 10.00),   # OpenAI GPT-4o
    "gemini-2.5-flash": (0.15,  0.60),   # Google Gemini 2.5 Flash (<200K ctx)
    "qwen3-vl-32b":     (0.65,  0.65),   # Together AI Qwen3-VL-32B
}


def compute_cost(
    model_name: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """
    Compute USD cost for a single API call.

    Returns None if token counts are unavailable or model has no pricing entry.
    """
    if input_tokens is None or output_tokens is None:
        return None
    pricing = PRICING.get(model_name)
    if pricing is None:
        return None
    input_rate, output_rate = pricing
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000

# ── Fields to evaluate (v3 schema paths) ─────────────────────
#
# scoring types:
#   "exact"    — case-insensitive exact match (0 or 1)
#   "numeric"  — absolute numeric equality (0 or 1)
#   "boolean"  — boolean equality, null-aware (0 or 1)
#   "fuzzy"    — token-level F1 score (0..1)
#   "set"      — Jaccard similarity over sets (0..1)

FIELD_SPEC = {
    # ── Core identifiers ──────────────────────────────────────
    "screen_type": {
        "gt_path": "screen_type",
        "scoring": "exact",
        "weight": 2.0,
    },
    "language": {
        "gt_path": "language",
        "scoring": "exact",
        "weight": 0.5,
    },

    # ── Game state: HP ────────────────────────────────────────
    "player_hp_current": {
        "gt_path": "game_state.player_hp_current",
        "scoring": "numeric",
        "weight": 1.0,
    },
    "player_hp_max": {
        "gt_path": "game_state.player_hp_max",
        "scoring": "numeric",
        "weight": 0.5,
    },
    "enemy_hp": {
        "gt_path": "game_state.enemy_hp",
        "scoring": "numeric",
        "weight": 0.5,
    },

    # ── Game state: turns & stage ─────────────────────────────
    "turn_current": {
        "gt_path": "game_state.turn_current",
        "scoring": "numeric",
        "weight": 1.0,
    },
    "turn_max": {
        "gt_path": "game_state.turn_max",
        "scoring": "numeric",
        "weight": 1.0,
    },
    "stage_id": {
        "gt_path": "game_state.stage_id",
        "scoring": "fuzzy",
        "weight": 0.5,
    },

    # ── Game state: battle controls ───────────────────────────
    "speed_multiplier": {
        "gt_path": "game_state.speed_multiplier",
        "scoring": "exact",
        "weight": 0.5,
    },
    "auto_battle_active": {
        "gt_path": "game_state.auto_battle_active",
        "scoring": "boolean",
        "weight": 0.5,
    },

    # ── Text (scored per-language for bilingual benchmark) ─────
    "text_en": {
        "gt_path": "text_content.EN",
        "scoring": "fuzzy",
        "weight": 1.0,
    },
    "text_jp": {
        "gt_path": "text_content.JP",
        "scoring": "fuzzy",
        "weight": 1.0,
    },
    "text_small": {
        "gt_path": "text_content.small",
        "scoring": "fuzzy",
        "weight": 1.0,
    },

    # ── UI & actions ──────────────────────────────────────────
    "ui_elements": {
        "gt_path": "ui_elements",
        "scoring": "ui_set",
        "weight": 1.0,
    },
    "available_actions": {
        "gt_path": "available_actions",
        "scoring": "set",
        "weight": 0.5,
    },

    # ── Gacha (scored only when present) ──────────────────────
    "gacha_phase": {
        "gt_path": "gacha.phase",
        "scoring": "exact",
        "weight": 1.0,
    },
    "gacha_banner_name": {
        "gt_path": "gacha.banner_name",
        "scoring": "fuzzy",
        "weight": 0.5,
    },
    "gacha_pity_current": {
        "gt_path": "gacha.pity_current",
        "scoring": "numeric",
        "weight": 0.5,
    },
}

# ── Prompt template (v3-aligned) ─────────────────────────────
# Shared across all models for fair comparison.
EXTRACT_PROMPT = """\
Analyze this G123 anime game screenshot. Respond with ONLY a raw JSON object,
no markdown, no code fences, no explanation.

Extract every field you can identify. Use null for fields you cannot determine.

{
  "screen_type": "battle|idle|pre_battle|post_battle|gacha",
  "language": "EN|JP|MIXED",
  "player_hp_current": null,
  "player_hp_max": null,
  "enemy_hp": null,
  "turn_current": null,
  "turn_max": null,
  "stage_id": null,
  "speed_multiplier": null,
  "auto_battle_active": null,
  "text_en": ["visible English text strings on screen"],
  "text_jp": ["visible Japanese text strings on screen"],
  "text_small": ["small or hard-to-read peripheral text"],
  "ui_elements": [{"name": "element name", "zone": "tl|tc|tr|ml|c|mr|bl|bc|br"}],
  "available_actions": ["names of interactive buttons the player can tap"],
  "gacha_phase": "lobby|animation|reveal_single|reveal_multi",
  "gacha_banner_name": null,
  "gacha_pity_current": null
}"""
