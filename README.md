# G123 VLM Game State Benchmark

**Evaluating Vision Language Models for automated game state extraction from anime gacha game screenshots.**

A research benchmark that tests whether frontier VLMs (GPT-4o, Gemini 2.5 Flash, Qwen3-VL-32B) can reliably extract structured game state — HP, turns, gacha pity, UI elements, Japanese/English text — from screenshots of CTW/G123 browser games. Includes a production-grade LangGraph QA agent, error taxonomy framework, and gacha economy tracker.

---

## Research Question

> Can current Vision Language Models extract structured game state from anime game screenshots accurately enough — and cheaply enough — to power production game analytics at scale?

This matters for CTW/G123 because automated screenshot understanding enables:
- **Game QA automation** — detect rendering bugs, UI regressions, and economy imbalances without manual testers
- **Gacha compliance monitoring** — verify observed pull rates match published rates (JOGA guidelines)
- **Live ops analytics** — track game economy metrics across 28 titles in real-time
- **Player experience analysis** — understand what players see at scale

## Architecture

```
Screenshot → VLM Provider → JSON Extraction → Schema Validation → Weighted Scoring
                                                      ↓
                                            Error Taxonomy Analysis
                                                      ↓
                                              Production Report
```

### LangGraph QA Agent Pipeline

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Classify │────→│ Extract  │────→│ Validate │──┬──→│ QA Check │────→│  Output  │
│ (screen) │     │ (fields) │     │ (schema) │  │   │ (rules)  │     │ (report) │
└──────────┘     └──────────┘     └──────────┘  │   └──────────┘     └──────────┘
                                                │
                                                ↓ (validation fails)
                                           ┌──────────┐
                                           │  Retry   │
                                           │ (max 2x) │
                                           └──────────┘
