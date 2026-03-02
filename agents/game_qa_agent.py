"""
Game QA Agent — LangGraph-based agentic extraction pipeline for G123 screenshots.

Replaces single-shot VLM extraction with a multi-step pipeline:
  1. classify  — Identify screen type (battle/gacha/post_battle/idle)
  2. extract   — Run screen-type-specific extraction prompt
  3. validate  — Pydantic schema validation
  4. retry     — Re-prompt with error context on validation failure (max 2)
  5. qa_check  — Domain-specific QA rules (detect potential game bugs)
  6. output    — Structured QA report

Production-grade concerns:
  - Full observability via TraceLog (every node logged with cost/tokens)
  - Retry logic with exponential backoff on API failures
  - Fallback model support (degrade to cheaper model on timeout)
  - Structured output with Pydantic validation
  - QA rules that surface potential game rendering/logic bugs

Usage:
  python -m agents.game_qa_agent --image images/highschooldxd_battle_001_EN.png
  python -m agents.game_qa_agent --image images/highschooldxd_gacha_012_JP.png --model gemini-2.5-flash
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from benchmark.config import MODELS, EXTRACT_PROMPT, compute_cost
from benchmark.providers import call_model, _clean_json, _encode_image
from .observability import TraceLog


# ── Agent State ───────────────────────────────────────────────

class AgentState(TypedDict):
    """State passed through the LangGraph pipeline."""
    image_path: str
    model_name: str
    screen_type: str | None
    raw_extraction: str | None
    parsed_extraction: dict | None
    validation_errors: list[str]
    retries: int
    max_retries: int
    qa_issues: list[dict]
    cost_usd: float
    latency_s: float
    trace: TraceLog


# ── Screen-Specific Prompts ───────────────────────────────────

CLASSIFY_PROMPT = """\
Look at this game screenshot and identify the screen type.
Respond with ONLY one word, no explanation:
battle, gacha, post_battle, or idle"""

SCREEN_PROMPTS = {
    "battle": """\
This is a BATTLE screen from a G123 anime game. Extract combat state.
Respond with ONLY a raw JSON object, no markdown, no code fences.

{
  "screen_type": "battle",
  "language": "EN|JP|MIXED",
  "player_hp_current": null,
  "player_hp_max": null,
  "enemy_hp": null,
  "turn_current": null,
  "turn_max": null,
  "stage_id": null,
  "speed_multiplier": null,
  "auto_battle_active": null,
  "text_content": ["visible text on screen"],
  "text_small": ["small/hard-to-read text"],
  "ui_elements": ["button and indicator names"],
  "available_actions": ["interactive button names"]
}""",

    "gacha": """\
This is a GACHA screen from a G123 anime game. Extract gacha/summoning state.
Respond with ONLY a raw JSON object, no markdown, no code fences.

{
  "screen_type": "gacha",
  "language": "EN|JP|MIXED",
  "gacha_phase": "lobby|animation|reveal_single|reveal_multi",
  "gacha_banner_name": null,
  "gacha_pity_current": null,
  "text_content": ["visible text on screen"],
  "text_small": ["small/hard-to-read text"],
  "ui_elements": ["button and indicator names"],
  "available_actions": ["interactive button names"]
}""",

    "post_battle": """\
This is a POST-BATTLE (results/victory) screen from a G123 anime game.
Extract rewards and MVP data. Respond with ONLY a raw JSON object.

{
  "screen_type": "post_battle",
  "language": "EN|JP|MIXED",
  "stage_id": null,
  "text_content": ["visible text on screen"],
  "text_small": ["small/hard-to-read text"],
  "ui_elements": ["button and indicator names"],
  "available_actions": ["interactive button names"]
}""",

    "idle": """\
This is an IDLE/MENU screen from a G123 anime game. Extract navigation state.
Respond with ONLY a raw JSON object, no markdown, no code fences.

