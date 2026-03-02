"""
Scoring functions — compare VLM predictions against ground-truth annotations.
"""
from __future__ import annotations


def _resolve_path(obj: dict, dotpath: str):
    """Resolve a dot-separated path like 'game_state.player_hp' into a value."""
    for key in dotpath.split("."):
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        else:
            return None
    return obj


def score_exact(predicted, ground_truth) -> float:
    """Case-insensitive exact match. Returns 0.0 or 1.0."""
    if predicted is None and ground_truth is None:
        return 1.0
    if predicted is None or ground_truth is None:
        return 0.0
    return 1.0 if str(predicted).lower().strip() == str(ground_truth).lower().strip() else 0.0


def score_numeric(predicted, ground_truth) -> float:
    """Numeric equality. Returns 0.0 or 1.0."""
    if predicted is None and ground_truth is None:
        return 1.0
    if predicted is None or ground_truth is None:
        return 0.0
    try:
        return 1.0 if float(predicted) == float(ground_truth) else 0.0
    except (ValueError, TypeError):
        return 0.0


def _tokenize(text: str) -> set[str]:
    """Simple whitespace + lowercased tokenization."""
    return set(text.lower().split())


def score_fuzzy(predicted, ground_truth) -> float:
    """
    Token-level F1 between predicted and ground-truth text.
    Handles strings and lists of strings.
    """
    def flatten(val):
        if val is None:
            return ""
        if isinstance(val, list):
            return " ".join(str(v) for v in val)
        if isinstance(val, dict):
            # text_content has {"EN": [...], "JP": [...]}
            parts = []
            for v in val.values():
                if isinstance(v, list):
                    parts.extend(str(x) for x in v)
                else:
                    parts.append(str(v))
            return " ".join(parts)
        return str(val)

    pred_tokens = _tokenize(flatten(predicted))
    gt_tokens = _tokenize(flatten(ground_truth))

    if not gt_tokens and not pred_tokens:
        return 1.0
    if not gt_tokens or not pred_tokens:
        return 0.0

    overlap = pred_tokens & gt_tokens
    precision = len(overlap) / len(pred_tokens) if pred_tokens else 0.0
    recall = len(overlap) / len(gt_tokens) if gt_tokens else 0.0

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def score_set(predicted, ground_truth) -> float:
    """
    Jaccard similarity over sets of element names.
    Handles lists of strings or lists of dicts with 'name' key.
    """
    def to_set(val):
        if val is None:
            return set()
        if isinstance(val, list):
            items = set()
            for v in val:
                if isinstance(v, dict):
                    items.add(v.get("name", "").lower().strip())
                else:
                    items.add(str(v).lower().strip())
            items.discard("")
            return items
        return {str(val).lower().strip()}

    pred_set = to_set(predicted)
    gt_set = to_set(ground_truth)

    if not gt_set and not pred_set:
        return 1.0
    if not gt_set or not pred_set:
        return 0.0

    intersection = pred_set & gt_set
    union = pred_set | gt_set
    return len(intersection) / len(union)


def score_boolean(predicted, ground_truth) -> float:
    """Boolean equality, null-aware. Returns 0.0 or 1.0."""
    if predicted is None and ground_truth is None:
        return 1.0
    if predicted is None or ground_truth is None:
        return 0.0
    # Normalize: VLMs may return "true"/"false" strings
    def to_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower().strip() in ("true", "1", "yes", "on")
        return bool(v)
    return 1.0 if to_bool(predicted) == to_bool(ground_truth) else 0.0


SCORERS = {
    "exact": score_exact,
    "numeric": score_numeric,
    "boolean": score_boolean,
    "fuzzy": score_fuzzy,
    "set": score_set,
}


def score_prediction(prediction: dict | None, annotation: dict, field_spec: dict) -> dict:
    """
    Score a single VLM prediction against a ground-truth annotation.

    Returns:
        {
            "fields": {field_name: {"score": float, "predicted": ..., "ground_truth": ...}},
            "weighted_score": float,
            "max_possible": float,
        }
    """
    results = {}
    weighted_total = 0.0
    max_possible = 0.0

    for field_name, spec in field_spec.items():
        gt_value = _resolve_path(annotation, spec["gt_path"])
        pred_value = prediction.get(field_name) if prediction else None
        scorer = SCORERS[spec["scoring"]]
        score = scorer(pred_value, gt_value)
        weight = spec.get("weight", 1.0)

        results[field_name] = {
            "score": score,
            "predicted": pred_value,
            "ground_truth": gt_value,
            "scoring": spec["scoring"],
        }
        weighted_total += score * weight
        max_possible += weight

    return {
        "fields": results,
        "weighted_score": weighted_total,
        "max_possible": max_possible,
    }