```

The agent uses conditional routing — different extraction prompts per screen type, schema-aware retries, and domain-specific QA rules (HP > max, negative pity, missing UI elements).

## Project Structure

```
g123_research/
├── benchmark/              # Core benchmark framework
│   ├── config.py           # Model configs, pricing, field weights (18 fields, 6 scorer types)
│   ├── providers.py        # VLM API wrappers (OpenAI, Google, Together)
│   ├── runner.py           # Benchmark execution with cost/latency/extraction recall tracking
│   ├── scoring.py          # Weighted scoring (exact, numeric, boolean, fuzzy, set, ui_set)
│   └── report.py           # Report with bootstrap CIs, Pareto analysis, stratified breakdowns
├── agents/                 # LangGraph Game QA Agent
│   ├── game_qa_agent.py    # 6-node StateGraph: classify→extract→validate→retry→qa→output
│   ├── observability.py    # Structured tracing: per-node cost, tokens, latency
│   ├── evaluation.py       # Agent vs single-shot comparison harness
│   └── batch_qa.py         # Directory-level batch runner with aggregate stats
├── analysis/               # Error taxonomy & research analysis
│   ├── error_taxonomy.py   # 11-category error classifier with cross-model analysis
│   └── error_report.py     # Publication-ready markdown error report
├── demos/                  # Business application demos
│   ├── gacha_tracker.py    # Gacha economy extraction from screenshot sequences
│   └── gacha_report.py     # Gacha analytics: rarity distribution, pity, cost
├── scripts/                # Data pipeline utilities
│   └── migrate_v1_to_v3.py # Legacy v1→v3 annotation migration (111 annotations)
├── data/
│   ├── annotations/
│   │   ├── compact/        # Human-friendly annotation templates
│   │   ├── full/           # Hydrated Pydantic-validated schemas
│   │   ├── migrated/       # 111 v3 annotations from legacy migration
│   │   └── legacy/         # Original v1 annotations
│   └── templates/          # Annotation templates + examples
├── images/                 # 168 game screenshots (DxD + Arifureta)
├── exploration/            # Early POC scripts (CLIP, BERT, GPT-4V, etc.)
├── tests/                 # Test suite (154 tests)
│   ├── test_scoring.py    # Scoring functions, null handling, extraction recall
│   ├── test_config.py     # Field spec/prompt alignment, pricing math
│   ├── test_error_taxonomy.py  # Error classification logic
│   └── test_report.py     # Bootstrap CI, formatting helpers
├── g123_schema.py          # Pydantic schema + compact↔hydrated conversion
├── run_benchmark.py        # CLI entry point
└── requirements.txt        # Dependencies
```

## Methodology

### Annotation Schema (v3)

Two-layer annotation system designed for speed:

1. **Compact layer** — 25-line human-friendly JSON with shorthand:
   ```json
   {
     "id": "highschooldxd_battle_001_en",
     "screen": "battle",
     "state": {"hp": "1200/2000", "turn": "3/15", "speed": "x3"},
     "ui": ["Pause|button|middle_right|on", "Speed x3|toggle|top_right|on"],
     "actions": ["attack", "use_skill", "pause"],
     "text_en": ["Total Damage 12,450"],
     "text_jp": ["総ダメージ 12,450"]
   }
   ```

2. **Hydrated layer** — full Pydantic model with cross-field validation:
   ```
   python g123_schema.py hydrate data/annotations/compact/ data/annotations/full/
   ```

### Scoring

18 weighted fields across 6 metric types:

| Metric | Fields | Method |
|--------|--------|--------|
| **Exact** | screen_type, language, speed_multiplier, gacha_phase | Case-insensitive equality |
| **Numeric** | player_hp_current/max, enemy_hp, turn_current/max, gacha_pity | Numeric equality with format normalization (commas, K/M suffixes) |
| **Boolean** | auto_battle_active | Boolean with string normalization |
| **Fuzzy (F1)** | text_en, text_jp, text_small, stage_id, gacha_banner_name | Token-level F1 |
| **Set (Jaccard)** | available_actions | Name-based Jaccard similarity |
| **UI Set** | ui_elements | Zone-aware Jaccard (name+zone=1.0, name-only=0.5) |

Screen type has the highest weight (2.0) — wrong screen classification makes all other extractions irrelevant.

**Key methodological decisions:**
- **Extraction Recall**: Companion metric that excludes null-null agreements from scoring. On idle screens where ~10/18 fields are null, overall score inflates (model scores 83% for extracting nothing). Extraction recall only counts fields where the ground truth is non-null, revealing true model capability.
- **Numeric Normalization**: VLMs frequently format numbers with commas ("8,450"), spaces ("8 450"), or suffixes ("8.45K"). These are formatting differences, not perception errors. Normalization handles these before comparison. No tolerance bands — "8400" vs "8450" is a real error.
- **Per-language Text Scoring**: EN and JP text scored independently rather than merged into a single F1 bag. For a bilingual benchmark targeting a Japanese gaming platform, per-language performance visibility is essential.
- **Zone-aware UI Scoring**: UI elements scored on both name and spatial zone. A model placing "Pause button" in `top_left` instead of `middle_right` gets partial credit (0.5) rather than full credit.
- **Bootstrap 95% CIs**: 1000 resamples with fixed seed for reproducible confidence intervals. With ~100 samples, CIs matter for defensible model comparison claims.
- **Stratified Reporting**: Per-screen-type and per-language accuracy breakdowns. Battle screens (rich game state) and idle screens (mostly nulls) have very different difficulty profiles.

### Models Evaluated

| Model | Provider | Input Cost | Output Cost | Notes |
|-------|----------|-----------|-------------|-------|
| **GPT-4o** | OpenAI | $2.50/1M | $10.00/1M | Frontier multimodal |
| **Gemini 2.5 Flash** | Google | $0.15/1M | $0.60/1M | 16.7× cheaper than GPT-4o |
| **Qwen3-VL-32B** | Together | $0.65/1M | $0.65/1M | Open-weight, self-hostable |

### Dataset

- **168 screenshots** from 2 CTW games: High School DxD and Arifureta
- **111 annotated samples** (migrated from v1 schema → v3)
- **5 screen types**: battle (27), gacha (39), idle (33), post_battle (8), pre_battle (4)
- **Bilingual**: 50 EN + 61 JP screenshots
- **Games**: High School DxD: Operation Paradise Infinity, Arifureta: From Commonplace to World's Strongest

## Error Taxonomy

The error taxonomy classifies every incorrect VLM prediction into 11 categories:

| Category | Description | Example |
|----------|-------------|---------|
| `numeric_ocr` | Wrong number (digit transposition, misread) | HP 1200 → 1290 |
| `text_hallucination` | Text not present on screen | Invented character name |
| `jp_text_error` | Japanese-specific failures (kanji misread) | 総ダメージ → 終ダメージ |
| `screen_type_confusion` | Wrong screen classification | gacha lobby → idle |
| `spatial_error` | UI element in wrong zone | bottom_left → bottom_right |
| `false_null` | Model returns null for visible data | Misses visible HP bar |
| `false_positive` | Model hallucinates data not on screen | Invents currency amount |
| `partial_match` | Partially correct extraction | Gets 3 of 5 UI elements |
| `total_miss` | Completely wrong value | Wrong screen type entirely |
| `parse_failure` | Model output isn't valid JSON | Malformed response |

This taxonomy is critical for production: `numeric_ocr` errors can be fixed with targeted re-extraction, while `false_null` errors require higher-resolution images or multi-crop strategies.

## LangGraph Game QA Agent

The agent extends single-shot extraction with:

- **Screen-type-aware routing** — specialized prompts per screen type reduce irrelevant extraction
- **Schema validation** — Pydantic validation catches structural errors before scoring
- **Retry with error context** — failed validations get re-prompted with specific error messages
- **Domain QA rules** — detects game logic violations:
  - HP > max HP → potential rendering bug
  - Pity > pity max → gacha logic error
  - Negative currency → display bug
  - Missing expected UI elements → layout regression

**Observability**: Every node logs timestamps, token usage, cost, and error context as a structured trace:

```python
from agents.game_qa_agent import run_qa_agent