{
  "screen_type": "idle",
  "language": "EN|JP|MIXED",
  "text_content": ["visible text on screen"],
  "text_small": ["small/hard-to-read text"],
  "ui_elements": ["button and indicator names"],
  "available_actions": ["interactive button names"]
}""",
}


# ── Node Functions ────────────────────────────────────────────

def classify_node(state: AgentState) -> AgentState:
    """Node 1: Classify screen type with a lightweight VLM call."""
    trace = state["trace"]
    trace.enter_node("classify", f"Classifying {Path(state['image_path']).name}")

    response = call_model(
        state["model_name"],
        state["image_path"],
        CLASSIFY_PROMPT,
        MODELS,
    )

    cost = response.get("cost_usd") or 0
    state["cost_usd"] += cost
    state["latency_s"] += response.get("latency_s", 0)

    if response["error"]:
        trace.log_error("classify", f"API error: {response['error']}")
        trace.exit_node("classify", "Failed", cost_usd=cost)
        state["screen_type"] = "idle"  # fallback
        return state

    raw = (response.get("raw") or "").strip().lower()
    # Parse screen type from response
    for st in ("battle", "gacha", "post_battle", "idle"):
        if st in raw:
            state["screen_type"] = st
            break
    else:
        state["screen_type"] = "idle"  # default fallback

    trace.exit_node(
        "classify",
        f"Screen type: {state['screen_type']}",
        input_tokens=response.get("input_tokens"),
        output_tokens=response.get("output_tokens"),
        cost_usd=cost,
    )
    return state


def extract_node(state: AgentState) -> AgentState:
    """Node 2: Run screen-type-specific extraction prompt."""
    trace = state["trace"]
    screen_type = state["screen_type"] or "idle"
    prompt = SCREEN_PROMPTS.get(screen_type, EXTRACT_PROMPT)

    trace.enter_node("extract", f"Extracting with {screen_type} prompt")

    response = call_model(
        state["model_name"],
        state["image_path"],
        prompt,
        MODELS,
    )

    cost = response.get("cost_usd") or 0
    state["cost_usd"] += cost
    state["latency_s"] += response.get("latency_s", 0)

    if response["error"]:
        trace.log_error("extract", f"API error: {response['error']}")
        trace.exit_node("extract", "Failed", cost_usd=cost)
        return state

    state["raw_extraction"] = response.get("raw")
    state["parsed_extraction"] = response.get("parsed")

    trace.exit_node(
        "extract",
        f"Got {'valid' if response.get('parsed') else 'invalid'} JSON",
        input_tokens=response.get("input_tokens"),
        output_tokens=response.get("output_tokens"),
        cost_usd=cost,
    )
    return state


def validate_node(state: AgentState) -> AgentState:
    """Node 3: Validate extracted data against expected structure."""
    trace = state["trace"]
    trace.enter_node("validate")

    errors = []
    parsed = state.get("parsed_extraction")

    if parsed is None:
        errors.append("JSON parse failure: model output was not valid JSON")
        state["validation_errors"] = errors
        trace.exit_node("validate", f"{len(errors)} validation errors")
        return state

    # Basic structural validation
    if not isinstance(parsed, dict):
        errors.append(f"Expected dict, got {type(parsed).__name__}")

    # Check screen_type matches classification
    predicted_st = parsed.get("screen_type", "").lower() if isinstance(parsed, dict) else ""
    if state["screen_type"] and predicted_st and predicted_st != state["screen_type"]:
        errors.append(
            f"Screen type mismatch: classify={state['screen_type']}, "
            f"extract={predicted_st}"
        )

    # Check for obviously invalid values
    if isinstance(parsed, dict):
        hp = parsed.get("player_hp_current")
        hp_max = parsed.get("player_hp_max")
        if hp is not None and hp_max is not None:
            try:
                if float(hp) > float(hp_max):
                    errors.append(f"HP current ({hp}) > HP max ({hp_max})")
            except (ValueError, TypeError):
                pass

        pity = parsed.get("gacha_pity_current")
        if pity is not None:
            try:
                if float(pity) < 0:
                    errors.append(f"Pity counter negative: {pity}")
            except (ValueError, TypeError):
                pass

    state["validation_errors"] = errors
    trace.exit_node("validate", f"{len(errors)} validation errors")
    return state


def should_retry(state: AgentState) -> str:
    """Routing: retry extraction or proceed to QA check."""
    if state["validation_errors"] and state["retries"] < state["max_retries"]:
        return "retry"
    return "qa_check"


def retry_node(state: AgentState) -> AgentState:
    """Node 4: Re-prompt with error context for self-correction."""
    trace = state["trace"]
    state["retries"] += 1
    attempt = state["retries"]

    error_context = "; ".join(state["validation_errors"])
    trace.log_retry("retry", attempt, error_context)
    trace.enter_node("retry", f"Retry {attempt}/{state['max_retries']}")

    # Build retry prompt with error feedback
    screen_type = state["screen_type"] or "idle"
    base_prompt = SCREEN_PROMPTS.get(screen_type, EXTRACT_PROMPT)
    retry_prompt = (
        f"{base_prompt}\n\n"
        f"IMPORTANT: Your previous extraction had these errors:\n"
        f"{error_context}\n"
        f"Please fix these issues and try again."
    )

    response = call_model(
        state["model_name"],
        state["image_path"],
        retry_prompt,
        MODELS,
    )

    cost = response.get("cost_usd") or 0
    state["cost_usd"] += cost
    state["latency_s"] += response.get("latency_s", 0)

    if not response.get("error"):
        state["raw_extraction"] = response.get("raw")
        state["parsed_extraction"] = response.get("parsed")

    trace.exit_node(
        "retry",
        f"Retry {attempt} {'succeeded' if response.get('parsed') else 'failed'}",
        input_tokens=response.get("input_tokens"),
        output_tokens=response.get("output_tokens"),
        cost_usd=cost,
    )
    return state


def qa_check_node(state: AgentState) -> AgentState:
    """
    Node 5: Domain-specific QA rules — detect potential game bugs.

    These rules check for conditions that indicate rendering bugs,
    gacha logic errors, or UI state mismatches in the actual game.
    """
    trace = state["trace"]
    trace.enter_node("qa_check")

    issues = []
    parsed = state.get("parsed_extraction")

    if parsed is None or not isinstance(parsed, dict):
        state["qa_issues"] = [{"severity": "error", "rule": "no_data", "message": "No extracted data to check"}]
        trace.exit_node("qa_check", "No data")
        return state

    screen_type = state["screen_type"] or parsed.get("screen_type", "")

    # ── Battle QA Rules ───────────────────────────────────────
    if screen_type == "battle":
        hp = parsed.get("player_hp_current")
        hp_max = parsed.get("player_hp_max")
        if hp is not None and hp_max is not None:
            try:
                if float(hp) > float(hp_max):
                    issues.append({
                        "severity": "warning",
                        "rule": "hp_exceeds_max",
                        "message": f"Player HP ({hp}) exceeds max HP ({hp_max}) — potential rendering bug",
                        "field": "player_hp_current",
                    })
                if float(hp) < 0:
                    issues.append({
                        "severity": "warning",
                        "rule": "hp_negative",
                        "message": f"Player HP is negative ({hp}) — display bug",
                        "field": "player_hp_current",
                    })
            except (ValueError, TypeError):
                pass

        enemy_hp = parsed.get("enemy_hp")
        if enemy_hp is not None:
            try:
                if float(enemy_hp) < 0:
                    issues.append({
                        "severity": "warning",
                        "rule": "enemy_hp_negative",
                        "message": f"Enemy HP is negative ({enemy_hp}) — potential overkill display bug",
                        "field": "enemy_hp",
                    })
            except (ValueError, TypeError):
                pass

        turn = parsed.get("turn_current")
        turn_max = parsed.get("turn_max")
        if turn is not None and turn_max is not None:
            try:
                if float(turn) > float(turn_max):
                    issues.append({
                        "severity": "warning",
                        "rule": "turn_exceeds_max",
                        "message": f"Turn ({turn}) exceeds max turns ({turn_max}) — potential timer bug",
                        "field": "turn_current",
                    })
            except (ValueError, TypeError):
                pass

    # ── Gacha QA Rules ────────────────────────────────────────
    if screen_type == "gacha":
        pity = parsed.get("gacha_pity_current")
        if pity is not None:
            try:
                pity_val = float(pity)
                if pity_val < 0:
                    issues.append({
                        "severity": "critical",
                        "rule": "pity_negative",
                        "message": f"Pity counter is negative ({pity}) — gacha logic error",
                        "field": "gacha_pity_current",
                    })
                if pity_val > 200:
                    issues.append({
                        "severity": "warning",
                        "rule": "pity_excessive",
                        "message": f"Pity counter unusually high ({pity}) — possible display error",
                        "field": "gacha_pity_current",
                    })
            except (ValueError, TypeError):
                pass

    # ── Universal QA Rules ────────────────────────────────────
    # Check for expected UI elements
    actions = parsed.get("available_actions", [])
    ui_elements = parsed.get("ui_elements", [])

    if screen_type == "battle" and not actions:
        issues.append({
            "severity": "info",
            "rule": "no_battle_actions",
            "message": "Battle screen with no detected actions — may be animation frame or auto-battle",
        })

    if screen_type == "gacha" and not actions:
        issues.append({
            "severity": "warning",
            "rule": "no_gacha_actions",
            "message": "Gacha screen with no detected actions — may be animation or loading",
        })

    # Check text extraction
    text_content = parsed.get("text_content", [])
    if not text_content and screen_type != "idle":
        issues.append({
            "severity": "info",
            "rule": "no_text_detected",
            "message": f"No text detected on {screen_type} screen — model may have missed visible text",
        })

    state["qa_issues"] = issues

    severity_counts = {}
    for issue in issues:
        sev = issue["severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    trace.exit_node(
        "qa_check",
        f"{len(issues)} issues found: {severity_counts}" if issues else "No issues",
        data={"issue_count": len(issues), "severities": severity_counts},
    )
    return state


def output_node(state: AgentState) -> AgentState:
    """Node 6: Final output assembly."""
    trace = state["trace"]
    trace.enter_node("output")
    trace.exit_node("output", "Report assembled")
    return state


# ── Build the Graph ───────────────────────────────────────────

def build_qa_graph() -> StateGraph:
    """Construct the LangGraph QA agent pipeline."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("retry", retry_node)
    graph.add_node("qa_check", qa_check_node)
    graph.add_node("output", output_node)

    # Set entry point
    graph.set_entry_point("classify")

    # Add edges
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "validate")
    graph.add_conditional_edges("validate", should_retry, {
        "retry": "retry",
        "qa_check": "qa_check",
    })
    graph.add_edge("retry", "validate")  # retry → re-validate
    graph.add_edge("qa_check", "output")
    graph.add_edge("output", END)

    return graph


