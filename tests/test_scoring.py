"""
Tests for benchmark.scoring — verifying all scorer types, null handling,
extraction recall, and edge cases.
"""
import pytest

from benchmark.scoring import (
    _normalize_numeric,
    _is_null_or_empty,
    _resolve_path,
    score_exact,
    score_numeric,
    score_boolean,
    score_fuzzy,
    score_set,
    score_ui_set,
    score_prediction,
    SCORERS,
)


# ── _normalize_numeric ────────────────────────────────────────

class TestNormalizeNumeric:
    """Tests for the numeric format normalizer."""

    def test_integers(self):
        assert _normalize_numeric(100) == 100.0
        assert _normalize_numeric(0) == 0.0

    def test_floats(self):
        assert _normalize_numeric(3.14) == 3.14

    def test_string_integers(self):
        assert _normalize_numeric("100") == 100.0

    def test_commas(self):
        assert _normalize_numeric("8,450") == 8450.0
        assert _normalize_numeric("1,234,567") == 1234567.0

    def test_spaces(self):
        assert _normalize_numeric("8 450") == 8450.0

    def test_k_suffix(self):
        assert _normalize_numeric("8.45K") == 8450.0
        assert _normalize_numeric("8.45k") == 8450.0
        assert _normalize_numeric("10K") == 10000.0

    def test_m_suffix(self):
        assert _normalize_numeric("1.5M") == 1500000.0
        assert _normalize_numeric("2m") == 2000000.0

    def test_b_suffix(self):
        assert _normalize_numeric("1.2B") == 1200000000.0

    def test_none(self):
        assert _normalize_numeric(None) is None

    def test_empty_string(self):
        assert _normalize_numeric("") is None

    def test_non_numeric(self):
        assert _normalize_numeric("hello") is None
        assert _normalize_numeric("abc123") is None

    def test_whitespace(self):
        assert _normalize_numeric("  100  ") == 100.0

    def test_negative(self):
        assert _normalize_numeric(-5) == -5.0
        assert _normalize_numeric("-5") == -5.0


# ── _is_null_or_empty ─────────────────────────────────────────

class TestIsNullOrEmpty:
    """Tests for null/empty detection."""

    def test_none(self):
        assert _is_null_or_empty(None) is True

    def test_empty_list(self):
        assert _is_null_or_empty([]) is True

    def test_empty_dict(self):
        assert _is_null_or_empty({}) is True

    def test_empty_string(self):
        assert _is_null_or_empty("") is True

    def test_non_empty_list(self):
        assert _is_null_or_empty(["a"]) is False

    def test_non_empty_dict(self):
        assert _is_null_or_empty({"a": 1}) is False

    def test_non_empty_string(self):
        assert _is_null_or_empty("hello") is False

    def test_zero(self):
        assert _is_null_or_empty(0) is False

    def test_false(self):
        assert _is_null_or_empty(False) is False


# ── _resolve_path ──────────────────────────────────────────────

class TestResolvePath:
    """Tests for dotpath resolution."""

    def test_simple(self):
        assert _resolve_path({"a": 1}, "a") == 1

    def test_nested(self):
        obj = {"game_state": {"player_hp": 100}}
        assert _resolve_path(obj, "game_state.player_hp") == 100

    def test_missing(self):
        assert _resolve_path({"a": 1}, "b") is None

    def test_deep_missing(self):
        obj = {"a": {"b": 1}}
        assert _resolve_path(obj, "a.c") is None

    def test_three_levels(self):
        obj = {"a": {"b": {"c": "deep"}}}
        assert _resolve_path(obj, "a.b.c") == "deep"


# ── score_exact ────────────────────────────────────────────────

class TestScoreExact:
    """Tests for exact match scoring."""

    def test_match(self):
        assert score_exact("battle", "battle") == 1.0

    def test_case_insensitive(self):
        assert score_exact("BATTLE", "battle") == 1.0
        assert score_exact("Battle", "BATTLE") == 1.0

    def test_whitespace(self):
        assert score_exact("  battle  ", "battle") == 1.0

    def test_mismatch(self):
        assert score_exact("battle", "gacha") == 0.0

    def test_both_null(self):
        assert score_exact(None, None) == 1.0

    def test_pred_null(self):
        assert score_exact(None, "battle") == 0.0

    def test_gt_null(self):
        assert score_exact("battle", None) == 0.0


