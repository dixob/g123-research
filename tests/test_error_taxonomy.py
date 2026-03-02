"""
Tests for analysis.error_taxonomy — error classification logic.
"""
import pytest

from analysis.error_taxonomy import (
    classify_field_error,
    _contains_japanese,
    _is_numeric_like,
    _digits_of,
)


class TestContainsJapanese:
    def test_hiragana(self):
        assert _contains_japanese("こんにちは") is True

    def test_katakana(self):
        assert _contains_japanese("アタック") is True

    def test_kanji(self):
        assert _contains_japanese("攻撃") is True

    def test_english(self):
        assert _contains_japanese("hello") is False

    def test_empty(self):
        assert _contains_japanese("") is False

    def test_mixed(self):
        assert _contains_japanese("Damage 総ダメージ") is True


class TestIsNumericLike:
    def test_int(self):
        assert _is_numeric_like(100) is True

    def test_float(self):
        assert _is_numeric_like(3.14) is True

    def test_string_number(self):
        assert _is_numeric_like("100") is True

    def test_non_numeric(self):
        assert _is_numeric_like("hello") is False

    def test_none(self):
        assert _is_numeric_like(None) is False


class TestDigitsOf:
    def test_integer(self):
        assert _digits_of(1234) == "1234"

    def test_float(self):
        assert _digits_of(12.34) == "1234"

    def test_comma_formatted(self):
        assert _digits_of("8,450") == "8450"

    def test_none(self):
        assert _digits_of(None) is None


class TestClassifyFieldError:
    """Tests for the field error classifier."""

    def test_correct(self):
        assert classify_field_error("screen_type", "battle", "battle", 1.0, "exact") == "correct"

    def test_false_null(self):
        """Model returns null but GT has data."""
        assert classify_field_error("player_hp_current", None, 1200, 0.0, "numeric") == "false_null"

    def test_false_positive(self):
        """Model returns data but GT is null."""
        assert classify_field_error("enemy_hp", 500, None, 0.0, "numeric") == "false_positive"

    def test_screen_type_confusion(self):
        assert classify_field_error("screen_type", "idle", "battle", 0.0, "exact") == "screen_type_confusion"

    def test_numeric_ocr(self):
        """Numeric field with wrong number → numeric_ocr."""
        result = classify_field_error("player_hp_current", 1290, 1200, 0.0, "numeric")
        assert result == "numeric_ocr"

    def test_jp_text_error_by_field_name(self):
        """text_jp field with error → jp_text_error."""
        result = classify_field_error("text_jp", ["wrong"], ["right"], 0.3, "fuzzy")
        assert result == "jp_text_error"

    def test_jp_text_error_by_content(self):
        """Field containing Japanese characters → jp_text_error."""
        result = classify_field_error(
            "text_en", "攻撃 damage", "Attack damage", 0.3, "fuzzy"
        )
        assert result == "jp_text_error"

    def test_spatial_error(self):
        """UI element scoring partial match → spatial_error."""
        result = classify_field_error("ui_elements", None, None, 0.5, "ui_set")
        # When both are non-null and score < 1.0
        result2 = classify_field_error(
            "ui_elements",
            [{"name": "pause"}],
            [{"name": "pause", "zone": "tr"}],
            0.5, "ui_set"
        )
        assert result2 == "spatial_error"

    def test_partial_match(self):
        """Fuzzy score between 0 and 1 → partial_match."""
        result = classify_field_error("text_en", "hello world", "hello there", 0.5, "fuzzy")
        assert result == "partial_match"

    def test_text_hallucination(self):
        """Fuzzy score 0 with both non-null → text_hallucination."""
        result = classify_field_error("text_en", "completely wrong", "actual text", 0.0, "fuzzy")
        assert result == "text_hallucination"

    def test_total_miss(self):
        """Score 0 with non-matching non-null → total_miss."""
        result = classify_field_error("language", "MIXED", "EN", 0.0, "exact")
        assert result == "total_miss"