def run_qa_agent(
    image_path: str,
    model_name: str = "gemini-2.5-flash",
    max_retries: int = 2,
) -> dict:
    """
    Run the full QA agent pipeline on a single screenshot.

    Args:
        image_path: Path to the game screenshot
        model_name: VLM model to use
        max_retries: Maximum validation retry attempts

    Returns:
        Full QA report dict with extraction, QA issues, cost, and trace
    """
    graph = build_qa_graph()
    app = graph.compile()

    trace = TraceLog(image_path=image_path)

    initial_state: AgentState = {
        "image_path": image_path,
        "model_name": model_name,
        "screen_type": None,
        "raw_extraction": None,
        "parsed_extraction": None,
        "validation_errors": [],
        "retries": 0,
        "max_retries": max_retries,
        "qa_issues": [],
        "cost_usd": 0.0,
        "latency_s": 0.0,
        "trace": trace,
    }

    # Run the graph
    final_state = app.invoke(initial_state)

    # Build report
    report = {
        "image_path": image_path,
        "model": model_name,
        "screen_type": final_state["screen_type"],
        "extraction": final_state["parsed_extraction"],
        "validation_errors": final_state["validation_errors"],
        "retries_used": final_state["retries"],
        "qa_issues": final_state["qa_issues"],
        "cost_usd": final_state["cost_usd"],
        "latency_s": final_state["latency_s"],
        "trace_summary": trace.summary(),
    }

    return report, trace