# ── score_numeric ──────────────────────────────────────────────

class TestScoreNumeric:
    """Tests for numeric scoring with format normalization."""

    def test_match(self):
        assert score_numeric(100, 100) == 1.0

    def test_mismatch(self):
        assert score_numeric(100, 200) == 0.0

    def test_comma_formatting(self):
        assert score_numeric("8,450", 8450) == 1.0
        assert score_numeric(8450, "8,450") == 1.0

    def test_k_suffix(self):
        assert score_numeric("8.45K", 8450) == 1.0

    def test_both_null(self):
        assert score_numeric(None, None) == 1.0

    def test_pred_null(self):
        assert score_numeric(None, 100) == 0.0

    def test_gt_null(self):
        assert score_numeric(100, None) == 0.0

    def test_string_vs_int(self):
        assert score_numeric("100", 100) == 1.0

    def test_float_equality(self):
        assert score_numeric(3.0, 3) == 1.0

    def test_unparseable(self):
        assert score_numeric("abc", 100) == 0.0

    def test_both_unparseable(self):
        assert score_numeric("abc", "xyz") == 0.0


# ── score_boolean ──────────────────────────────────────────────

class TestScoreBoolean:
    """Tests for boolean scoring with string normalization."""

    def test_both_true(self):
        assert score_boolean(True, True) == 1.0

    def test_both_false(self):
        assert score_boolean(False, False) == 1.0

    def test_mismatch(self):
        assert score_boolean(True, False) == 0.0

    def test_string_true(self):
        assert score_boolean("true", True) == 1.0
        assert score_boolean("yes", True) == 1.0
        assert score_boolean("1", True) == 1.0
        assert score_boolean("on", True) == 1.0

    def test_string_false(self):
        assert score_boolean("false", False) == 1.0
        assert score_boolean("no", False) == 1.0

    def test_both_null(self):
        assert score_boolean(None, None) == 1.0

    def test_pred_null(self):
        assert score_boolean(None, True) == 0.0


# ── score_fuzzy ────────────────────────────────────────────────