report, trace = run_qa_agent("screenshot.png", "gemini-2.5-flash", max_retries=2)
trace.print_timeline()  # Node-by-node execution log
print(f"Total cost: ${trace.total_cost_usd:.5f}")
```

## Gacha Economy Tracker

End-to-end demo: screenshot sequences → VLM extraction → gacha analytics.

```bash
python -m demos.gacha_tracker --images images/highschooldxd_gacha_*.png --model gemini-2.5-flash
```

Produces:
- **Rarity distribution** — observed SSR/SR/R rates vs published rates
- **Pity progression** — pity counter advancement across pulls
- **Currency efficiency** — premium currency per card, spend-to-SSR estimate
- **New card rate** — duplicate vs new card ratio

Business application: automated gacha rate compliance monitoring for JOGA regulations, A/B test analysis across banner variants, and player behavior analytics.

## Quick Start

### Prerequisites

```bash
# Clone and install
git clone https://github.com/dixob/g123-research.git
cd g123_research
pip install -r requirements.txt

# Set API keys
cp .env.example .env
# Edit .env with your keys:
#   OPENAI_API_KEY=sk-...
#   GOOGLE_API_KEY=AI...
#   TOGETHER_API_KEY=...
```

### Run Benchmark

```bash
# Run all models on annotated screenshots
python run_benchmark.py --models gpt-4o gemini-2.5-flash qwen3-vl-32b

# Single model, limited samples
python run_benchmark.py --models gemini-2.5-flash --max-samples 10

# Filter by screen type or language
python run_benchmark.py --screen-types battle gacha --languages EN
```

### Run QA Agent

```bash
# Single screenshot
python -m agents.game_qa_agent --image images/highschooldxd_battle_001_EN.png --trace

# Batch processing
python -m agents.batch_qa --dir images/ --max 10 --model gemini-2.5-flash

# Agent evaluation (vs single-shot)
python -m agents.evaluation --annotations-dir data/annotations/full/ --images-dir images/
```

### Run Tests

```bash
# Full test suite (154 tests, ~0.3s)
python -m pytest tests/ -v

# Just scoring tests
python -m pytest tests/test_scoring.py -v

# Just config alignment tests
python -m pytest tests/test_config.py -v
```

### Run Error Analysis

```bash
# Generate error taxonomy from benchmark results
python -m analysis.error_taxonomy benchmark_results/latest.json -o analysis/errors.json

# Generate markdown report
python -m analysis.error_report benchmark_results/latest.json -o analysis/error_report.md
```

### Migrate Legacy Annotations

```bash
# Dry run (preview)
python scripts/migrate_v1_to_v3.py --dry-run

# Full migration
python scripts/migrate_v1_to_v3.py --output-dir data/annotations/migrated/
```

### Gacha Economy Demo

```bash
# Track gacha session
python -m demos.gacha_tracker --images images/highschooldxd_gacha_*.png

# Generate markdown report
python -m demos.gacha_report gacha_results.json -o gacha_analysis.md
```

## Production Implications for CTW/G123

### Cost Projections at Scale

| Scale | Gemini 2.5 Flash | GPT-4o | Qwen3 (self-hosted) |
|-------|-----------------|--------|---------------------|
| 100 screenshots/day | ~$0.05/day | ~$0.75/day | Infrastructure cost |
| 1,000 screenshots/day | ~$0.45/day | ~$7.50/day | Infrastructure cost |
| 10,000 screenshots/day | ~$4.50/day | ~$75.00/day | Infrastructure cost |

Gemini 2.5 Flash is the cost-optimal choice for high-volume screenshot analysis. Self-hosted Qwen3 becomes competitive above ~5,000 screenshots/day depending on GPU costs.

### Deployment Recommendations

1. **Two-stage pipeline**: CLIP pre-classifier (free, <10ms) routes to screen-type-specific VLM prompts → reduces cost by avoiding irrelevant field extraction
2. **Tiered model strategy**: Gemini Flash for high-volume screening, GPT-4o for edge cases flagged by QA rules
3. **Japanese text handling**: Consider JP-specialized OCR preprocessing for numeric fields (manga OCR) — all VLMs underperform on Japanese small text
4. **Structured output**: Use JSON mode (OpenAI) or JSON schema (Gemini) to eliminate parse failures
5. **Retry budget**: Agent retries improve accuracy but at ~2× cost — budget appropriately per use case

## Tech Stack

- **VLM APIs**: OpenAI (GPT-4o), Google GenAI (Gemini 2.5 Flash), Together AI (Qwen3-VL-32B)
- **Agent Framework**: LangGraph (StateGraph with conditional edges)
- **Schema Validation**: Pydantic v2
- **Scoring**: Custom weighted multi-metric (exact, numeric with format normalization, fuzzy F1, Jaccard, zone-aware UI set)
- **Statistical Rigor**: Bootstrap 95% CIs, extraction recall metric, stratified reporting
- **Analysis**: Error taxonomy with 11 failure categories
- **Testing**: pytest suite with 154 tests covering scoring, config alignment, error taxonomy, and reporting

## License

Research project — not for commercial use.
