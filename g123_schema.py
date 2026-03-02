"""
G123 VLM Evaluation Schema v3.0
================================
Two-layer annotation system:
  1. Compact template  (~25 lines) — human fills this out
  2. Full schema       (this file) — Pydantic models for validation + scoring

Usage:
  python g123_schema.py hydrate data/annotations/compact/  data/annotations/full/
  python g123_schema.py validate data/annotations/full/
  python g123_schema.py template  # prints blank template to stdout
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums ────────────────────────────────────────────────────────────────

class ScreenType(str, Enum):
    battle      = "battle"
    idle        = "idle"
    pre_battle  = "pre_battle"
    post_battle = "post_battle"
    gacha       = "gacha"

class Language(str, Enum):
    EN    = "EN"
    JP    = "JP"
    MIXED = "MIXED"

class UIType(str, Enum):
    button    = "button"
    indicator = "indicator"
    card      = "card"
    text      = "text"
    nav       = "nav"
    toggle    = "toggle"

class LocationZone(str, Enum):
    top_left      = "top_left"
    top_center    = "top_center"
    top_right     = "top_right"
    middle_left   = "middle_left"
    center        = "center"
    middle_right  = "middle_right"
    bottom_left   = "bottom_left"
    bottom_center = "bottom_center"
    bottom_right  = "bottom_right"
    full_screen   = "full_screen"

class Rarity(str, Enum):
    N    = "N"
    R    = "R"
    SR   = "SR"
    SSR  = "SSR"
    SSRp = "SSR+"
    UR   = "UR"

class GachaPhase(str, Enum):
    lobby        = "lobby"
    animation    = "animation"
    reveal_single = "reveal_single"
    reveal_multi  = "reveal_multi"

class BannerType(str, Enum):
    standard  = "standard"
    special   = "special"
    limited   = "limited"
    collab    = "collab"
    attribute = "attribute"
    other     = "other"

class Confidence(str, Enum):
    high   = "high"
    medium = "medium"
    low    = "low"

class Difficulty(str, Enum):
    easy   = "easy"
    medium = "medium"
    hard   = "hard"


# ── Game Registry ────────────────────────────────────────────────────────

GAME_REGISTRY: dict[str, str] = {
    "highschooldxd": "High School DxD: Operation Paradise Infinity",
    "arifureta":     "Arifureta: From Commonplace to World's Strongest",
    "queensblade":   "Queen's Blade: Limit Break",
    "aigis":         "Millennium War Aigis",
    # Add new games here as screenshots are collected
}


# ── Full Schema Models ───────────────────────────────────────────────────

class GameState(BaseModel):
    player_hp_current:  Optional[int]  = None
    player_hp_max:      Optional[int]  = None
    enemy_hp:           Optional[int | list[int]] = None
    turn_current:       Optional[int]  = None
    turn_max:           Optional[int]  = None
    stage_id:           Optional[str]  = None
    team_power_player:  Optional[int]  = None
    team_power_enemy:   Optional[int]  = None
    currency_premium:   Optional[int]  = None
    currency_tickets:   Optional[int]  = None
    auto_battle_active: Optional[bool] = None
    auto_battle_timer:  Optional[str]  = None
    speed_multiplier:   Optional[str]  = None


class RevealedCard(BaseModel):
    card_name: Optional[str]     = None
    rarity:    Optional[Rarity]  = None
    stars:     Optional[int]     = Field(None, ge=1, le=6)
    is_new:    Optional[bool]    = None


class Gacha(BaseModel):
    phase:              GachaPhase
    banner_type:        Optional[BannerType] = None
    banner_name:        Optional[str]        = None
    pull_cost_type:     Optional[str]        = None
    pity_current:       Optional[int]        = None
    pity_max:           Optional[int]        = None
    free_pull_available: Optional[bool]      = None
    free_pull_timer:    Optional[str]        = None
    revealed_cards:     Optional[list[RevealedCard]] = None


class RewardItem(BaseModel):
    item_name: str
    quantity:  Optional[int] = None


class MVP(BaseModel):
    character_name: Optional[str]   = None
    damage_value:   Optional[int]   = None
    damage_percent: Optional[float] = None


class UIElement(BaseModel):
    name:       str
    type:       UIType
    location:   LocationZone
    is_enabled: Optional[bool] = None
    label_text: Optional[str]  = None


class TextContent(BaseModel):
    EN:    Optional[list[str]] = None
    JP:    Optional[list[str]] = None
    small: Optional[list[str]] = Field(
        None,
        description="Small, hard-to-read, or peripheral text. "
                    "Key for scoring VLM accuracy on low-prominence text."
    )


class AnnotationMetadata(BaseModel):
    annotator:           str
    annotation_date:     date
    confidence:          Confidence
    expected_difficulty: Difficulty


class G123Annotation(BaseModel):
    """Full evaluation-ready annotation. Validated by Pydantic, scored by harness."""

    screenshot_id:      str
    game_name:          str
    game_slug:          str
    language:           Language
    screen_type:        ScreenType
    sub_type:           Optional[str]              = None
    game_state:         GameState                  = Field(default_factory=GameState)
    gacha:              Optional[Gacha]            = None
    post_battle_rewards: Optional[list[RewardItem]] = None
    mvp:                Optional[MVP]              = None
    ui_elements:        list[UIElement]
    text_content:       TextContent
    available_actions:  list[str]
    game_extension:     Optional[dict]             = None
    screen_notes:       str
    annotation_metadata: AnnotationMetadata

    # ── Cross-field validation ──

    @model_validator(mode="after")
    def check_conditional_requirements(self) -> "G123Annotation":
        errors = []

        # gacha object required when screen is gacha
        if self.screen_type == ScreenType.gacha and self.gacha is None:
            errors.append("screen_type='gacha' requires gacha object to be populated")

        # gacha must be null for non-gacha screens
        if self.screen_type != ScreenType.gacha and self.gacha is not None:
            errors.append(f"screen_type='{self.screen_type.value}' must have gacha=null")

        # post_battle needs rewards
        if self.screen_type == ScreenType.post_battle and self.post_battle_rewards is None:
            errors.append("screen_type='post_battle' requires post_battle_rewards")

        # rewards must be null for non-post_battle
        if self.screen_type != ScreenType.post_battle and self.post_battle_rewards is not None:
            errors.append(f"screen_type='{self.screen_type.value}' must have post_battle_rewards=null")

        # available_actions should reference enabled ui_elements
        enabled_names = {
            el.name for el in self.ui_elements
            if el.is_enabled is not False  # True or None both count
        }
        orphan_actions = [a for a in self.available_actions if a not in enabled_names]
        if orphan_actions:
            errors.append(
                f"available_actions entries not found in enabled ui_elements: {orphan_actions}"
            )

        if errors:
            raise ValueError("; ".join(errors))

        return self

    @field_validator("screenshot_id")
    @classmethod
    def validate_screenshot_id(cls, v: str) -> str:
        pattern = r"^[a-z]+_[a-z_]+_\d{3}_(en|jp)$"
        if not re.match(pattern, v):
            raise ValueError(
                f"screenshot_id '{v}' does not match pattern: "
                f"{{game_slug}}_{{screen_type}}_{{seq:03d}}_{{lang}}"
            )
        return v


# ── Shorthand Parsers ────────────────────────────────────────────────────

# Zone abbreviation map
_ZONE_MAP: dict[str, LocationZone] = {
    "tl": LocationZone.top_left,     "tc": LocationZone.top_center,    "tr": LocationZone.top_right,
    "ml": LocationZone.middle_left,  "c":  LocationZone.center,        "mr": LocationZone.middle_right,
    "bl": LocationZone.bottom_left,  "bc": LocationZone.bottom_center, "br": LocationZone.bottom_right,
    "fs": LocationZone.full_screen,
}

# UI type abbreviation map
_UITYPE_MAP: dict[str, UIType] = {
    "btn": UIType.button,  "ind": UIType.indicator, "card": UIType.card,
    "txt": UIType.text,    "nav": UIType.nav,       "tog":  UIType.toggle,
}


def parse_ui_shorthand(s: str) -> UIElement:
    """Parse 'Label|type|zone|state' → UIElement.

    Examples:
        'Attack|btn|br|on'   → UIElement(name='Attack', type=button, location=bottom_right, is_enabled=True)
        'HP Bar|ind|tl'      → UIElement(name='HP Bar', type=indicator, location=top_left, is_enabled=None)
        'Retreat|btn|bl|off' → UIElement(name='Retreat', type=button, location=bottom_left, is_enabled=False)
    """
    parts = s.split("|")
    if len(parts) < 3:
        raise ValueError(f"UI shorthand needs at least 3 parts (name|type|zone), got: '{s}'")

    name = parts[0].strip()
    ui_type = _UITYPE_MAP.get(parts[1].strip())
    if ui_type is None:
        raise ValueError(f"Unknown UI type '{parts[1]}' in '{s}'. Valid: {list(_UITYPE_MAP.keys())}")

    zone = _ZONE_MAP.get(parts[2].strip())
    if zone is None:
        raise ValueError(f"Unknown zone '{parts[2]}' in '{s}'. Valid: {list(_ZONE_MAP.keys())}")

    is_enabled = None
    if len(parts) >= 4:
        state = parts[3].strip().lower()
        is_enabled = {"on": True, "off": False}.get(state)
        if is_enabled is None:
            raise ValueError(f"Unknown state '{parts[3]}' in '{s}'. Valid: on, off")

    return UIElement(name=name, type=ui_type, location=zone, is_enabled=is_enabled)


def parse_card_shorthand(s: str) -> RevealedCard:
    """Parse 'Name|Rarity|Stars|new' → RevealedCard.

    Examples:
        '不死鳥の王子 / ライザー|SSR+|5|y' → RevealedCard(card_name=..., rarity=SSR+, stars=5, is_new=True)
        'アソシスト|N|1|n'                  → RevealedCard(card_name='アソシスト', rarity=N, stars=1, is_new=False)
    """
    parts = s.split("|")
    if len(parts) < 3:
        raise ValueError(f"Card shorthand needs at least 3 parts (name|rarity|stars), got: '{s}'")

    name = parts[0].strip() or None
    rarity = Rarity(parts[1].strip()) if parts[1].strip() else None
    stars = int(parts[2].strip()) if parts[2].strip() else None

    is_new = None
    if len(parts) >= 4:
        is_new = {"y": True, "n": False}.get(parts[3].strip().lower())

    return RevealedCard(card_name=name, rarity=rarity, stars=stars, is_new=is_new)


def parse_hp(val) -> tuple[Optional[int], Optional[int]]:
    """Parse HP shorthand → (current, max).

    '8450/12000' → (8450, 12000)
    22000        → (22000, None)   # single value, no max
    null/None    → (None, None)
    """
    if val is None:
        return None, None
    if isinstance(val, int):
        return val, None
    if isinstance(val, str) and "/" in val:
        parts = val.split("/")
        return int(parts[0].strip()), int(parts[1].strip())
    return int(val), None


def parse_turn(val) -> tuple[Optional[int], Optional[int]]:
    """Parse turn shorthand → (current, max). Same format as HP."""
    return parse_hp(val)


def parse_pity(val) -> tuple[Optional[int], Optional[int]]:
    """Parse pity shorthand → (current, max). Same format as HP."""
    return parse_hp(val)


def parse_reward(s: str) -> RewardItem:
    """Parse 'ItemName|Quantity' → RewardItem.

    'Gold|1500'       → RewardItem(item_name='Gold', quantity=1500)
    'Mystery Scroll'  → RewardItem(item_name='Mystery Scroll', quantity=None)
    """
    parts = s.split("|")
    name = parts[0].strip()
    qty = int(parts[1].strip()) if len(parts) >= 2 and parts[1].strip() else None
    return RewardItem(item_name=name, quantity=qty)


def parse_text_small(entries: Optional[list[str]]) -> list[str]:
    """Strip [s] prefix from small text entries. Prefix is for annotator UX only."""
    if not entries:
        return []
    return [e.replace("[s]", "").strip() for e in entries]


# ── Hydration: Compact → Full ────────────────────────────────────────────

def hydrate(compact: dict, annotator: str = "robert") -> G123Annotation:
    """Expand a compact annotation template into a full G123Annotation."""

    sid = compact["id"]
    # Derive game_slug from screenshot_id (everything before the screen_type)
    parts = sid.rsplit("_", 2)  # [slug_and_screen, seq, lang]
    screen_raw = compact["screen"]
    # game_slug = everything before _screen_type_ in the id
    slug_end = sid.index(f"_{screen_raw}_")
    game_slug = sid[:slug_end]
    game_name = GAME_REGISTRY.get(game_slug, f"Unknown ({game_slug})")

    # Parse state
    state = compact.get("state", {}) or {}
    hp_cur, hp_max = parse_hp(state.get("hp_player"))
    turn_cur, turn_max = parse_turn(state.get("turn"))

    game_state = GameState(
        player_hp_current=hp_cur,
        player_hp_max=hp_max,
        enemy_hp=state.get("hp_enemy"),
        turn_current=turn_cur,
        turn_max=turn_max,
        stage_id=state.get("stage"),
        team_power_player=state.get("power_player"),
        team_power_enemy=state.get("power_enemy"),
        currency_premium=state.get("currency_premium"),
        currency_tickets=state.get("currency_tickets"),
        auto_battle_active=state.get("auto"),
        auto_battle_timer=state.get("auto_timer"),
        speed_multiplier=state.get("speed"),
    )

    # Parse gacha
    gacha_obj = None
    gacha_raw = compact.get("gacha")
    if gacha_raw:
        pity_cur, pity_max = parse_pity(gacha_raw.get("pity"))
        cards = None
        if gacha_raw.get("cards"):
            cards = [parse_card_shorthand(c) for c in gacha_raw["cards"]]

        gacha_obj = Gacha(
            phase=GachaPhase(gacha_raw["phase"]),
            banner_type=BannerType(gacha_raw["banner_type"]) if gacha_raw.get("banner_type") else None,
            banner_name=gacha_raw.get("banner_name"),
            pull_cost_type=gacha_raw.get("pull_cost"),
            pity_current=pity_cur,
            pity_max=pity_max,
            free_pull_available=gacha_raw.get("free_pull"),
            free_pull_timer=gacha_raw.get("free_timer"),
            revealed_cards=cards,
        )

    # Parse rewards
    rewards = None
    if compact.get("rewards"):
        rewards = [parse_reward(r) for r in compact["rewards"]]

    # Parse MVP
    mvp_obj = None
    mvp_raw = compact.get("mvp")
    if mvp_raw:
        mvp_obj = MVP(
            character_name=mvp_raw.get("name"),
            damage_value=mvp_raw.get("damage"),
            damage_percent=mvp_raw.get("pct"),
        )

    # Parse UI elements
    ui_elements = [parse_ui_shorthand(u) for u in compact.get("ui", [])]

    # Parse text content
    text_content = TextContent(
        EN=compact.get("text_en"),
        JP=compact.get("text_jp"),
        small=parse_text_small(compact.get("text_small")),
    )

    # Build annotation metadata
    metadata = AnnotationMetadata(
        annotator=annotator,
        annotation_date=date.today(),
        confidence=Confidence(compact["confidence"]),
        expected_difficulty=Difficulty(compact["difficulty"]),
    )

    return G123Annotation(
        screenshot_id=sid,
        game_name=game_name,
        game_slug=game_slug,
        language=Language(compact["lang"]),
        screen_type=ScreenType(compact["screen"]),
        sub_type=compact.get("sub"),
        game_state=game_state,
        gacha=gacha_obj,
        post_battle_rewards=rewards,
        mvp=mvp_obj,
        ui_elements=ui_elements,
        text_content=text_content,
        available_actions=compact.get("actions", []),
        game_extension=compact.get("ext"),
        screen_notes=compact["notes"],
        annotation_metadata=metadata,
    )


# ── CLI ──────────────────────────────────────────────────────────────────

def cmd_hydrate(src_dir: str, dst_dir: str, annotator: str = "robert"):
    """Hydrate all compact annotations in src_dir → full schemas in dst_dir."""
    src = Path(src_dir)
    dst = Path(dst_dir)
    dst.mkdir(parents=True, exist_ok=True)

    files = sorted(src.glob("*.json"))
    if not files:
        print(f"No .json files found in {src}")
        return

    ok, fail = 0, 0
    for f in files:
        try:
            compact = json.loads(f.read_text(encoding="utf-8"))
            # Skip template/instruction files
            if "_TEMPLATE_VERSION" in compact or "_BLANK_TEMPLATE" in compact:
                continue

            full = hydrate(compact, annotator=annotator)
            out_path = dst / f.name
            out_path.write_text(
                full.model_dump_json(indent=2, exclude_none=False),
                encoding="utf-8"
            )
            ok += 1
            print(f"  OK {f.name}")
        except Exception as e:
            fail += 1
            print(f"  FAIL {f.name}: {e}")

    print(f"\nHydrated: {ok} ok, {fail} failed out of {ok + fail} files")


def cmd_validate(full_dir: str):
    """Validate all full-schema annotations in a directory."""
    d = Path(full_dir)
    files = sorted(d.glob("*.json"))
    if not files:
        print(f"No .json files found in {d}")
        return

    ok, fail = 0, 0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            G123Annotation(**data)
            ok += 1
            print(f"  OK {f.name}")
        except Exception as e:
            fail += 1
            print(f"  FAIL {f.name}: {e}")

    print(f"\nValidated: {ok} ok, {fail} failed out of {ok + fail} files")


def cmd_template():
    """Print a blank compact template to stdout."""
    template = {
        "id": "",
        "lang": "",
        "screen": "",
        "sub": None,
        "state": {
            "hp_player": None, "hp_enemy": None, "turn": None,
            "stage": None, "speed": None, "auto": None, "auto_timer": None,
            "power_player": None, "power_enemy": None,
            "currency_premium": None, "currency_tickets": None
        },
        "gacha": None,
        "rewards": None,
        "mvp": None,
        "ui": [],
        "actions": [],
        "text_en": None,
        "text_jp": None,
        "text_small": None,
        "ext": None,
        "notes": "",
        "confidence": "",
        "difficulty": ""
    }
    print(json.dumps(template, indent=2, ensure_ascii=False))


def cmd_export_json_schema(out_path: str = "g123_schema_v3.json"):
    """Export the Pydantic model as a JSON Schema file."""
    schema = G123Annotation.model_json_schema()
    schema["$id"] = "g123-core-annotation-schema-v3.0"
    schema["title"] = "G123 Core Annotation Schema"
    schema["version"] = "3.0.0"
    Path(out_path).write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported JSON Schema to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python g123_schema.py hydrate  <compact_dir> <full_dir> [annotator]")
        print("  python g123_schema.py validate <full_dir>")
        print("  python g123_schema.py template")
        print("  python g123_schema.py export-schema [output_path]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "hydrate":
        cmd_hydrate(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "robert")
    elif cmd == "validate":
        cmd_validate(sys.argv[2])
    elif cmd == "template":
        cmd_template()
    elif cmd == "export-schema":
        cmd_export_json_schema(sys.argv[2] if len(sys.argv) > 2 else "g123_schema_v3.json")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