class TestScoreFuzzy:
    """Tests for token-level F1 scoring."""

    def test_exact_match(self):
        assert score_fuzzy("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert score_fuzzy("hello", "goodbye") == 0.0

    def test_partial_overlap(self):
        # pred: {hello, world}  gt: {hello, there}
        # overlap: {hello}  precision: 1/2  recall: 1/2  F1: 0.5
        assert score_fuzzy("hello world", "hello there") == 0.5

    def test_list_input(self):
        assert score_fuzzy(["hello", "world"], ["hello", "world"]) == 1.0

    def test_both_null(self):
        assert score_fuzzy(None, None) == 1.0

    def test_pred_null(self):
        assert score_fuzzy(None, "hello") == 0.0

    def test_gt_null(self):
        assert score_fuzzy("hello", None) == 0.0

    def test_both_empty_lists(self):
        assert score_fuzzy([], []) == 1.0

    def test_case_insensitive(self):
        assert score_fuzzy("HELLO WORLD", "hello world") == 1.0


# ── score_set ──────────────────────────────────────────────────

class TestScoreSet:
    """Tests for Jaccard set scoring."""

    def test_perfect_match(self):
        assert score_set(["a", "b", "c"], ["a", "b", "c"]) == 1.0

    def test_no_overlap(self):
        assert score_set(["a", "b"], ["c", "d"]) == 0.0

    def test_partial_overlap(self):
        # intersection: {a}, union: {a, b, c}  → 1/3
        result = score_set(["a", "b"], ["a", "c"])
        assert abs(result - 1/3) < 0.01

    def test_dict_input(self):
        pred = [{"name": "button"}, {"name": "slider"}]
        gt = [{"name": "button"}, {"name": "slider"}]
        assert score_set(pred, gt) == 1.0

    def test_case_insensitive(self):
        assert score_set(["Attack", "PAUSE"], ["attack", "pause"]) == 1.0

    def test_both_null(self):
        assert score_set(None, None) == 1.0

    def test_both_empty(self):
        assert score_set([], []) == 1.0

    def test_pred_null(self):
        assert score_set(None, ["a"]) == 0.0


# ── score_ui_set ───────────────────────────────────────────────

class TestScoreUiSet:
    """Tests for zone-aware UI element scoring."""

    def test_perfect_match(self):
        """Full name+zone match gives 1.0."""
        pred = [{"name": "pause", "zone": "tr"}, {"name": "attack", "zone": "bc"}]
        gt = [{"name": "pause", "zone": "tr"}, {"name": "attack", "zone": "bc"}]
        assert score_ui_set(pred, gt) == 1.0

    def test_name_match_wrong_zone(self):
        """Name matches but wrong zone gives 0.5 per element."""
        pred = [{"name": "pause", "zone": "tl"}]
        gt = [{"name": "pause", "zone": "tr"}]
        assert score_ui_set(pred, gt) == 0.5

    def test_no_match(self):
        """No matching names gives 0.0."""
        pred = [{"name": "foo", "zone": "tl"}]
        gt = [{"name": "bar", "zone": "tl"}]
        assert score_ui_set(pred, gt) == 0.0

    def test_mixed_match(self):
        """Mix of full match and name-only match."""
        pred = [
            {"name": "pause", "zone": "tr"},   # full match
            {"name": "attack", "zone": "tl"},   # wrong zone → 0.5
        ]
        gt = [
            {"name": "pause", "zone": "tr"},
            {"name": "attack", "zone": "bc"},
        ]
        # 1.0 + 0.5 = 1.5 / max(2, 2) = 0.75
        assert score_ui_set(pred, gt) == 0.75

    def test_no_zone_data(self):
        """When zones are absent, name-only match gives full credit."""
        pred = [{"name": "pause"}, {"name": "attack"}]
        gt = [{"name": "pause"}, {"name": "attack"}]
        assert score_ui_set(pred, gt) == 1.0

    def test_both_null(self):
        assert score_ui_set(None, None) == 1.0

    def test_both_empty(self):
        assert score_ui_set([], []) == 1.0

    def test_pred_null_gt_has_data(self):
        gt = [{"name": "pause", "zone": "tr"}]
        assert score_ui_set(None, gt) == 0.0

    def test_extra_predictions(self):
        """Extra predicted elements reduce score via denominator."""
        pred = [
            {"name": "pause", "zone": "tr"},
            {"name": "attack", "zone": "bc"},
            {"name": "extra", "zone": "tl"},
        ]
        gt = [{"name": "pause", "zone": "tr"}]
        # 1 full match = 1.0 credit / max(1, 3) = 1/3
        assert abs(score_ui_set(pred, gt) - 1/3) < 0.01

    def test_string_fallback(self):
        """String elements (no dict) should be treated as name-only."""
        pred = ["pause", "attack"]
        gt = ["pause", "attack"]
        assert score_ui_set(pred, gt) == 1.0


# ── score_prediction (integration) ────────────────────────────

class TestScorePrediction:
    """Integration tests for the full prediction scoring pipeline."""

    MINIMAL_SPEC = {
        "screen_type": {
            "gt_path": "screen_type",
            "scoring": "exact",
            "weight": 2.0,
        },
        "player_hp_current": {
            "gt_path": "game_state.player_hp_current",
            "scoring": "numeric",
            "weight": 1.0,
        },
    }

    def test_perfect_score(self):
        annotation = {
            "screen_type": "battle",
            "game_state": {"player_hp_current": 1200},
        }
        prediction = {
            "screen_type": "battle",
            "player_hp_current": 1200,
        }
        result = score_prediction(prediction, annotation, self.MINIMAL_SPEC)
        assert result["weighted_score"] == 3.0  # 2.0 + 1.0
        assert result["max_possible"] == 3.0
        assert result["extraction_recall"] is not None

    def test_partial_score(self):
        annotation = {
            "screen_type": "battle",
            "game_state": {"player_hp_current": 1200},
        }
        prediction = {
            "screen_type": "battle",
            "player_hp_current": 999,  # wrong
        }
        result = score_prediction(prediction, annotation, self.MINIMAL_SPEC)
        assert result["weighted_score"] == 2.0  # screen_type correct, hp wrong
        assert result["max_possible"] == 3.0

    def test_null_agreement_tracking(self):
        """Fields where both GT and pred are null should be tagged."""
        annotation = {
            "screen_type": "idle",
            "game_state": {"player_hp_current": None},
        }
        prediction = {
            "screen_type": "idle",
            "player_hp_current": None,
        }
        result = score_prediction(prediction, annotation, self.MINIMAL_SPEC)
        # screen_type is "idle"/"idle" → not null agreement (both have values)
        assert result["fields"]["screen_type"]["null_agreement"] is False
        # player_hp is None/None → null agreement
        assert result["fields"]["player_hp_current"]["null_agreement"] is True

    def test_null_agreement_rate(self):
        """Null agreement rate should reflect fraction of null-null fields."""
        annotation = {
            "screen_type": None,
            "game_state": {"player_hp_current": None},
        }
        prediction = {
            "screen_type": None,
            "player_hp_current": None,
        }
        result = score_prediction(prediction, annotation, self.MINIMAL_SPEC)
        assert result["null_agreement_rate"] == 1.0  # both fields are null-null

    def test_extraction_recall_excludes_null(self):
        """Extraction recall should only score non-null GT fields."""
        spec = {
            "field_a": {"gt_path": "a", "scoring": "exact", "weight": 1.0},
            "field_b": {"gt_path": "b", "scoring": "exact", "weight": 1.0},
        }
        annotation = {"a": "hello", "b": None}
        prediction = {"field_a": "hello", "field_b": None}
        result = score_prediction(prediction, annotation, spec)
        # field_a: correct, not null agreement
        # field_b: null-null agreement → excluded from extraction recall
        assert result["extraction_recall"] == 100.0  # only field_a counts, and it's correct

    def test_extraction_recall_none_when_all_null(self):
        """If all fields are null-null, extraction recall should be None."""
        spec = {
            "field_a": {"gt_path": "a", "scoring": "exact", "weight": 1.0},
        }
        annotation = {"a": None}
        prediction = {"field_a": None}
        result = score_prediction(prediction, annotation, spec)
        assert result["extraction_recall"] is None

    def test_none_prediction(self):
        """Handle prediction=None (total parse failure)."""
        annotation = {
            "screen_type": "battle",
            "game_state": {"player_hp_current": 1200},
        }
        result = score_prediction(None, annotation, self.MINIMAL_SPEC)
        assert result["weighted_score"] == 0.0
        assert result["max_possible"] == 3.0


# ── SCORERS registry ──────────────────────────────────────────

class TestScorersRegistry:
    """Verify the SCORERS dict contains all expected scorers."""

    def test_all_scorers_registered(self):
        expected = {"exact", "numeric", "boolean", "fuzzy", "set", "ui_set"}
        assert set(SCORERS.keys()) == expected

    def test_scorers_are_callable(self):
        for name, fn in SCORERS.items():
            assert callable(fn), f"SCORERS[{name!r}] is not callable"


# ── Numeric normalization edge cases ──────────────────────────

class TestNumericEdgeCases:
    """Detailed edge cases for numeric normalization in scoring context."""

    def test_comma_thousands_score(self):
        """VLM returning '8,450' should match GT of 8450."""
        assert score_numeric("8,450", 8450) == 1.0

    def test_space_thousands_score(self):
        """VLM returning '8 450' should match GT of 8450."""
        assert score_numeric("8 450", 8450) == 1.0

    def test_k_suffix_score(self):
        """VLM returning '8.45K' should match GT of 8450."""
        assert score_numeric("8.45K", 8450) == 1.0

    def test_m_suffix_score(self):
        """VLM returning '1.5M' should match GT of 1500000."""
        assert score_numeric("1.5M", 1500000) == 1.0

    def test_no_tolerance(self):
        """8400 vs 8450 is a real error — no tolerance bands."""
        assert score_numeric(8400, 8450) == 0.0

    def test_both_comma_formatted(self):
        """Both values comma-formatted should still match."""
        assert score_numeric("1,234", "1,234") == 1.0
