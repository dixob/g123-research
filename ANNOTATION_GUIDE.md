# G123 Screenshot Annotation Guide

> How to annotate game screenshots for the VLM benchmark.
> Schema version: **3.0** | Last updated: 2026-03-01

---

## Table of Contents

1. [Overview](#1-overview)
2. [Before You Start](#2-before-you-start)
3. [File Naming & Setup](#3-file-naming--setup)
4. [Filling Out the Template](#4-filling-out-the-template)
   - [Header Fields](#41-header-fields)
   - [Game State](#42-game-state)
   - [Gacha](#43-gacha-gacha-screens-only)
   - [Rewards & MVP](#44-rewards--mvp-post_battle-only)
   - [UI Elements](#45-ui-elements)
   - [Available Actions](#46-available-actions)
   - [Text Content](#47-text-content)
   - [Notes & Metadata](#48-notes--metadata)
5. [Shorthand Reference](#5-shorthand-reference)
6. [Screen Type Decision Tree](#6-screen-type-decision-tree)
7. [Worked Examples](#7-worked-examples)
8. [Validation Rules](#8-validation-rules)
9. [Common Mistakes](#9-common-mistakes)
10. [Running the Pipeline](#10-running-the-pipeline)

---

## 1. Overview

We are building a benchmark to measure how well Vision Language Models (VLMs) can extract structured game state from anime game screenshots. Your job as an annotator is to look at a screenshot and write down **exactly what you see** in a compact JSON template.

**The golden rule: `null` means NOT VISIBLE on screen. Never guess.**

If you cannot read a number, cannot tell if something is on or off, or the information simply is not on screen — use `null`. Accurate nulls are as important as accurate values.

### How your annotation gets used

```
You fill this         Script expands it        Benchmark scores
  (compact)      -->    (full schema)      -->   VLMs against it
  ~25 lines            Pydantic-validated         17 scored fields
```

1. You fill out a **compact JSON template** (~25 lines) per screenshot
2. The hydration script expands it into a **full Pydantic-validated schema**
3. The benchmark runs VLMs on the same screenshot and **scores their output against your annotation**

Your annotation is the ground truth. Accuracy matters.

---

## 2. Before You Start

### What you need

- The screenshot image file (PNG)
- A text editor with JSON syntax highlighting (VS Code recommended)
- The blank template (run `make template` or `python g123_schema.py template`)

### Supported games

| Slug | Full Name |
|------|-----------|
| `highschooldxd` | High School DxD: Operation Paradise Infinity |
| `arifureta` | Arifureta: From Commonplace to World's Strongest |
| `queensblade` | Queen's Blade: Limit Break |
| `aigis` | Millennium War Aigis |

If your game is not listed, add it to `GAME_REGISTRY` in `g123_schema.py` before annotating.

### Screen types

| Type | When to use |
|------|-------------|
| `battle` | Active combat — characters fighting, HP bars moving, damage numbers |
| `idle` | Menus, lobby, home screen, character viewer, settings |
| `pre_battle` | Team selection, stage select, loading screen before a fight |
| `post_battle` | Victory/defeat screen, reward summary, results |
| `gacha` | Summoning — banner lobby, pull animation, card reveal |

---

## 3. File Naming & Setup

### Screenshot ID format

Every screenshot gets a unique ID following this exact pattern:

```
{game_slug}_{screen_type}_{sequence:03d}_{lang}
```

| Part | Rules | Examples |
|------|-------|---------|
| `game_slug` | Lowercase, no spaces, from GAME_REGISTRY | `highschooldxd`, `arifureta` |
| `screen_type` | One of: `battle`, `idle`, `pre_battle`, `post_battle`, `gacha` | `battle`, `gacha` |
| `sequence` | 3-digit zero-padded, unique within game+type | `001`, `012`, `100` |
| `lang` | Lowercase: `en` or `jp` | `en`, `jp` |

**Examples:**
- `highschooldxd_battle_001_en`
- `highschooldxd_gacha_012_jp`
- `arifureta_post_battle_003_en`

### Creating your annotation file

1. Copy the blank template:
   ```
   make template > data/annotations/compact/highschooldxd_battle_001_en.json
   ```
   Or copy `_BLANK_TEMPLATE` from `data/annotations/g123_annotation_template.json`.

2. The JSON filename **must match** the screenshot ID:
   ```
   data/annotations/compact/highschooldxd_battle_001_en.json
   ```

3. Rename the screenshot image to match the ID:
   ```
   images/highschooldxd_battle_001_EN.png
   ```
   Note: image files use **uppercase** language suffix (`_EN.png`, `_JP.png`).

---

## 4. Filling Out the Template

Open the screenshot side-by-side with your JSON file. Work through each section top to bottom.

### 4.1 Header Fields

```json
{
  "id": "highschooldxd_battle_001_en",
  "lang": "EN",
  "screen": "battle",
  "sub": null,
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | The screenshot ID (must match filename, see Section 3) |
| `lang` | `"EN"` / `"JP"` / `"MIXED"` | Primary language of on-screen text. Use `MIXED` if both EN and JP text are prominent |
| `screen` | string | Screen type (see Section 2 table) |
| `sub` | string or null | Optional sub-type for edge cases (e.g. `"boss"` for a boss battle). Usually `null` |

**How to decide `lang`:**
- If all readable UI text is in English: `"EN"`
- If all readable UI text is in Japanese: `"JP"`
- If the UI has a mix of both (common in JP games with EN button labels): `"MIXED"`
- Judge by the **UI labels and menus**, not by character names or game terms

---

### 4.2 Game State

The `state` object captures numeric and boolean values visible on screen.

```json
"state": {
  "hp_player": "8450/12000",
  "hp_enemy": 22000,
  "turn": "3/10",
  "stage": "校門 1-8",
  "speed": "x3",
  "auto": true,
  "auto_timer": null,
  "power_player": null,
  "power_enemy": null,
  "currency_premium": null,
  "currency_tickets": null
},
```

#### Field-by-field guide:

| Field | Format | What to look for |
|-------|--------|-----------------|
| `hp_player` | `"current/max"` or integer | The player's / team's HP bar. If you see `8450/12000`, write `"8450/12000"`. If only one number is shown (no max), write just the integer: `22000`. If no HP bar is visible, write `null` |
| `hp_enemy` | integer or list of integers | Enemy HP. If multiple enemies each show HP, use a list: `[15000, 8000, 12000]`. Single enemy: just the integer |
| `turn` | `"current/max"` or integer | Turn counter. `"3/10"` means turn 3 of 10. If only current turn shows, use integer. Not visible = `null` |
| `stage` | string | Stage/level identifier exactly as displayed. Could be `"1-8"`, `"校門 1-8"`, `"Chapter 3"`, etc. Copy it verbatim |
| `speed` | string | Speed multiplier toggle. Usually `"x1"`, `"x2"`, `"x3"`. Write exactly what the button/indicator shows |
| `auto` | boolean | Is auto-battle currently **active**? `true` if the auto indicator is ON/highlighted, `false` if OFF/dimmed, `null` if not visible |
| `auto_timer` | string | If there's a countdown timer on the auto-battle, write it: `"00:11:17"`. Usually `null` |
| `power_player` | integer | Team combat power (often shown in pre-battle). `null` if not on screen |
| `power_enemy` | integer | Enemy team power. `null` if not on screen |
| `currency_premium` | integer | Premium currency count (gems, crystals, etc.). Only if visible in a corner/header |
| `currency_tickets` | integer | Ticket/special currency count. Only if visible |

**Tips:**
- For `hp_player` and `turn`: always prefer `"current/max"` format when both values are visible
- Read numbers **exactly**. `8450` is not `8500`. Zoom in if needed
- `speed` is a string, not a number, because it displays as "x2", "x3", etc.
- Only `auto` is boolean. Everything else is string, integer, or null

---

### 4.3 Gacha (Gacha Screens Only)

**Only fill this section if `screen` is `"gacha"`.** For all other screen types, set `"gacha": null`.

```json
"gacha": {
  "phase": "reveal_multi",
  "banner_type": "standard",
  "banner_name": "レギュラー召喚",
  "pull_cost": "魔石",
  "pity": "45/100",
  "free_pull": false,
  "free_timer": null,
  "cards": [
    "不死鳥の王子 / ライザー|SSR+|5|y",
    "魔王の長子|SR|3|y",
    "アソシスト|N|1|n"
  ]
},
```

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string | **Required.** What part of the gacha flow is shown. See table below |
| `banner_type` | string | `"standard"`, `"special"`, `"limited"`, `"collab"`, `"attribute"`, `"other"`. Use `null` if unclear |
| `banner_name` | string | The banner title exactly as shown: `"レギュラー召喚"`, `"Premium Summon"`, etc. |
| `pull_cost` | string | Currency name used for pulls: `"魔石"`, `"Gems"`, `"Tickets"`, etc. |
| `pity` | `"current/max"` | Pity counter. `"45/100"` means 45 pulls toward the 100-pull guarantee. `null` if not shown |
| `free_pull` | boolean | Is a free pull currently available? `true`/`false`/`null` |
| `free_timer` | string | Countdown until next free pull: `"23:45:00"`. `null` if not shown |
| `cards` | list of strings | Revealed cards in shorthand format (see below). `null` if no cards are shown |

**Gacha phases:**

| Phase | What you see |
|-------|-------------|
| `lobby` | Banner selection screen with pull buttons, no animation |
| `animation` | Pull animation in progress (crystals flying, orbs spinning, etc.) |
| `reveal_single` | One card being revealed |
| `reveal_multi` | Multiple cards shown (10-pull result grid) |

**Card shorthand format:** `Name|Rarity|Stars|new`

- **Name**: Card/character name exactly as displayed
- **Rarity**: `N`, `R`, `SR`, `SSR`, `SSR+`, `UR`
- **Stars**: Number of stars shown (1-6)
- **new**: `y` if a "NEW" badge is visible, `n` if not, omit if unclear

Example: `"不死鳥の王子 / ライザー|SSR+|5|y"` means an SSR+ card with 5 stars marked as NEW.

List cards **left-to-right, top-to-bottom** as they appear in the reveal grid.

---

### 4.4 Rewards & MVP (post_battle Only)

**Only fill these if `screen` is `"post_battle"`.** Otherwise, set both to `null`.

#### Rewards

```json
"rewards": [
  "Gold|1500",
  "EXP Potion|3",
  "Promotion Stone|1"
],
```

Format: `"ItemName|Quantity"`
- Write the item name exactly as shown
- If quantity is not displayed, just write the item name: `"Mystery Scroll"`
- List rewards in the order they appear on screen

#### MVP

```json
"mvp": {
  "name": "Rias Gremory",
  "damage": 45200,
  "pct": 38.5
},
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | MVP character name as shown |
| `damage` | integer | Total damage number. `null` if not shown |
| `pct` | float | Damage percentage. `38.5` means 38.5%. `null` if not shown |

If no MVP panel is visible, set `"mvp": null`.

---

### 4.5 UI Elements

List every **button, indicator, toggle, card, navigation element, and text label** visible on screen.

```json
"ui": [
  "Attack|btn|br|on",
  "Skill|btn|bc|on",
  "HP Bar|ind|tl",
  "Enemy HP|ind|tc",
  "Turn Counter|ind|tr",
  "Speed x3|tog|tr|on",
  "Auto|tog|tr|off"
],
```

**Format:** `Name|type|zone|state`

#### Types

| Abbreviation | Full name | What it is |
|-------------|-----------|------------|
| `btn` | button | Tappable button that triggers an action |
| `ind` | indicator | Read-only display (HP bar, counter, timer, progress bar) |
| `card` | card | Character card, item card, or any card-shaped element |
| `txt` | text | Standalone text label or dialogue box |
| `nav` | nav | Navigation element (back button, tab bar, menu icon) |
| `tog` | toggle | On/off switch (auto-battle, speed, settings toggle) |

#### Zones (screen location)

Think of the screen as a 3x3 grid, plus one full-screen option:

```
 tl  |  tc  |  tr
-----+------+-----
 ml  |   c  |  mr
-----+------+-----
 bl  |  bc  |  br

 fs = full_screen (overlays, modals, splash screens)
```

| Abbreviation | Position |
|-------------|----------|
| `tl` | Top-left |
| `tc` | Top-center |
| `tr` | Top-right |
| `ml` | Middle-left |
| `c` | Center |
| `mr` | Middle-right |
| `bl` | Bottom-left |
| `bc` | Bottom-center |
| `br` | Bottom-right |
| `fs` | Full-screen |

#### State (optional 4th field)

| Value | Meaning |
|-------|---------|
| `on` | Enabled / highlighted / active |
| `off` | Disabled / grayed out / inactive |
| *(omit)* | State is unclear or not applicable (indicators, text) |

**Tips:**
- Name elements using their **visible label text** when possible: `"Attack"`, not `"action button 1"`
- For Japanese UI, use the Japanese text: `"召喚10回"`, not `"Summon 10x"`
- Indicators usually don't have an on/off state — omit the 4th field
- Be thorough: annotate **everything** visible, even small icons and counters
- If a button is grayed out / can't be tapped, mark it `off`

---

### 4.6 Available Actions

List the **names of UI elements that the player can currently interact with** (tap/click). These must be a subset of your `ui` elements.

```json
"actions": ["Attack", "Skill"],
```

**Rules:**
- Only include elements marked `on` (or without a state, which defaults to enabled)
- Do NOT include indicators (`ind`), static text (`txt`), or disabled buttons (`off`)
- Each action name must **exactly match** a name in your `ui` list
- This is what the player can actually **do** right now on this screen

**Example:**
If your UI has `"Retreat|btn|bl|off"`, do NOT put `"Retreat"` in actions (it's disabled).

---

### 4.7 Text Content

Record all readable text on screen, split by language.

```json
"text_en": ["Attack", "Skill", "Stage 1-8", "Turn 3/10"],
"text_jp": null,
"text_small": ["[s]00:11:17", "[s]x3"],
```

#### `text_en` — English text

A list of all readable English text strings visible on screen. Include:
- Button labels
- Headers and titles
- Status text
- Dialogue/story text
- Numbers with labels ("Turn 3/10", "HP 8450")

Set to `null` if no English text is visible.

#### `text_jp` — Japanese text

Same as above, but for Japanese text. Set to `null` if no Japanese text is visible.

#### `text_small` — Small / Hard-to-Read Text (Objective Definition)

`text_small` captures peripheral, secondary, or hard-to-read text. **Include text that meets ANY of these criteria:**

1. **Corner zone text (tl/tr/bl/br)** that is NOT a primary UI element label
2. **Timer/countdown values** — any time-based display (e.g., `"00:11:17"`, `"Event ends in 3d"`)
3. **Version numbers** — app/game version strings (e.g., `"v1.2.3"`)
4. **Sub-labels under icons** — small text beneath resource icons or action buttons
5. **Numeric counters** — small counters on icons (badge numbers, notification counts)
6. **System messages** — loading text, connection status, copyright notices
7. **Low contrast text** — light text on light background, dark text on dark background
8. **Partially obscured text** — behind effects, at screen edges, or overlapped by UI

**When in doubt, include it** — better to have more small text for scoring than less. The worst outcome is that a model gets credit for reading text we didn't annotate.

**Do NOT include in text_small:**
- Primary button labels (those go in `ui` elements)
- Large header/title text (goes in `text_en` or `text_jp`)
- HP/turn values (those go in `game_state` numeric fields)

**Important:** Prefix every entry with `[s]` — this marker is stripped during hydration but helps you identify small text while annotating.

```json
"text_small": ["[s]00:11:17", "[s]x3", "[s]45/100", "[s]魔石 x300"]
```

Set to `null` if no small/hard-to-read text is present.

**Why this matters:** Small text is where VLMs struggle most. Your `text_small` annotations directly measure whether a model can read fine details.

---

### 4.8 Notes & Metadata

```json
"ext": null,
"notes": "HP bar red gradient below 25%. Mid-combat frame, floating damage numbers visible.",
"confidence": "high",
"difficulty": "easy"
```

| Field | Type | Description |
|-------|------|-------------|
| `ext` | object or null | Game-specific extension data for unusual mechanics. Usually `null`. Ask the project lead if you think something needs an extension field |
| `notes` | string | **Required.** Free-text description of what's happening in the screenshot. Mention: visual effects, animations, anything that might confuse a VLM, unusual UI states. 1-3 sentences. |
| `confidence` | `"high"` / `"medium"` / `"low"` | How confident are you in this annotation overall? |
| `difficulty` | `"easy"` / `"medium"` / `"hard"` | How hard do you expect this screenshot to be for a VLM? |

**Confidence guide:**
- `high` — Everything is clearly readable, no ambiguity
- `medium` — Some values are hard to read or one or two fields are uncertain
- `low` — Significant visual clutter, text overlaps, or guesswork involved

**Difficulty guide:**
- `easy` — Clean UI, standard layout, high contrast, large text
- `medium` — Some visual effects, mixed languages, small text present
- `hard` — Heavy particle effects, overlapping UI, tiny text, non-standard layout, animation frame

---

## 5. Shorthand Reference

Quick-reference card for all shorthand formats:

### UI Elements: `Name|type|zone|state`

```
Types:  btn  ind  card  txt  nav  tog
Zones:  tl  tc  tr  ml  c  mr  bl  bc  br  fs
State:  on  off  (or omit)
```

### HP / Turn / Pity: `"current/max"` or integer

```
"8450/12000"  --> current=8450, max=12000
22000         --> current=22000, max=null
null          --> not visible
```

### Cards: `Name|Rarity|Stars|new`

```
Rarity: N  R  SR  SSR  SSR+  UR
Stars:  1-6
New:    y  n  (or omit)
```

### Rewards: `"ItemName|Quantity"`

```
"Gold|1500"        --> Gold, qty 1500
"Mystery Scroll"   --> Mystery Scroll, qty unknown
```

### Small text prefix: `[s]`

```
"[s]00:11:17"  --> small text showing a timer
"[s]x3"        --> small text showing speed
```

---

## 6. Screen Type Decision Tree

Use this when you're not sure what `screen` type to pick:

```
Is there active combat happening (HP bars, damage, characters fighting)?
  YES --> "battle"
  NO  -->
    Is this a summoning/gacha screen (banners, pull buttons, card reveals)?
      YES --> "gacha"
      NO  -->
        Is it showing battle results (victory, defeat, rewards, scores)?
          YES --> "post_battle"
          NO  -->
            Is it a team setup / stage select / pre-fight loading screen?
              YES --> "pre_battle"
              NO  --> "idle"
```

**Edge cases:**
- Team selection with "Start Battle" button = `pre_battle`
- Daily login rewards screen = `idle`
- Shop/store = `idle`
- Character enhancement/upgrade = `idle`
- Loading screen with battle tips = `pre_battle`
- Gacha animation in progress = `gacha` (phase: `animation`)

---

## 7. Worked Examples

### Example 1: Battle Screen (English)

You see: Active combat, player HP bar showing 8450/12000 at top-left, enemy HP 22000 at top-center, turn counter 3/10 at top-right, Attack and Skill buttons at bottom, speed x3 toggle active, auto-battle OFF, stage name "校門 1-8" visible, a timer showing 00:11:17 in small text.

```json
{
  "id": "highschooldxd_battle_001_en",
  "lang": "EN",
  "screen": "battle",
  "sub": null,
  "state": {
    "hp_player": "8450/12000",
    "hp_enemy": 22000,
    "turn": "3/10",
    "stage": "校門 1-8",
    "speed": "x3",
    "auto": false,
    "auto_timer": null,
    "power_player": null,
    "power_enemy": null,
    "currency_premium": null,
    "currency_tickets": null
  },
  "gacha": null,
  "rewards": null,
  "mvp": null,
  "ui": [
    "Attack|btn|br|on",
    "Skill|btn|bc|on",
    "HP Bar|ind|tl",
    "Enemy HP|ind|tc",
    "Turn Counter|ind|tr",
    "Speed x3|tog|tr|on",
    "Auto|tog|tr|off"
  ],
  "actions": ["Attack", "Skill"],
  "text_en": ["Attack", "Skill", "Stage 1-8", "Turn 3/10"],
  "text_jp": null,
  "text_small": ["[s]00:11:17", "[s]x3"],
  "ext": null,
  "notes": "HP bar red gradient below 25%. Mid-combat frame, floating damage numbers visible.",
  "confidence": "high",
  "difficulty": "easy"
}
```

**Key decisions:**
- `auto` is `false` because the toggle is OFF (not `null` — the toggle IS visible, it's just off)
- `"Speed x3"` in `ui` is a toggle (`tog`), not a button
- `stage` copies the exact on-screen text including the Japanese characters
- `text_small` captures the timer and speed indicator since they're in small font
- `actions` only lists `Attack` and `Skill` — the toggles and indicators are not "actions"

---

### Example 2: Gacha Reveal (Japanese)

You see: 10-pull results showing 10 cards in a grid. Banner name "レギュラー召喚" visible. Pity counter shows 45/100 in small text. Three cards have "NEW" badges. Pull buttons at bottom. Premium currency 1250 and 3 tickets shown in header.

```json
{
  "id": "highschooldxd_gacha_012_jp",
  "lang": "JP",
  "screen": "gacha",
  "sub": null,
  "state": {
    "hp_player": null, "hp_enemy": null, "turn": null,
    "stage": null, "speed": null, "auto": null, "auto_timer": null,
    "power_player": null, "power_enemy": null,
    "currency_premium": 1250, "currency_tickets": 3
  },
  "gacha": {
    "phase": "reveal_multi",
    "banner_type": "standard",
    "banner_name": "レギュラー召喚",
    "pull_cost": "魔石",
    "pity": "45/100",
    "free_pull": false,
    "free_timer": null,
    "cards": [
      "不死鳥の王子 / ライザー|SSR+|5|y",
      "魔王の長子|SR|3|y",
      "堕天紳士|SR|3|y",
      "夢幻舞姫|R|2|n",
      "猫娘少女・青|R|2|n",
      "神出鬼没|R|2|n",
      "愛の戦士|R|2|n",
      "アソシスト|N|1|n",
      "アソシスト|N|1|n",
      "アソシスト|N|1|n"
    ]
  },
  "rewards": null,
  "mvp": null,
  "ui": [
    "召喚1回|btn|bl|on",
    "召喚10回|btn|bc|on",
    "戻る|btn|br|on",
    "Pity Counter|ind|tl"
  ],
  "actions": ["召喚1回", "召喚10回", "戻る"],
  "text_en": null,
  "text_jp": ["召喚", "レギュラー召喚", "不死鳥の王子", "NEW", "召喚1回", "召喚10回"],
  "text_small": ["[s]45/100", "[s]魔石 x300"],
  "ext": null,
  "notes": "10-pull result grid. SSR+ card has gold flame border and full-art. 3 NEW badges visible. Confetti animation partially obscures bottom-row cards.",
  "confidence": "high",
  "difficulty": "medium"
}
```

**Key decisions:**
- All `state` combat fields are `null` — no battle happening on a gacha screen
- Currency IS visible in the header, so those are filled
- Cards are listed left-to-right, top-to-bottom
- Duplicate cards (アソシスト x3) are listed separately — don't combine them
- `text_en` is `null` because this is a JP screen (even "NEW" could be argued either way, but it's listed in JP text since the UI context is Japanese)
- Difficulty is `medium` because confetti partially obscures some cards

---

### Example 3: Post-Battle Results (English)

You see: Victory screen, stage "Gate 1-8", MVP panel showing Rias Gremory with 45,200 damage (38.5%), reward list showing Gold 1500, EXP Potion x3, Promotion Stone x1. Continue and Retry buttons at bottom.

```json
{
  "id": "highschooldxd_post_battle_003_en",
  "lang": "EN",
  "screen": "post_battle",
  "sub": null,
  "state": {
    "hp_player": null, "hp_enemy": null, "turn": null,
    "stage": "Gate 1-8", "speed": null, "auto": null, "auto_timer": null,
    "power_player": null, "power_enemy": null,
    "currency_premium": null, "currency_tickets": null
  },
  "gacha": null,
  "rewards": [
    "Gold|1500",
    "EXP Potion|3",
    "Promotion Stone|1"
  ],
  "mvp": {
    "name": "Rias Gremory",
    "damage": 45200,
    "pct": 38.5
  },
  "ui": [
    "Continue|btn|bc|on",
    "Retry|btn|bl|on",
    "MVP Panel|card|tc"
  ],
  "actions": ["Continue", "Retry"],
  "text_en": ["Victory!", "Stage Clear", "MVP", "Rias Gremory", "Continue", "Retry"],
  "text_jp": null,
  "text_small": ["[s]38.5%", "[s]45,200"],
  "ext": null,
  "notes": "Victory screen with reward summary. MVP panel shows character portrait with damage breakdown.",
  "confidence": "high",
  "difficulty": "easy"
}
```

**Key decisions:**
- `stage` is still visible on post-battle, so it's filled in
- `rewards` is required for `post_battle` — validation will fail without it
- MVP damage numbers go in `text_small` too since they're typically in small font
- The MVP Panel is typed as `card` not `btn` — it's a display panel, not interactive

---

## 8. Validation Rules

The hydration script enforces these rules automatically. If your annotation breaks any of them, it will fail with an error message.

### Cross-field rules

| Rule | What it means |
|------|--------------|
| `screen=gacha` requires `gacha` to be filled | You must provide the gacha object for gacha screens |
| Non-gacha screens require `gacha=null` | Don't put gacha data on battle/idle/etc. screens |
| `screen=post_battle` requires `rewards` | You must list rewards on post-battle screens |
| Non-post_battle screens require `rewards=null` | Don't put rewards on other screen types |
| Every `actions` entry must match an enabled `ui` element | If you list "Attack" in actions, there must be an "Attack" entry in `ui` that is not `off` |

### Screenshot ID format

Must match: `{game_slug}_{screen_type}_{3digits}_{lang}`
- All lowercase
- Valid game slug from GAME_REGISTRY
- Language must be `en` or `jp`

### Value constraints

- `stars` on cards: 1-6
- `rarity`: must be one of `N`, `R`, `SR`, `SSR`, `SSR+`, `UR`
- `confidence`: must be `high`, `medium`, or `low`
- `difficulty`: must be `easy`, `medium`, or `hard`
- `phase`: must be `lobby`, `animation`, `reveal_single`, or `reveal_multi`
- `banner_type`: must be `standard`, `special`, `limited`, `collab`, `attribute`, or `other`

---

## 9. Common Mistakes

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Using `0` instead of `null` | `0` means you see the number zero. `null` means the field is not visible | Use `null` for anything not on screen |
| Putting gacha data on a battle screen | Cross-field validation will reject it | Only fill `gacha` when `screen` is `"gacha"` |
| Actions listing a disabled button | Actions must only include enabled, interactive elements | Check that every action name matches an `on` or stateless UI element |
| Forgetting `[s]` prefix on small text | Without the prefix, small text won't be processed correctly | Always prefix small text entries with `[s]` |
| Inconsistent names between `ui` and `actions` | `"Attack Button"` in UI but `"Attack"` in actions won't validate | Use **identical** names. If the UI entry is `"Attack|btn|br|on"`, the action must be `"Attack"` |
| Guessing numbers you can't read | Your annotation is ground truth — wrong numbers are worse than null | Use `null` if you can't read it clearly. Add a note: `"HP value partially obscured"` |
| Writing `"true"` (string) instead of `true` (boolean) | JSON booleans are lowercase without quotes | `auto` takes `true`, `false`, or `null` — not `"true"` |
| Combining duplicate cards | Two copies of the same card should be listed twice | List each card separately, even if they're identical |
| Using uppercase in screenshot ID | IDs must be all lowercase | `highschooldxd_battle_001_en`, not `HighSchoolDxD_Battle_001_EN` |
| Leaving `notes` empty | Notes are required and help track annotation quality | Write at least 1 sentence describing the scene |

---

## 10. Running the Pipeline

After filling out your compact annotation:

### Step 1: Hydrate (expand compact to full schema)

```bash
make hydrate
# or: python g123_schema.py hydrate data/annotations/compact/ data/annotations/full/
```

This reads all files in `compact/`, expands them, and writes validated full-schema JSONs to `full/`. You'll see `OK` or `FAIL` for each file.

### Step 2: Validate

```bash
make validate
# or: python g123_schema.py validate data/annotations/full/
```

Re-validates all full-schema files. Use this after any manual edits to full-schema files.

### Step 3: Fix errors

If hydration or validation fails, the error message tells you exactly what's wrong:

```
FAIL highschooldxd_battle_001_en.json: screen_type='battle' must have gacha=null
```

Fix the issue in your compact file and re-run hydration.

### Step 4: Benchmark (optional, for testing)

```bash
# Quick smoke test — 1 model, 3 samples
make smoke

# Full benchmark — all models
make benchmark
```

### Full workflow cheatsheet

```bash
# 1. Print a blank template
make template > data/annotations/compact/GAMESLUG_SCREEN_001_LANG.json

# 2. Edit the file (this is where you do the annotation work)

# 3. Hydrate
make hydrate

# 4. Validate
make validate

# 5. Run benchmark
make benchmark
```

---

## Questions?

- Check the **template file** at `data/annotations/g123_annotation_template.json` for full examples
- Check the **hydrated example** at `data/annotations/example_hydrated_gacha.json` to see what your compact annotation expands into
- If a game mechanic doesn't fit the schema, use the `ext` field and note it in `notes`
- When in doubt: `null` + a descriptive note is always better than a guess
