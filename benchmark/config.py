"""
Benchmark configuration — models, fields, and scoring weights.
Aligned with g123_schema v3.0.
"""

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

    # ── Text ──────────────────────────────────────────────────
    "text_content": {
        "gt_path": "text_content",
        "scoring": "fuzzy",
        "weight": 1.5,
    },
    "text_small": {
        "gt_path": "text_content.small",
        "scoring": "fuzzy",
        "weight": 1.0,
    },

    # ── UI & actions ──────────────────────────────────────────
    "ui_elements": {
        "gt_path": "ui_elements",
        "scoring": "set",
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
  "text_content": ["visible text strings on screen"],
  "text_small": ["small or hard-to-read peripheral text"],
  "ui_elements": ["button and indicator names visible on screen"],
  "available_actions": ["names of interactive buttons the player can tap"],
  "gacha_phase": "lobby|animation|reveal_single|reveal_multi",
  "gacha_banner_name": null,
  "gacha_pity_current": null
}"""
