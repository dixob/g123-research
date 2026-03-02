"""
Scoring functions — compare VLM predictions against ground-truth annotations.

Includes: exact, numeric (with format normalization), boolean, fuzzy F1,
set Jaccard, and zone-aware UI element scoring. Each scorer handles null-null
agreement explicitly for extraction recall tracking.
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


def _normalize_numeric(val) -> float | None:
    """
    Normalize a numeric value for comparison.

    Handles VLM formatting quirks: commas ("8,450"), spaces ("8 450"),
    K/M/B suffixes ("8.45K"), and mixed formats. Returns None if the
    value cannot be interpreted as a number.

    Does NOT apply tolerance bands — exact equality after normalization
    is correct for a benchmark. "8400" vs "8450" is a real perception error.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    # Handle K/M/B suffixes (e.g., "8.45K" → 8450.0)
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    if s[-1].lower() in multipliers:
        try:
            return float(s[:-1]) * multipliers[s[-1].lower()]
        except (ValueError, TypeError):
            pass
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def score_numeric(predicted, ground_truth) -> float:
    """Numeric equality with format normalization. Returns 0.0 or 1.0."""
    if predicted is None and ground_truth is None:
        return 1.0
    if predicted is None or ground_truth is None:
        return 0.0
    pred_norm = _normalize_numeric(predicted)
    gt_norm = _normalize_numeric(ground_truth)
    if pred_norm is None or gt_norm is None:
        return 0.0
    return 1.0 if pred_norm == gt_norm else 0.0


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


def score_ui_set(predicted, ground_truth) -> float:
    """
    Zone-aware Jaccard for UI elements.

    Full match (name + zone both correct) = 1.0 credit.
    Name match but wrong zone = 0.5 credit.
    No match = 0.0 credit.

    Score = sum(credits) / max(len(gt), len(pred)).
    Falls back to plain name-only Jaccard if elements lack zone info.
    """
    def _extract_pairs(val):
        """Extract (name, zone) pairs from list of dicts or strings."""
        if val is None:
            return []
        if not isinstance(val, list):
            return []
        pairs = []
        for v in val:
            if isinstance(v, dict):
                name = v.get("name", "").lower().strip()
                zone = v.get("zone", "").lower().strip() or v.get("location", "").lower().strip()
                if name:
                    pairs.append((name, zone))
            else:
                pairs.append((str(v).lower().strip(), ""))
        return pairs

    pred_pairs = _extract_pairs(predicted)
    gt_pairs = _extract_pairs(ground_truth)

    if not gt_pairs and not pred_pairs:
        return 1.0
    if not gt_pairs or not pred_pairs:
        return 0.0

    total_credit = 0.0
    matched_pred = set()

    for gt_name, gt_zone in gt_pairs:
        best_credit = 0.0
        best_idx = -1
        for i, (pred_name, pred_zone) in enumerate(pred_pairs):
            if i in matched_pred:
                continue
            if pred_name == gt_name:
                if gt_zone and pred_zone and gt_zone == pred_zone:
                    credit = 1.0  # Full match: name + zone
                elif not gt_zone or not pred_zone:
                    credit = 1.0  # No zone data — name match is full credit
                else:
                    credit = 0.5  # Name matches, zone wrong
                if credit > best_credit:
                    best_credit = credit
                    best_idx = i
        if best_idx >= 0:
            matched_pred.add(best_idx)
            total_credit += best_credit

    denominator = max(len(gt_pairs), len(pred_pairs))
    return total_credit / denominator if denominator > 0 else 0.0


SCORERS = {
    "exact": score_exact,
    "numeric": score_numeric,
    "boolean": score_boolean,
    "fuzzy": score_fuzzy,
    "set": score_set,
    "ui_set": score_ui_set,
}


def _is_null_or_empty(value) -> bool:
    """Check if a value is None or semantically empty (empty list/dict/string)."""
    if value is None:
        return True
    if isinstance(value, (list, dict, str)) and len(value) == 0:
        return True
    return False


def score_prediction(prediction: dict | None, annotation: dict, field_spec: dict) -> dict:
    """
    Score a single VLM prediction against a ground-truth annotation.

    Returns:
        {
            "fields": {field_name: {
                "score": float,
                "predicted": ...,
                "ground_truth": ...,
                "null_agreement": bool,  # True if both GT and pred are null/empty
            }},
            "weighted_score": float,
            "max_possible": float,
            "extraction_recall": float | None,  # Score over non-null GT fields only
            "null_agreement_rate": float,  # Fraction of fields with null-null agreement
        }
    """
    results = {}
    weighted_total = 0.0
    max_possible = 0.0

    # Track extraction recall (excludes null-null agreements)
    extraction_weighted = 0.0
    extraction_max = 0.0
    null_agreements = 0

    for field_name, spec in field_spec.items():
        gt_value = _resolve_path(annotation, spec["gt_path"])
        pred_value = prediction.get(field_name) if prediction else None
        scorer = SCORERS[spec["scoring"]]
        score = scorer(pred_value, gt_value)
        weight = spec.get("weight", 1.0)

        is_null_agreement = _is_null_or_empty(gt_value) and _is_null_or_empty(pred_value)

        results[field_name] = {
            "score": score,
            "predicted": pred_value,
            "ground_truth": gt_value,
            "scoring": spec["scoring"],
            "null_agreement": is_null_agreement,
        }
        weighted_total += score * weight
        max_possible += weight

        if not is_null_agreement:
            extraction_weighted += score * weight
            extraction_max += weight
        else:
            null_agreements += 1

    total_fields = len(field_spec)
    null_rate = null_agreements / total_fields if total_fields > 0 else 0.0
    extraction_recall = (extraction_weighted / extraction_max * 100) if extraction_max > 0 else None

    return {
        "fields": results,
        "weighted_score": weighted_total,
        "max_possible": max_possible,
        "extraction_recall": extraction_recall,
        "null_agreement_rate": null_rate,
    }
