"""
Benchmark configuration — models, fields, and scoring weights.
"""

# ── Model registry ────────────────────────────────────────────
# Each entry: (display_name, provider, model_id, extract_fn module path)
# extract_fn is the function that takes (image_path, prompt) -> raw text
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

# ── Fields to evaluate ────────────────────────────────────────
# Maps VLM output field -> annotation ground-truth path + scoring type
#
# scoring types:
#   "exact"      — case-insensitive exact match (0 or 1)
#   "numeric"    — absolute numeric equality (0 or 1)
#   "fuzzy"      — token-level F1 score (0..1)
#   "set"        — Jaccard similarity over sets (0..1)
#   "nullable"   — correct if both null, or if both non-null and match

FIELD_SPEC = {
    "screen_type": {
        "gt_path": "screen_type",
        "scoring": "exact",
        "weight": 2.0,
    },
    "player_hp": {
        "gt_path": "game_state.player_hp",
        "scoring": "numeric",
        "weight": 1.0,
    },
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
    "total_damage": {
        "gt_path": "game_state.total_damage",
        "scoring": "numeric",
        "weight": 1.0,
    },
    "language": {
        "gt_path": "language",
        "scoring": "exact",
        "weight": 0.5,
    },
    "text_content": {
        "gt_path": "text_content",
        "scoring": "fuzzy",
        "weight": 1.5,
    },
    "ui_elements": {
        "gt_path": "ui_elements",
        "scoring": "set",
        "weight": 1.0,
    },
}

# ── Prompt template ───────────────────────────────────────────
# Shared prompt across all models for fair comparison.
EXTRACT_PROMPT = """\
Analyze this G123 anime game screenshot. Respond with ONLY a raw JSON object,
no markdown, no code fences, no explanation.

Extract every field you can identify. Use null for fields you cannot determine.

{
  "screen_type": "battle|menu|inventory|shop|loading|dialogue|gacha|character|campaign|post_battle|pre_battle|exchange|task|gear",
  "language": "EN|JP",
  "player_hp": null,
  "enemy_hp": null,
  "turn_current": null,
  "turn_max": null,
  "total_damage": null,
  "team_power_player": null,
  "team_power_enemy": null,
  "text_content": ["visible text strings on screen"],
  "ui_elements": ["button/indicator names visible on screen"],
  "user_level": null,
  "level_name": null,
  "user_name": null
}"""