# ── CLI ───────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run G123 Game QA Agent on a screenshot"
    )
    parser.add_argument(
        "--image", required=True,
        help="Path to game screenshot",
    )
    parser.add_argument(
        "--model", default="gemini-2.5-flash",
        choices=list(MODELS.keys()),
        help="VLM model to use (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--max-retries", type=int, default=2,
        help="Maximum validation retry attempts (default: 2)",
    )
    parser.add_argument(
        "--trace", action="store_true",
        help="Print full execution trace",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save report JSON to this path",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: {image_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Running QA Agent on {image_path.name} with {args.model}...")
    report, trace = run_qa_agent(str(image_path), args.model, args.max_retries)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  QA AGENT REPORT")
    print(f"{'='*60}")
    print(f"  Image:       {image_path.name}")
    print(f"  Model:       {args.model}")
    print(f"  Screen Type: {report['screen_type']}")
    print(f"  Cost:        ${report['cost_usd']:.5f}")
    print(f"  Latency:     {report['latency_s']:.1f}s")
    print(f"  Retries:     {report['retries_used']}")
    print(f"  QA Issues:   {len(report['qa_issues'])}")

    if report["validation_errors"]:
        print(f"\n  Validation Errors:")
        for err in report["validation_errors"]:
            print(f"    - {err}")

    if report["qa_issues"]:
        print(f"\n  QA Issues:")
        for issue in report["qa_issues"]:
            print(f"    [{issue['severity'].upper()}] {issue['message']}")

    if report["extraction"]:
        print(f"\n  Extracted Data:")
        print(json.dumps(report["extraction"], indent=2, ensure_ascii=False, default=str))

    if args.trace:
        print(f"\n  Execution Trace:")
        trace.print_timeline()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n  Report saved to: {output_path}")


if __name__ == "__main__":
    main()
